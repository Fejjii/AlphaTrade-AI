"""Explicit first-slice conversation preview text. Tests only; not a compiler default."""

from __future__ import annotations

from app.schemas.strategy_pattern_spec import canonical_first_slice_authored_spec


def complete_first_slice_preview_text() -> str:
    """Every authored first-slice field stated explicitly. No compiler defaults."""

    spec = canonical_first_slice_authored_spec()
    trigger = spec.trigger_atr
    context = spec.context_atr
    htf, ltf = spec.sequence
    return "\n".join(
        [
            f"kind: {spec.kind}",
            f"name: {spec.name}",
            f"symbol: {spec.symbol}",
            f"trigger_timeframe: {spec.trigger_timeframe}",
            f"context_timeframe: {spec.context_timeframe}",
            f"direction: {spec.direction.value}",
            f"requires_manual_4h_resistance: {str(spec.requires_manual_4h_resistance).lower()}",
            f"requires_confirmed_swing: {str(spec.requires_confirmed_swing).lower()}",
            f"trigger_atr.feature_type: {trigger.feature_type}",
            f"trigger_atr.feature_version: {trigger.feature_version}",
            f"trigger_atr.period: {trigger.period}",
            f"context_atr.feature_type: {context.feature_type}",
            f"context_atr.feature_version: {context.feature_version}",
            f"context_atr.period: {context.period}",
            f"resistance_distance_atr_threshold: {spec.resistance_distance_atr_threshold}",
            f"sweep_threshold_atr: {spec.sweep_threshold_atr}",
            f"close_below_swing: {str(spec.close_below_swing).lower()}",
            f"bearish_candle_close_below_open: {str(spec.bearish_candle_close_below_open).lower()}",
            f"volume_lookback_bars: {spec.volume_lookback_bars}",
            f"volume_ratio_threshold: {spec.volume_ratio_threshold}",
            f"requires_cvd_divergence: {str(spec.requires_cvd_divergence).lower()}",
            f"aggressive_sell_imbalance_threshold: {spec.aggressive_sell_imbalance_threshold}",
            f"required_finality: {str(spec.required_finality).lower()}",
            f"required_freshness: {str(spec.required_freshness).lower()}",
            f"required_no_gap: {str(spec.required_no_gap).lower()}",
            f"invalidation.atr_multiple: {spec.invalidation.atr_multiple}",
            f"invalidation.tick_multiple: {spec.invalidation.tick_multiple}",
            f"expiry_final_bars: {spec.expiry_final_bars}",
            f"{htf.step_id}",
            f"{ltf.step_id}",
            f"htf_min_offset: {htf.min_offset}",
            f"htf_max_offset: {htf.max_offset}",
            f"ltf_min_offset: {ltf.min_offset}",
            f"ltf_max_offset: {ltf.max_offset}",
            f"overlap_policy: {spec.overlap_policy.value}",
            f"reset_semantics: {htf.reset_semantics.value}",
            f"invalidation_semantics: {htf.invalidation_semantics.value}",
            f"finality_requirement: {htf.finality_requirement.value}",
            "liquidity sweep cvd bearish imbalance",
        ]
    )


INCOMPLETE_FIRST_SLICE_TEXT = (
    "liquidity sweep cvd bearish imbalance with 15m and 4h but no thresholds"
)
UNSUPPORTED_STRATEGY_TEXT = (
    "Buy the dip forever with a secret sauce and guaranteed returns on any symbol"
)
