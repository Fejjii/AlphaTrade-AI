"""Green day guard: protect exceptional winning days from overtrading."""

from __future__ import annotations

from app.schemas.common import StrategyId, TradeDirection
from app.strategies.base import StrategyEvaluationInput, StrategyModule, StrategySignal


class GreenDayGuardModule(StrategyModule):
    strategy_id = StrategyId.GREEN_DAY_GUARD

    def evaluate(self, data: StrategyEvaluationInput) -> StrategySignal | None:
        if not data.green_day_active:
            return None
        return self._signal(
            data,
            direction=TradeDirection.LONG,
            confidence=0.8,
            invalidation="N/A — advisory guard, not an entry signal.",
            evidence=["Exceptional green day detected"],
            risk_notes=["Stop trading after daily target", "Protect profits from euphoria"],
        )
