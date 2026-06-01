"""Profit protection: partial profits, stop management, runner logic."""

from __future__ import annotations

from app.schemas.common import StrategyId, TradeDirection
from app.strategies.base import StrategyEvaluationInput, StrategyModule, StrategySignal


class ProfitProtectionModule(StrategyModule):
    strategy_id = StrategyId.PROFIT_PROTECTION

    def evaluate(self, data: StrategyEvaluationInput) -> StrategySignal | None:
        if not data.tags.get("position_in_profit"):
            return None
        return self._signal(
            data,
            direction=TradeDirection.LONG,
            confidence=0.7,
            invalidation="Trend breaks; winner retraces to major loss.",
            evidence=["Open winner", "Recommend partial take profit"],
            risk_notes=["Move stop intelligently", "Never let major winner become major loser"],
        )
