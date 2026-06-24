"""Market structure primitives: swings, support/resistance, Fibonacci, trend.

All functions are pure and rule-based with explicit numeric criteria.
"""

from __future__ import annotations

from app.analysis.types import FibonacciLevels, Level, MarketStructure, SwingPoint

_FIB_RATIOS: dict[str, float] = {
    "0.0": 0.0,
    "0.236": 0.236,
    "0.382": 0.382,
    "0.5": 0.5,
    "0.618": 0.618,
    "0.786": 0.786,
    "1.0": 1.0,
}


def find_swings(
    highs: list[float],
    lows: list[float],
    *,
    left: int = 2,
    right: int = 2,
) -> list[SwingPoint]:
    """Return fractal swing points.

    A bar ``i`` is a swing high when its high is strictly greater than the
    ``left`` bars before and ``right`` bars after it (mirror for swing lows).
    """
    swings: list[SwingPoint] = []
    n = len(highs)
    for i in range(left, n - right):
        window_h = highs[i - left : i + right + 1]
        window_l = lows[i - left : i + right + 1]
        if highs[i] == max(window_h) and window_h.count(highs[i]) == 1:
            swings.append(SwingPoint(index=i, price=highs[i], kind="high"))
        elif lows[i] == min(window_l) and window_l.count(lows[i]) == 1:
            swings.append(SwingPoint(index=i, price=lows[i], kind="low"))
    return swings


def support_resistance(
    swings: list[SwingPoint],
    *,
    tolerance_pct: float = 0.0025,
) -> tuple[list[Level], list[Level]]:
    """Cluster swing lows into supports and swing highs into resistances.

    Swings within ``tolerance_pct`` of each other are treated as one level; the
    number of touches drives a normalized strength in ``[0, 1]``.
    """
    lows = [s.price for s in swings if s.kind == "low"]
    highs = [s.price for s in swings if s.kind == "high"]
    supports = _cluster(lows, "support", tolerance_pct)
    resistances = _cluster(highs, "resistance", tolerance_pct)
    return supports, resistances


def _cluster(prices: list[float], kind: str, tolerance_pct: float) -> list[Level]:
    if not prices:
        return []
    ordered = sorted(prices)
    clusters: list[list[float]] = [[ordered[0]]]
    for price in ordered[1:]:
        anchor = clusters[-1][0]
        if anchor > 0 and abs(price - anchor) / anchor <= tolerance_pct:
            clusters[-1].append(price)
        else:
            clusters.append([price])

    max_touches = max(len(c) for c in clusters)
    levels = [
        Level(
            price=sum(c) / len(c),
            kind=kind,
            touches=len(c),
            strength=len(c) / max_touches,
        )
        for c in clusters
    ]
    # Strongest levels first.
    return sorted(levels, key=lambda level: (level.touches, level.strength), reverse=True)


def market_structure(swings: list[SwingPoint]) -> MarketStructure:
    """Classify trend from the labeled sequence of alternating swings."""
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return MarketStructure(trend="range", last_label=None, swing_points=tuple(swings))

    higher_high = highs[-1].price > highs[-2].price
    higher_low = lows[-1].price > lows[-2].price
    lower_high = highs[-1].price < highs[-2].price
    lower_low = lows[-1].price < lows[-2].price

    last_label = _last_label(swings)
    if higher_high and higher_low:
        trend = "uptrend"
    elif lower_high and lower_low:
        trend = "downtrend"
    else:
        trend = "range"
    return MarketStructure(trend=trend, last_label=last_label, swing_points=tuple(swings))


def _last_label(swings: list[SwingPoint]) -> str | None:
    last = swings[-1]
    prior = [s for s in swings[:-1] if s.kind == last.kind]
    if not prior:
        return None
    if last.kind == "high":
        return "HH" if last.price > prior[-1].price else "LH"
    return "HL" if last.price > prior[-1].price else "LL"


def fibonacci_levels(swings: list[SwingPoint]) -> FibonacciLevels | None:
    """Fibonacci retracement for the most recent dominant swing leg."""
    if len(swings) < 2:
        return None
    last = swings[-1]
    prior = swings[-2]
    if last.kind == prior.kind:
        return None

    if last.kind == "high":
        swing_low, swing_high, direction = prior.price, last.price, "up"
    else:
        swing_low, swing_high, direction = last.price, prior.price, "down"

    span = swing_high - swing_low
    if span <= 0:
        return None
    levels = {
        label: (swing_high - ratio * span if direction == "up" else swing_low + ratio * span)
        for label, ratio in _FIB_RATIOS.items()
    }
    return FibonacciLevels(
        direction=direction,
        swing_high=swing_high,
        swing_low=swing_low,
        levels=levels,
    )
