"""Deterministic analysis engine: bars in, full :class:`AnalysisResult` out."""

from __future__ import annotations

from app.analysis import indicators as ind
from app.analysis import setups as st
from app.analysis import structure as stru
from app.analysis.confidence import compute_confidence
from app.analysis.filters import evaluate_no_trade_filters
from app.analysis.types import AnalysisResult, Indicators
from app.providers.market_data import OHLCVBar


def _session_ids(bars: list[OHLCVBar]) -> list[int]:
    """Group bars into sessions by UTC calendar day (for session VWAP reset)."""
    return [b.timestamp.toordinal() for b in bars]


def analyze(
    symbol: str,
    timeframe: str,
    bars: list[OHLCVBar],
    *,
    funding_rate: float | None = None,
    is_weekend: bool = False,
    is_stale: bool = False,
) -> AnalysisResult:
    """Run the full deterministic analysis pipeline on OHLCV bars."""
    opens = [float(b.open) for b in bars]
    highs = [float(b.high) for b in bars]
    lows = [float(b.low) for b in bars]
    closes = [float(b.close) for b in bars]
    volumes = [float(b.volume) for b in bars]

    macd_line, signal_line, hist = ind.macd(closes)
    indicators = Indicators(
        sma_fast=ind.sma(closes, 20),
        sma_slow=ind.sma(closes, 50),
        ema_fast=ind.ema(closes, 12),
        ema_slow=ind.ema(closes, 26),
        rsi=ind.rsi_wilder(closes, 14),
        macd=macd_line,
        macd_signal=signal_line,
        macd_hist=hist,
        atr=ind.atr_wilder(highs, lows, closes, 14),
        vwap=ind.vwap_session(highs, lows, closes, volumes, _session_ids(bars)) if bars else None,
        volume=volumes[-1] if volumes else None,
        volume_avg=ind.sma(volumes, 20),
        volume_ratio=ind.volume_ratio(volumes, 20),
        volatility=ind.volatility_pct(closes, 20),
        funding_rate=funding_rate,
    )

    swings = stru.find_swings(highs, lows)
    supports, resistances = stru.support_resistance(swings)
    structure = stru.market_structure(swings)
    fibonacci = stru.fibonacci_levels(swings)

    detections = (
        st.detect_liquidity_sweep(highs, lows, closes, swings, indicators.atr),
        st.detect_sfp(opens, highs, lows, closes, swings),
        st.detect_order_block(opens, highs, lows, closes, indicators.atr),
        st.detect_breakout_retest(highs, lows, closes, resistances, supports, indicators.atr),
        st.detect_trend_pullback(closes, indicators.ema_fast, indicators.ema_slow, structure),
    )

    no_trade_filters = tuple(
        evaluate_no_trade_filters(
            bar_count=len(bars),
            volume_ratio=indicators.volume_ratio,
            funding_rate=funding_rate,
            is_weekend=is_weekend,
            is_stale=is_stale,
        )
    )
    no_trade = any(f.blocked for f in no_trade_filters)

    confidence = compute_confidence(
        list(detections), indicators, structure, no_trade_blocked=no_trade
    )

    return AnalysisResult(
        symbol=symbol,
        timeframe=timeframe,
        bar_count=len(bars),
        indicators=indicators,
        structure=structure,
        support_levels=tuple(supports),
        resistance_levels=tuple(resistances),
        fibonacci=fibonacci,
        detections=detections,
        no_trade_filters=no_trade_filters,
        no_trade=no_trade,
        confidence=confidence,
    )
