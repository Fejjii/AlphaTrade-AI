"""Research replay contracts carried by existing backtest authorities."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.derivatives import DerivativeObservation
from app.market_contracts.observation import PublicMarketObservation
from app.market_contracts.ohlcv import OhlcvBar
from app.market_contracts.order_flow import OrderFlowObservation
from app.schemas.backtest import BacktestAssumptions
from app.schemas.common import BacktestSplitLabel, StrictModel, TradeDirection
from app.schemas.risk import RiskCheckResult
from app.strategy_brain.sfp.contracts import SfpDetection, StructuralLevel

REPLAY_ENGINE = "strategy-replay-001/v1"
SFP_REPLAY_ADAPTER = "sfp-research-replay-001/v1"


class ReplayCandleEvidence(StrictModel):
    bar: OhlcvBar
    observation: PublicMarketObservation


class SfpReplayEvidence(StrictModel):
    """Frozen historical proofs. Receipt clocks are never inferred from candle times."""

    candles: list[ReplayCandleEvidence] = Field(default_factory=list)
    context_levels: list[StructuralLevel] = Field(default_factory=list)
    order_flow: list[OrderFlowObservation] = Field(default_factory=list)
    derivatives: list[DerivativeObservation] = Field(default_factory=list)


class ReplayWindows(StrictModel):
    training_start: AwareDatetime
    training_end: AwareDatetime
    evaluation_start: AwareDatetime
    evaluation_end: AwareDatetime
    as_of: AwareDatetime

    @model_validator(mode="after")
    def chronological(self) -> Self:
        if not (
            self.training_start
            < self.training_end
            <= self.evaluation_start
            < self.evaluation_end
            <= self.as_of
        ):
            raise ValueError(
                "Training and evaluation must be chronologically separated and closed."
            )
        return self


class StrategyReplayCreate(StrictModel):
    strategy_version_id: UUID
    dataset_id: UUID
    windows: ReplayWindows
    assumptions: BacktestAssumptions
    minimum_sample: int = Field(default=30, ge=1, le=10000)
    idempotency_key: str = Field(min_length=1, max_length=255)
    sfp_evidence: SfpReplayEvidence | None = None

    @model_validator(mode="after")
    def supported_assumptions(self) -> Self:
        if self.assumptions.start_date is not None or self.assumptions.end_date is not None:
            raise ValueError("Replay dates belong in explicit windows.")
        if (
            self.assumptions.runner_trail_pct != Decimal("1.5")
            or self.assumptions.sample_size != 500
        ):
            raise ValueError("Legacy runner and sample_size overrides are unsupported by replay.")
        if self.assumptions.split_config is not None:
            raise ValueError("Replay uses explicit training/evaluation windows, not split_config.")
        if self.assumptions.funding_assumption != "neutral":
            raise ValueError("Replay only supports the explicit constant funding rate assumption.")
        return self


class ReplayCandidate(StrictModel):
    setup_id: UUID
    detected_at: datetime
    split_label: BacktestSplitLabel
    direction: TradeDirection
    entry: Decimal | None
    stop: Decimal | None
    targets: list[Decimal]
    state: str
    decision_at: datetime | None = None
    evidence: dict[str, str] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    risk_decision: RiskCheckResult | None = None
    trade_sequence: int | None = None
    sfp_detection: SfpDetection | None = None
    research_evidence: dict[str, dict[str, Any]] = Field(default_factory=dict)
    stale_evidence: list[str] = Field(default_factory=list)
    candidate_creation_eligibility: str | None = None
    risk_applicability: str | None = None


class ReplaySample(StrictModel):
    split_label: BacktestSplitLabel
    candle_count: int
    candidate_count: int
    blocked_count: int
    trade_count: int
    status: Literal["insufficient_sample", "descriptive_only", "missing_data", "cancelled"]
    net_pnl: Decimal | None
    mean_r: Decimal | None = None
    setup_count: int = 0
    lifecycle_counts: dict[str, int] = Field(default_factory=dict)


class ReplayLevelConsideration(StrictModel):
    split_label: BacktestSplitLabel
    considered_at: AwareDatetime
    level: StructuralLevel
    direction_matches: bool
    significance_passes: bool
    evidence_fresh: bool


class ReplayEvidenceGap(StrictModel):
    split_label: BacktestSplitLabel
    decision_at: AwareDatetime
    availability: str
    reasons: list[str]


class ReplayEvidenceFrame(StrictModel):
    split_label: BacktestSplitLabel
    decision_at: AwareDatetime
    evidence: dict[str, dict[str, Any]]


class ReplayResearchBucket(StrictModel):
    split_label: BacktestSplitLabel
    symbol: str
    timeframe: str
    direction: TradeDirection
    level_type: str
    strategy_version_id: UUID
    quality_bucket: str
    regime: str
    setup_count: int
    confirmed_count: int


class ReplayReport(StrictModel):
    strategy_version_id: UUID
    strategy_content_hash: str
    parameter_hash: str
    input_hash: str
    candidates: list[ReplayCandidate] = Field(default_factory=list)
    samples: list[ReplaySample] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    improvement_claim: Literal[False] = False
    risk_scope: str = "Canonical RiskEngine over isolated simulated account; no live risk approval."
    mode: Literal["trade_simulation", "sfp_research"] = "trade_simulation"
    adapter_version: str | None = None
    evidence_hash: str | None = None
    structural_levels: list[ReplayLevelConsideration] = Field(default_factory=list)
    evidence_gaps: list[ReplayEvidenceGap] = Field(default_factory=list)
    evidence_frames: list[ReplayEvidenceFrame] = Field(default_factory=list)
    research_buckets: list[ReplayResearchBucket] = Field(default_factory=list)
    stale_evidence: list[str] = Field(default_factory=list)


class ReplayComparisonRequest(StrictModel):
    baseline_run_id: UUID
    proposed_run_id: UUID


class ReplayComparison(StrictModel):
    comparison_hash: str
    baseline_run_id: UUID
    proposed_run_id: UUID
    baseline_version_id: UUID
    proposed_version_id: UUID
    baseline_samples: list[ReplaySample]
    proposed_samples: list[ReplaySample]
    evaluation_net_pnl_delta: Decimal | None
    improvement_claim: Literal[False] = False
    limitations: list[str]
    baseline_research_buckets: list[ReplayResearchBucket] = Field(default_factory=list)
    proposed_research_buckets: list[ReplayResearchBucket] = Field(default_factory=list)
