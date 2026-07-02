"""Dollar-equity and daily portfolio series (Slice 91A).

Pure functions over normalized closed/open trade records. Computes dollar
equity (starting balance + PnL), daily PnL, daily drawdown, and max drawdown
on equity — distinct from Slice 62 cumulative-PnL-only curves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.services.performance.unified_trade import UnifiedTradeRecord, closed_trades
from app.services.risk.settings_service import normalize_timezone

_ZERO = Decimal("0")


@dataclass(frozen=True)
class DollarEquityPoint:
    index: int
    timestamp: datetime | None
    equity: Decimal
    cumulative_realized_pnl: Decimal
    unrealized_pnl: Decimal | None = None
    event: str = "trade_close"


@dataclass(frozen=True)
class DailyPortfolioPoint:
    date: date
    starting_equity: Decimal
    ending_equity: Decimal
    daily_pnl: Decimal
    daily_drawdown: Decimal
    daily_drawdown_pct: float | None
    trades_closed: int


@dataclass(frozen=True)
class EquitySeriesResult:
    equity_curve: tuple[DollarEquityPoint, ...]
    daily_series: tuple[DailyPortfolioPoint, ...]
    max_drawdown: Decimal
    max_drawdown_pct: float | None
    cumulative_realized_pnl: Decimal


class PortfolioEquityCalculator:
    """Build dollar-equity curves and daily portfolio metrics."""

    def build(
        self,
        *,
        starting_balance: Decimal,
        records: list[UnifiedTradeRecord],
        unrealized_pnl: Decimal | None,
        as_of: datetime,
        timezone: str | None,
        series_start: date | None = None,
        series_end: date | None = None,
    ) -> EquitySeriesResult:
        closed = _sorted_closed(records)
        cumulative = sum((t.realized_pnl for t in closed), _ZERO)
        curve = self._equity_curve(
            starting_balance=starting_balance,
            closed=closed,
            unrealized_pnl=unrealized_pnl,
            as_of=as_of,
        )
        daily = self._daily_series(
            starting_balance=starting_balance,
            closed=closed,
            timezone=timezone,
            series_start=series_start,
            series_end=series_end,
        )
        max_dd, max_dd_pct = _max_drawdown_on_equity(curve)
        return EquitySeriesResult(
            equity_curve=tuple(curve),
            daily_series=tuple(daily),
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            cumulative_realized_pnl=cumulative,
        )

    def _equity_curve(
        self,
        *,
        starting_balance: Decimal,
        closed: list[UnifiedTradeRecord],
        unrealized_pnl: Decimal | None,
        as_of: datetime,
    ) -> list[DollarEquityPoint]:
        points: list[DollarEquityPoint] = [
            DollarEquityPoint(
                index=0,
                timestamp=closed[0].opened_at if closed else as_of,
                equity=starting_balance,
                cumulative_realized_pnl=_ZERO,
                event="start",
            )
        ]
        running = _ZERO
        for idx, trade in enumerate(closed, start=1):
            running += trade.realized_pnl
            points.append(
                DollarEquityPoint(
                    index=idx,
                    timestamp=trade.closed_at,
                    equity=starting_balance + running,
                    cumulative_realized_pnl=running,
                    event="trade_close",
                )
            )
        live_equity = starting_balance + running + (unrealized_pnl or _ZERO)
        points.append(
            DollarEquityPoint(
                index=len(points),
                timestamp=as_of,
                equity=live_equity,
                cumulative_realized_pnl=running,
                unrealized_pnl=unrealized_pnl,
                event="live",
            )
        )
        return points

    def _daily_series(
        self,
        *,
        starting_balance: Decimal,
        closed: list[UnifiedTradeRecord],
        timezone: str | None,
        series_start: date | None,
        series_end: date | None,
    ) -> list[DailyPortfolioPoint]:
        tz_label, _ = normalize_timezone(timezone)
        tz = ZoneInfo(tz_label)

        if not closed and series_start is None and series_end is None:
            return []

        by_day: dict[date, list[UnifiedTradeRecord]] = {}
        for trade in closed:
            if trade.closed_at is None:
                continue
            day = trade.closed_at.astimezone(tz).date()
            by_day.setdefault(day, []).append(trade)

        if not by_day and series_start is None:
            return []

        first_day = min(by_day) if by_day else series_start
        last_day = max(by_day) if by_day else series_end
        if series_start is not None:
            first_day = series_start if first_day is None else min(first_day, series_start)
        if series_end is not None:
            last_day = series_end if last_day is None else max(last_day, series_end)
        if first_day is None or last_day is None:
            return []

        # Realized PnL from closes strictly before the series window.
        pre_window = _ZERO
        for trade in closed:
            if trade.closed_at is None:
                continue
            day = trade.closed_at.astimezone(tz).date()
            if day < first_day:
                pre_window += trade.realized_pnl

        points: list[DailyPortfolioPoint] = []
        equity = starting_balance + pre_window
        current = first_day
        while current <= last_day:
            day_trades = sorted(
                by_day.get(current, []),
                key=lambda t: t.closed_at or datetime.min.replace(tzinfo=UTC),
            )
            day_start_equity = equity
            peak = equity
            max_day_dd = _ZERO
            daily_pnl = _ZERO
            for trade in day_trades:
                daily_pnl += trade.realized_pnl
                equity += trade.realized_pnl
                peak = max(peak, equity)
                drop = peak - equity
                if drop > max_day_dd:
                    max_day_dd = drop
            dd_pct = float(max_day_dd / peak) if peak > _ZERO and max_day_dd > _ZERO else None
            points.append(
                DailyPortfolioPoint(
                    date=current,
                    starting_equity=day_start_equity,
                    ending_equity=equity,
                    daily_pnl=daily_pnl,
                    daily_drawdown=max_day_dd,
                    daily_drawdown_pct=dd_pct,
                    trades_closed=len(day_trades),
                )
            )
            current += timedelta(days=1)
        return points


def _sorted_closed(records: list[UnifiedTradeRecord]) -> list[UnifiedTradeRecord]:
    closed = closed_trades(records)

    def sort_key(item: tuple[int, UnifiedTradeRecord]) -> tuple[int, float, int]:
        idx, trade = item
        ts = trade.closed_at or trade.opened_at
        has_ts = 0 if ts is not None else 1
        epoch = ts.timestamp() if ts is not None else 0.0
        return (has_ts, epoch, idx)

    return [t for _, t in sorted(enumerate(closed), key=sort_key)]


def _max_drawdown_on_equity(curve: list[DollarEquityPoint]) -> tuple[Decimal, float | None]:
    peak = _ZERO
    max_dd = _ZERO
    max_dd_pct: float | None = None
    for point in curve:
        peak = max(peak, point.equity)
        drop = peak - point.equity
        if drop > max_dd:
            max_dd = drop
            if peak > _ZERO:
                max_dd_pct = float(drop / peak)
    return max_dd, max_dd_pct
