"""Liquidity sweep reversal: sweep, rejection, reclaim, confirmation."""

from __future__ import annotations

from app.schemas.common import StrategyId, TradeDirection
from app.strategies.base import StrategyEvaluationInput, StrategyModule, StrategySignal


class LiquiditySweepReversalModule(StrategyModule):
    strategy_id = StrategyId.LIQUIDITY_SWEEP_REVERSAL

    def evaluate(self, data: StrategyEvaluationInput) -> StrategySignal | None:
        if not data.liquidity_sweep_detected:
            return None
        return self._signal(
            data,
            direction=TradeDirection.LONG,
            confidence=0.55,
            invalidation="No reclaim after sweep; momentum continues.",
            evidence=["Liquidity sweep detected", "Rejection wick", "Awaiting reclaim"],
            risk_notes=["Small size until reversal confirms"],
        )
