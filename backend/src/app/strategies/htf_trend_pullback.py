"""HTF trend pullback: trade with higher-timeframe trend after LTF confirmation."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.common import StrategyId, TradeDirection
from app.schemas.strategy import EntryZone
from app.strategies.base import StrategyEvaluationInput, StrategyModule, StrategySignal


class HtfTrendPullbackModule(StrategyModule):
    strategy_id = StrategyId.HTF_TREND_PULLBACK

    def evaluate(self, data: StrategyEvaluationInput) -> StrategySignal | None:
        if data.htf_trend is None or data.ema_fast is None or data.ema_slow is None:
            return None
        if data.close >= data.ema_fast >= data.ema_slow and data.htf_trend is TradeDirection.LONG:
            zone = EntryZone(low=data.close * Decimal("0.995"), high=data.close)
            return self._signal(
                data,
                direction=TradeDirection.LONG,
                confidence=0.65,
                invalidation="Close below local structure / EMA fast.",
                evidence=["HTF trend aligned long", "Pullback to EMA fast", "Volume present"],
                risk_notes=["Take partial profit quickly", "Stop below local structure"],
                entry_zone=zone,
            )
        return None
