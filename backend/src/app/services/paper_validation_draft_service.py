"""Paper validation draft service (Slice 78 — draft only, no execution)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import PaperValidationAlert as AlertModel
from app.db.models import PaperValidationDraft as DraftModel
from app.repositories.paper_scheduler import PaperAlertRepository
from app.repositories.paper_validation_draft import PaperValidationDraftRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperValidationDraftRiskMode,
    PaperValidationDraftStatus,
    SetupAlertReviewStatus,
)
from app.schemas.paper_validation_draft import (
    CREATE_PAPER_VALIDATION_DRAFT_CONFIRM,
    PaginatedPaperValidationDrafts,
    PaperValidationDraftItem,
    PaperValidationDraftSummary,
    SetupAlertDraftCreateRequest,
    SetupAlertDraftCreateResult,
)
from app.services.audit_service import AuditService

_DRAFTABLE_REVIEW_STATUSES = {
    SetupAlertReviewStatus.WATCHING,
    SetupAlertReviewStatus.IMPORTANT,
}


class PaperValidationDraftService:
    """Create and read non-executable paper validation drafts from setup alerts."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._alerts = PaperAlertRepository(session)
        self._drafts = PaperValidationDraftRepository(session)
        self._audit = AuditService(session)

    def create_from_setup_alert(
        self,
        alert_id: uuid.UUID,
        payload: SetupAlertDraftCreateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> SetupAlertDraftCreateResult:
        if payload.confirm != CREATE_PAPER_VALIDATION_DRAFT_CONFIRM:
            self._record_audit(
                "setup_alert_draft_blocked",
                alert_id=alert_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "confirmation_required"},
            )
            raise ValidationAppError(
                "Exact confirmation required to create a paper validation draft.",
                details={"required_confirm": CREATE_PAPER_VALIDATION_DRAFT_CONFIRM},
            )

        self._record_audit(
            "setup_alert_draft_requested",
            alert_id=alert_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "risk_mode": payload.risk_mode.value,
                "has_notes": bool(payload.notes),
            },
        )

        row = self._alerts.get_setup_review_alert(alert_id, organization_id=organization_id)
        if row is None:
            from sqlalchemy import select

            generic = self._session.scalar(
                select(AlertModel).where(
                    AlertModel.id == alert_id,
                    AlertModel.organization_id == organization_id,
                )
            )
            if generic is not None:
                self._record_audit(
                    "setup_alert_draft_blocked",
                    alert_id=alert_id,
                    organization_id=organization_id,
                    user_id=user_id,
                    metadata={"reason": "non_market_watcher_alert"},
                )
                raise ValidationAppError(
                    "Only scanner-created setup alerts can be converted to drafts.",
                    details={"alert_id": str(alert_id)},
                )
            raise NotFoundError("Alert not found.")

        try:
            review_status = SetupAlertReviewStatus(row.review_status)
        except ValueError:
            review_status = SetupAlertReviewStatus.UNREVIEWED

        if review_status not in _DRAFTABLE_REVIEW_STATUSES:
            self._record_audit(
                "setup_alert_draft_blocked",
                alert_id=alert_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={
                    "reason": "review_status_not_draftable",
                    "review_status": review_status.value,
                },
            )
            raise ValidationAppError(
                "Only watching or important setup alerts can be converted to drafts.",
                details={
                    "alert_id": str(alert_id),
                    "review_status": review_status.value,
                },
            )

        existing = self._drafts.get_active_for_alert(organization_id, alert_id)
        if existing is not None:
            self._record_audit(
                "setup_alert_draft_already_exists",
                alert_id=alert_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"draft_id": str(existing.id)},
            )
            return SetupAlertDraftCreateResult(
                draft=self._to_item(existing),
                already_exists=True,
            )

        draft = self._build_draft(row, payload, organization_id=organization_id, user_id=user_id)
        self._drafts.add(draft)
        self._record_audit(
            "setup_alert_draft_created",
            alert_id=alert_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "draft_id": str(draft.id),
                "risk_mode": payload.risk_mode.value,
                "review_status": review_status.value,
            },
        )
        return SetupAlertDraftCreateResult(draft=self._to_item(draft), already_exists=False)

    def list_drafts(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedPaperValidationDrafts:
        rows, total = self._drafts.list_for_org(
            organization_id,
            status=PaperValidationDraftStatus.DRAFT,
            limit=limit,
            offset=offset,
        )
        return PaginatedPaperValidationDrafts(
            items=[self._to_item(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_draft(
        self,
        draft_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationDraftItem:
        row = self._drafts.get_for_org(draft_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Draft not found.")
        return self._to_item(row)

    def draft_summary(self, organization_id: uuid.UUID) -> PaperValidationDraftSummary:
        _, total = self._drafts.list_for_org(
            organization_id,
            status=PaperValidationDraftStatus.DRAFT,
            limit=1,
            offset=0,
        )
        latest = self._drafts.latest_for_org(organization_id)
        return PaperValidationDraftSummary(
            total_drafts=total,
            latest_condition=latest.condition if latest is not None else None,
            latest_created_at=latest.created_at if latest is not None else None,
        )

    @staticmethod
    def _build_draft(
        alert: AlertModel,
        payload: SetupAlertDraftCreateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> DraftModel:
        meta = alert.metadata_json or {}
        metrics = meta.get("metrics") if isinstance(meta.get("metrics"), dict) else {}
        latest_price = metrics.get("latest_price")
        if latest_price is None:
            latest_price = meta.get("latest_price")
        confidence = meta.get("confidence")
        trigger_level = meta.get("trigger_level")
        invalidation_level = meta.get("invalidation_level")
        return DraftModel(
            organization_id=organization_id,
            source_alert_id=alert.id,
            symbol=meta.get("symbol") if isinstance(meta.get("symbol"), str) else None,
            timeframe=meta.get("timeframe") if isinstance(meta.get("timeframe"), str) else None,
            condition=meta.get("condition") if isinstance(meta.get("condition"), str) else None,
            direction=meta.get("direction") if isinstance(meta.get("direction"), str) else None,
            confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            reason=meta.get("reason") if isinstance(meta.get("reason"), str) else None,
            trigger_level=float(trigger_level) if isinstance(trigger_level, (int, float)) else None,
            invalidation_level=(
                float(invalidation_level) if isinstance(invalidation_level, (int, float)) else None
            ),
            latest_price=float(latest_price) if isinstance(latest_price, (int, float)) else None,
            review_status=alert.review_status,
            user_notes=payload.notes,
            risk_mode=payload.risk_mode.value,
            status=PaperValidationDraftStatus.DRAFT.value,
            created_by=user_id,
        )

    @staticmethod
    def _to_item(row: DraftModel) -> PaperValidationDraftItem:
        try:
            risk_mode = PaperValidationDraftRiskMode(row.risk_mode)
        except ValueError:
            risk_mode = PaperValidationDraftRiskMode.CONSERVATIVE
        try:
            status = PaperValidationDraftStatus(row.status)
        except ValueError:
            status = PaperValidationDraftStatus.DRAFT
        return PaperValidationDraftItem(
            draft_id=row.id,
            source_alert_id=row.source_alert_id,
            symbol=row.symbol,
            timeframe=row.timeframe,
            condition=row.condition,
            direction=row.direction,
            confidence=row.confidence,
            trigger_level=row.trigger_level,
            invalidation_level=row.invalidation_level,
            latest_price=row.latest_price,
            reason=row.reason,
            risk_mode=risk_mode,
            status=status,
            created_at=row.created_at,
            created_by=row.created_by,
        )

    def _record_audit(
        self,
        action: str,
        *,
        alert_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id=f"setup-alert-draft-{alert_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="paper_validation_draft",
                resource_id=str(alert_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"action": action, **(metadata or {})},
            )
        )
