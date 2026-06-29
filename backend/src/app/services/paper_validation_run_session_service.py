"""Paper validation run session service (Slice 82 — manual start, record only, no engine).

This service deliberately depends only on the run-plan repository, the run-session
repository, and the audit service. It never imports or invokes the paper validation
runtime engine, scheduler, exchange, proposal/approval, or Telegram paths, so a manual
"start" can only ever create a record-only session row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import PaperValidationRunPlan as PlanModel
from app.db.models import PaperValidationRunSession as SessionModel
from app.repositories.paper_validation_run_plan import PaperValidationRunPlanRepository
from app.repositories.paper_validation_run_session import PaperValidationRunSessionRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperValidationDraftRiskMode,
    PaperValidationRunPlanStatus,
    PaperValidationRunSessionStatus,
)
from app.schemas.paper_validation_run_session import (
    START_PAPER_VALIDATION_RUN_CONFIRM,
    PaginatedPaperValidationRunSessions,
    PaperValidationRunSessionItem,
    PaperValidationRunSessionStartRequest,
    PaperValidationRunSessionStartResult,
    PaperValidationRunSessionStatusUpdate,
)
from app.services.audit_service import AuditService


class PaperValidationRunSessionService:
    """Manually start and review record-only paper validation run sessions from planned plans."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._plans = PaperValidationRunPlanRepository(session)
        self._sessions = PaperValidationRunSessionRepository(session)
        self._audit = AuditService(session)

    def start_from_plan(
        self,
        plan_id: uuid.UUID,
        payload: PaperValidationRunSessionStartRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationRunSessionStartResult:
        if payload.confirm != START_PAPER_VALIDATION_RUN_CONFIRM:
            self._record_audit(
                "paper_validation_run_session_blocked",
                plan_id=plan_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "confirmation_required"},
            )
            raise ValidationAppError(
                "Exact confirmation required to start a paper validation run.",
                details={"required_confirm": START_PAPER_VALIDATION_RUN_CONFIRM},
            )

        self._record_audit(
            "paper_validation_run_session_requested",
            plan_id=plan_id,
            organization_id=organization_id,
            user_id=user_id,
        )

        plan = self._plans.get_for_org(plan_id, organization_id=organization_id)
        if plan is None:
            raise NotFoundError("Run plan not found.")

        if plan.plan_status != PaperValidationRunPlanStatus.PLANNED.value:
            self._record_audit(
                "paper_validation_run_session_blocked",
                plan_id=plan_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "plan_not_planned", "plan_status": plan.plan_status},
            )
            raise ValidationAppError(
                "Run plan must be in planned status before starting a run.",
                details={"plan_id": str(plan_id), "plan_status": plan.plan_status},
            )

        existing = self._sessions.get_active_for_plan(organization_id, plan_id)
        if existing is not None:
            self._record_audit(
                "paper_validation_run_session_already_active",
                plan_id=plan_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"session_id": str(existing.id)},
            )
            return PaperValidationRunSessionStartResult(
                session=self._to_item(existing),
                already_active=True,
            )

        session_row = self._build_session(
            plan,
            payload,
            organization_id=organization_id,
            user_id=user_id,
        )
        try:
            with self._session.begin_nested():
                self._sessions.add(session_row)
        except IntegrityError:
            # Concurrent double-submit: the partial unique index rejected the second
            # running session. Recover the winner instead of surfacing a 500.
            duplicate = self._sessions.get_active_for_plan(organization_id, plan_id)
            if duplicate is None:
                raise
            self._record_audit(
                "paper_validation_run_session_already_active",
                plan_id=plan_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"session_id": str(duplicate.id)},
            )
            return PaperValidationRunSessionStartResult(
                session=self._to_item(duplicate),
                already_active=True,
            )

        self._record_audit(
            "paper_validation_run_session_started",
            plan_id=plan_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "session_id": str(session_row.id),
                "condition": session_row.condition,
                "symbol": session_row.symbol,
            },
        )
        return PaperValidationRunSessionStartResult(
            session=self._to_item(session_row),
            already_active=False,
        )

    def list_sessions(
        self,
        organization_id: uuid.UUID,
        *,
        status: PaperValidationRunSessionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedPaperValidationRunSessions:
        rows, total = self._sessions.list_for_org(
            organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return PaginatedPaperValidationRunSessions(
            items=[self._to_item(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_session(
        self,
        session_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRunSessionItem:
        row = self._sessions.get_for_org(session_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Run session not found.")
        return self._to_item(row)

    def update_status(
        self,
        session_id: uuid.UUID,
        payload: PaperValidationRunSessionStatusUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationRunSessionItem:
        row = self._sessions.get_for_org(session_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Run session not found.")

        if payload.session_status not in {
            PaperValidationRunSessionStatus.COMPLETED,
            PaperValidationRunSessionStatus.CANCELLED,
        }:
            raise ValidationAppError(
                "Run session can only be set to completed or cancelled.",
                details={"session_status": payload.session_status.value},
            )

        if row.session_status != PaperValidationRunSessionStatus.RUNNING.value:
            self._record_audit(
                "paper_validation_run_session_blocked",
                plan_id=row.run_plan_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={
                    "reason": "session_not_running",
                    "session_status": row.session_status,
                },
            )
            raise ValidationAppError(
                "Only a running session can be completed or cancelled.",
                details={
                    "session_id": str(session_id),
                    "session_status": row.session_status,
                },
            )

        row.session_status = payload.session_status.value
        row.ended_at = datetime.now(UTC)
        item = self._to_item(row)
        self._record_audit(
            "paper_validation_run_session_status_updated",
            plan_id=row.run_plan_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "session_id": str(session_id),
                "session_status": payload.session_status.value,
            },
        )
        return item

    @staticmethod
    def _build_session(
        plan: PlanModel,
        payload: PaperValidationRunSessionStartRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> SessionModel:
        return SessionModel(
            organization_id=organization_id,
            run_plan_id=plan.id,
            candidate_id=plan.candidate_id,
            draft_id=plan.draft_id,
            source_alert_id=plan.source_alert_id,
            symbol=plan.symbol,
            timeframe=plan.timeframe,
            condition=plan.condition,
            direction=plan.direction,
            risk_mode=plan.risk_mode,
            validation_window=plan.validation_window,
            observation_timeframe=plan.observation_timeframe,
            max_duration_minutes=plan.max_duration_minutes,
            session_status=PaperValidationRunSessionStatus.RUNNING.value,
            notes=payload.notes,
            started_by=user_id,
            started_at=datetime.now(UTC),
        )

    @classmethod
    def _to_item(cls, row: SessionModel) -> PaperValidationRunSessionItem:
        try:
            risk_mode = PaperValidationDraftRiskMode(row.risk_mode)
        except ValueError:
            risk_mode = PaperValidationDraftRiskMode.CONSERVATIVE
        try:
            session_status = PaperValidationRunSessionStatus(row.session_status)
        except ValueError:
            session_status = PaperValidationRunSessionStatus.RUNNING
        return PaperValidationRunSessionItem(
            session_id=row.id,
            run_plan_id=row.run_plan_id,
            candidate_id=row.candidate_id,
            draft_id=row.draft_id,
            source_alert_id=row.source_alert_id,
            symbol=row.symbol,
            timeframe=row.timeframe,
            condition=row.condition,
            direction=row.direction,
            risk_mode=risk_mode,
            validation_window=row.validation_window,
            observation_timeframe=row.observation_timeframe,
            max_duration_minutes=row.max_duration_minutes,
            session_status=session_status,
            notes=row.notes,
            started_at=row.started_at,
            ended_at=row.ended_at,
            created_at=row.created_at,
        )

    def _record_audit(
        self,
        action: str,
        *,
        plan_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        safe_metadata: dict[str, object] = {"action": action, **(metadata or {})}
        if "notes" in safe_metadata and isinstance(safe_metadata["notes"], str):
            text = safe_metadata["notes"]
            if len(text) > 120:
                safe_metadata["notes"] = f"{text[:117]}..."
        self._audit.record(
            AuditRecordCreate(
                request_id=f"paper-validation-run-session-{plan_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="paper_validation_run_session",
                resource_id=str(plan_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata=safe_metadata,
            )
        )
