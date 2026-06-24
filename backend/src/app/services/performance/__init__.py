"""Shared performance analytics (Slice 62).

A single deterministic :class:`PerformanceCalculator` consumes normalized
:class:`TradeRecord` values and produces account- and group-level metrics
(equity curve, PnL, fees/funding, win rate, profit factor, expectancy,
R-multiple, drawdown, durations, violations, human-vs-system). Keeping the math
pure and source-agnostic lets paper, demo, and backtest paths reuse one engine.
"""

from __future__ import annotations

from app.services.performance.calculator import PerformanceCalculator
from app.services.performance.types import (
    EquityPoint,
    GroupBreakdown,
    PerformanceMetrics,
    TradeRecord,
    TradeSource,
)

__all__ = [
    "EquityPoint",
    "GroupBreakdown",
    "PerformanceCalculator",
    "PerformanceMetrics",
    "TradeRecord",
    "TradeSource",
]
