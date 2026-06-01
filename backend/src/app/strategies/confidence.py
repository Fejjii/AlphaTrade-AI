"""Strategy confidence adjustments based on market data quality."""

from __future__ import annotations

from app.schemas.market import MarketDataMeta
from app.strategies.base import StrategyEvaluationInput

MOCK_CONFIDENCE_PENALTY = 0.15
STALE_CONFIDENCE_PENALTY = 0.10


def adjust_confidence_for_data_quality(confidence: float, data: StrategyEvaluationInput) -> float:
    """Lower confidence when market evidence is mock, stale, or fallback."""
    adjusted = confidence
    if data.data_fallback_used or not data.data_is_live:
        adjusted -= MOCK_CONFIDENCE_PENALTY
    if data.data_is_stale:
        adjusted -= STALE_CONFIDENCE_PENALTY
    return max(0.0, min(1.0, adjusted))


def data_quality_label(meta: MarketDataMeta) -> str:
    if meta.fallback_used or not meta.is_live:
        return "mock"
    if meta.is_stale:
        return "stale"
    return "live"
