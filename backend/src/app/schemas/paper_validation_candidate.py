"""Paper validation candidate schemas (Slice 80 — queue only, no run/execution)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.backtest import SetupEvidenceTier
from app.schemas.common import (
    PaperValidationCandidateStatus,
    PaperValidationDraftRiskMode,
    PromotionSource,
    StrictModel,
)
from app.schemas.paper_validation_draft import PaperValidationDraftChecklist

QUEUE_PAPER_VALIDATION_CANDIDATE_CONFIRM = "QUEUE_PAPER_VALIDATION_CANDIDATE"


class PaperValidationCandidateItem(StrictModel):
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
    candidate_status: PaperValidationCandidateStatus
    created_at: datetime
    # AT-035 research provenance (nullable for legacy / alert-draft rows)
    promotion_source: PromotionSource | None = None
    backtest_run_id: UUID | None = None
    strategy_id: UUID | None = None
    strategy_version_id: UUID | None = None
    dataset_hash: str | None = None
    config_hash: str | None = None
    result_hash: str | None = None
    evidence_tier: SetupEvidenceTier | None = None
    sample_size: int | None = None
    oos_expectancy: Decimal | None = None
    regime: str | None = None
    evidence_snapshot: dict[str, Any] | None = None


class PaginatedPaperValidationCandidates(StrictModel):
    items: list[PaperValidationCandidateItem]
    total: int
    limit: int
    offset: int


class PaperValidationCandidateQueueRequest(StrictModel):
    confirm: str


class PaperValidationCandidateQueueResult(StrictModel):
    candidate: PaperValidationCandidateItem
    already_exists: bool = False


class PaperValidationCandidateStatusUpdate(StrictModel):
    candidate_status: PaperValidationCandidateStatus


class PaperValidationCandidateSummary(StrictModel):
    total_queued: int
    total_reviewing: int
    total_archived: int
    by_condition: dict[str, int] = Field(default_factory=dict)
    by_symbol: dict[str, int] = Field(default_factory=dict)
    latest_created_at: datetime | None = None
