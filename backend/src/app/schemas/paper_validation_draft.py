"""Paper validation draft schemas (Slice 78 — draft only, no execution)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    PaperValidationDraftRiskMode,
    PaperValidationDraftStatus,
    StrictModel,
)

CREATE_PAPER_VALIDATION_DRAFT_CONFIRM = "CREATE_PAPER_VALIDATION_DRAFT"
PAPER_VALIDATION_DRAFT_NOTES_MAX = 4000


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


class PaperValidationDraftSummary(StrictModel):
    total_drafts: int
    latest_condition: str | None = None
    latest_created_at: datetime | None = None
