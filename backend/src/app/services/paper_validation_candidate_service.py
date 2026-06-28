"""Paper validation candidate service (Slice 80 - queue only, no run/execution)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import PaperValidationCandidate as CandidateModel
from app.db.models import PaperValidationDraft as DraftModel
from app.repositories.paper_validation_candidate import PaperValidationCandidateRepository
from app.repositories.paper_validation_draft import PaperValidationDraftRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperValidationCandidateStatus,
    PaperValidationDraftPrepStatus,
    PaperValidationDraftRiskMode,
    PaperValidationDraftStatus,
)
from app.schemas.paper_validation_candidate import (
    QUEUE_PAPER_VALIDATION_CANDIDATE_CONFIRM,
    PaginatedPaperValidationCandidates,
    PaperValidationCandidateItem,
    PaperValidationCandidateQueueRequest,
    PaperValidationCandidateQueueResult,
    PaperValidationCandidateStatusUpdate,
    PaperValidationCandidateSummary,
)
from app.schemas.paper_validation_draft import PaperValidationDraftItem
from app.services.audit_service import AuditService
from app.services.paper_validation_draft_service import PaperValidationDraftService


class PaperValidationCandidateService:
    """Queue and review non-executable paper validation candidates from ready drafts."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._drafts = PaperValidationDraftRepository(session)
        self._candidates = PaperValidationCandidateRepository(session)
        self._audit = AuditService(session)

    def queue_from_draft(
        self,
        draft_id: uuid.UUID,
        payload: PaperValidationCandidateQueueRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationCandidateQueueResult:
        if payload.confirm != QUEUE_PAPER_VALIDATION_CANDIDATE_CONFIRM:
            self._record_audit(
                "paper_validation_candidate_blocked",
                draft_id=draft_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "confirmation_required"},
            )
            raise ValidationAppError(
                "Exact confirmation required to queue a paper validation candidate.",
                details={"required_confirm": QUEUE_PAPER_VALIDATION_CANDIDATE_CONFIRM},
            )

        self._record_audit(
            "paper_validation_candidate_queue_requested",
            draft_id=draft_id,
            organization_id=organization_id,
            user_id=user_id,
        )

        row = self._drafts.get_for_org(draft_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Draft not found.")

        draft_item = PaperValidationDraftService._to_item(row)

        if row.status != PaperValidationDraftStatus.DRAFT.value:
            self._record_audit(
                "paper_validation_candidate_blocked",
                draft_id=draft_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "draft_not_editable", "status": row.status},
            )
            raise ValidationAppError(
                "Only active drafts can be queued for validation.",
                details={"draft_id": str(draft_id), "status": row.status},
            )

        if draft_item.prep_status != PaperValidationDraftPrepStatus.READY_FOR_VALIDATION:
            self._record_audit(
                "paper_validation_candidate_blocked",
                draft_id=draft_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={
                    "reason": "prep_status_not_ready",
                    "prep_status": draft_item.prep_status.value,
                },
            )
            raise ValidationAppError(
                "Draft prep status must be ready_for_validation before queueing.",
                details={
                    "draft_id": str(draft_id),
                    "prep_status": draft_item.prep_status.value,
                },
            )

        if not draft_item.is_ready_for_validation:
            self._record_audit(
                "paper_validation_candidate_blocked",
                draft_id=draft_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "draft_not_ready"},
            )
            raise ValidationAppError(
                "Draft is not ready for validation.",
                details={"draft_id": str(draft_id)},
            )

        existing = self._candidates.get_active_for_draft(organization_id, draft_id)
        if existing is not None:
            self._record_audit(
                "paper_validation_candidate_already_exists",
                draft_id=draft_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"candidate_id": str(existing.id)},
            )
            return PaperValidationCandidateQueueResult(
                candidate=self._to_item(existing),
                already_exists=True,
            )

        candidate = self._build_candidate(
            row, draft_item, organization_id=organization_id, user_id=user_id
        )
        self._candidates.add(candidate)
        self._record_audit(
            "paper_validation_candidate_created",
            draft_id=draft_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "candidate_id": str(candidate.id),
                "condition": candidate.condition,
                "symbol": candidate.symbol,
            },
        )
        return PaperValidationCandidateQueueResult(
            candidate=self._to_item(candidate),
            already_exists=False,
        )

    def list_candidates(
        self,
        organization_id: uuid.UUID,
        *,
        status: PaperValidationCandidateStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedPaperValidationCandidates:
        rows, total = self._candidates.list_for_org(
            organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return PaginatedPaperValidationCandidates(
            items=[self._to_item(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_candidate(
        self,
        candidate_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationCandidateItem:
        row = self._candidates.get_for_org(candidate_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Candidate not found.")
        return self._to_item(row)

    def candidate_summary(self, organization_id: uuid.UUID) -> PaperValidationCandidateSummary:
        data = self._candidates.summary_for_org(organization_id)
        return PaperValidationCandidateSummary(**data)

    def update_status(
        self,
        candidate_id: uuid.UUID,
        payload: PaperValidationCandidateStatusUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationCandidateItem:
        row = self._candidates.get_for_org(candidate_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Candidate not found.")

        row.candidate_status = payload.candidate_status.value
        item = self._to_item(row)
        self._record_audit(
            "paper_validation_candidate_status_updated",
            draft_id=row.draft_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "candidate_id": str(candidate_id),
                "candidate_status": payload.candidate_status.value,
            },
        )
        return item

    @staticmethod
    def _build_candidate(
        draft_row: DraftModel,
        draft_item: PaperValidationDraftItem,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> CandidateModel:
        return CandidateModel(
            organization_id=organization_id,
            draft_id=draft_row.id,
            source_alert_id=draft_row.source_alert_id,
            symbol=draft_row.symbol,
            timeframe=draft_row.timeframe,
            condition=draft_row.condition,
            direction=draft_row.direction,
            confidence=draft_row.confidence,
            trigger_level=draft_row.trigger_level,
            invalidation_level=draft_row.invalidation_level,
            latest_price=draft_row.latest_price,
            thesis=draft_row.thesis,
            entry_criteria=draft_row.entry_criteria,
            invalidation_criteria=draft_row.invalidation_criteria,
            risk_notes=draft_row.risk_notes,
            checklist_snapshot=draft_item.checklist.model_dump(),
            risk_mode=draft_row.risk_mode,
            candidate_status=PaperValidationCandidateStatus.QUEUED.value,
            created_by=user_id,
        )

    @classmethod
    def _to_item(cls, row: CandidateModel) -> PaperValidationCandidateItem:
        try:
            risk_mode = PaperValidationDraftRiskMode(row.risk_mode)
        except ValueError:
            risk_mode = PaperValidationDraftRiskMode.CONSERVATIVE
        try:
            candidate_status = PaperValidationCandidateStatus(row.candidate_status)
        except ValueError:
            candidate_status = PaperValidationCandidateStatus.QUEUED
        checklist = PaperValidationDraftService._parse_checklist(row.checklist_snapshot)
        return PaperValidationCandidateItem(
            candidate_id=row.id,
            draft_id=row.draft_id,
            source_alert_id=row.source_alert_id,
            symbol=row.symbol,
            timeframe=row.timeframe,
            condition=row.condition,
            direction=row.direction,
            confidence=row.confidence,
            trigger_level=row.trigger_level,
            invalidation_level=row.invalidation_level,
            latest_price=row.latest_price,
            thesis=row.thesis,
            entry_criteria=row.entry_criteria,
            invalidation_criteria=row.invalidation_criteria,
            risk_notes=row.risk_notes,
            checklist_snapshot=checklist,
            risk_mode=risk_mode,
            candidate_status=candidate_status,
            created_at=row.created_at,
        )

    def _record_audit(
        self,
        action: str,
        *,
        draft_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id=f"paper-validation-candidate-{draft_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="paper_validation_candidate",
                resource_id=str(draft_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"action": action, **(metadata or {})},
            )
        )
