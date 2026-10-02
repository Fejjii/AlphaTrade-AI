"""Explainable advisory contracts. Quality points are never winning probabilities."""

from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.market_contracts.enums import FreshnessState
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.schemas.common import TradeDirection
from app.schemas.nested_continuation import EvidenceAvailability
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.eligibility import ActionEligibility
from app.signal_fusion.types import Sha256Hex


class ComponentName(StrEnum):
    PATTERN = "pattern_structure"
    HTF = "higher_timeframe_regime"
    VOLUME = "volume"
    ORDER_FLOW = "five_minute_order_flow"
    CVD = "cvd"
    OI = "open_interest"
    FUNDING = "funding"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"
    BTC = "btc_context"
    EXPOSURE = "existing_exposure"
    DAILY_RISK = "daily_risk_state"
    EXPECTANCY = "measured_strategy_expectancy"


class AnalysisState(StrEnum):
    READY = "ready"
    REQUIRED_DATA_UNAVAILABLE = "required_data_unavailable"
    HARD_REQUIREMENTS_FAILED = "hard_requirements_failed"


class EvidenceSource(CanonicalModel):
    contract: str
    record_id: str | None = None
    content_hash: Sha256Hex | None = None


class ComponentFact(CanonicalModel):
    key: str
    value: CanonicalDecimal | str | bool | int | None


class ConfluenceComponent(CanonicalModel):
    key: str
    availability: EvidenceAvailability
    value: CanonicalDecimal | str | bool | None = None
    unit: str
    normalized_contribution: CanonicalDecimal | None = Field(default=None, ge=0, le=1)
    weight: CanonicalDecimal = Field(default=Decimal(0), ge=0)
    source: tuple[EvidenceSource, ...] = ()
    timestamp: AwareDatetime | None = None
    freshness: FreshnessState = FreshnessState.UNKNOWN
    age_seconds: CanonicalDecimal | None = None
    reason: str
    passed: bool | None = None
    facts: tuple[ComponentFact, ...] = ()


class Coverage(CanonicalModel):
    available: int = Field(ge=0)
    total: int = Field(ge=0)
    fraction: CanonicalDecimal = Field(ge=0, le=1)
    missing_keys: tuple[str, ...]


class AssessmentCoverage(CanonicalModel):
    required: Coverage
    optional: Coverage
    context: Coverage
    scored_weight_available: CanonicalDecimal
    scored_weight_total: CanonicalDecimal
    scored_weight_fraction: CanonicalDecimal = Field(ge=0, le=1)


class HistoricalExpectancy(CanonicalModel):
    component: ConfluenceComponent
    sample_count: int = Field(ge=0)
    min_sample_size: int = Field(ge=1)
    insufficient_history: bool
    truncated: bool
    cohort_filters: tuple[ComponentFact, ...] = ()
    outcome_basis: Literal["closed_canonical_journal_trades"] = "closed_canonical_journal_trades"


class RiskEligibilityContext(CanonicalModel):
    availability: EvidenceAvailability
    canonical_record: ActionEligibility | None = None
    reason: str


class DataQuality(CanonicalModel):
    unavailable_keys: tuple[str, ...]
    stale_keys: tuple[str, ...]
    insufficient_score_coverage: bool


class ConfluenceAssessment(CanonicalModel):
    contract_version: Literal["confluence-intelligence/v2"] = "confluence-intelligence/v2"
    analysis_only: Literal[True] = True
    score_semantics: Literal["quality_points_not_win_probability"] = (
        "quality_points_not_win_probability"
    )
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    # Reuse the exact setup record. No confluence-dependent setup/candidate identity.
    setup: SetupAssessment
    evidence_identity: EvidenceMarketIdentity
    direction: TradeDirection
    detector_kind: str
    policy_version: str
    policy_content_hash: Sha256Hex
    state: AnalysisState
    hard_requirements: tuple[ConfluenceComponent, ...]
    optional_confluence: tuple[ConfluenceComponent, ...]
    quality_components: tuple[ConfluenceComponent, ...]
    context_components: tuple[ConfluenceComponent, ...]
    quality_score: CanonicalDecimal | None = Field(default=None, ge=0, le=100)
    quality_band: Literal["unavailable", "below_reference", "at_or_above_reference"]
    coverage: AssessmentCoverage
    historical_expectancy: HistoricalExpectancy
    data_quality: DataQuality
    risk_eligibility: RiskEligibilityContext
    assessed_at: AwareDatetime
    content_hash: Sha256Hex
