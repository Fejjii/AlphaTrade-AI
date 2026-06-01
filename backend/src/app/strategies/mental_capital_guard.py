"""Mental capital guard: sleep test and stress-based sizing warnings."""

from __future__ import annotations

from app.schemas.common import StrategyId, TradeDirection
from app.strategies.base import StrategyEvaluationInput, StrategyModule, StrategySignal


class MentalCapitalGuardModule(StrategyModule):
    strategy_id = StrategyId.MENTAL_CAPITAL_GUARD

    def evaluate(self, data: StrategyEvaluationInput) -> StrategySignal | None:
        if data.stress_score is None or data.stress_score < 7:
            return None
        return self._signal(
            data,
            direction=TradeDirection.LONG,
            confidence=0.75,
            invalidation="Stress subsides after size reduction.",
            evidence=[f"Elevated stress score: {data.stress_score}"],
            risk_notes=["Apply Sleep Test", "Reduce size — mental capital is capital"],
        )
