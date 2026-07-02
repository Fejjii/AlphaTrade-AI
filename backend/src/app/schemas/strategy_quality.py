"""Strategy quality and detector performance API schemas (Slice 89 — read-only).

Response models for the strategy quality layer that scores setup detectors from
existing manual paper validation outcomes. These schemas describe derived,
read-only study guidance for human review. They never represent orders,
proposals, approvals, executions, rule changes, or any executable intent, and
they never enable automation or recommend live trades.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.analytics import AnalyticsDateRange
from app.schemas.common import StrictModel
from app.schemas.learning_analytics import ConfidenceBucketStat, OutcomeDistributionItem
from app.schemas.validation_priority import FactorDirection


class DetectorTrustTier(StrEnum):
    """How much validation evidence backs a detector's quality read."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DetectorVerdict(StrEnum):
    """Study guidance verdict for a detector. Never an execution instruction."""

    TRUSTED = "trusted"
    WATCH = "watch"
    IMPROVE = "improve"
    AVOID_FOR_NOW = "avoid_for_now"
    NEEDS_MORE_VALIDATION = "needs_more_validation"


class CalibrationLabel(StrEnum):
    """How a detector's confidence compares to its actual success rate."""

    WELL_CALIBRATED = "well_calibrated"
    OVERCONFIDENT = "overconfident"
    UNDERCONFIDENT = "underconfident"
    INSUFFICIENT_DATA = "insufficient_data"


class DetectorFactor(StrictModel):
    """A single explainable contributor to a detector's quality score."""

    code: str
    label: str
    direction: FactorDirection
    contribution: float
    detail: str


class DetectorWarning(StrictModel):
    """A read-only caution label for a detector."""

    code: str
    message: str
    severity: str = "info"


class ConfidenceCalibration(StrictModel):
    """Detector confidence versus actual paper validation outcomes."""

    mean_confidence: float | None = None
    mean_success_rate: float | None = None
    correlation: str = "insufficient_data"
    calibration_label: CalibrationLabel = CalibrationLabel.INSUFFICIENT_DATA
    buckets: list[ConfidenceBucketStat] = Field(default_factory=list)


class DetectorTimeframeStat(StrictModel):
    """Per-timeframe invalidation and success rates for one detector."""

    condition: str
    timeframe: str
    sample_size: int = 0
    insufficient_data: bool = True
    invalidation_rate: float | None = None
    success_rate: float | None = None


class DetectorQualityReport(StrictModel):
    """Read-only quality report for a single setup detector (grouped by condition)."""

    condition: str
    detector_version: str | None = None
    sample_size: int = 0
    insufficient_data: bool = True
    trust_tier: DetectorTrustTier = DetectorTrustTier.NONE
    verdict: DetectorVerdict = DetectorVerdict.NEEDS_MORE_VALIDATION
    quality_score: float | None = None
    raw_quality_score: float | None = None
    success_rate: float | None = None
    failure_rate: float | None = None
    invalidated_rate: float | None = None
    missed_entry_rate: float | None = None
    no_trade_rate: float | None = None
    inconclusive_rate: float | None = None
    invalidation_hit_rate: float | None = None
    behaved_as_expected_rate: float | None = None
    should_have_avoided_rate: float | None = None
    should_have_waited_rate: float | None = None
    outcome_distribution: list[OutcomeDistributionItem] = Field(default_factory=list)
    discipline_breakdown: dict[str, int] = Field(default_factory=dict)
    entry_breakdown: dict[str, int] = Field(default_factory=dict)
    confidence_calibration: ConfidenceCalibration = Field(default_factory=ConfidenceCalibration)
    warnings: list[DetectorWarning] = Field(default_factory=list)
    factors: list[DetectorFactor] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class StrategyQualityContext(StrictModel):
    """Shared response context echoed by every strategy quality endpoint."""

    organization_id: UUID
    user_id: UUID | None = None
    date_range: AnalyticsDateRange
    min_sample: int
    note: str


class StrategyQualityDetectorsResponse(StrategyQualityContext):
    condition_filter: str | None = None
    timeframe_filter: str | None = None
    detectors: list[DetectorQualityReport] = Field(default_factory=list)


class TrustTierCount(StrictModel):
    trust_tier: DetectorTrustTier
    count: int = 0


class VerdictCount(StrictModel):
    verdict: DetectorVerdict
    count: int = 0


class DetectorRankItem(StrictModel):
    condition: str
    rank: int
    quality_score: float
    sample_size: int
    trust_tier: DetectorTrustTier
    verdict: DetectorVerdict


class StrategyQualitySummaryResponse(StrategyQualityContext):
    total_detectors: int = 0
    detectors_with_data: int = 0
    total_results: int = 0
    by_trust_tier: list[TrustTierCount] = Field(default_factory=list)
    by_verdict: list[VerdictCount] = Field(default_factory=list)
    ranked: list[DetectorRankItem] = Field(default_factory=list)
    warnings: list[DetectorWarning] = Field(default_factory=list)


class DetectorExplainResponse(StrategyQualityContext):
    report: DetectorQualityReport
    timeframes: list[DetectorTimeframeStat] = Field(default_factory=list)
