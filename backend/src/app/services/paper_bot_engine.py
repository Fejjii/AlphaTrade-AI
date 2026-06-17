"""Paper bot engine v1 — deterministic scan/tick simulation (Slice 39, paper only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.db.models import HistoricalCandle as HistoricalCandleModel
from app.schemas.common import TradeDirection
from app.services.strategy_rule_adapter import ParsedStrategyRules


@dataclass
class _OpenPaperTrade:
    direction: TradeDirection
    entry_time: datetime
    entry_price: Decimal
    stop_loss: Decimal
    size: Decimal
    tp_levels: list[Decimal]
    tp_hit: int
    use_runner: bool
    entry_fees: Decimal
    entry_slippage: Decimal
    bars_open: int = 0


@dataclass(frozen=True)
class EntryEvaluation:
    triggered: bool
    entry_price: Decimal | None
    stop_loss: Decimal | None
    notes: str
    matched_blocks: list[str]


@dataclass(frozen=True)
class CloseEvaluation:
    exit_time: datetime
    exit_price: Decimal
    exit_reason: str
    tp_status: str
    gross_pnl: Decimal
    net_pnl: Decimal
    fees: Decimal
    slippage: Decimal
    stop_respected: bool
    early_exit: bool
    runner_helped: bool


class PaperBotEngine:
    """Deterministic paper signal and trade lifecycle — no exchange APIs."""

    WARMUP_BARS = 25

    def evaluate_no_trade_filters(
        self,
        rules: ParsedStrategyRules,
        *,
        no_trade_rules: list[str],
        funding_rate: Decimal | None = None,
    ) -> list[str]:
        blocked: list[str] = []
        joined = " ".join(no_trade_rules).lower()
        funding_extreme = (
            "funding" in joined
            and funding_rate is not None
            and abs(funding_rate) > Decimal("0.001")
        )
        if funding_extreme:
            blocked.append("no_trade: extreme funding rate")
        if not rules.machine_readable and no_trade_rules:
            blocked.append("no_trade: rules not machine testable")
        return blocked

    def evaluate_entry(
        self,
        rules: ParsedStrategyRules,
        rows: list[HistoricalCandleModel],
        *,
        engine_source: str,
    ) -> EntryEvaluation:
        if len(rows) < self.WARMUP_BARS + 2:
            return EntryEvaluation(False, None, None, "Insufficient candles.", [])

        if not rules.machine_readable:
            return EntryEvaluation(
                False,
                None,
                None,
                "Rules not machine testable — improve structured rules.",
                [],
            )

        idx = len(rows) - 1
        closes = [row.close for row in rows]
        ema20 = self._ema(closes, 20)
        signal = self._entry_signal(rules, rows, idx, ema20)
        if signal is None:
            return EntryEvaluation(False, None, None, "No entry setup on latest bar.", [])

        entry_price, stop, notes = signal
        return EntryEvaluation(
            True,
            entry_price,
            stop,
            notes,
            [engine_source, rules.entry_mode],
        )

    def open_trade_state(
        self,
        *,
        direction: TradeDirection,
        entry_time: datetime,
        entry_price: Decimal,
        stop_loss: Decimal,
        size: Decimal,
        rules: ParsedStrategyRules,
        fee_rate: Decimal,
        slip_rate: Decimal,
    ) -> _OpenPaperTrade:
        slip = entry_price * slip_rate
        fill = entry_price + slip if direction == TradeDirection.LONG else entry_price - slip
        entry_fees = fill * size * fee_rate
        tp_levels = self._tp_prices(fill, stop_loss, rules.tp_r_multiples, direction)
        return _OpenPaperTrade(
            direction=direction,
            entry_time=entry_time,
            entry_price=fill,
            stop_loss=stop_loss,
            size=size,
            tp_levels=tp_levels,
            tp_hit=0,
            use_runner=rules.use_runner,
            entry_fees=entry_fees,
            entry_slippage=slip * size,
        )

    def monitor_bar(
        self,
        trade: _OpenPaperTrade,
        bar: HistoricalCandleModel,
        *,
        fee_rate: Decimal,
        slip_rate: Decimal,
        timeout_bars: int,
    ) -> CloseEvaluation | None:
        trade.bars_open += 1
        closed = self._maybe_close(trade, bar=bar, fee_rate=fee_rate, slip_rate=slip_rate)
        if closed is not None:
            return closed
        if trade.bars_open >= timeout_bars:
            return self._close_at_price(
                trade,
                exit_time=bar.close_time,
                exit_price=bar.close,
                exit_reason="timeout",
                tp_status="timeout",
                fee_rate=fee_rate,
                slip_rate=slip_rate,
            )
        return None

    def _entry_signal(
        self,
        rules: ParsedStrategyRules,
        rows: list[HistoricalCandleModel],
        idx: int,
        ema20: list[Decimal],
    ) -> tuple[Decimal, Decimal, str] | None:
        bar = rows[idx]
        prev = rows[idx - 1]
        ema = ema20[idx]
        close = bar.close

        if rules.entry_mode == "pullback_ema" and rules.direction == TradeDirection.LONG:
            dipped = prev.low < ema and bar.low <= ema
            reclaimed = close > ema and prev.close <= ema
            if dipped and reclaimed:
                stop = close * (Decimal("1") - rules.stop_pct)
                return close, stop, "pullback_ema: reclaim above EMA20"
        if rules.entry_mode == "breakout":
            lookback = rows[max(0, idx - 20) : idx]
            prior_high = max(r.high for r in lookback)
            if close > prior_high and rules.direction == TradeDirection.LONG:
                stop = close * (Decimal("1") - rules.stop_pct)
                return close, stop, "breakout: close above 20-bar high"
        if rules.entry_mode == "liquidity_sweep":
            lookback = rows[max(0, idx - 15) : idx]
            swing_low = min(r.low for r in lookback)
            if bar.low < swing_low and close > swing_low:
                stop = bar.low * (Decimal("1") - rules.stop_pct / Decimal("2"))
                return close, stop, "liquidity_sweep: sweep and reclaim"
        return None

    def _maybe_close(
        self,
        trade: _OpenPaperTrade,
        *,
        bar: HistoricalCandleModel,
        fee_rate: Decimal,
        slip_rate: Decimal,
    ) -> CloseEvaluation | None:
        direction = trade.direction
        if direction == TradeDirection.LONG:
            stop_hit = bar.low <= trade.stop_loss
        else:
            stop_hit = bar.high >= trade.stop_loss
        if stop_hit:
            return self._close_at_price(
                trade,
                exit_time=bar.open_time,
                exit_price=trade.stop_loss,
                exit_reason="stop_loss",
                tp_status="none",
                fee_rate=fee_rate,
                slip_rate=slip_rate,
            )

        for level_idx, tp in enumerate(trade.tp_levels):
            if level_idx < trade.tp_hit:
                continue
            hit = bar.high >= tp if direction == TradeDirection.LONG else bar.low <= tp
            if hit:
                trade.tp_hit = level_idx + 1
                if level_idx < len(trade.tp_levels) - 1 and not trade.use_runner:
                    continue
                return self._close_at_price(
                    trade,
                    exit_time=bar.open_time,
                    exit_price=tp,
                    exit_reason=f"take_profit_{level_idx + 1}",
                    tp_status=f"tp{level_idx + 1}",
                    fee_rate=fee_rate,
                    slip_rate=slip_rate,
                )

        if trade.use_runner and trade.tp_hit >= 1:
            if direction == TradeDirection.LONG:
                trail = bar.close * Decimal("0.985")
            else:
                trail = bar.close * Decimal("1.015")
            runner_hit = (direction == TradeDirection.LONG and bar.close < trail) or (
                direction == TradeDirection.SHORT and bar.close > trail
            )
            if runner_hit:
                return self._close_at_price(
                    trade,
                    exit_time=bar.open_time,
                    exit_price=bar.close,
                    exit_reason="runner_trail",
                    tp_status=f"tp{trade.tp_hit}+runner",
                    fee_rate=fee_rate,
                    slip_rate=slip_rate,
                    runner_helped=True,
                )
        return None

    def _close_at_price(
        self,
        trade: _OpenPaperTrade,
        *,
        exit_time: datetime,
        exit_price: Decimal,
        exit_reason: str,
        tp_status: str,
        fee_rate: Decimal,
        slip_rate: Decimal,
        runner_helped: bool = False,
    ) -> CloseEvaluation:
        slip = exit_price * slip_rate
        fill = exit_price - slip if trade.direction == TradeDirection.LONG else exit_price + slip
        exit_fees = fill * trade.size * fee_rate
        gross = (
            (fill - trade.entry_price) * trade.size
            if trade.direction == TradeDirection.LONG
            else (trade.entry_price - fill) * trade.size
        )
        total_fees = trade.entry_fees + exit_fees
        total_slip = trade.entry_slippage + slip * trade.size
        net = gross - total_fees - total_slip
        stop_respected = exit_reason == "stop_loss"
        early_exit = exit_reason in {"runner_trail"} and trade.tp_hit == 0
        return CloseEvaluation(
            exit_time=exit_time,
            exit_price=fill,
            exit_reason=exit_reason,
            tp_status=tp_status,
            gross_pnl=gross,
            net_pnl=net,
            fees=total_fees,
            slippage=total_slip,
            stop_respected=stop_respected,
            early_exit=early_exit,
            runner_helped=runner_helped,
        )

    @staticmethod
    def _tp_prices(
        entry: Decimal,
        stop: Decimal,
        multiples: tuple[Decimal, ...],
        direction: TradeDirection,
    ) -> list[Decimal]:
        risk = abs(entry - stop)
        levels: list[Decimal] = []
        for mult in multiples:
            if direction == TradeDirection.LONG:
                levels.append(entry + risk * mult)
            else:
                levels.append(entry - risk * mult)
        return levels

    @staticmethod
    def _ema(values: list[Decimal], period: int) -> list[Decimal]:
        if not values:
            return []
        k = Decimal("2") / Decimal(str(period + 1))
        ema = values[0]
        out = [ema]
        for price in values[1:]:
            ema = price * k + ema * (Decimal("1") - k)
            out.append(ema)
        return out

    @staticmethod
    def default_lookback_days(timeframe: str) -> int:
        if timeframe in {"1m", "5m", "15m"}:
            return 14
        if timeframe in {"1h", "4h"}:
            return 30
        return 90

    @staticmethod
    def bar_duration(timeframe: str) -> timedelta:
        mapping = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
        }
        return mapping.get(timeframe, timedelta(hours=1))
