"""Passive level order: resting limits at high-confluence levels."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.common import StrategyId, TradeDirection
from app.schemas.strategy import EntryZone
from app.strategies.base import StrategyEvaluationInput, StrategyModule, StrategySignal


class PassiveLevelOrderModule(StrategyModule):
    strategy_id = StrategyId.PASSIVE_LEVEL_ORDER

    def evaluate(self, data: StrategyEvaluationInput) -> StrategySignal | None:
        if not data.at_confluence_level:
            return None
        zone = EntryZone(low=data.close * Decimal("0.99"), high=data.close * Decimal("1.01"))
        return self._signal(
            data,
            direction=TradeDirection.LONG,
            confidence=0.45,
            invalidation="Level breaks without reaction; remove resting order.",
            evidence=["High-confluence level", "Passive limit placement"],
            risk_notes=["Unattended order: cap size and require stop plan"],
            entry_zone=zone,
        )
