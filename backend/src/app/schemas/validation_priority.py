"""Validation prioritization API schemas (Slice 85 — read-only, record derived).

Response models for the validation prioritization layer that ranks pending
paper validation run plans and candidates by a deterministic priority score.
These schemas describe derived, read-only study guidance. They never represent
orders, proposals, approvals, executions, or any executable intent, and they
never enable automation.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.analytics import AnalyticsDateRange
from app.schemas.common import StrictModel


class PriorityItemType(StrEnum):
    """The kind of pending item being prioritized for manual validation."""

    RUN_PLAN = "run_plan"
    CANDIDATE = "candidate"


class ValidationActionLabel(StrEnum):
    """Study guidance label for a pending setup. Never an execution instruction."""

    PRIORITIZE = "prioritize"
    WATCH = "watch"
    COLLECT_MORE_DATA = "collect_more_data"
    AVOID_FOR_NOW = "avoid_for_now"


class ReliabilityTier(StrEnum):
    """How much historical evidence backs an item's priority score."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FactorDirection(StrEnum):
    """Whether a scoring factor pushed priority up, down, or was neutral."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class PriorityFactor(StrictModel):
    """A single explainable contributor to an item's priority score."""

    code: str
    label: str
    direction: FactorDirection
    contribution: float
    detail: str


class ValidationPriorityContext(StrictModel):
    """Shared response context echoed by every validation priority endpoint."""

    organization_id: UUID
    user_id: UUID | None = None
    date_range: AnalyticsDateRange
    min_sample: int
    note: str


class ValidationPriorityItem(StrictModel):
    """A pending setup with its derived, read-only validation priority."""

    item_type: PriorityItemType
    item_id: UUID
    symbol: str | None = None
    condition: str | None = None
    timeframe: str | None = None
    direction: str | None = None
    confidence: float | None = None
    confidence_bucket: str | None = None
    current_status: str
    priority_score: int
    action_label: ValidationActionLabel
    reliability: ReliabilityTier
    matched_dimension: str
    matched_key: str
    matched_sample_size: int = 0
    historical_success_rate: float | None = None
    historical_invalidation_rate: float | None = None
    factors: list[PriorityFactor] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class ValidationPriorityQueueResponse(ValidationPriorityContext):
    item_type_filter: PriorityItemType | None = None
    limit: int
    total_pending: int = 0
    items: list[ValidationPriorityItem] = Field(default_factory=list)


class ActionLabelCount(StrictModel):
    action_label: ValidationActionLabel
    count: int = 0


class ReliabilityCount(StrictModel):
    reliability: ReliabilityTier
    count: int = 0


class ValidationPrioritySummaryResponse(ValidationPriorityContext):
    total_pending: int = 0
    run_plans_pending: int = 0
    candidates_pending: int = 0
    by_action: list[ActionLabelCount] = Field(default_factory=list)
    by_reliability: list[ReliabilityCount] = Field(default_factory=list)


class ValidationPriorityExplainResponse(ValidationPriorityContext):
    item: ValidationPriorityItem
