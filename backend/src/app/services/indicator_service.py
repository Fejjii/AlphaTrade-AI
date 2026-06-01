"""Deterministic technical indicator calculations from OHLCV bars."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.providers.market_data import OHLCVBar
from app.schemas.common import Symbol, Timeframe
from app.schemas.market import IndicatorContext


def _to_float(value: Decimal) -> float:
    return float(value)


def _ema(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None] * len(values)
    multiplier = 2 / (period + 1)
    result: list[float | None] = [None] * (period - 1)
    seed = sum(values[:period]) / period
    result.append(seed)
    prev = seed
    for val in values[period:]:
        prev = (val - prev) * multiplier + prev
        result.append(prev)
    return result


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(closes: list[float]) -> tuple[float | None, float | None]:
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line: list[float | None] = []
    for fast, slow in zip(ema12, ema26, strict=True):
        if fast is None or slow is None:
            macd_line.append(None)
        else:
            macd_line.append(fast - slow)
    valid = [v for v in macd_line if v is not None]
    if not valid:
        return None, None
    signal_series = _ema(valid, 9)
    macd_val = valid[-1]
    signal_val = signal_series[-1] if signal_series else None
    return macd_val, signal_val


def _atr(bars: list[OHLCVBar], period: int = 14) -> Decimal | None:
    if len(bars) <= period:
        return None
    trs: list[float] = []
    for i in range(1, len(bars)):
        high = _to_float(bars[i].high)
        low = _to_float(bars[i].low)
        prev_close = _to_float(bars[i - 1].close)
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    if len(trs) < period:
        return None
    atr_val = sum(trs[-period:]) / period
    return Decimal(str(round(atr_val, 8)))


def _vwap(bars: list[OHLCVBar]) -> Decimal | None:
    if not bars:
        return None
    cumulative_pv = 0.0
    cumulative_vol = 0.0
    for bar in bars:
        typical = (_to_float(bar.high) + _to_float(bar.low) + _to_float(bar.close)) / 3
        vol = _to_float(bar.volume)
        cumulative_pv += typical * vol
        cumulative_vol += vol
    if cumulative_vol == 0:
        return None
    return Decimal(str(round(cumulative_pv / cumulative_vol, 8)))


def _volume_trend(bars: list[OHLCVBar], lookback: int = 10) -> float | None:
    if len(bars) < lookback * 2:
        return None
    recent = [_to_float(b.volume) for b in bars[-lookback:]]
    prior = [_to_float(b.volume) for b in bars[-lookback * 2 : -lookback]]
    recent_avg = sum(recent) / len(recent)
    prior_avg = sum(prior) / len(prior)
    if prior_avg == 0:
        return None
    return (recent_avg - prior_avg) / prior_avg


class IndicatorService:
    """Compute indicators deterministically from OHLCV history."""

    def calculate(
        self,
        *,
        symbol: Symbol,
        timeframe: Timeframe,
        bars: list[OHLCVBar],
        funding_rate: Decimal | None = None,
    ) -> IndicatorContext:
        closes = [_to_float(b.close) for b in bars]
        ema_fast_series = _ema(closes, 12)
        ema_slow_series = _ema(closes, 26)
        ema_fast = ema_fast_series[-1]
        ema_slow = ema_slow_series[-1]
        rsi = _rsi(closes)
        macd, macd_signal = _macd(closes)
        atr = _atr(bars)
        vwap = _vwap(bars)
        vol_trend = _volume_trend(bars)
        volatility = None
        if len(closes) >= 20:
            window = closes[-20:]
            mean = sum(window) / len(window)
            variance = sum((x - mean) ** 2 for x in window) / len(window)
            volatility = variance**0.5 / mean if mean else None

        return IndicatorContext(
            symbol=symbol,
            timeframe=timeframe,
            rsi=rsi,
            vwap=vwap,
            ema_fast=Decimal(str(round(ema_fast, 8))) if ema_fast is not None else None,
            ema_slow=Decimal(str(round(ema_slow, 8))) if ema_slow is not None else None,
            macd=macd,
            macd_signal=macd_signal,
            atr=atr,
            volatility=volatility,
            volume_trend=vol_trend,
            funding_rate=funding_rate,
            timestamp=datetime.now(UTC),
        )
