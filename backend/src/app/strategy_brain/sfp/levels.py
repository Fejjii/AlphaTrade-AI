"""Causal structural references: no float pivots or future pivot-time backdating."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.market_contracts.enums import Finality, FreshnessState
from app.market_contracts.observation import PublicMarketObservation
from app.market_contracts.ohlcv import OhlcvBar
from app.strategy_brain.sfp.contracts import (
    LevelKind,
    LevelSignificance,
    SfpParameters,
    StructuralLevel,
    available_at,
    validate_binding,
)


def level_evidence_fresh(level: StructuralLevel) -> bool:
    """Historical validity flags are separate from current candle freshness."""
    return all(
        observation.freshness_state is FreshnessState.FRESH
        for observation in level.basis_observations
    )


def validate_level(level: StructuralLevel) -> None:
    bars, observations = level.basis_bars, level.basis_observations
    if len(bars) != len(observations):
        raise ValueError("Every structural basis candle needs its canonical observation")
    for i, (bar, observation) in enumerate(zip(bars, observations, strict=True)):
        validate_binding(bar, observation)
        if (
            observation.identity != level.identity
            or bar.finality is not Finality.FINAL
            or not bar.provider_complete
            or (i and bars[i - 1].interval_end != bar.interval_start)
        ):
            raise ValueError("Structural levels require contiguous complete closed evidence")
    anchors = [bar for bar in bars if bar.source_event_id in level.anchor_event_ids]
    if len(anchors) != len(level.anchor_event_ids) or len(set(level.anchor_event_ids)) != len(
        anchors
    ):
        raise ValueError("Structural anchors must identify distinct basis candles")
    low = level.kind.support
    values = [b.low if low else b.high for b in bars]
    anchor_values = [b.low if low else b.high for b in anchors]
    expected = min(anchor_values) if low else max(anchor_values)
    width = level.significance.pivot_confirmation_bars
    is_range = level.kind in {LevelKind.RANGE_HIGH, LevelKind.RANGE_LOW}
    is_equal = level.kind in {LevelKind.EQUAL_HIGHS, LevelKind.EQUAL_LOWS}
    if is_range:
        expected = min(values) if low else max(values)
        if width or len(bars) < 3 or len(anchors) != 1 or anchor_values[0] != expected:
            raise ValueError("Range references require a complete historical window")
    else:
        if width < 1 or (is_equal and len(anchors) < 2) or (not is_equal and len(anchors) != 1):
            raise ValueError("Swing and equal levels require confirmed pivot anchors")
        for anchor in anchors:
            i = bars.index(anchor)
            if i < width or i + width >= len(bars):
                raise ValueError("Pivot right-hand evidence is missing")
            peers = values[i - width : i] + values[i + 1 : i + width + 1]
            value = values[i]
            if not all(value < v if low else value > v for v in peers):
                raise ValueError("Structural anchor is not a strictly confirmed pivot")
        if (
            is_equal
            and (max(anchor_values) - min(anchor_values)) / expected > level.equality_tolerance
        ):
            raise ValueError("Equal level anchors exceed configured tolerance")
    prominence = (max(b.high for b in bars) - min(b.low for b in bars)) / expected
    touches = sum(abs(v - expected) / expected <= level.equality_tolerance for v in values)
    if (
        level.price != expected
        or level.established_at != min(b.interval_start for b in anchors)
        or level.known_at
        != max(
            max(b.interval_end, available_at(o)) for b, o in zip(bars, observations, strict=True)
        )
        or level.significance.touches != touches
        or level.significance.prominence_ratio != prominence
        or level.significance.higher_timeframe_reference
        != (level.kind in {LevelKind.HTF_SUPPORT, LevelKind.HTF_RESISTANCE})
    ):
        raise ValueError("Structural level values and significance must match their evidence")


def _level(
    kind: LevelKind,
    bars: tuple[OhlcvBar, ...],
    observations: tuple[PublicMarketObservation, ...],
    anchors: tuple[OhlcvBar, ...],
    p: SfpParameters,
    width: int,
) -> StructuralLevel:
    values = [b.low if kind.support else b.high for b in bars]
    anchor_values = [b.low if kind.support else b.high for b in anchors]
    price = min(anchor_values) if kind.support else max(anchor_values)
    return StructuralLevel(
        kind=kind,
        identity=observations[0].identity,
        price=price,
        anchor_event_ids=tuple(b.source_event_id for b in anchors),
        basis_bars=bars,
        basis_observations=observations,
        established_at=min(b.interval_start for b in anchors),
        known_at=max(
            max(b.interval_end, available_at(o)) for b, o in zip(bars, observations, strict=True)
        ),
        significance=LevelSignificance(
            touches=sum(abs(v - price) / price <= p.equal_level_tolerance for v in values),
            pivot_confirmation_bars=width,
            prominence_ratio=(max(b.high for b in bars) - min(b.low for b in bars)) / price,
            higher_timeframe_reference=kind in {LevelKind.HTF_SUPPORT, LevelKind.HTF_RESISTANCE},
        ),
        equality_tolerance=p.equal_level_tolerance,
    )


def derive_levels(
    bars: tuple[OhlcvBar, ...],
    observations: tuple[PublicMarketObservation, ...],
    parameters: SfpParameters,
    *,
    evaluated_at: datetime,
    higher_timeframe: bool = False,
) -> tuple[StructuralLevel, ...]:
    """Derive closed-evidence levels. HTF labels require an explicit contextual series.

    Each level carries its actual availability time, including right-wing closes
    and delayed observations. The detector additionally requires availability
    before the sweep candle opens. Session levels cannot be inferred here.
    """
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    if len(bars) != len(observations):
        raise ValueError("Level candles and observations must be paired")
    p, width = parameters, parameters.pivot_width
    selected = []
    for bar, observation in zip(bars, observations, strict=True):
        if available_at(observation) > evaluated_at or bar.interval_end > evaluated_at:
            continue
        validate_binding(bar, observation)
        if bar.finality is Finality.FINAL and bar.provider_complete:
            selected.append((bar, observation))
    if not selected:
        return ()
    bars = tuple(b for b, _ in selected)
    observations = tuple(o for _, o in selected)
    for i, (bar, observation) in enumerate(selected):
        if observation.identity != observations[0].identity or (
            i and bar.interval_start != bars[i - 1].interval_end
        ):
            raise ValueError("Level evidence must have one identity and no gaps")
    found: dict[UUID, StructuralLevel] = {}
    pivots: dict[bool, list[int]] = {True: [], False: []}
    for end in range(len(bars)):
        pivot = end - width
        if pivot >= width:
            for support in (True, False):
                values = [b.low if support else b.high for b in bars[pivot - width : end + 1]]
                if all(
                    values[width] < v if support else values[width] > v
                    for j, v in enumerate(values)
                    if j != width
                ):
                    kind = (
                        (LevelKind.HTF_SUPPORT if support else LevelKind.HTF_RESISTANCE)
                        if higher_timeframe
                        else (LevelKind.SWING_LOW if support else LevelKind.SWING_HIGH)
                    )
                    level = _level(
                        kind,
                        bars[pivot - width : end + 1],
                        observations[pivot - width : end + 1],
                        (bars[pivot],),
                        p,
                        width,
                    )
                    found.setdefault(level.level_id, level)
                    for prior in pivots[support]:
                        if pivot - prior >= p.level_lookback:
                            continue
                        a, b = bars[prior], bars[pivot]
                        av, bv = (a.low, b.low) if support else (a.high, b.high)
                        reference = min(av, bv) if support else max(av, bv)
                        if abs(av - bv) / reference <= p.equal_level_tolerance:
                            equal = _level(
                                LevelKind.EQUAL_LOWS if support else LevelKind.EQUAL_HIGHS,
                                bars[prior - width : end + 1],
                                observations[prior - width : end + 1],
                                (a, b),
                                p,
                                width,
                            )
                            found.setdefault(equal.level_id, equal)
                    pivots[support].append(pivot)
        if not higher_timeframe and end + 1 >= p.level_lookback:
            start = end + 1 - p.level_lookback
            window, proof = bars[start : end + 1], observations[start : end + 1]
            for support in (True, False):
                anchor = (
                    min(window, key=lambda b: b.low)
                    if support
                    else max(window, key=lambda b: b.high)
                )
                level = _level(
                    LevelKind.RANGE_LOW if support else LevelKind.RANGE_HIGH,
                    window,
                    proof,
                    (anchor,),
                    p,
                    0,
                )
                found.setdefault(level.level_id, level)
    return tuple(sorted(found.values(), key=lambda level: (level.known_at, str(level.level_id))))
