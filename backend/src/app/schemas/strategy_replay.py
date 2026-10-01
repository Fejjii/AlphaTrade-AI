"""Research replay contracts carried by existing backtest authorities."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.backtest import BacktestAssumptions
from app.schemas.common import BacktestSplitLabel, StrictModel, TradeDirection
from app.schemas.risk import RiskCheckResult

REPLAY_ENGINE = "strategy-replay-001/v1"


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


class ReplaySample(StrictModel):
    split_label: BacktestSplitLabel
    candle_count: int
    candidate_count: int
    blocked_count: int
    trade_count: int
    status: Literal["insufficient_sample", "descriptive_only", "missing_data", "cancelled"]
    net_pnl: Decimal
    mean_r: Decimal | None = None


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
