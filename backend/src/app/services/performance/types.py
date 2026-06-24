"""Value objects for the shared performance calculator (Slice 62).

These are intentionally source-agnostic: a :class:`TradeRecord` is the normalized
unit of closed-trade information, regardless of whether it originated from an
internal paper fill, a BloFin demo mirror, or a backtest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class TradeSource(StrEnum):
    """Who initiated the trade — used for human-vs-system comparison."""

    HUMAN = "human"
    SYSTEM = "system"


@dataclass(frozen=True)
class TradeRecord:
    """A single closed trade, normalized across execution sources.

    ``realized_pnl`` is net of nothing by definition here; callers pass the value
    they want aggregated. ``fees``/``funding`` are reported separately for
    transparency and are not re-subtracted from ``realized_pnl``.
    """

    realized_pnl: Decimal
    symbol: str | None = None
    strategy_id: str | None = None
    timeframe: str | None = None
    direction: str | None = None
    size: Decimal | None = None
    fees: Decimal = Decimal("0")
    funding: Decimal = Decimal("0")
    risk_amount: Decimal | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    source: TradeSource = TradeSource.SYSTEM
    had_violation: bool = False


@dataclass(frozen=True)
class EquityPoint:
    """A single point on the cumulative-PnL equity curve."""

    index: int
    timestamp: datetime | None
    cumulative_pnl: Decimal


@dataclass(frozen=True)
class PerformanceMetrics:
    """Aggregate metrics over a set of trades.

    Ratios that are mathematically undefined (e.g. profit factor with zero
    losses) are reported as ``None`` rather than a sentinel number.
    """

    trade_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    net_pnl: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    total_fees: Decimal
    total_funding: Decimal
    avg_win: Decimal
    avg_loss: Decimal
    expectancy: Decimal
    profit_factor: float | None
    avg_r_multiple: float | None
    max_drawdown: Decimal
    max_drawdown_pct: float | None
    avg_duration_seconds: float | None
    violations: int
    equity_curve: tuple[EquityPoint, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class GroupBreakdown:
    """Metrics for a single group key (e.g. one strategy, symbol, or source)."""

    key: str
    metrics: PerformanceMetrics
