"""Paper validation session result service (Slice 83 — outcome classification, record only).

This service deliberately depends only on the result repository, the run-session
repository, and the audit service. It never imports or invokes the paper validation
runtime engine, scheduler, exchange, proposal/approval, or Telegram paths.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import PaperValidationRunSession as SessionModel
from app.db.models import PaperValidationSessionResult as ResultModel
from app.repositories.paper_validation_run_session import PaperValidationRunSessionRepository
from app.repositories.paper_validation_session_result import PaperValidationSessionResultRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperValidationCriteriaMet,
    PaperValidationDisciplineAssessment,
    PaperValidationEntryAssessment,
    PaperValidationOutcome,
    PaperValidationRunSessionStatus,
)
from app.schemas.paper_validation_session_result import (
    RECORD_PAPER_VALIDATION_OUTCOME_CONFIRM,
    PaperValidationSessionResultCreateRequest,
    PaperValidationSessionResultCreateResult,
    PaperValidationSessionResultItem,
    PaperValidationSessionResultUpdateRequest,
)
from app.services.audit_service import AuditService


class PaperValidationSessionResultService:
    """Manually record and update the outcome for a running paper validation session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._sessions = PaperValidationRunSessionRepository(session)
        self._results = PaperValidationSessionResultRepository(session)
        self._audit = AuditService(session)

    def get_result(
        self,
        session_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationSessionResultItem:
        parent = self._sessions.get_for_org(session_id, organization_id=organization_id)
        if parent is None:
            raise NotFoundError("Run session not found.")
        row = self._results.get_for_session(organization_id, session_id)
        if row is None:
            raise NotFoundError("Session result not found.")
        return self._to_item(row)

    def record_result(
        self,
        session_id: uuid.UUID,
        payload: PaperValidationSessionResultCreateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationSessionResultCreateResult:
        if payload.confirm != RECORD_PAPER_VALIDATION_OUTCOME_CONFIRM:
            self._record_audit(
                "paper_validation_session_result_blocked",
                session_id=session_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "confirmation_required"},
            )
            raise ValidationAppError(
                "Exact confirmation required to record a session outcome.",
                details={"required_confirm": RECORD_PAPER_VALIDATION_OUTCOME_CONFIRM},
            )

        self._record_audit(
            "paper_validation_session_result_requested",
            session_id=session_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={"outcome": payload.outcome.value},
        )

        existing = self._results.get_for_session(organization_id, session_id)
        if existing is not None:
            self._record_audit(
                "paper_validation_session_result_already_exists",
                session_id=session_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"result_id": str(existing.id)},
            )
            return PaperValidationSessionResultCreateResult(
                result=self._to_item(existing),
                already_exists=True,
            )

        parent = self._require_running_session(
            session_id,
            organization_id=organization_id,
            user_id=user_id,
            blocked_action="paper_validation_session_result_blocked",
        )

        row = self._build_result(parent, payload, organization_id=organization_id, user_id=user_id)
        self._results.add(row)
        try:
            self._session.flush()
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            duplicate = self._results.get_for_session(organization_id, session_id)
            if duplicate is None:
                raise
            self._record_audit(
                "paper_validation_session_result_already_exists",
                session_id=session_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"result_id": str(duplicate.id)},
            )
            return PaperValidationSessionResultCreateResult(
                result=self._to_item(duplicate),
                already_exists=True,
            )

        self._session.refresh(row)
        self._record_audit(
            "paper_validation_session_result_recorded",
            session_id=session_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={"result_id": str(row.id), "outcome": payload.outcome.value},
        )
        return PaperValidationSessionResultCreateResult(
            result=self._to_item(row),
            already_exists=False,
        )

    def update_result(
        self,
        session_id: uuid.UUID,
        payload: PaperValidationSessionResultUpdateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationSessionResultItem:
        parent = self._require_running_session(
            session_id,
            organization_id=organization_id,
            user_id=user_id,
            blocked_action="paper_validation_session_result_blocked",
        )
        row = self._results.get_for_session(organization_id, session_id)
        if row is None:
            raise NotFoundError("Session result not found.")

        if payload.outcome is not None:
            row.outcome = payload.outcome.value
        if payload.success_criteria_met is not None:
            row.success_criteria_met = payload.success_criteria_met.value
        if payload.success_criteria_notes is not None:
            row.success_criteria_notes = payload.success_criteria_notes
        if payload.failure_criteria_met is not None:
            row.failure_criteria_met = payload.failure_criteria_met.value
        if payload.failure_criteria_notes is not None:
            row.failure_criteria_notes = payload.failure_criteria_notes
        if payload.invalidation_hit is not None:
            row.invalidation_hit = payload.invalidation_hit
        if payload.invalidation_notes is not None:
            row.invalidation_notes = payload.invalidation_notes
        if payload.entry_assessment is not None:
            row.entry_assessment = payload.entry_assessment.value
        if payload.discipline_assessment is not None:
            row.discipline_assessment = payload.discipline_assessment.value
        if payload.behaved_as_expected is not None:
            row.behaved_as_expected = payload.behaved_as_expected
        if payload.lessons is not None:
            row.lessons = payload.lessons
        row.recorded_at = datetime.now(UTC)
        _ = parent  # parent fetch validates tenant + running window

        item = self._to_item(row)
        self._record_audit(
            "paper_validation_session_result_updated",
            session_id=session_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={"result_id": str(row.id), "outcome": row.outcome},
        )
        return item

    def _require_running_session(
        self,
        session_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        blocked_action: str,
    ) -> SessionModel:
        parent = self._sessions.get_for_org(session_id, organization_id=organization_id)
        if parent is None:
            raise NotFoundError("Run session not found.")
        if parent.session_status != PaperValidationRunSessionStatus.RUNNING.value:
            self._record_audit(
                blocked_action,
                session_id=session_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={
                    "reason": "session_not_running",
                    "session_status": parent.session_status,
                },
            )
            raise ValidationAppError(
                "Session outcome can only be recorded or updated while the session is running.",
                details={
                    "session_id": str(session_id),
                    "session_status": parent.session_status,
                },
            )
        return parent

    @staticmethod
    def _build_result(
        parent: SessionModel,
        payload: PaperValidationSessionResultCreateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> ResultModel:
        return ResultModel(
            organization_id=organization_id,
            run_session_id=parent.id,
            run_plan_id=parent.run_plan_id,
            outcome=payload.outcome.value,
            success_criteria_met=payload.success_criteria_met.value,
            success_criteria_notes=payload.success_criteria_notes,
            failure_criteria_met=payload.failure_criteria_met.value,
            failure_criteria_notes=payload.failure_criteria_notes,
            invalidation_hit=payload.invalidation_hit,
            invalidation_notes=payload.invalidation_notes,
            entry_assessment=payload.entry_assessment.value,
            discipline_assessment=payload.discipline_assessment.value,
            behaved_as_expected=payload.behaved_as_expected,
            lessons=payload.lessons,
            recorded_by=user_id,
            recorded_at=datetime.now(UTC),
        )

    @classmethod
    def _to_item(cls, row: ResultModel) -> PaperValidationSessionResultItem:
        def _enum_or_default(enum_cls: type[Enum], raw: str, default: Enum) -> Enum:
            try:
                return enum_cls(raw)
            except ValueError:
                return default

        return PaperValidationSessionResultItem(
            result_id=row.id,
            run_session_id=row.run_session_id,
            run_plan_id=row.run_plan_id,
            outcome=_enum_or_default(
                PaperValidationOutcome, row.outcome, PaperValidationOutcome.INCONCLUSIVE
            ),  # type: ignore[arg-type]
            success_criteria_met=_enum_or_default(
                PaperValidationCriteriaMet,
                row.success_criteria_met,
                PaperValidationCriteriaMet.UNKNOWN,
            ),  # type: ignore[arg-type]
            success_criteria_notes=row.success_criteria_notes,
            failure_criteria_met=_enum_or_default(
                PaperValidationCriteriaMet,
                row.failure_criteria_met,
                PaperValidationCriteriaMet.UNKNOWN,
            ),  # type: ignore[arg-type]
            failure_criteria_notes=row.failure_criteria_notes,
            invalidation_hit=row.invalidation_hit,
            invalidation_notes=row.invalidation_notes,
            entry_assessment=_enum_or_default(
                PaperValidationEntryAssessment,
                row.entry_assessment,
                PaperValidationEntryAssessment.NO_ENTRY,
            ),  # type: ignore[arg-type]
            discipline_assessment=_enum_or_default(
                PaperValidationDisciplineAssessment,
                row.discipline_assessment,
                PaperValidationDisciplineAssessment.DISCIPLINED,
            ),  # type: ignore[arg-type]
            behaved_as_expected=row.behaved_as_expected,
            lessons=row.lessons,
            recorded_at=row.recorded_at,
            created_at=row.created_at,
        )

    @classmethod
    def _sanitize_audit_value(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return cls._sanitize_audit_metadata(value)  # type: ignore[arg-type]
        if isinstance(value, list):
            return [cls._sanitize_audit_value(item) for item in value]
        if isinstance(value, tuple):
            return [cls._sanitize_audit_value(item) for item in value]
        return value

    @classmethod
    def _sanitize_audit_metadata(cls, metadata: dict[str, object]) -> dict[str, object]:
        return {key: cls._sanitize_audit_value(value) for key, value in metadata.items()}

    def _record_audit(
        self,
        action: str,
        *,
        session_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        safe_metadata = self._sanitize_audit_metadata({"action": action, **(metadata or {})})
        if "lessons" in safe_metadata and isinstance(safe_metadata["lessons"], str):
            text = safe_metadata["lessons"]
            if len(text) > 120:
                safe_metadata["lessons"] = f"{text[:117]}..."
        self._audit.record(
            AuditRecordCreate(
                request_id=f"pv-session-result-{session_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="paper_validation_session_result",
                resource_id=str(session_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata=safe_metadata,
            )
        )
