"""Versioned operational continuation proxy, not Elliott wave counting."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.schemas.common import StrictModel, Timeframe, TradeDirection

NESTED_KIND = "operational_nested_continuation/v1"


class EvidenceAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    STALE = "STALE"
    UNSUPPORTED = "UNSUPPORTED"
    INCOMPLETE = "INCOMPLETE"


class BrainSetupState(StrEnum):
    NO_SETUP = "NO_SETUP"
    WATCH = "WATCH"
    FORMING = "FORMING"
    CONFIRMED = "CONFIRMED"
    TRADE_CANDIDATE = "TRADE_CANDIDATE"
    BLOCKED_BY_RISK = "BLOCKED_BY_RISK"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class NestedParameters(StrictModel):
    """One provisional research configuration; no profitability claim."""

    version: Literal["nested-research/v1"] = "nested-research/v1"
    provisional: Literal[True] = True
    pivot_sensitivity: int = Field(default=2, ge=1, le=5)
    minimum_impulse: Decimal = Field(default=Decimal("0.005"), gt=0, le=1)
    retracement_depth: Decimal = Field(default=Decimal("0.20"), gt=0, lt=1)
    maximum_retracement: Decimal = Field(default=Decimal("0.75"), gt=0, lt=1)
    retracement_duration: int = Field(default=12, ge=2, le=24)
    structural_invalidation: Decimal = Field(default=Decimal("0"), ge=0, lt=1)
    confirmation_window: int = Field(default=24, ge=3, le=48)
    relative_volume_threshold: Decimal = Field(default=Decimal("0"), ge=0, le=10)
    entry_trigger: Literal["closed_break_of_impulse_extreme"] = "closed_break_of_impulse_extreme"
    max_sequence_bars: int = Field(default=96, ge=24, le=128)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.retracement_depth >= self.maximum_retracement:
            raise ValueError("retracement_depth must be below maximum_retracement")
        return self


class NestedContinuationSpec(StrictModel):
    spec_version: Literal["strategy-pattern-spec/v1"] = "strategy-pattern-spec/v1"
    kind: Literal["operational_nested_continuation/v1"] = NESTED_KIND
    name: str = "Nested Continuation operational proxy"
    symbol: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9]+USDT$")
    trigger_timeframe: Timeframe = Timeframe.M15
    direction: TradeDirection = TradeDirection.LONG
    parameters: NestedParameters = Field(default_factory=NestedParameters)


class StrategyBrainDefinition(StrictModel):
    """Semantic metadata embedded in the existing immutable strategy card/version."""

    family: Literal["nested_continuation", "sfp", "d_line", "higher_timeframe_swing"]
    market_regime: str = "directional continuation"
    required_inputs: list[str] = Field(
        default_factory=lambda: ["closed_ohlcv", "volume", "identity", "freshness"]
    )
    optional_inputs: list[str] = Field(
        default_factory=lambda: ["moving_average", "relative_volume", "higher_timeframe"]
    )
    structure_conditions: list[str] = Field(default_factory=list)
    setup_conditions: list[str] = Field(default_factory=list)
    execution_constraints: list[str] = Field(
        default_factory=lambda: ["paper_only", "existing_risk_and_execution_gates"]
    )
    confluence_inputs: list[str] = Field(default_factory=list)
    alert_rules: list[str] = Field(default_factory=lambda: ["confirmed_paper_informational_only"])
    statistics_references: list[str] = Field(default_factory=list)
    learning_notes: list[str] = Field(
        default_factory=lambda: ["Insufficient history; provisional research defaults."]
    )
    evidence_references: list[str] = Field(default_factory=list)
    risk_limits: Literal["existing_canonical_risk_limits"] = "existing_canonical_risk_limits"
    created_from: str = "explicit user strategy proposal"
