"""Paper validation session observation service (Slice 83 — manual log, record only).

This service deliberately depends only on the observation repository, the run-session
repository, and the audit service. It never imports or invokes the paper validation
runtime engine, scheduler, exchange, proposal/approval, or Telegram paths.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import PaperValidationRunSession as SessionModel
from app.db.models import PaperValidationSessionObservation as ObservationModel
from app.repositories.paper_validation_run_session import PaperValidationRunSessionRepository
from app.repositories.paper_validation_session_observation import (
    PaperValidationSessionObservationRepository,
)
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperValidationObservationKind,
    PaperValidationRunSessionStatus,
)
from app.schemas.paper_validation_session_observation import (
    RECORD_PAPER_VALIDATION_OBSERVATION_CONFIRM,
    PaginatedPaperValidationSessionObservations,
    PaperValidationSessionObservationCreateRequest,
    PaperValidationSessionObservationItem,
)
from app.services.audit_service import AuditService


class PaperValidationSessionObservationService:
    """Manually record observations during a running paper validation session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._sessions = PaperValidationRunSessionRepository(session)
        self._observations = PaperValidationSessionObservationRepository(session)
        self._audit = AuditService(session)

    def list_observations(
        self,
        session_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedPaperValidationSessionObservations:
        parent = self._sessions.get_for_org(session_id, organization_id=organization_id)
        if parent is None:
            raise NotFoundError("Run session not found.")
        rows, total = self._observations.list_for_session(
            organization_id,
            session_id,
            limit=limit,
            offset=offset,
        )
        return PaginatedPaperValidationSessionObservations(
            items=[self._to_item(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def record_observation(
        self,
        session_id: uuid.UUID,
        payload: PaperValidationSessionObservationCreateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationSessionObservationItem:
        if payload.confirm != RECORD_PAPER_VALIDATION_OBSERVATION_CONFIRM:
            self._record_audit(
                "paper_validation_session_observation_blocked",
                session_id=session_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "confirmation_required"},
            )
            raise ValidationAppError(
                "Exact confirmation required to record an observation.",
                details={"required_confirm": RECORD_PAPER_VALIDATION_OBSERVATION_CONFIRM},
            )

        self._record_audit(
            "paper_validation_session_observation_requested",
            session_id=session_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={"observation_kind": payload.observation_kind.value},
        )

        parent = self._require_running_session(
            session_id,
            organization_id=organization_id,
            user_id=user_id,
            blocked_action="paper_validation_session_observation_blocked",
        )

        observed_at = payload.observed_at or datetime.now(UTC)
        row = ObservationModel(
            organization_id=organization_id,
            run_session_id=session_id,
            run_plan_id=parent.run_plan_id,
            observation_kind=payload.observation_kind.value,
            observed_price=payload.observed_price,
            observed_at=observed_at,
            note=payload.note,
            recorded_by=user_id,
        )
        self._observations.add(row)
        self._session.flush()
        self._session.commit()
        self._session.refresh(row)

        self._record_audit(
            "paper_validation_session_observation_recorded",
            session_id=session_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "observation_id": str(row.id),
                "observation_kind": payload.observation_kind.value,
            },
        )
        return self._to_item(row)

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
                "Observations can only be recorded while the session is running.",
                details={
                    "session_id": str(session_id),
                    "session_status": parent.session_status,
                },
            )
        return parent

    @classmethod
    def _to_item(cls, row: ObservationModel) -> PaperValidationSessionObservationItem:
        try:
            kind = PaperValidationObservationKind(row.observation_kind)
        except ValueError:
            kind = PaperValidationObservationKind.GENERAL_NOTE
        return PaperValidationSessionObservationItem(
            observation_id=row.id,
            run_session_id=row.run_session_id,
            run_plan_id=row.run_plan_id,
            observation_kind=kind,
            observed_price=row.observed_price,
            observed_at=row.observed_at,
            note=row.note,
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
        if "note" in safe_metadata and isinstance(safe_metadata["note"], str):
            text = safe_metadata["note"]
            if len(text) > 120:
                safe_metadata["note"] = f"{text[:117]}..."
        self._audit.record(
            AuditRecordCreate(
                request_id=f"pv-session-obs-{session_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="paper_validation_session_observation",
                resource_id=str(session_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata=safe_metadata,
            )
        )
