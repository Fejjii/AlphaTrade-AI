"""Learning analytics API schemas (Slice 84 — read-only, record derived).

Response models for the learning analytics layer that summarizes manual paper
validation sessions, observations, and outcomes. These schemas describe derived
read-only summaries; they never represent orders, proposals, approvals, or any
executable intent.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.analytics import AnalyticsDateRange
from app.schemas.common import PaperValidationOutcome, StrictModel


class SetupDimension(StrEnum):
    """Grouping dimension for setup performance and ranking analytics."""

    CONDITION = "condition"
    TIMEFRAME = "timeframe"
    SYMBOL = "symbol"
    DIRECTION = "direction"
    CONFIDENCE_BUCKET = "confidence_bucket"


class LearningAnalyticsContext(StrictModel):
    """Shared response context echoed by every learning analytics endpoint."""

    organization_id: UUID
    user_id: UUID | None = None
    date_range: AnalyticsDateRange
    min_sample: int


class LearningAnalyticsFunnel(StrictModel):
    """Stage counts across the manual paper validation workflow (Slices 77-83)."""

    alerts: int = 0
    drafts: int = 0
    candidates: int = 0
    run_plans: int = 0
    run_sessions: int = 0
    completed_sessions: int = 0
    cancelled_sessions: int = 0
    results: int = 0


class OutcomeDistributionItem(StrictModel):
    outcome: PaperValidationOutcome
    count: int = 0
    rate: float | None = None


class RateMetrics(StrictModel):
    """Outcome rates over sessions with a recorded result. None when no sample."""

    success_rate: float | None = None
    failure_rate: float | None = None
    invalidated_rate: float | None = None
    missed_entry_rate: float | None = None
    no_trade_rate: float | None = None
    inconclusive_rate: float | None = None
    behaved_as_expected_rate: float | None = None
    invalidation_hit_rate: float | None = None


class ObservationMetrics(StrictModel):
    total_observations: int = 0
    average_per_session: float | None = None
    by_kind: dict[str, int] = Field(default_factory=dict)


class LearningAnalyticsSummaryResponse(LearningAnalyticsContext):
    funnel: LearningAnalyticsFunnel
    total_sessions: int = 0
    completed_sessions: int = 0
    cancelled_sessions: int = 0
    results_count: int = 0
    outcome_distribution: list[OutcomeDistributionItem] = Field(default_factory=list)
    rates: RateMetrics
    observations: ObservationMetrics
    average_minutes_to_outcome: float | None = None
    lessons_count: int = 0


class SetupPerformanceGroup(StrictModel):
    dimension_value: str
    sample_size: int = 0
    insufficient_data: bool = True
    quality_score: float | None = None
    success_rate: float | None = None
    failure_rate: float | None = None
    invalidation_hit_rate: float | None = None
    behaved_as_expected_rate: float | None = None
    outcome_distribution: list[OutcomeDistributionItem] = Field(default_factory=list)


class SetupPerformanceResponse(LearningAnalyticsContext):
    dimension: SetupDimension
    groups: list[SetupPerformanceGroup] = Field(default_factory=list)


class DisciplineAnalyticsResponse(LearningAnalyticsContext):
    sample_size: int = 0
    insufficient_data: bool = True
    discipline_score: int | None = None
    discipline_grade: str = "insufficient_data"
    discipline_breakdown: dict[str, int] = Field(default_factory=dict)
    entry_breakdown: dict[str, int] = Field(default_factory=dict)
    issue_frequency: dict[str, float] = Field(default_factory=dict)
    positive_behaviors: list[str] = Field(default_factory=list)
    negative_behaviors: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)


class ConfidenceBucketStat(StrictModel):
    bucket: str
    lower: float
    upper: float
    sample_size: int = 0
    insufficient_data: bool = True
    success_rate: float | None = None


class ConfidenceOutcomeResponse(LearningAnalyticsContext):
    buckets: list[ConfidenceBucketStat] = Field(default_factory=list)
    correlation: str = "insufficient_data"


class BehaviorInsight(StrictModel):
    code: str
    message: str
    severity: str = "info"
    sample_size: int = 0
    confidence: str = "low"


class BehaviorInsightsResponse(LearningAnalyticsContext):
    insights: list[BehaviorInsight] = Field(default_factory=list)


class LessonTheme(StrictModel):
    theme: str
    count: int = 0
    example_excerpt: str | None = None


class LessonThemesResponse(LearningAnalyticsContext):
    lessons_count: int = 0
    themes: list[LessonTheme] = Field(default_factory=list)


class SetupRankingItem(StrictModel):
    setup_key: str
    rank: int
    quality_score: float
    sample_size: int


class SetupRankingResponse(LearningAnalyticsContext):
    dimension: SetupDimension
    note: str
    ranked: list[SetupRankingItem] = Field(default_factory=list)
