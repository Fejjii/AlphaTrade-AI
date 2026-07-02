"""Coaching prompt API schemas (Slice 87 — record derived, no automation).

Response models for deterministic coaching prompts derived from paper validation
outcomes and learning analytics. These schemas describe read-only study guidance
and optional journaling into the existing lesson candidate workflow. They never
represent orders, proposals, approvals, executions, or any executable intent.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.analytics import AnalyticsDateRange
from app.schemas.common import LessonSeverity, StrictModel
from app.schemas.validation_priority import FactorDirection, ReliabilityTier


class CoachingCategory(StrEnum):
    """Deterministic coaching pattern categories (Slice 87)."""

    MISSED_ENTRY = "missed_entry"
    SHOULD_HAVE_WAITED = "should_have_waited"
    SHOULD_HAVE_AVOIDED = "should_have_avoided"
    INVALIDATION_HIT = "invalidation_hit"
    LOW_QUALITY_SETUP = "low_quality_setup"
    OVERCONFIDENCE = "overconfidence"
    WEAK_CONFIDENCE_CORRELATION = "weak_confidence_correlation"


CoachingSeverity = LessonSeverity


class CoachingSource(StrictModel):
    """Source evidence backing a coaching prompt."""

    matched_dimension: str
    matched_key: str
    sample_size: int
    source_session_ids: list[UUID] = Field(default_factory=list)
    analytics_codes: list[str] = Field(default_factory=list)
    rate: float | None = None


class CoachingFactor(StrictModel):
    """A single explainable contributor to a coaching concern score."""

    code: str
    label: str
    direction: FactorDirection
    contribution: float
    detail: str


class CoachingPrompt(StrictModel):
    """A live-computed coaching prompt for behavior review."""

    signature: str
    category: CoachingCategory
    title: str
    prompt_text: str
    severity: LessonSeverity
    reliability: ReliabilityTier
    concern_score: int
    insufficient_data: bool
    source: CoachingSource
    factors: list[CoachingFactor] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    already_saved_lesson_id: UUID | None = None


class CoachingContext(StrictModel):
    """Shared response context echoed by every coaching endpoint."""

    organization_id: UUID
    user_id: UUID | None = None
    date_range: AnalyticsDateRange
    min_sample: int
    note: str


class CoachingPromptsResponse(CoachingContext):
    total: int = 0
    items: list[CoachingPrompt] = Field(default_factory=list)


class CategoryCount(StrictModel):
    category: CoachingCategory
    count: int = 0


class SeverityCount(StrictModel):
    severity: LessonSeverity
    count: int = 0


class CoachingSummaryResponse(CoachingContext):
    total_open: int = 0
    pending_coaching_lessons: int = 0
    by_category: list[CategoryCount] = Field(default_factory=list)
    by_severity: list[SeverityCount] = Field(default_factory=list)
    top_prompt: CoachingPrompt | None = None


class CoachingExplainResponse(CoachingContext):
    prompt: CoachingPrompt


class CoachingSaveRequest(StrictModel):
    """Save a coaching prompt into the lesson review queue.

    The server recomputes prompt text; client-supplied lesson body is ignored.
    """

    category: CoachingCategory
    matched_dimension: str = Field(min_length=1, max_length=60)
    matched_key: str = Field(min_length=1, max_length=120)
    min_sample: int = Field(default=5, ge=1, le=100)
    start_date: date | None = None
    end_date: date | None = None
    reviewer_note: str | None = Field(default=None, max_length=4000)
