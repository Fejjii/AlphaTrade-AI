"""Countertrend short build: scale in only after momentum exhaustion."""

from __future__ import annotations

from app.schemas.common import StrategyId, TradeDirection
from app.strategies.base import StrategyEvaluationInput, StrategyModule, StrategySignal


class CountertrendShortBuildModule(StrategyModule):
    strategy_id = StrategyId.COUNTERTREND_SHORT_BUILD

    def evaluate(self, data: StrategyEvaluationInput) -> StrategySignal | None:
        if not data.momentum_exhausted:
            return None
        return self._signal(
            data,
            direction=TradeDirection.SHORT,
            confidence=0.5,
            invalidation="Momentum resumes; volume expands on breakout.",
            evidence=["Momentum exhaustion", "Decreasing volume"],
            risk_notes=["Start small", "Never add while move is hot"],
        )
