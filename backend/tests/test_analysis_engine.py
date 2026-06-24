"""Golden-vector tests for the deterministic analysis engine (Slice 58)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.analysis import analyze
from app.analysis import indicators as ind
from app.analysis import setups as st
from app.analysis import structure as stru
from app.analysis.confidence import compute_confidence, dominant_direction
from app.analysis.filters import evaluate_no_trade_filters
from app.analysis.types import Indicators, MarketStructure, SwingPoint
from app.providers.market_data import OHLCVBar


def _bars(closes: list[float], *, volume: float = 1000.0) -> list[OHLCVBar]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars: list[OHLCVBar] = []
    for i, c in enumerate(closes):
        bars.append(
            OHLCVBar(
                open=Decimal(str(c)),
                high=Decimal(str(c + 1)),
                low=Decimal(str(c - 1)),
                close=Decimal(str(c)),
                volume=Decimal(str(volume)),
                timestamp=start + timedelta(hours=i),
            )
        )
    return bars


# --- indicators (golden values) -------------------------------------------


def test_sma_golden() -> None:
    assert ind.sma([1, 2, 3, 4, 5], 5) == 3.0
    assert ind.sma([1, 2], 5) is None


def test_ema_golden() -> None:
    # period=3 -> k=0.5: 1, 1.5, 2.25, 3.125, 4.0625
    assert ind.ema([1, 2, 3, 4, 5], 3) == pytest.approx(4.0625)


def test_rsi_all_gains_is_100() -> None:
    assert ind.rsi_wilder([float(i) for i in range(1, 20)], 14) == 100.0


def test_atr_constant_range() -> None:
    highs = [11.0] * 20
    lows = [9.0] * 20
    closes = [10.0] * 20
    assert ind.atr_wilder(highs, lows, closes, 14) == pytest.approx(2.0)


def test_volume_ratio_equal_volumes() -> None:
    assert ind.volume_ratio([5.0] * 25, 20) == pytest.approx(1.0)


def test_vwap_session_resets_by_day() -> None:
    # Two bars same price/volume -> vwap equals typical price.
    highs = [11.0, 11.0]
    lows = [9.0, 9.0]
    closes = [10.0, 10.0]
    volumes = [100.0, 100.0]
    assert ind.vwap_session(highs, lows, closes, volumes, [1, 1]) == pytest.approx(10.0)
    # Different session id for the last bar isolates it.
    assert ind.vwap_session(highs, lows, closes, volumes, [1, 2]) == pytest.approx(10.0)


# --- structure -------------------------------------------------------------


def test_find_swings_simple_pivot() -> None:
    highs = [1, 2, 3, 2, 1]
    lows = [5, 4, 3, 4, 5]
    swings = stru.find_swings(highs, lows, left=2, right=2)
    assert any(s.kind == "high" and s.index == 2 for s in swings)


def test_market_structure_uptrend() -> None:
    swings = [
        SwingPoint(0, 10.0, "low"),
        SwingPoint(1, 20.0, "high"),
        SwingPoint(2, 15.0, "low"),
        SwingPoint(3, 25.0, "high"),
    ]
    result = stru.market_structure(swings)
    assert result.trend == "uptrend"
    assert result.last_label == "HH"


def test_fibonacci_levels_up_leg() -> None:
    swings = [SwingPoint(0, 100.0, "low"), SwingPoint(1, 200.0, "high")]
    fib = stru.fibonacci_levels(swings)
    assert fib is not None
    assert fib.direction == "up"
    assert fib.levels["0.5"] == pytest.approx(150.0)


# --- detectors -------------------------------------------------------------


def test_liquidity_sweep_long() -> None:
    swings = [SwingPoint(3, 100.0, "low")]
    highs = [105.0] * 11
    lows = [101.0] * 10 + [99.0]
    closes = [102.0] * 10 + [101.0]
    result = st.detect_liquidity_sweep(highs, lows, closes, swings, atr=2.0)
    assert result.detected is True
    assert result.direction == "long"


def test_sfp_short() -> None:
    swings = [SwingPoint(3, 200.0, "high")]
    opens = [150.0] * 10 + [200.5]  # last bar is bearish (close < open)
    highs = [150.0] * 10 + [201.0]
    lows = [149.0] * 11
    closes = [150.0] * 10 + [199.0]
    result = st.detect_sfp(opens, highs, lows, closes, swings)
    assert result.detected is True
    assert result.direction == "short"


def test_breakout_retest_long() -> None:
    from app.analysis.types import Level

    resistances = [Level(price=100.0, kind="resistance", touches=3, strength=1.0)]
    highs = [105.0] * 7
    lows = [95.0] * 7
    # Broke above 100 in the lookback, latest close retests right at the level.
    closes = [101.0, 102.0, 103.0, 102.0, 101.0, 101.0, 100.1]
    result = st.detect_breakout_retest(highs, lows, closes, resistances, [], atr=1.0)
    assert result.detected is True
    assert result.direction == "long"


def test_trend_pullback_long() -> None:
    structure = MarketStructure(trend="uptrend", last_label="HH", swing_points=())
    result = st.detect_trend_pullback([99.0], ema_fast=100.0, ema_slow=90.0, structure=structure)
    assert result.detected is True
    assert result.direction == "long"


# --- filters & confidence --------------------------------------------------


def test_no_trade_filters_block_low_volume_and_short_history() -> None:
    filters = evaluate_no_trade_filters(bar_count=5, volume_ratio=0.2, funding_rate=0.0)
    blocked = {f.name for f in filters if f.blocked}
    assert "insufficient_data" in blocked
    assert "low_volume" in blocked


def test_extreme_funding_blocks() -> None:
    filters = evaluate_no_trade_filters(bar_count=100, volume_ratio=1.0, funding_rate=0.01)
    assert any(f.name == "extreme_funding" and f.blocked for f in filters)


def test_dominant_direction() -> None:
    from app.analysis.types import SetupDetection

    detections = [
        SetupDetection("a", True, "long", "", {}),
        SetupDetection("b", True, "long", "", {}),
        SetupDetection("c", True, "short", "", {}),
    ]
    assert dominant_direction(detections) == "long"


def test_confidence_zero_when_no_trade_blocked() -> None:
    from app.analysis.types import SetupDetection

    indicators = Indicators(
        None, None, None, None, 60.0, 1.0, 0.5, 0.5, 2.0, None, 1000.0, 1000.0, 1.2, 0.01, 0.0
    )
    structure = MarketStructure(trend="uptrend", last_label="HH", swing_points=())
    detections = [SetupDetection("a", True, "long", "", {})]
    score = compute_confidence(detections, indicators, structure, no_trade_blocked=True)
    assert score.score == 0.0
    # Factors are still reported for transparency.
    assert len(score.factors) == 4


# --- engine end-to-end -----------------------------------------------------


def test_engine_is_deterministic() -> None:
    closes = [100.0 + i * 0.5 for i in range(80)]
    bars = _bars(closes)
    a = analyze("BTCUSDT", "1h", bars, funding_rate=0.0001)
    b = analyze("BTCUSDT", "1h", bars, funding_rate=0.0001)
    assert a == b


def test_engine_uptrend_no_block() -> None:
    closes = [100.0 + i * 0.5 for i in range(80)]
    result = analyze("BTCUSDT", "1h", _bars(closes), funding_rate=0.0001)
    assert result.bar_count == 80
    assert result.indicators.rsi is not None
    assert result.no_trade is False


def test_engine_blocks_on_short_history() -> None:
    result = analyze("BTCUSDT", "1h", _bars([100.0, 101.0, 102.0]))
    assert result.no_trade is True
    assert result.confidence.score == 0.0
