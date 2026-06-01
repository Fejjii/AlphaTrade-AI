"""Strategy evaluation orchestration."""

from __future__ import annotations

from app.schemas.common import StrategyId
from app.schemas.strategy import StrategySignal
from app.strategies.base import StrategyEvaluationInput
from app.strategies.registry import StrategyRegistry, get_strategy_registry


class StrategyService:
    def __init__(self, registry: StrategyRegistry | None = None) -> None:
        self._registry = registry or get_strategy_registry()

    def list_strategy_ids(self) -> list[StrategyId]:
        return [m.strategy_id for m in self._registry.all()]

    def evaluate(
        self, strategy_id: StrategyId, data: StrategyEvaluationInput
    ) -> StrategySignal | None:
        module = self._registry.get(strategy_id)
        if module is None:
            raise ValueError(f"Unknown strategy: {strategy_id}")
        return module.evaluate(data)
