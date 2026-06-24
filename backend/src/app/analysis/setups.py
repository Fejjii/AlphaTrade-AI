"""Rule-based setup detectors with explicit numeric criteria.

Each detector returns a :class:`SetupDetection` describing whether it fired, the
direction, a human-readable reason, and the metrics that drove the decision.
Detectors are pure: no I/O, no randomness, no wall-clock dependence.
"""

from __future__ import annotations

from app.analysis.types import Level, MarketStructure, SetupDetection, SwingPoint


def _none(name: str, reason: str) -> SetupDetection:
    return SetupDetection(name=name, detected=False, direction=None, reason=reason, metrics={})


def _prior_swing(swings: list[SwingPoint], kind: str, before_index: int) -> SwingPoint | None:
    candidates = [s for s in swings if s.kind == kind and s.index < before_index]
    return candidates[-1] if candidates else None


def detect_liquidity_sweep(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    swings: list[SwingPoint],
    atr: float | None,
    *,
    k: float = 0.25,
) -> SetupDetection:
    """Wick beyond a prior swing by >= k*ATR, with close back inside the range."""
    name = "liquidity_sweep"
    if atr is None or atr <= 0 or len(closes) < 2:
        return _none(name, "Insufficient data or ATR.")
    last = len(closes) - 1
    threshold = k * atr

    prior_low = _prior_swing(swings, "low", last)
    if prior_low and lows[last] < prior_low.price - threshold and closes[last] > prior_low.price:
        return SetupDetection(
            name=name,
            detected=True,
            direction="long",
            reason="Swept liquidity below prior swing low and closed back above it.",
            metrics={"swept_level": prior_low.price, "low": lows[last], "atr": atr},
        )

    prior_high = _prior_swing(swings, "high", last)
    if (
        prior_high
        and highs[last] > prior_high.price + threshold
        and closes[last] < prior_high.price
    ):
        return SetupDetection(
            name=name,
            detected=True,
            direction="short",
            reason="Swept liquidity above prior swing high and closed back below it.",
            metrics={"swept_level": prior_high.price, "high": highs[last], "atr": atr},
        )
    return _none(name, "No sweep beyond the ATR threshold.")


def detect_sfp(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    swings: list[SwingPoint],
) -> SetupDetection:
    """Swing failure: new extreme beyond a prior swing that closes back inside."""
    name = "sfp"
    if len(closes) < 2:
        return _none(name, "Insufficient data.")
    last = len(closes) - 1

    prior_low = _prior_swing(swings, "low", last)
    if (
        prior_low
        and lows[last] < prior_low.price
        and closes[last] > prior_low.price
        and closes[last] > opens[last]
    ):
        return SetupDetection(
            name=name,
            detected=True,
            direction="long",
            reason="Bullish swing failure below prior swing low.",
            metrics={"failed_level": prior_low.price, "close": closes[last]},
        )

    prior_high = _prior_swing(swings, "high", last)
    if (
        prior_high
        and highs[last] > prior_high.price
        and closes[last] < prior_high.price
        and closes[last] < opens[last]
    ):
        return SetupDetection(
            name=name,
            detected=True,
            direction="short",
            reason="Bearish swing failure above prior swing high.",
            metrics={"failed_level": prior_high.price, "close": closes[last]},
        )
    return _none(name, "No swing failure pattern.")


def detect_order_block(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    atr: float | None,
    *,
    impulse_k: float = 1.5,
    lookahead: int = 3,
) -> SetupDetection:
    """Last opposite candle preceding an impulsive move >= impulse_k*ATR."""
    name = "order_block"
    if atr is None or atr <= 0 or len(closes) < lookahead + 2:
        return _none(name, "Insufficient data or ATR.")
    move = impulse_k * atr
    start = len(closes) - 1 - lookahead

    for i in range(start, 0, -1):
        net = closes[i + lookahead] - closes[i]
        if net >= move and closes[i] < opens[i]:
            return SetupDetection(
                name=name,
                detected=True,
                direction="long",
                reason="Bullish order block: down candle before an impulsive up move.",
                metrics={"ob_low": lows[i], "ob_high": highs[i], "impulse": net},
            )
        if net <= -move and closes[i] > opens[i]:
            return SetupDetection(
                name=name,
                detected=True,
                direction="short",
                reason="Bearish order block: up candle before an impulsive down move.",
                metrics={"ob_low": lows[i], "ob_high": highs[i], "impulse": net},
            )
    return _none(name, "No impulsive move from an opposite candle.")


def detect_breakout_retest(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    resistances: list[Level],
    supports: list[Level],
    atr: float | None,
    *,
    lookback: int = 5,
    tol_k: float = 0.25,
) -> SetupDetection:
    """Break of a level within ``lookback`` bars, then a retest holding it."""
    name = "breakout_retest"
    if atr is None or atr <= 0 or len(closes) < lookback + 1:
        return _none(name, "Insufficient data or ATR.")
    last = len(closes) - 1
    tol = tol_k * atr

    for level in resistances:
        broke = any(closes[i] > level.price for i in range(last - lookback, last))
        retest = abs(closes[last] - level.price) <= tol and closes[last] >= level.price
        if broke and retest:
            return SetupDetection(
                name=name,
                detected=True,
                direction="long",
                reason="Broke resistance then retested it as support.",
                metrics={"level": level.price, "close": closes[last]},
            )

    for level in supports:
        broke = any(closes[i] < level.price for i in range(last - lookback, last))
        retest = abs(closes[last] - level.price) <= tol and closes[last] <= level.price
        if broke and retest:
            return SetupDetection(
                name=name,
                detected=True,
                direction="short",
                reason="Broke support then retested it as resistance.",
                metrics={"level": level.price, "close": closes[last]},
            )
    return _none(name, "No breakout-retest within tolerance.")


def detect_trend_pullback(
    closes: list[float],
    ema_fast: float | None,
    ema_slow: float | None,
    structure: MarketStructure,
) -> SetupDetection:
    """Pullback to the fast EMA within an established trend."""
    name = "trend_pullback"
    if ema_fast is None or ema_slow is None or not closes:
        return _none(name, "Missing EMAs.")
    close = closes[-1]

    if structure.trend == "uptrend" and ema_fast > ema_slow and close <= ema_fast:
        return SetupDetection(
            name=name,
            detected=True,
            direction="long",
            reason="Uptrend pullback to the fast EMA.",
            metrics={"close": close, "ema_fast": ema_fast, "ema_slow": ema_slow},
        )
    if structure.trend == "downtrend" and ema_fast < ema_slow and close >= ema_fast:
        return SetupDetection(
            name=name,
            detected=True,
            direction="short",
            reason="Downtrend pullback to the fast EMA.",
            metrics={"close": close, "ema_fast": ema_fast, "ema_slow": ema_slow},
        )
    return _none(name, "No trend pullback.")
