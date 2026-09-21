"""First-slice compatibility adapter for compiled strategy evaluation.

The first-slice predicate engine is not a second policy. It only interprets
the allowlisted compiled first-slice authored spec. Unsupported kinds, incomplete
specs, and compiler failures fail closed. There is no AST VM and no LLM.
"""

from __future__ import annotations

from typing import Literal

from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.schemas.strategy_pattern_spec import (
    FIRST_SLICE_ATR_PERIOD,
    FIRST_SLICE_KIND,
    FirstSliceAuthoredPatternSpec,
)
from app.services.setup_ast_compiler import compile_from_spec
from app.signal_fusion.errors import StrategyEvaluationPolicyError
from app.signal_fusion.first_slice_types import (
    FIRST_SLICE_EXPIRY_BARS,
    FIRST_SLICE_INVALIDATION_ATR,
    FIRST_SLICE_INVALIDATION_TICKS,
    FIRST_SLICE_SELL_IMBALANCE,
    FIRST_SLICE_SWEEP_ATR,
    FIRST_SLICE_SWING_ATR_DISTANCE,
    FIRST_SLICE_VOLUME_LOOKBACK,
    FIRST_SLICE_VOLUME_RATIO,
)

FIRST_SLICE_ADAPTER_ID: Literal["first_slice_compatibility/v1"] = "first_slice_compatibility/v1"


class FirstSliceEvaluationParams(CanonicalModel):
    """Thresholds the first-slice predicate engine may legally consume."""

    adapter_id: Literal["first_slice_compatibility/v1"] = FIRST_SLICE_ADAPTER_ID
    swing_atr_distance: CanonicalDecimal
    sweep_atr: CanonicalDecimal
    volume_lookback: int
    volume_ratio: CanonicalDecimal
    sell_imbalance: CanonicalDecimal
    invalidation_atr: CanonicalDecimal
    invalidation_ticks: CanonicalDecimal
    expiry_bars: int
    atr_period: int


def default_first_slice_evaluation_params() -> FirstSliceEvaluationParams:
    """Adapter defaults identical to the canonical first-slice authored spec."""

    return FirstSliceEvaluationParams(
        swing_atr_distance=FIRST_SLICE_SWING_ATR_DISTANCE,
        sweep_atr=FIRST_SLICE_SWEEP_ATR,
        volume_lookback=FIRST_SLICE_VOLUME_LOOKBACK,
        volume_ratio=FIRST_SLICE_VOLUME_RATIO,
        sell_imbalance=FIRST_SLICE_SELL_IMBALANCE,
        invalidation_atr=FIRST_SLICE_INVALIDATION_ATR,
        invalidation_ticks=FIRST_SLICE_INVALIDATION_TICKS,
        expiry_bars=FIRST_SLICE_EXPIRY_BARS,
        atr_period=FIRST_SLICE_ATR_PERIOD,
    )


def bind_first_slice_compatibility_adapter(
    spec: FirstSliceAuthoredPatternSpec,
) -> FirstSliceEvaluationParams:
    """Map a compiled-capable first-slice spec onto the predicate adapter.

    Fail closed when the spec is not the allowlisted first-slice pattern or the
    compiler rejects it. Thresholds come from the spec, not a silent second table.
    """

    if spec.kind != FIRST_SLICE_KIND:
        raise StrategyEvaluationPolicyError(
            "Compiled pattern kind is not supported by the first-slice adapter.",
            reason_code="unsupported_strategy_rule",
        )
    compiled = compile_from_spec(spec)
    if compiled.document is None:
        detail = compiled.failures[0].code if compiled.failures else "unsupported_strategy_rule"
        raise StrategyEvaluationPolicyError(
            "Compiled strategy rules are unsupported or incomplete.",
            reason_code="unsupported_strategy_rule",
            details={"compiler_code": detail},
        )
    return FirstSliceEvaluationParams(
        swing_atr_distance=spec.resistance_distance_atr_threshold,
        sweep_atr=spec.sweep_threshold_atr,
        volume_lookback=spec.volume_lookback_bars,
        volume_ratio=spec.volume_ratio_threshold,
        sell_imbalance=spec.aggressive_sell_imbalance_threshold,
        invalidation_atr=spec.invalidation.atr_multiple,
        invalidation_ticks=spec.invalidation.tick_multiple,
        expiry_bars=spec.expiry_final_bars,
        atr_period=spec.trigger_atr.period,
    )


def resolve_evaluation_params(
    evaluation_params: FirstSliceEvaluationParams | None,
) -> FirstSliceEvaluationParams:
    """Adapter-level defaulting for direct ``evaluate_setup`` tests only."""

    return (
        default_first_slice_evaluation_params() if evaluation_params is None else evaluation_params
    )


__all__ = [
    "FIRST_SLICE_ADAPTER_ID",
    "FirstSliceEvaluationParams",
    "bind_first_slice_compatibility_adapter",
    "default_first_slice_evaluation_params",
    "resolve_evaluation_params",
]
