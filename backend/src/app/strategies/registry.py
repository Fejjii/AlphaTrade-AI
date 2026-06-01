"""Registry of all MVP strategy modules."""

from __future__ import annotations

from app.schemas.common import StrategyId
from app.strategies.base import StrategyModule
from app.strategies.countertrend_short_build import CountertrendShortBuildModule
from app.strategies.green_day_guard import GreenDayGuardModule
from app.strategies.htf_trend_pullback import HtfTrendPullbackModule
from app.strategies.liquidity_sweep_reversal import LiquiditySweepReversalModule
from app.strategies.mental_capital_guard import MentalCapitalGuardModule
from app.strategies.passive_level_order import PassiveLevelOrderModule
from app.strategies.profit_protection import ProfitProtectionModule


class StrategyRegistry:
    def __init__(self) -> None:
        self._modules: dict[StrategyId, StrategyModule] = {}

    def register(self, module: StrategyModule) -> None:
        self._modules[module.strategy_id] = module

    def get(self, strategy_id: StrategyId) -> StrategyModule | None:
        return self._modules.get(strategy_id)

    def all(self) -> list[StrategyModule]:
        return list(self._modules.values())


def build_default_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    for module in (
        HtfTrendPullbackModule(),
        LiquiditySweepReversalModule(),
        CountertrendShortBuildModule(),
        PassiveLevelOrderModule(),
        ProfitProtectionModule(),
        GreenDayGuardModule(),
        MentalCapitalGuardModule(),
    ):
        registry.register(module)
    return registry


_registry: StrategyRegistry | None = None


def get_strategy_registry() -> StrategyRegistry:
    global _registry
    if _registry is None:
        _registry = build_default_registry()
    return _registry
