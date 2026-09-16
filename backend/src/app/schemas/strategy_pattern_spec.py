"""Authored StrategyPatternSpec embedded in one immutable UserStrategyVersion.

This is the exact deterministic input the AST compiler may use. StructuredRules
and strategy names are not proof of executable parity. Missing fields fail closed;
the compiler never restores canonical default thresholds.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.schemas.common import StrictModel, TradeDirection
from app.schemas.setup_ast import (
    WILDER_ATR_FEATURE_TYPE,
    WILDER_ATR_FEATURE_VERSION,
    FeatureRole,
    FinalityRequirement,
    OverlapPolicy,
)

PATTERN_SPEC_VERSION = "strategy-pattern-spec/v1"
FIRST_SLICE_KIND = "bearish_liquidity_sweep_cvd_sell_imbalance_at_4h_resistance/v1"
FIRST_SLICE_NAME = (
    "Bearish Liquidity Sweep with CVD Divergence and Aggressive Sell Imbalance at 4h Resistance"
)
FIRST_SLICE_SYMBOL = "BTCUSDT"
FIRST_SLICE_TRIGGER_TF = "15m"
FIRST_SLICE_CONTEXT_TF = "4h"
FIRST_SLICE_DIRECTION = TradeDirection.SHORT
FIRST_SLICE_ATR_PERIOD = 14
FIRST_SLICE_HTF_STEP = "htf_resistance_context"
FIRST_SLICE_LTF_STEP = "ltf_liquidity_sweep"
FIRST_SLICE_REQUIRED_SEQUENCE = (FIRST_SLICE_HTF_STEP, FIRST_SLICE_LTF_STEP)


class PatternResetSemantics(StrEnum):
    NONE = "none"
    RETURN_TO_STEP_ZERO = "return_to_step_zero"


class PatternInvalidationSemantics(StrEnum):
    NONE = "none"
    TERMINATE_OCCURRENCE = "terminate_occurrence"


class AuthoredFeatureSpec(StrictModel):
    feature_type: str = Field(min_length=1, max_length=40)
    feature_version: str = Field(min_length=1, max_length=40)
    role: FeatureRole
    period: int = Field(ge=1, le=200)
    timeframe: str = Field(min_length=1, max_length=8)


class AuthoredInvalidationSpec(StrictModel):
    atr_multiple: Decimal
    tick_multiple: Decimal


class AuthoredSequenceStep(StrictModel):
    step_id: str = Field(min_length=1, max_length=80)
    min_offset: int = Field(ge=0)
    max_offset: int = Field(ge=0)
    finality_requirement: FinalityRequirement
    overlap_policy: OverlapPolicy
    reset_semantics: PatternResetSemantics
    invalidation_semantics: PatternInvalidationSemantics

    @model_validator(mode="after")
    def _offset_order(self) -> Self:
        if self.max_offset < self.min_offset:
            raise ValueError("max_offset must be >= min_offset")
        return self


class FirstSliceAuthoredPatternSpec(StrictModel):
    """Exact first-slice authored Pattern. Every executable threshold is explicit."""

    spec_version: Literal["strategy-pattern-spec/v1"]
    kind: Literal["bearish_liquidity_sweep_cvd_sell_imbalance_at_4h_resistance/v1"]
    name: str = Field(min_length=1, max_length=200)
    symbol: str = Field(min_length=1, max_length=30)
    trigger_timeframe: str = Field(min_length=1, max_length=8)
    context_timeframe: str = Field(min_length=1, max_length=8)
    direction: TradeDirection
    requires_manual_4h_resistance: bool
    requires_confirmed_swing: bool
    trigger_atr: AuthoredFeatureSpec
    context_atr: AuthoredFeatureSpec
    resistance_distance_atr_threshold: Decimal
    sweep_threshold_atr: Decimal
    close_below_swing: bool
    bearish_candle_close_below_open: bool
    volume_lookback_bars: int = Field(ge=1, le=500)
    volume_ratio_threshold: Decimal
    requires_cvd_divergence: bool
    aggressive_sell_imbalance_threshold: Decimal
    required_finality: bool
    required_freshness: bool
    required_no_gap: bool
    invalidation: AuthoredInvalidationSpec
    expiry_final_bars: int = Field(ge=1, le=500)
    sequence: list[AuthoredSequenceStep] = Field(min_length=1)
    overlap_policy: OverlapPolicy


def canonical_first_slice_authored_spec() -> FirstSliceAuthoredPatternSpec:
    """Canonical first-slice authored values. Tests and golden fixtures only."""

    return FirstSliceAuthoredPatternSpec(
        spec_version=PATTERN_SPEC_VERSION,
        kind=FIRST_SLICE_KIND,
        name=FIRST_SLICE_NAME,
        symbol=FIRST_SLICE_SYMBOL,
        trigger_timeframe=FIRST_SLICE_TRIGGER_TF,
        context_timeframe=FIRST_SLICE_CONTEXT_TF,
        direction=FIRST_SLICE_DIRECTION,
        requires_manual_4h_resistance=True,
        requires_confirmed_swing=True,
        trigger_atr=AuthoredFeatureSpec(
            feature_type=WILDER_ATR_FEATURE_TYPE,
            feature_version=WILDER_ATR_FEATURE_VERSION,
            role=FeatureRole.TRIGGER,
            period=FIRST_SLICE_ATR_PERIOD,
            timeframe=FIRST_SLICE_TRIGGER_TF,
        ),
        context_atr=AuthoredFeatureSpec(
            feature_type=WILDER_ATR_FEATURE_TYPE,
            feature_version=WILDER_ATR_FEATURE_VERSION,
            role=FeatureRole.CONTEXT,
            period=FIRST_SLICE_ATR_PERIOD,
            timeframe=FIRST_SLICE_CONTEXT_TF,
        ),
        resistance_distance_atr_threshold=Decimal("0.50"),
        sweep_threshold_atr=Decimal("0.25"),
        close_below_swing=True,
        bearish_candle_close_below_open=True,
        volume_lookback_bars=20,
        volume_ratio_threshold=Decimal("1.50"),
        requires_cvd_divergence=True,
        aggressive_sell_imbalance_threshold=Decimal("-0.10"),
        required_finality=True,
        required_freshness=True,
        required_no_gap=True,
        invalidation=AuthoredInvalidationSpec(
            atr_multiple=Decimal("0.10"),
            tick_multiple=Decimal("2"),
        ),
        expiry_final_bars=2,
        sequence=[
            AuthoredSequenceStep(
                step_id=FIRST_SLICE_HTF_STEP,
                min_offset=0,
                max_offset=0,
                finality_requirement=FinalityRequirement.FINAL_ONLY,
                overlap_policy=OverlapPolicy.DISALLOW,
                reset_semantics=PatternResetSemantics.NONE,
                invalidation_semantics=PatternInvalidationSemantics.NONE,
            ),
            AuthoredSequenceStep(
                step_id=FIRST_SLICE_LTF_STEP,
                min_offset=0,
                max_offset=2,
                finality_requirement=FinalityRequirement.FINAL_ONLY,
                overlap_policy=OverlapPolicy.DISALLOW,
                reset_semantics=PatternResetSemantics.NONE,
                invalidation_semantics=PatternInvalidationSemantics.NONE,
            ),
        ],
        overlap_policy=OverlapPolicy.DISALLOW,
    )
