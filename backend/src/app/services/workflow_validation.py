"""Shared validation helpers for workflow services."""

from __future__ import annotations

from app.core.errors import ValidationAppError
from app.schemas.common import StrategyId, Timeframe

ALLOWED_EXCHANGES = frozenset({"binance", "bybit", "okx", "paper", "mock"})


def validate_exchange(exchange: str) -> str:
    normalized = exchange.strip().lower()
    if normalized not in ALLOWED_EXCHANGES:
        raise ValidationAppError(
            f"Unsupported exchange: {exchange}",
            details={"allowed": sorted(ALLOWED_EXCHANGES)},
        )
    return normalized


def validate_timeframes(timeframes: list[Timeframe]) -> list[Timeframe]:
    if not timeframes:
        raise ValidationAppError("At least one timeframe is required.")
    return timeframes


def validate_strategy_ids(strategy_ids: list[StrategyId]) -> list[StrategyId]:
    if not strategy_ids:
        raise ValidationAppError("At least one strategy is required.")
    return strategy_ids
