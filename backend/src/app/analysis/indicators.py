"""Pure indicator calculations.

Functions operate on plain ``list[float]`` (or OHLC tuples) and return either a
scalar latest value or a full series. They are deterministic and have no I/O.
Smoothed indicators (RSI, ATR) use Wilder's method to match common charting.
"""

from __future__ import annotations

from itertools import pairwise
from statistics import fmean, pstdev


def sma(values: list[float], period: int) -> float | None:
    """Simple moving average of the last ``period`` values."""
    if period <= 0 or len(values) < period:
        return None
    return fmean(values[-period:])


def ema_series(values: list[float], period: int) -> list[float]:
    """Exponential moving average series seeded with the first value."""
    if period <= 0 or not values:
        return []
    k = 2.0 / (period + 1.0)
    out = [values[0]]
    for value in values[1:]:
        out.append(value * k + out[-1] * (1.0 - k))
    return out


def ema(values: list[float], period: int) -> float | None:
    """Latest EMA value, or ``None`` when there is insufficient data."""
    if period <= 0 or len(values) < period:
        return None
    series = ema_series(values, period)
    return series[-1] if series else None


def rsi_wilder(closes: list[float], period: int = 14) -> float | None:
    """Relative Strength Index using Wilder's smoothing."""
    if len(closes) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for prev, curr in pairwise(closes):
        change = curr - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    closes: list[float],
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[float | None, float | None, float | None]:
    """Return (macd_line, signal_line, histogram) for the latest bar."""
    if len(closes) < slow:
        return None, None, None
    fast_series = ema_series(closes, fast)
    slow_series = ema_series(closes, slow)
    macd_line_series = [f - s for f, s in zip(fast_series, slow_series, strict=False)]
    if len(macd_line_series) < signal:
        return macd_line_series[-1], None, None
    signal_series = ema_series(macd_line_series, signal)
    macd_line = macd_line_series[-1]
    signal_line = signal_series[-1]
    return macd_line, signal_line, macd_line - signal_line


def true_ranges(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    """Per-bar true range; the first bar uses ``high - low``."""
    if not highs:
        return []
    out = [highs[0] - lows[0]]
    for i in range(1, len(highs)):
        prev_close = closes[i - 1]
        out.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - prev_close),
                abs(lows[i] - prev_close),
            )
        )
    return out


def atr_wilder(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> float | None:
    """Average True Range using Wilder's smoothing."""
    trs = true_ranges(highs, lows, closes)
    if len(trs) < period:
        return None
    atr = fmean(trs[:period])
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def vwap_session(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    session_ids: list[int],
) -> float | None:
    """Volume-weighted average price for the latest session.

    ``session_ids`` marks bars belonging to the same session (e.g. UTC day).
    VWAP resets when the latest session id changes.
    """
    if not closes or not volumes:
        return None
    latest_session = session_ids[-1]
    pv_total = 0.0
    vol_total = 0.0
    for i in range(len(closes)):
        if session_ids[i] != latest_session:
            continue
        typical = (highs[i] + lows[i] + closes[i]) / 3.0
        pv_total += typical * volumes[i]
        vol_total += volumes[i]
    if vol_total == 0:
        return None
    return pv_total / vol_total


def volume_ratio(volumes: list[float], period: int = 20) -> float | None:
    """Latest volume divided by the average of the prior ``period`` bars."""
    if len(volumes) <= period:
        return None
    avg = fmean(volumes[-period - 1 : -1])
    if avg == 0:
        return None
    return volumes[-1] / avg


def volatility_pct(closes: list[float], period: int = 20) -> float | None:
    """Population stddev of the last ``period`` closes as a fraction of the mean."""
    if len(closes) < period:
        return None
    window = closes[-period:]
    mean = fmean(window)
    if mean == 0:
        return None
    return pstdev(window) / mean
