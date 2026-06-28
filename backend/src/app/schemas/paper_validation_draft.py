"""Paper validation draft schemas (Slice 78-79 - draft/prep only, no execution)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    PaperValidationDraftPrepStatus,
    PaperValidationDraftRiskMode,
    PaperValidationDraftStatus,
    StrictModel,
)

CREATE_PAPER_VALIDATION_DRAFT_CONFIRM = "CREATE_PAPER_VALIDATION_DRAFT"
PAPER_VALIDATION_DRAFT_NOTES_MAX = 4000
PAPER_VALIDATION_DRAFT_PREP_FIELD_MAX = 4000

PREP_CHECKLIST_KEYS = (
    "trend_checked",
    "support_resistance_checked",
    "volume_checked",
    "risk_reward_checked",
    "invalidation_checked",
    "higher_timeframe_checked",
    "news_or_funding_checked",
)


class PaperValidationDraftChecklist(StrictModel):
    trend_checked: bool = False
    support_resistance_checked: bool = False
    volume_checked: bool = False
    risk_reward_checked: bool = False
    invalidation_checked: bool = False
    higher_timeframe_checked: bool = False
    news_or_funding_checked: bool = False


class PaperValidationDraftItem(StrictModel):
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
    reason: str | None = None
    risk_mode: PaperValidationDraftRiskMode
    status: PaperValidationDraftStatus
    created_at: datetime
    created_by: UUID | None = None
    thesis: str | None = None
    entry_criteria: str | None = None
    invalidation_criteria: str | None = None
    risk_notes: str | None = None
    prep_status: PaperValidationDraftPrepStatus = PaperValidationDraftPrepStatus.DRAFT
    checklist: PaperValidationDraftChecklist = Field(default_factory=PaperValidationDraftChecklist)
    prep_completion_score: int = 0
    missing_checklist_items: list[str] = Field(default_factory=list)
    is_ready_for_validation: bool = False


class PaginatedPaperValidationDrafts(StrictModel):
    items: list[PaperValidationDraftItem]
    total: int
    limit: int
    offset: int


class SetupAlertDraftCreateRequest(StrictModel):
    confirm: str
    notes: str | None = Field(default=None, max_length=PAPER_VALIDATION_DRAFT_NOTES_MAX)
    risk_mode: PaperValidationDraftRiskMode = PaperValidationDraftRiskMode.CONSERVATIVE


class SetupAlertDraftCreateResult(StrictModel):
    draft: PaperValidationDraftItem
    already_exists: bool = False


class PaperValidationDraftPrepUpdateRequest(StrictModel):
    prep_status: PaperValidationDraftPrepStatus | None = None
    thesis: str | None = Field(default=None, max_length=PAPER_VALIDATION_DRAFT_PREP_FIELD_MAX)
    entry_criteria: str | None = Field(
        default=None, max_length=PAPER_VALIDATION_DRAFT_PREP_FIELD_MAX
    )
    invalidation_criteria: str | None = Field(
        default=None, max_length=PAPER_VALIDATION_DRAFT_PREP_FIELD_MAX
    )
    risk_notes: str | None = Field(default=None, max_length=PAPER_VALIDATION_DRAFT_PREP_FIELD_MAX)
    checklist: PaperValidationDraftChecklist | None = None


class PaperValidationDraftSummary(StrictModel):
    total_drafts: int
    latest_condition: str | None = None
    latest_created_at: datetime | None = None
    ready_for_validation_count: int = 0
