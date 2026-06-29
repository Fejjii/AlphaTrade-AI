"""Paper validation run plan service (Slice 81 — planning only, no run/execution)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import PaperValidationCandidate as CandidateModel
from app.db.models import PaperValidationRunPlan as PlanModel
from app.repositories.paper_validation_candidate import PaperValidationCandidateRepository
from app.repositories.paper_validation_run_plan import PaperValidationRunPlanRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperValidationCandidateStatus,
    PaperValidationDraftRiskMode,
    PaperValidationRunPlanStatus,
)
from app.schemas.paper_validation_candidate import PaperValidationCandidateItem
from app.schemas.paper_validation_run_plan import (
    CREATE_PAPER_VALIDATION_RUN_PLAN_CONFIRM,
    PaginatedPaperValidationRunPlans,
    PaperValidationRunPlanCreateRequest,
    PaperValidationRunPlanCreateResult,
    PaperValidationRunPlanItem,
    PaperValidationRunPlanStatusUpdate,
    PaperValidationRunPlanSummary,
)
from app.services.audit_service import AuditService
from app.services.paper_validation_candidate_service import PaperValidationCandidateService
from app.services.paper_validation_draft_service import PaperValidationDraftService


class PaperValidationRunPlanService:
    """Create and review non-executable paper validation run plans from reviewing candidates."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._candidates = PaperValidationCandidateRepository(session)
        self._plans = PaperValidationRunPlanRepository(session)
        self._audit = AuditService(session)

    def create_from_candidate(
        self,
        candidate_id: uuid.UUID,
        payload: PaperValidationRunPlanCreateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationRunPlanCreateResult:
        if payload.confirm != CREATE_PAPER_VALIDATION_RUN_PLAN_CONFIRM:
            self._record_audit(
                "paper_validation_run_plan_blocked",
                candidate_id=candidate_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"reason": "confirmation_required"},
            )
            raise ValidationAppError(
                "Exact confirmation required to create a paper validation run plan.",
                details={"required_confirm": CREATE_PAPER_VALIDATION_RUN_PLAN_CONFIRM},
            )

        self._record_audit(
            "paper_validation_run_plan_requested",
            candidate_id=candidate_id,
            organization_id=organization_id,
            user_id=user_id,
        )

        candidate_row = self._candidates.get_for_org(candidate_id, organization_id=organization_id)
        if candidate_row is None:
            raise NotFoundError("Candidate not found.")

        candidate_item = PaperValidationCandidateService._to_item(candidate_row)

        if candidate_item.candidate_status != PaperValidationCandidateStatus.REVIEWING:
            self._record_audit(
                "paper_validation_run_plan_blocked",
                candidate_id=candidate_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={
                    "reason": "candidate_not_reviewing",
                    "candidate_status": candidate_item.candidate_status.value,
                },
            )
            raise ValidationAppError(
                "Candidate status must be reviewing before creating a run plan.",
                details={
                    "candidate_id": str(candidate_id),
                    "candidate_status": candidate_item.candidate_status.value,
                },
            )

        existing = self._plans.get_active_for_candidate(organization_id, candidate_id)
        if existing is not None:
            self._record_audit(
                "paper_validation_run_plan_already_exists",
                candidate_id=candidate_id,
                organization_id=organization_id,
                user_id=user_id,
                metadata={"plan_id": str(existing.id)},
            )
            return PaperValidationRunPlanCreateResult(
                plan=self._to_item(existing),
                already_exists=True,
            )

        plan = self._build_plan(
            candidate_row,
            candidate_item,
            payload,
            organization_id=organization_id,
            user_id=user_id,
        )
        self._plans.add(plan)
        self._record_audit(
            "paper_validation_run_plan_created",
            candidate_id=candidate_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "plan_id": str(plan.id),
                "condition": plan.condition,
                "symbol": plan.symbol,
            },
        )
        return PaperValidationRunPlanCreateResult(plan=self._to_item(plan), already_exists=False)

    def list_plans(
        self,
        organization_id: uuid.UUID,
        *,
        status: PaperValidationRunPlanStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedPaperValidationRunPlans:
        rows, total = self._plans.list_for_org(
            organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return PaginatedPaperValidationRunPlans(
            items=[self._to_item(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_plan(
        self,
        plan_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRunPlanItem:
        row = self._plans.get_for_org(plan_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Run plan not found.")
        return self._to_item(row)

    def plan_summary(self, organization_id: uuid.UUID) -> PaperValidationRunPlanSummary:
        data = self._plans.summary_for_org(organization_id)
        return PaperValidationRunPlanSummary(**data)

    def update_status(
        self,
        plan_id: uuid.UUID,
        payload: PaperValidationRunPlanStatusUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PaperValidationRunPlanItem:
        row = self._plans.get_for_org(plan_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Run plan not found.")

        row.plan_status = payload.plan_status.value
        item = self._to_item(row)
        self._record_audit(
            "paper_validation_run_plan_status_updated",
            candidate_id=row.candidate_id,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "plan_id": str(plan_id),
                "plan_status": payload.plan_status.value,
            },
        )
        return item

    @staticmethod
    def _build_plan(
        candidate_row: CandidateModel,
        candidate_item: PaperValidationCandidateItem,
        payload: PaperValidationRunPlanCreateRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> PlanModel:
        return PlanModel(
            organization_id=organization_id,
            candidate_id=candidate_row.id,
            draft_id=candidate_row.draft_id,
            source_alert_id=candidate_row.source_alert_id,
            symbol=candidate_row.symbol,
            timeframe=candidate_row.timeframe,
            condition=candidate_row.condition,
            direction=candidate_row.direction,
            confidence=candidate_row.confidence,
            trigger_level=candidate_row.trigger_level,
            invalidation_level=candidate_row.invalidation_level,
            latest_price=candidate_row.latest_price,
            thesis=candidate_row.thesis,
            entry_criteria=candidate_row.entry_criteria,
            invalidation_criteria=candidate_row.invalidation_criteria,
            risk_notes=candidate_row.risk_notes,
            checklist_snapshot=candidate_item.checklist_snapshot.model_dump(),
            risk_mode=candidate_row.risk_mode,
            plan_status=PaperValidationRunPlanStatus.PLANNED.value,
            validation_window=payload.validation_window,
            observation_timeframe=payload.observation_timeframe,
            max_duration_minutes=payload.max_duration_minutes,
            planned_entry_rule=payload.planned_entry_rule,
            planned_invalidation_rule=payload.planned_invalidation_rule,
            planned_success_criteria=payload.planned_success_criteria,
            planned_failure_criteria=payload.planned_failure_criteria,
            created_by=user_id,
        )

    @classmethod
    def _to_item(cls, row: PlanModel) -> PaperValidationRunPlanItem:
        try:
            risk_mode = PaperValidationDraftRiskMode(row.risk_mode)
        except ValueError:
            risk_mode = PaperValidationDraftRiskMode.CONSERVATIVE
        try:
            plan_status = PaperValidationRunPlanStatus(row.plan_status)
        except ValueError:
            plan_status = PaperValidationRunPlanStatus.PLANNED
        checklist = PaperValidationDraftService._parse_checklist(row.checklist_snapshot)
        return PaperValidationRunPlanItem(
            plan_id=row.id,
            candidate_id=row.candidate_id,
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
            plan_status=plan_status,
            validation_window=row.validation_window,
            observation_timeframe=row.observation_timeframe,
            max_duration_minutes=row.max_duration_minutes,
            planned_entry_rule=row.planned_entry_rule,
            planned_invalidation_rule=row.planned_invalidation_rule,
            planned_success_criteria=row.planned_success_criteria,
            planned_failure_criteria=row.planned_failure_criteria,
            created_at=row.created_at,
        )

    def _record_audit(
        self,
        action: str,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        safe_metadata: dict[str, object] = {"action": action, **(metadata or {})}
        for key in (
            "planned_entry_rule",
            "planned_invalidation_rule",
            "planned_success_criteria",
            "planned_failure_criteria",
            "thesis",
        ):
            if key in safe_metadata and isinstance(safe_metadata[key], str):
                text = safe_metadata[key]
                if len(text) > 120:
                    safe_metadata[key] = f"{text[:117]}..."
        self._audit.record(
            AuditRecordCreate(
                request_id=f"paper-validation-run-plan-{candidate_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="paper_validation_run_plan",
                resource_id=str(candidate_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata=safe_metadata,
            )
        )
