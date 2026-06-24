"""Deterministic performance calculator (Slice 62).

Pure functions only: no I/O, no clock, no randomness. Given a list of
:class:`TradeRecord` the calculator returns a :class:`PerformanceMetrics`
aggregate plus grouped breakdowns. The same engine serves paper, demo, and
backtest callers.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from decimal import Decimal

from app.services.performance.types import (
    EquityPoint,
    GroupBreakdown,
    PerformanceMetrics,
    TradeRecord,
    TradeSource,
)

_ZERO = Decimal("0")


class PerformanceCalculator:
    """Stateless aggregator over normalized trade records."""

    def calculate(self, trades: Iterable[TradeRecord]) -> PerformanceMetrics:
        """Aggregate account-level metrics over ``trades`` (order-independent input).

        Trades are sorted by close time (falling back to open time, then input
        order) to build a stable equity curve and drawdown.
        """
        ordered = self._sort_for_equity(list(trades))
        if not ordered:
            return self._empty_metrics()

        wins = [t for t in ordered if t.realized_pnl > _ZERO]
        losses = [t for t in ordered if t.realized_pnl < _ZERO]
        breakeven = [t for t in ordered if t.realized_pnl == _ZERO]

        gross_profit = sum((t.realized_pnl for t in wins), _ZERO)
        gross_loss = sum((t.realized_pnl for t in losses), _ZERO)  # negative or zero
        net_pnl = sum((t.realized_pnl for t in ordered), _ZERO)
        total_fees = sum((t.fees for t in ordered), _ZERO)
        total_funding = sum((t.funding for t in ordered), _ZERO)

        trade_count = len(ordered)
        win_rate = len(wins) / trade_count if trade_count else 0.0
        avg_win = gross_profit / len(wins) if wins else _ZERO
        avg_loss = gross_loss / len(losses) if losses else _ZERO
        expectancy = net_pnl / trade_count if trade_count else _ZERO

        equity_curve = self._equity_curve(ordered)
        max_drawdown, max_drawdown_pct = self._drawdown(equity_curve)

        return PerformanceMetrics(
            trade_count=trade_count,
            wins=len(wins),
            losses=len(losses),
            breakeven=len(breakeven),
            win_rate=win_rate,
            net_pnl=net_pnl,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_fees=total_fees,
            total_funding=total_funding,
            avg_win=avg_win,
            avg_loss=avg_loss,
            expectancy=expectancy,
            profit_factor=self._profit_factor(gross_profit, gross_loss),
            avg_r_multiple=self._avg_r_multiple(ordered),
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            avg_duration_seconds=self._avg_duration_seconds(ordered),
            violations=sum(1 for t in ordered if t.had_violation),
            equity_curve=tuple(equity_curve),
        )

    def breakdown_by_strategy(self, trades: Iterable[TradeRecord]) -> list[GroupBreakdown]:
        return self._breakdown(trades, lambda t: t.strategy_id)

    def breakdown_by_symbol(self, trades: Iterable[TradeRecord]) -> list[GroupBreakdown]:
        return self._breakdown(trades, lambda t: t.symbol)

    def breakdown_by_timeframe(self, trades: Iterable[TradeRecord]) -> list[GroupBreakdown]:
        return self._breakdown(trades, lambda t: t.timeframe)

    def breakdown_by_source(self, trades: Iterable[TradeRecord]) -> list[GroupBreakdown]:
        return self._breakdown(trades, lambda t: t.source.value)

    # --- internals --------------------------------------------------------- #

    def _breakdown(
        self,
        trades: Iterable[TradeRecord],
        key_fn: Callable[[TradeRecord], str | None],
    ) -> list[GroupBreakdown]:
        groups: dict[str, list[TradeRecord]] = {}
        for trade in trades:
            key = key_fn(trade) or "unknown"
            groups.setdefault(key, []).append(trade)
        return [
            GroupBreakdown(key=key, metrics=self.calculate(group))
            for key, group in sorted(groups.items())
        ]

    @staticmethod
    def _sort_for_equity(trades: list[TradeRecord]) -> list[TradeRecord]:
        # Stable sort preserves input order for ties (e.g. missing timestamps).
        def sort_key(item: tuple[int, TradeRecord]) -> tuple[int, float, int]:
            idx, trade = item
            ts = trade.closed_at or trade.opened_at
            # Records without a timestamp sort last but keep their relative order.
            has_ts = 0 if ts is not None else 1
            epoch = ts.timestamp() if ts is not None else 0.0
            return (has_ts, epoch, idx)

        return [t for _, t in sorted(enumerate(trades), key=sort_key)]

    @staticmethod
    def _equity_curve(ordered: list[TradeRecord]) -> list[EquityPoint]:
        cumulative = _ZERO
        points: list[EquityPoint] = []
        for index, trade in enumerate(ordered):
            cumulative += trade.realized_pnl
            points.append(
                EquityPoint(
                    index=index,
                    timestamp=trade.closed_at or trade.opened_at,
                    cumulative_pnl=cumulative,
                )
            )
        return points

    @staticmethod
    def _drawdown(curve: list[EquityPoint]) -> tuple[Decimal, float | None]:
        """Max peak-to-trough decline of cumulative PnL.

        Returns absolute drawdown and, when the running peak is positive, the
        drawdown as a fraction of that peak. Percentage is ``None`` when no
        positive peak exists (it would be undefined / misleading otherwise).
        """
        peak = _ZERO
        max_dd = _ZERO
        max_dd_pct: float | None = None
        for point in curve:
            peak = max(peak, point.cumulative_pnl)
            drop = peak - point.cumulative_pnl
            if drop > max_dd:
                max_dd = drop
                if peak > _ZERO:
                    max_dd_pct = float(drop / peak)
        return max_dd, max_dd_pct

    @staticmethod
    def _profit_factor(gross_profit: Decimal, gross_loss: Decimal) -> float | None:
        if gross_loss == _ZERO:
            return None
        return float(gross_profit / abs(gross_loss))

    @staticmethod
    def _avg_r_multiple(trades: list[TradeRecord]) -> float | None:
        r_values = [
            float(t.realized_pnl / t.risk_amount)
            for t in trades
            if t.risk_amount is not None and t.risk_amount > _ZERO
        ]
        if not r_values:
            return None
        return sum(r_values) / len(r_values)

    @staticmethod
    def _avg_duration_seconds(trades: list[TradeRecord]) -> float | None:
        durations = [
            (t.closed_at - t.opened_at).total_seconds()
            for t in trades
            if t.opened_at is not None and t.closed_at is not None
        ]
        if not durations:
            return None
        return sum(durations) / len(durations)

    @staticmethod
    def _empty_metrics() -> PerformanceMetrics:
        return PerformanceMetrics(
            trade_count=0,
            wins=0,
            losses=0,
            breakeven=0,
            win_rate=0.0,
            net_pnl=_ZERO,
            gross_profit=_ZERO,
            gross_loss=_ZERO,
            total_fees=_ZERO,
            total_funding=_ZERO,
            avg_win=_ZERO,
            avg_loss=_ZERO,
            expectancy=_ZERO,
            profit_factor=None,
            avg_r_multiple=None,
            max_drawdown=_ZERO,
            max_drawdown_pct=None,
            avg_duration_seconds=None,
            violations=0,
            equity_curve=(),
        )


def trade_record_from_human_flag(*, strategy_id: str | None) -> TradeSource:
    """Classify a trade source from its strategy id.

    Manual review strategies are treated as human-initiated; everything else is
    system-initiated. Centralized so callers stay consistent.
    """
    if strategy_id == "manual_review":
        return TradeSource.HUMAN
    return TradeSource.SYSTEM
