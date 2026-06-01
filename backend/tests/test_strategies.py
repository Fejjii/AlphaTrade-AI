"""Strategy module interface and synthetic-data evaluation tests."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.common import StrategyId, Timeframe, TradeDirection
from app.services.strategy_service import StrategyService
from app.strategies.base import StrategyEvaluationInput
from app.strategies.registry import build_default_registry


def test_registry_has_seven_mvp_modules() -> None:
    registry = build_default_registry()
    assert len(registry.all()) == 7


def test_htf_trend_pullback_emits_signal_with_synthetic_data() -> None:
    service = StrategyService(registry=build_default_registry())
    data = StrategyEvaluationInput(
        symbol="BTCUSDT",
        timeframe=Timeframe.H4,
        close=Decimal("61000"),
        volume=Decimal("1000000"),
        ema_fast=Decimal("60500"),
        ema_slow=Decimal("60000"),
        htf_trend=TradeDirection.LONG,
    )
    signal = service.evaluate(StrategyId.HTF_TREND_PULLBACK, data)
    assert signal is not None
    assert signal.strategy_id is StrategyId.HTF_TREND_PULLBACK
    assert signal.invalidation
    assert signal.evidence


def test_liquidity_sweep_no_signal_without_sweep() -> None:
    service = StrategyService(registry=build_default_registry())
    data = StrategyEvaluationInput(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        close=Decimal("60000"),
        volume=Decimal("1000000"),
        liquidity_sweep_detected=False,
    )
    assert service.evaluate(StrategyId.LIQUIDITY_SWEEP_REVERSAL, data) is None


def test_mental_capital_guard_on_high_stress() -> None:
    service = StrategyService(registry=build_default_registry())
    data = StrategyEvaluationInput(
        symbol="BTCUSDT",
        timeframe=Timeframe.H4,
        close=Decimal("60000"),
        volume=Decimal("1000000"),
        stress_score=8,
    )
    signal = service.evaluate(StrategyId.MENTAL_CAPITAL_GUARD, data)
    assert signal is not None
    assert "stress" in signal.evidence[0].lower()
