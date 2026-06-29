"""Paper validation run plan schemas (Slice 81 — planning only, no run/execution)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import (
    PaperValidationDraftRiskMode,
    PaperValidationRunPlanStatus,
    StrictModel,
)
from app.schemas.paper_validation_draft import PaperValidationDraftChecklist

CREATE_PAPER_VALIDATION_RUN_PLAN_CONFIRM = "CREATE_PAPER_VALIDATION_RUN_PLAN"
_MAX_PLAN_TEXT = 4000


class PaperValidationRunPlanItem(StrictModel):
    plan_id: UUID
    candidate_id: UUID
    draft_id: UUID
    source_alert_id: UUID
    symbol: str | None = None
    timeframe: str | None = None
    condition: str | None = None
    direction: str | None = None
    confidence: float | None = None
    trigger_level: float | None = None
    invalidation_level: float | None = None
    latest_price: float | None = None
    thesis: str | None = None
    entry_criteria: str | None = None
    invalidation_criteria: str | None = None
    risk_notes: str | None = None
    checklist_snapshot: PaperValidationDraftChecklist = Field(
        default_factory=PaperValidationDraftChecklist
    )
    risk_mode: PaperValidationDraftRiskMode
    plan_status: PaperValidationRunPlanStatus
    validation_window: str | None = None
    observation_timeframe: str | None = None
    max_duration_minutes: int | None = None
    planned_entry_rule: str | None = None
    planned_invalidation_rule: str | None = None
    planned_success_criteria: str | None = None
    planned_failure_criteria: str | None = None
    created_at: datetime


class PaginatedPaperValidationRunPlans(StrictModel):
    items: list[PaperValidationRunPlanItem]
    total: int
    limit: int
    offset: int


class PaperValidationRunPlanCreateRequest(StrictModel):
    confirm: str
    validation_window: str = Field(min_length=1, max_length=32)
    observation_timeframe: str = Field(min_length=1, max_length=10)
    max_duration_minutes: int = Field(ge=1, le=10_080)
    planned_entry_rule: str = Field(min_length=1, max_length=_MAX_PLAN_TEXT)
    planned_invalidation_rule: str = Field(min_length=1, max_length=_MAX_PLAN_TEXT)
    planned_success_criteria: str = Field(min_length=1, max_length=_MAX_PLAN_TEXT)
    planned_failure_criteria: str = Field(min_length=1, max_length=_MAX_PLAN_TEXT)


class PaperValidationRunPlanCreateResult(StrictModel):
    plan: PaperValidationRunPlanItem
    already_exists: bool = False


class PaperValidationRunPlanStatusUpdate(StrictModel):
    plan_status: PaperValidationRunPlanStatus

    @field_validator("plan_status")
    @classmethod
    def allowed_statuses(cls, value: PaperValidationRunPlanStatus) -> PaperValidationRunPlanStatus:
        if value not in {
            PaperValidationRunPlanStatus.PLANNED,
            PaperValidationRunPlanStatus.NEEDS_REVISION,
            PaperValidationRunPlanStatus.ARCHIVED,
        }:
            raise ValueError("Invalid plan status.")
        return value


class PaperValidationRunPlanSummary(StrictModel):
    total_planned: int
    total_needs_revision: int
    total_archived: int
    by_condition: dict[str, int] = Field(default_factory=dict)
    by_symbol: dict[str, int] = Field(default_factory=dict)
    latest_created_at: datetime | None = None
