"""Causal deterministic Nested Continuation. Only already closed candles are used.

Pivots become usable at i + sensitivity, never at their historical pivot time.
A sequence ends on structural failure, expiry or bounded episode age. Each
continuation leg has its own immutable setup ID; higher highs alone do not count.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid5

from pydantic import Field

from app.market_contracts.enums import Finality
from app.market_contracts.identity import interval_timedelta
from app.market_contracts.ohlcv import OhlcvBar
from app.schemas.common import StrictModel, TradeDirection
from app.schemas.nested_continuation import (
    BrainSetupState,
    EvidenceAvailability,
    NestedContinuationSpec,
)
from app.services.canonical_serialization import canonical_sha256

NAMESPACE = UUID("1ba10001-0000-4000-8000-000000000001")


class NestedDetection(StrictModel):
    setup_id: UUID
    sequence_id: UUID
    state: BrainSetupState
    stage: str
    completed_continuations: int
    direction: TradeDirection
    event_index: int
    anchor_index: int
    impulse_index: int
    pullback_index: int | None
    confirmed_index: int | None = None
    detected_at: datetime
    expires_at: datetime
    entry: Decimal | None = None
    stop: Decimal | None = None
    targets: list[Decimal] = Field(default_factory=list)
    extension: Decimal = Decimal("0")
    quality_components: dict[str, str] = Field(default_factory=dict)
    reason_codes: list[str]
    evidence: dict[str, EvidenceAvailability]
    history_expectancy: str = "insufficient_history"
    invalidation_state: str = "intact"


def detect_nested(
    bars: tuple[OhlcvBar, ...],
    spec: NestedContinuationSpec,
    *,
    evaluated_at: datetime,
) -> tuple[NestedDetection, ...]:
    """Return chronological lifecycle events; replay is independent of wall-clock time."""
    if not bars:
        return ()
    delta = interval_timedelta(spec.trigger_timeframe)
    for i, bar in enumerate(bars):
        if (
            bar.finality is not Finality.FINAL
            or not bar.provider_complete
            or bar.interval_end > evaluated_at
            or bar.timeframe != spec.trigger_timeframe
            or bar.instrument.provider_symbol != spec.symbol
            or bar.instrument != bars[0].instrument
            or (i and bar.interval_start != bars[i - 1].interval_end)
        ):
            return ()
    p = spec.parameters
    sign = Decimal(1) if spec.direction is TradeDirection.LONG else Decimal(-1)
    # Coordinate mirror: increasing transformed prices always mean continuation.
    highs = [bar.high if sign == 1 else -bar.low for bar in bars]
    lows = [bar.low if sign == 1 else -bar.high for bar in bars]
    closes = [bar.close * sign for bar in bars]
    anchor: int | None = None
    impulse: int | None = None
    pullback: int | None = None
    sequence: UUID | None = None
    sequence_start = 0
    reset_at = -1
    count = 0
    confirmed: int | None = None
    results: list[NestedDetection] = []
    width = p.pivot_sensitivity
    for i, bar in enumerate(bars):
        pivot = i - width
        pivot_low = pivot >= width and all(
            lows[pivot] < lows[j] for j in range(pivot - width, i + 1) if j != pivot
        )
        pivot_high = pivot >= width and all(
            highs[pivot] > highs[j] for j in range(pivot - width, i + 1) if j != pivot
        )
        if anchor is None:
            if pivot_low and pivot >= reset_at:
                anchor = pivot
                sequence_start = pivot
                sequence = uuid5(
                    NAMESPACE,
                    f"{bars[0].instrument.instrument_id}:{spec.direction}:{spec.trigger_timeframe}:{bars[pivot].source_event_id}",
                )
                count = 0
            continue
        if impulse is None:
            if (
                pivot_high
                and pivot > anchor
                and (highs[pivot] - lows[anchor]) / abs(lows[anchor]) >= p.minimum_impulse
            ):
                impulse = pivot
                pullback = None
                confirmed = None
            else:
                structural_failure = lows[i] <= lows[anchor]
                expired = i - sequence_start >= p.max_sequence_bars or (
                    results
                    and results[-1].state is BrainSetupState.CONFIRMED
                    and bar.interval_end >= results[-1].expires_at
                )
                if structural_failure or expired:
                    if results and results[-1].state is BrainSetupState.CONFIRMED:
                        results.append(
                            results[-1].model_copy(
                                update={
                                    "state": BrainSetupState.INVALIDATED
                                    if structural_failure
                                    else BrainSetupState.EXPIRED,
                                    "event_index": i,
                                    "detected_at": bar.interval_end,
                                    "invalidation_state": "failed"
                                    if structural_failure
                                    else "intact",
                                    "reason_codes": [
                                        "structural_failure"
                                        if structural_failure
                                        else "formation_expired_new_episode_required"
                                    ],
                                }
                            )
                        )
                    anchor = None
                    reset_at = i
                continue
        assert impulse is not None and sequence is not None
        extreme = highs[impulse]
        span = extreme - lows[anchor]
        if span <= 0:
            anchor = impulse = None
            reset_at = i
            continue
        candidates = list(range(impulse + 1, i + 1))
        if not candidates:
            continue
        pullback = min(candidates, key=lambda j: lows[j])
        depth = (extreme - lows[pullback]) / span
        episode = uuid5(sequence, bars[impulse].source_event_id)
        expiry = bars[impulse].interval_end + delta * p.confirmation_window
        state = BrainSetupState.WATCH
        reasons = ["awaiting_controlled_pullback"]
        stop = lows[pullback] * sign
        if (
            lows[i] <= lows[anchor] - span * p.structural_invalidation
            or depth > p.maximum_retracement
        ):
            state, reasons = BrainSetupState.INVALIDATED, ["structural_failure"]
        elif i - impulse >= p.confirmation_window or i - sequence_start >= p.max_sequence_bars:
            state, reasons = BrainSetupState.EXPIRED, ["formation_expired_new_episode_required"]
        elif depth >= p.retracement_depth:
            if pullback - impulse > p.retracement_duration:
                state, reasons = BrainSetupState.EXPIRED, ["pullback_duration_exceeded"]
            else:
                state, reasons = BrainSetupState.FORMING, ["awaiting_closed_structural_break"]
                # The pullback pivot must already be confirmed at this event time.
                known_low = (
                    pullback >= width
                    and pullback + width <= i
                    and all(
                        lows[pullback] < lows[j]
                        for j in range(pullback - width, pullback + width + 1)
                        if j != pullback
                    )
                )
                prior_volume = (
                    sum(b.base_volume for b in bars[max(0, i - 20) : i]) / Decimal(min(i, 20))
                    if i
                    else Decimal(0)
                )
                volume_ratio = bar.base_volume / prior_volume if prior_volume else Decimal(0)
                if (
                    known_low
                    and closes[i] > extreme
                    and bar.base_volume > 0
                    and prior_volume > 0
                    and volume_ratio >= p.relative_volume_threshold
                ):
                    state, reasons = (
                        BrainSetupState.CONFIRMED,
                        ["closed_structural_break", "controlled_pullback_confirmed"],
                    )
                    confirmed = i
                    count += 1
                elif not known_low:
                    reasons.append("pullback_pivot_not_yet_confirmed")
                elif closes[i] > extreme:
                    reasons.append("required_volume_or_relative_threshold_not_met")
        stage_count = count if state is BrainSetupState.CONFIRMED else count + 1
        stage = f"N{stage_count}" if stage_count < 4 else "N4_PLUS"
        entry = closes[i] * sign if confirmed == i else extreme * sign
        distance = abs(entry - stop)
        # A measured impulse is a structural concept, not an imposed 3R/4R target.
        target = (extreme + span) * sign
        targets = [target] if (target - entry) * sign > 0 else []
        ranges = [b.high - b.low for b in bars[max(0, i - 20) : i]]
        baseline = sum(ranges) / len(ranges) if ranges else Decimal(0)
        expansion = (bar.high - bar.low) / baseline if baseline else Decimal(0)
        prior_volume = (
            sum(b.base_volume for b in bars[max(0, i - 20) : i]) / Decimal(min(i, 20))
            if i
            else Decimal(0)
        )
        volume_expansion = bar.base_volume / prior_volume if prior_volume else Decimal(0)
        results.append(
            NestedDetection(
                setup_id=episode,
                sequence_id=sequence,
                state=state,
                stage=stage,
                completed_continuations=count,
                direction=spec.direction,
                event_index=i,
                anchor_index=anchor,
                impulse_index=impulse,
                pullback_index=pullback,
                confirmed_index=confirmed,
                detected_at=bar.interval_end,
                expires_at=expiry,
                entry=entry,
                stop=stop,
                targets=targets,
                extension=(closes[i] - extreme) / span,
                quality_components={
                    "relative_candle_expansion": str(expansion),
                    "relative_volume_expansion": str(volume_expansion),
                    "distance_from_structure": str(abs(closes[i] - extreme)),
                    "sequence_maturity": str(count),
                    "vertical_acceleration": str(expansion),
                    "acceleration_risk": "research_context_only"
                    if expansion >= 2
                    else "not_flagged",
                    "initial_risk_basis": str(distance),
                },
                reason_codes=reasons,
                invalidation_state="failed" if state is BrainSetupState.INVALIDATED else "intact",
                evidence={
                    "closed_ohlcv": EvidenceAvailability.AVAILABLE,
                    "volume": EvidenceAvailability.AVAILABLE,
                    "moving_average": EvidenceAvailability.MISSING,
                    "higher_timeframe": EvidenceAvailability.MISSING,
                    "cvd": EvidenceAvailability.UNSUPPORTED,
                    "order_flow": EvidenceAvailability.UNSUPPORTED,
                    "open_interest": EvidenceAvailability.UNSUPPORTED,
                    "funding": EvidenceAvailability.UNSUPPORTED,
                },
            )
        )
        if state is BrainSetupState.CONFIRMED:
            anchor = pullback
            impulse = None
        elif state in {BrainSetupState.INVALIDATED, BrainSetupState.EXPIRED}:
            anchor = impulse = None
            reset_at = i
    return tuple(results)


def detection_hash(detection: NestedDetection, bars: tuple[OhlcvBar, ...]) -> str:
    payload = detection.model_dump(mode="json")
    for field in (
        "event_index",
        "anchor_index",
        "impulse_index",
        "pullback_index",
        "confirmed_index",
    ):
        index = payload.pop(field)
        payload[field.removesuffix("_index") + "_bar"] = (
            bars[index].source_event_id if index is not None else None
        )
    return canonical_sha256(
        {
            "event": payload,
            "bars": [
                bar.content_hash for bar in bars[detection.anchor_index : detection.event_index + 1]
            ],
        }
    )
