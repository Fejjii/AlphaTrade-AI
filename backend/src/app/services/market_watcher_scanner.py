"""Read-only market watcher condition scanner (Slice 72 — no execution)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.analysis.engine import analyze
from app.analysis.types import AnalysisResult
from app.providers.market_data import OHLCVBar
from app.schemas.common import PaperAlertSeverity, PaperAlertType, Timeframe

SCAN_CONFIRM_PHRASE = "RUN_READ_ONLY_SCAN"

SUPPORTED_SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
SUPPORTED_TIMEFRAMES: tuple[str, ...] = ("15m", "1h")

STRONG_MOVE_PCT = 2.0
HIGH_VOLUME_RATIO = 1.5
HIGH_VOLUME_MOVE_PCT = 1.0
VOLATILITY_WARNING_PCT = 3.0
SUPPORT_PROXIMITY_PCT = 1.0
RESISTANCE_PROXIMITY_PCT = 0.5


class MarketWatcherConditionType:
    STRONG_MOVE = "strong_move"
    PULLBACK_NEAR_SUPPORT = "pullback_near_support"
    RANGE_BREAKOUT_WATCH = "range_breakout_watch"
    HIGH_VOLUME_MOVE = "high_volume_move"
    RISK_VOLATILITY_WARNING = "risk_volatility_warning"


@dataclass(frozen=True)
class ScanCandidate:
    symbol: str
    timeframe: str
    condition: str
    message: str
    severity: PaperAlertSeverity
    alert_type: PaperAlertType
    metrics: dict[str, Any]
    dedup_key: str


def _pct_change(closes: list[float], lookback: int = 5) -> float | None:
    if len(closes) <= lookback:
        return None
    start = closes[-lookback - 1]
    end = closes[-1]
    if start == 0:
        return None
    return ((end - start) / start) * 100.0


def _level_price(level: Any) -> float | None:
    """Extract a numeric price from analyze() Level objects, dicts, or plain numbers."""
    if level is None:
        return None
    if isinstance(level, (int, float, Decimal)):
        try:
            return float(level)
        except (TypeError, ValueError):
            return None
    if isinstance(level, dict):
        raw = level.get("price")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    raw = getattr(level, "price", None)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _coerce_level_prices(levels: tuple[Any, ...] | list[Any] | None) -> list[float]:
    if not levels:
        return []
    prices: list[float] = []
    for level in levels:
        price = _level_price(level)
        if price is not None:
            prices.append(price)
    return prices


def _nearest_level(price: float, levels: tuple[Any, ...] | list[Any] | None) -> float | None:
    prices = _coerce_level_prices(levels)
    if not prices:
        return None
    return min(prices, key=lambda candidate: abs(candidate - price))


def _proximity_pct(price: float, level: float | None) -> float | None:
    if level is None or price == 0:
        return None
    return abs(price - level) / price * 100.0


def _trend_direction(result: AnalysisResult, closes: list[float]) -> str:
    sma_fast = result.indicators.sma_fast
    sma_slow = result.indicators.sma_slow
    if sma_fast is not None and sma_slow is not None:
        if sma_fast > sma_slow:
            return "up"
        if sma_fast < sma_slow:
            return "down"
    if len(closes) >= 2:
        if closes[-1] > closes[-2]:
            return "up"
        if closes[-1] < closes[-2]:
            return "down"
    return "flat"


def detect_candidates(
    *,
    symbol: str,
    timeframe: str,
    bars: list[OHLCVBar],
) -> list[ScanCandidate]:
    """Evaluate simple watch conditions from OHLCV bars."""
    if len(bars) < 30:
        return []

    result = analyze(symbol, timeframe, bars)
    closes = [float(b.close) for b in bars]
    latest_price = closes[-1]
    pct_change = _pct_change(closes)
    rsi = result.indicators.rsi
    vwap = result.indicators.vwap
    volume_ratio = result.indicators.volume_ratio
    volatility = result.indicators.volatility
    trend = _trend_direction(result, closes)
    support = _nearest_level(latest_price, result.support_levels)
    resistance = _nearest_level(latest_price, result.resistance_levels)
    support_proximity = _proximity_pct(latest_price, support)
    resistance_proximity = _proximity_pct(latest_price, resistance)

    metrics: dict[str, Any] = {
        "latest_price": round(latest_price, 4),
        "pct_change_window": round(pct_change, 3) if pct_change is not None else None,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "vwap": round(vwap, 4) if vwap is not None else None,
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "volatility_pct": round(volatility, 3) if volatility is not None else None,
        "trend": trend,
        "support": round(support, 4) if support is not None else None,
        "resistance": round(resistance, 4) if resistance is not None else None,
    }

    candidates: list[ScanCandidate] = []
    dedup_prefix = f"market_watcher:{symbol}:{timeframe}"

    if pct_change is not None and abs(pct_change) >= STRONG_MOVE_PCT:
        direction = "up" if pct_change > 0 else "down"
        candidates.append(
            ScanCandidate(
                symbol=symbol,
                timeframe=timeframe,
                condition=MarketWatcherConditionType.STRONG_MOVE,
                message=(
                    f"{symbol} {timeframe}: strong {direction} move "
                    f"({pct_change:+.2f}% over recent window). Paper-only watch candidate."
                ),
                severity=PaperAlertSeverity.WARNING,
                alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
                metrics={**metrics, "direction": direction},
                dedup_key=f"{dedup_prefix}:strong_move",
            )
        )

    if (
        trend == "up"
        and support_proximity is not None
        and support_proximity <= SUPPORT_PROXIMITY_PCT
    ):
        candidates.append(
            ScanCandidate(
                symbol=symbol,
                timeframe=timeframe,
                condition=MarketWatcherConditionType.PULLBACK_NEAR_SUPPORT,
                message=(
                    f"{symbol} {timeframe}: uptrend pullback near support "
                    f"({support_proximity:.2f}% from level). Paper-only watch candidate."
                ),
                severity=PaperAlertSeverity.INFO,
                alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
                metrics={**metrics, "support_proximity_pct": round(support_proximity, 3)},
                dedup_key=f"{dedup_prefix}:pullback_near_support",
            )
        )

    if resistance_proximity is not None and resistance_proximity <= RESISTANCE_PROXIMITY_PCT:
        candidates.append(
            ScanCandidate(
                symbol=symbol,
                timeframe=timeframe,
                condition=MarketWatcherConditionType.RANGE_BREAKOUT_WATCH,
                message=(
                    f"{symbol} {timeframe}: price approaching resistance "
                    f"({resistance_proximity:.2f}% away). Breakout watch — paper only."
                ),
                severity=PaperAlertSeverity.INFO,
                alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
                metrics={**metrics, "resistance_proximity_pct": round(resistance_proximity, 3)},
                dedup_key=f"{dedup_prefix}:range_breakout_watch",
            )
        )

    if (
        volume_ratio is not None
        and volume_ratio >= HIGH_VOLUME_RATIO
        and pct_change is not None
        and abs(pct_change) >= HIGH_VOLUME_MOVE_PCT
    ):
        candidates.append(
            ScanCandidate(
                symbol=symbol,
                timeframe=timeframe,
                condition=MarketWatcherConditionType.HIGH_VOLUME_MOVE,
                message=(
                    f"{symbol} {timeframe}: high-volume move "
                    f"(volume ratio {volume_ratio:.2f}, change {pct_change:+.2f}%). "
                    "Paper-only watch candidate."
                ),
                severity=PaperAlertSeverity.WARNING,
                alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
                metrics={**metrics},
                dedup_key=f"{dedup_prefix}:high_volume_move",
            )
        )

    if volatility is not None and volatility >= VOLATILITY_WARNING_PCT:
        candidates.append(
            ScanCandidate(
                symbol=symbol,
                timeframe=timeframe,
                condition=MarketWatcherConditionType.RISK_VOLATILITY_WARNING,
                message=(
                    f"{symbol} {timeframe}: elevated volatility "
                    f"({volatility:.2f}%). Risk watch — no trading action."
                ),
                severity=PaperAlertSeverity.WARNING,
                alert_type=PaperAlertType.OVERTRADING_WARNING,
                metrics={**metrics},
                dedup_key=f"{dedup_prefix}:risk_volatility_warning",
            )
        )

    return candidates


def parse_timeframe(value: str) -> Timeframe | None:
    normalized = value.strip().lower()
    for tf in Timeframe:
        if tf.value == normalized:
            return tf
    return None


def normalize_symbols(symbols: list[str]) -> list[str]:
    allowed = {s.upper() for s in SUPPORTED_SYMBOLS}
    return sorted({s.strip().upper() for s in symbols if s.strip().upper() in allowed})


def normalize_timeframes(timeframes: list[str]) -> list[str]:
    allowed = set(SUPPORTED_TIMEFRAMES)
    return sorted({tf.strip().lower() for tf in timeframes if tf.strip().lower() in allowed})


def decimal_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            converted[key] = float(Decimal(str(round(value, 6))))
        else:
            converted[key] = value
    return converted
