"""Paper validation alert storage (Slice 40 — no delivery)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import PaperValidationAlert as AlertModel
from app.repositories.paper_scheduler import PaperAlertRepository
from app.schemas.alerts import PaginatedPaperAlerts, PaperAlert, PaperAlertSummary
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperAlertSeverity,
    PaperAlertType,
)
from app.services.audit_service import AuditService

# Cooldown seconds per alert type — suppress duplicate notifications within the window.
ALERT_COOLDOWN_SECONDS: dict[PaperAlertType, int] = {
    PaperAlertType.SETUP_SIGNAL_DETECTED: 3600,
    PaperAlertType.PAPER_TRADE_OPENED: 1800,
    PaperAlertType.PAPER_TRADE_CLOSED: 86400,
    PaperAlertType.STOP_HIT: 86400,
    PaperAlertType.TP_HIT: 86400,
    PaperAlertType.RUNNER_EXIT: 86400,
    PaperAlertType.DATA_STALE: 3600,
    PaperAlertType.STRATEGY_BLOCKED: 3600,
    PaperAlertType.OVERTRADING_WARNING: 86400,
    PaperAlertType.DAILY_LOSS_LOCK_WARNING: 86400,
    PaperAlertType.PROMOTION_STATUS_CHANGED: 3600,
}


def build_alert_dedup_key(
    *,
    alert_type: PaperAlertType,
    organization_id: uuid.UUID,
    paper_validation_run_id: uuid.UUID | None = None,
    paper_trade_id: uuid.UUID | None = None,
    strategy_id: uuid.UUID | None = None,
) -> str:
    parts = [alert_type.value, str(organization_id)]
    if paper_validation_run_id is not None:
        parts.append(str(paper_validation_run_id))
    if paper_trade_id is not None:
        parts.append(str(paper_trade_id))
    elif strategy_id is not None:
        parts.append(str(strategy_id))
    return ":".join(parts)


class PaperAlertService:
    def __init__(self, session: Session, *, audit_service: AuditService | None = None) -> None:
        self._session = session
        self._alerts = PaperAlertRepository(session)
        self._audit = audit_service or AuditService(session)

    def create(
        self,
        *,
        organization_id: uuid.UUID,
        alert_type: PaperAlertType,
        message: str,
        severity: PaperAlertSeverity = PaperAlertSeverity.INFO,
        user_id: uuid.UUID | None = None,
        strategy_id: uuid.UUID | None = None,
        paper_validation_run_id: uuid.UUID | None = None,
        paper_trade_id: uuid.UUID | None = None,
        metadata: dict | None = None,
        dedup_key: str | None = None,
        skip_dedup: bool = False,
    ) -> PaperAlert | None:
        """Create an alert, returning None when deduplication suppresses a duplicate."""
        key = dedup_key or build_alert_dedup_key(
            alert_type=alert_type,
            organization_id=organization_id,
            paper_validation_run_id=paper_validation_run_id,
            paper_trade_id=paper_trade_id,
            strategy_id=strategy_id,
        )
        if not skip_dedup:
            cooldown = ALERT_COOLDOWN_SECONDS.get(alert_type, 3600)
            since = datetime.now(UTC) - timedelta(seconds=cooldown)
            existing = self._alerts.find_recent_by_dedup_key(organization_id, key, since=since)
            if existing is not None:
                return None

        row = AlertModel(
            organization_id=organization_id,
            user_id=user_id,
            alert_type=alert_type,
            severity=severity,
            strategy_id=strategy_id,
            paper_validation_run_id=paper_validation_run_id,
            paper_trade_id=paper_trade_id,
            message=message,
            metadata_json=metadata,
            dedup_key=key,
        )
        self._alerts.add(row)
        return self._to_schema(row)

    def list_alerts(
        self,
        organization_id: uuid.UUID,
        *,
        alert_type: PaperAlertType | None = None,
        severity: PaperAlertSeverity | None = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedPaperAlerts:
        rows, total = self._alerts.list_for_org(
            organization_id,
            alert_type=alert_type,
            severity=severity,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )
        return PaginatedPaperAlerts(
            items=[self._to_schema(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_alert(self, alert_id: uuid.UUID, *, organization_id: uuid.UUID) -> PaperAlert:
        from sqlalchemy import select

        row = self._session.scalar(
            select(AlertModel).where(
                AlertModel.id == alert_id,
                AlertModel.organization_id == organization_id,
            )
        )
        if row is None:
            raise NotFoundError("Alert not found.")
        return self._to_schema(row)

    def mark_read(
        self,
        alert_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperAlert:
        row = self._alerts.mark_read(alert_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Alert not found.")
        self._audit.record(
            AuditRecordCreate(
                request_id=f"alert-read-{alert_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="paper_validation_alert",
                resource_id=str(alert_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"action": "alert_read"},
            )
        )
        return self._to_schema(row)

    def mark_all_read(self, organization_id: uuid.UUID, *, user_id: uuid.UUID | None = None) -> int:
        count = self._alerts.mark_all_read(organization_id)
        if count > 0:
            self._audit.record(
                AuditRecordCreate(
                    request_id=f"alert-read-all-{organization_id}",
                    trace_id=str(uuid.uuid4()),
                    user_id=user_id,
                    organization_id=organization_id,
                    event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                    resource_type="paper_validation_alert",
                    resource_id=str(organization_id),
                    actor_type=ActorType.USER,
                    result=AuditResult.SUCCESS,
                    severity=AuditSeverity.INFO,
                    metadata={"action": "alert_read_all", "marked_read": count},
                )
            )
        return count

    def summary(self, organization_id: uuid.UUID) -> PaperAlertSummary:
        rows, total = self._alerts.list_for_org(organization_id, limit=500)
        unread = self._alerts.count_unread(organization_id)
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for row in rows:
            by_type[row.alert_type.value] = by_type.get(row.alert_type.value, 0) + 1
            by_severity[row.severity.value] = by_severity.get(row.severity.value, 0) + 1
        return PaperAlertSummary(
            total=total,
            unread=unread,
            by_type=by_type,
            by_severity=by_severity,
        )

    @staticmethod
    def _to_schema(row: AlertModel) -> PaperAlert:
        return PaperAlert(
            id=row.id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            alert_type=row.alert_type,
            severity=row.severity,
            strategy_id=row.strategy_id,
            paper_validation_run_id=row.paper_validation_run_id,
            paper_trade_id=row.paper_trade_id,
            message=row.message,
            read_at=row.read_at,
            metadata=row.metadata_json,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def alert_type_for_exit(exit_reason: str | None) -> PaperAlertType:
        if not exit_reason:
            return PaperAlertType.PAPER_TRADE_CLOSED
        lowered = exit_reason.lower()
        if "stop" in lowered:
            return PaperAlertType.STOP_HIT
        if "take_profit" in lowered or lowered.startswith("tp"):
            return PaperAlertType.TP_HIT
        if "runner" in lowered:
            return PaperAlertType.RUNNER_EXIT
        return PaperAlertType.PAPER_TRADE_CLOSED
