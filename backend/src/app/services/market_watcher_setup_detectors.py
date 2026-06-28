"""Adapter from analysis setup detectors to market watcher scan candidates (Slice 74)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.analysis.types import AnalysisResult, SetupDetection
from app.providers.market_data import OHLCVBar
from app.schemas.common import PaperAlertSeverity, PaperAlertType

if TYPE_CHECKING:
    from app.services.market_watcher_scanner import ScanCandidate

SETUP_DETECTOR_VERSIONS: dict[str, str] = {
    "liquidity_sweep": "1.0.0",
    "sfp": "1.0.0",
    "trend_pullback": "1.0.0",
    "order_block": "1.0.0",
    "breakout_retest": "1.0.0",
}

WATCHER_SETUP_CONDITIONS: frozenset[str] = frozenset(SETUP_DETECTOR_VERSIONS)


def detectors_enabled() -> list[str]:
    return sorted(WATCHER_SETUP_CONDITIONS)


def _trigger_bucket(level: float | None) -> str:
    if level is None:
        return "none"
    return f"{level:.4f}"


def _extract_levels(
    detection: SetupDetection,
    *,
    last_high: float,
    last_low: float,
) -> tuple[float | None, float | None]:
    metrics = detection.metrics
    if detection.name == "liquidity_sweep":
        trigger = metrics.get("swept_level")
        invalidation = last_low if detection.direction == "long" else last_high
        return trigger, invalidation
    if detection.name == "sfp":
        trigger = metrics.get("failed_level")
        invalidation = last_low if detection.direction == "long" else last_high
        return trigger, invalidation
    if detection.name == "trend_pullback":
        return metrics.get("ema_fast"), metrics.get("ema_slow")
    if detection.name == "order_block":
        ob_low = metrics.get("ob_low")
        ob_high = metrics.get("ob_high")
        if detection.direction == "long":
            return ob_high, ob_low
        if detection.direction == "short":
            return ob_low, ob_high
        return ob_low, ob_high
    if detection.name == "breakout_retest":
        level = metrics.get("level")
        if detection.direction == "long":
            return level, last_low
        if detection.direction == "short":
            return level, last_high
        return level, None
    return None, None


def _map_detection(
    *,
    symbol: str,
    timeframe: str,
    detection: SetupDetection,
    result: AnalysisResult,
    latest_price: float,
    last_high: float,
    last_low: float,
) -> ScanCandidate | None:
    from app.services.market_watcher_scanner import ScanCandidate

    if not detection.detected or detection.name not in WATCHER_SETUP_CONDITIONS:
        return None

    trigger_level, invalidation_level = _extract_levels(
        detection,
        last_high=last_high,
        last_low=last_low,
    )
    direction = detection.direction
    version = SETUP_DETECTOR_VERSIONS[detection.name]
    dedup_prefix = f"market_watcher:{symbol}:{timeframe}"
    dedup_key = (
        f"{dedup_prefix}:{detection.name}:{direction or 'none'}:{_trigger_bucket(trigger_level)}"
    )

    metrics: dict[str, Any] = {
        "latest_price": round(latest_price, 4),
        "direction": direction,
        "confidence": round(result.confidence.score, 2),
        "trigger_level": round(trigger_level, 4) if trigger_level is not None else None,
        "invalidation_level": (
            round(invalidation_level, 4) if invalidation_level is not None else None
        ),
        "reason": detection.reason,
        "source": "market_watcher",
        "detector_version": version,
        **{k: round(v, 6) if isinstance(v, float) else v for k, v in detection.metrics.items()},
    }

    direction_label = direction or "neutral"
    message = (
        f"{symbol} {timeframe}: {detection.name} ({direction_label}) — "
        f"{detection.reason} Paper-only watch candidate."
    )

    return ScanCandidate(
        symbol=symbol,
        timeframe=timeframe,
        condition=detection.name,
        message=message,
        severity=PaperAlertSeverity.INFO,
        alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
        metrics=metrics,
        dedup_key=dedup_key,
        direction=direction,
        confidence=result.confidence.score,
        reason=detection.reason,
        trigger_level=trigger_level,
        invalidation_level=invalidation_level,
        source="market_watcher",
        detector_version=version,
    )


def detect_setup_candidates(
    *,
    symbol: str,
    timeframe: str,
    bars: list[OHLCVBar],
    result: AnalysisResult,
) -> list[ScanCandidate]:
    """Map fired analysis setup detectors to non-executable watch candidates."""
    if not bars:
        return []

    latest_price = float(bars[-1].close)
    last_high = float(bars[-1].high)
    last_low = float(bars[-1].low)
    candidates: list[ScanCandidate] = []

    for detection in result.detections:
        try:
            candidate = _map_detection(
                symbol=symbol,
                timeframe=timeframe,
                detection=detection,
                result=result,
                latest_price=latest_price,
                last_high=last_high,
                last_low=last_low,
            )
            if candidate is not None:
                candidates.append(candidate)
        except Exception:
            continue

    return candidates
