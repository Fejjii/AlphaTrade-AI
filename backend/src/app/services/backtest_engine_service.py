"""Deterministic backtest engine v1 (Slice 35 — historical simulation only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import BacktestRun as BacktestRunModel
from app.db.models import BacktestTrade as BacktestTradeModel
from app.db.models import HistoricalCandle as HistoricalCandleModel
from app.repositories.backtest_trades import BacktestTradeRepository
from app.schemas.backtest import (
    BacktestAssumptions,
    BacktestMetrics,
    BacktestResult,
    BacktestTradeRecord,
    EquityCurvePoint,
)
from app.schemas.common import BacktestRecommendation, TradeDirection
from app.schemas.strategy_library import StrategyCard
from app.services.historical_candle_service import HistoricalCandleService
from app.services.strategy_promotion import evaluate_promotion
from app.services.strategy_rule_adapter import ParsedStrategyRules, parse_strategy_rules


@dataclass
class _OpenTrade:
    direction: TradeDirection
    entry_time: datetime
    entry_price: Decimal
    stop_loss: Decimal
    size: Decimal
    risk_per_unit: Decimal
    tp_levels: list[Decimal]
    tp_hit: int
    use_runner: bool
    rule_notes: str
    entry_fees: Decimal
    entry_slippage: Decimal


class BacktestEngineService:
    WARMUP_BARS = 25

    def __init__(
        self,
        session: Session,
        candle_service: HistoricalCandleService,
    ) -> None:
        self._session = session
        self._candles = candle_service
        self._trades = BacktestTradeRepository(session)

    def run(
        self,
        *,
        run: BacktestRunModel,
        card: StrategyCard,
        setup_type: object,
    ) -> BacktestResult:
        assumptions = BacktestAssumptions.model_validate(run.assumptions or {})
        rules = parse_strategy_rules(card, setup_type)  # type: ignore[arg-type]

        if not rules.machine_readable:
            return BacktestResult(
                metrics=self._empty_metrics(assumptions),
                trades=[],
                recommendation=BacktestRecommendation.NEEDS_STRUCTURED_RULES,
                limitations=[rules.limitation or "Rules not machine readable."],
                data_quality="n/a",
            )

        start_date = assumptions.start_date or (datetime.now(UTC) - timedelta(days=90)).date()
        end_date = assumptions.end_date or datetime.now(UTC).date()
        candle_rows, data_limitations = self._candles.ensure_candles_for_backtest(
            symbol=assumptions.symbol,
            exchange=assumptions.exchange,
            timeframe=assumptions.timeframe,
            start_date=start_date,
            end_date=end_date,
        )
        data_quality = "ok" if not data_limitations else "degraded"
        if len(candle_rows) < self.WARMUP_BARS + 10:
            limitations = [*data_limitations, "Insufficient candles for backtest v1."]
            return BacktestResult(
                metrics=self._empty_metrics(assumptions),
                trades=[],
                recommendation=BacktestRecommendation.UNRELIABLE_DATA,
                limitations=limitations,
                data_quality="unreliable",
            )

        fee_rate = assumptions.fees_bps / Decimal("10000")
        slip_rate = assumptions.slippage_bps / Decimal("10000")
        equity = assumptions.initial_capital
        peak_equity = equity
        max_dd = Decimal("0")
        equity_curve: list[EquityCurvePoint] = []
        simulated: list[BacktestTradeRecord] = []
        open_trade: _OpenTrade | None = None
        max_trades = assumptions.max_trades or 500

        closes = [row.close for row in candle_rows]
        ema20 = self._ema(closes, 20)

        for idx in range(self.WARMUP_BARS, len(candle_rows)):
            bar = candle_rows[idx]
            equity_curve.append(EquityCurvePoint(timestamp=bar.open_time, equity=equity))

            if open_trade is not None:
                closed = self._maybe_close_trade(
                    open_trade,
                    bar=bar,
                    fee_rate=fee_rate,
                    slip_rate=slip_rate,
                )
                if closed is not None:
                    trade, pnl = closed
                    equity += pnl
                    simulated.append(trade)
                    open_trade = None
                    peak_equity = max(peak_equity, equity)
                    if peak_equity:
                        dd = (peak_equity - equity) / peak_equity * Decimal("100")
                    else:
                        dd = Decimal("0")
                    max_dd = max(max_dd, dd)
                    if len(simulated) >= max_trades:
                        break

            if open_trade is None and len(simulated) < max_trades:
                signal = self._entry_signal(rules, candle_rows, idx, ema20)
                if signal:
                    entry_price, stop, notes = signal
                    risk_capital = equity * (assumptions.risk_per_trade_pct / Decimal("100"))
                    risk_per_unit = abs(entry_price - stop)
                    if risk_per_unit <= 0:
                        continue
                    size = risk_capital / risk_per_unit
                    slip = entry_price * slip_rate
                    if rules.direction == TradeDirection.LONG:
                        fill = entry_price + slip
                    else:
                        fill = entry_price - slip
                    entry_fees = fill * size * fee_rate
                    tp_levels = self._tp_prices(fill, stop, rules.tp_r_multiples, rules.direction)
                    open_trade = _OpenTrade(
                        direction=rules.direction,
                        entry_time=bar.open_time,
                        entry_price=fill,
                        stop_loss=stop,
                        size=size,
                        risk_per_unit=risk_per_unit,
                        tp_levels=tp_levels,
                        tp_hit=0,
                        use_runner=rules.use_runner,
                        rule_notes=notes,
                        entry_fees=entry_fees,
                        entry_slippage=slip * size,
                    )

        if open_trade is not None:
            last = candle_rows[-1]
            trade, pnl = self._force_close(
                open_trade,
                bar=last,
                fee_rate=fee_rate,
                slip_rate=slip_rate,
            )
            equity += pnl
            simulated.append(trade)

        metrics = self._compute_metrics(
            simulated,
            assumptions=assumptions,
            equity_curve=equity_curve,
            max_dd=max_dd,
            ending_equity=equity,
        )
        meets = self._meets_success_criteria(card, metrics)
        promotion = evaluate_promotion(
            metrics=metrics,
            machine_readable=True,
            data_quality=data_quality,
            meets_success_criteria=meets,
        )
        limitations = data_limitations + promotion.limitations
        if metrics.trade_count < 30:
            limitations.append("Small sample size — treat metrics as indicative only.")

        result = BacktestResult(
            metrics=metrics,
            trades=simulated,
            recommendation=promotion.recommendation,
            meets_success_criteria=meets,
            limitations=limitations,
            data_quality=data_quality,
        )

        for trade in simulated:
            self._trades.add(
                BacktestTradeModel(
                    backtest_run_id=run.id,
                    entry_time=trade.entry_time,
                    exit_time=trade.exit_time,
                    direction=trade.direction.value,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    stop_loss=trade.stop_loss,
                    size=trade.size,
                    fees=trade.fees,
                    slippage_cost=trade.slippage_cost,
                    gross_pnl=trade.gross_pnl,
                    net_pnl=trade.net_pnl,
                    tp_hit_status=trade.tp_hit_status,
                    exit_reason=trade.exit_reason,
                    rule_notes=trade.rule_notes,
                )
            )

        run.result = result.model_dump(mode="json")
        return result

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

    def _maybe_close_trade(
        self,
        trade: _OpenTrade,
        *,
        bar: HistoricalCandleModel,
        fee_rate: Decimal,
        slip_rate: Decimal,
    ) -> tuple[BacktestTradeRecord, Decimal] | None:
        direction = trade.direction
        if direction == TradeDirection.LONG:
            stop_hit = bar.low <= trade.stop_loss
        else:
            stop_hit = bar.high >= trade.stop_loss
        if stop_hit:
            exit_price = trade.stop_loss
            return self._build_trade_record(
                trade,
                exit_time=bar.open_time,
                exit_price=exit_price,
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
                exit_price = tp
                return self._build_trade_record(
                    trade,
                    exit_time=bar.open_time,
                    exit_price=exit_price,
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
            if direction == TradeDirection.LONG and bar.close < trail:
                return self._build_trade_record(
                    trade,
                    exit_time=bar.open_time,
                    exit_price=bar.close,
                    exit_reason="runner_trail",
                    tp_status=f"tp{trade.tp_hit}+runner",
                    fee_rate=fee_rate,
                    slip_rate=slip_rate,
                )
        return None

    def _force_close(
        self,
        trade: _OpenTrade,
        *,
        bar: HistoricalCandleModel,
        fee_rate: Decimal,
        slip_rate: Decimal,
    ) -> tuple[BacktestTradeRecord, Decimal]:
        record, pnl = self._build_trade_record(
            trade,
            exit_time=bar.close_time,
            exit_price=bar.close,
            exit_reason="end_of_data",
            tp_status="partial" if trade.tp_hit else "none",
            fee_rate=fee_rate,
            slip_rate=slip_rate,
        )
        return record, pnl

    def _build_trade_record(
        self,
        trade: _OpenTrade,
        *,
        exit_time: datetime,
        exit_price: Decimal,
        exit_reason: str,
        tp_status: str,
        fee_rate: Decimal,
        slip_rate: Decimal,
    ) -> tuple[BacktestTradeRecord, Decimal]:
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
        record = BacktestTradeRecord(
            entry_time=trade.entry_time,
            exit_time=exit_time,
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=fill,
            stop_loss=trade.stop_loss,
            size=trade.size,
            fees=total_fees,
            slippage_cost=total_slip,
            gross_pnl=gross,
            net_pnl=net,
            tp_hit_status=tp_status,
            exit_reason=exit_reason,
            rule_notes=trade.rule_notes,
        )
        return record, net

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
    def _empty_metrics(assumptions: BacktestAssumptions) -> BacktestMetrics:
        return BacktestMetrics(
            trade_count=0,
            win_rate=0.0,
            profit_factor=0.0,
            expectancy=Decimal("0"),
            max_drawdown_pct=0.0,
            average_win=Decimal("0"),
            average_loss=Decimal("0"),
            largest_win=Decimal("0"),
            largest_loss=Decimal("0"),
            consecutive_losses=0,
            average_time_in_trade_bars=0.0,
            total_fees=Decimal("0"),
            total_slippage=Decimal("0"),
            net_pnl=Decimal("0"),
            return_pct=0.0,
            ending_equity=assumptions.initial_capital,
            equity_curve=[],
            symbol=assumptions.symbol,
            timeframe=assumptions.timeframe.value,
        )

    def _compute_metrics(
        self,
        trades: list[BacktestTradeRecord],
        *,
        assumptions: BacktestAssumptions,
        equity_curve: list[EquityCurvePoint],
        max_dd: Decimal,
        ending_equity: Decimal,
    ) -> BacktestMetrics:
        if not trades:
            return self._empty_metrics(assumptions)

        wins = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl <= 0]
        gross_profit = sum((t.net_pnl for t in wins), Decimal("0"))
        gross_loss = abs(sum((t.net_pnl for t in losses), Decimal("0")))
        pf = float(gross_profit / gross_loss) if gross_loss > 0 else float(gross_profit)
        net = sum((t.net_pnl for t in trades), Decimal("0"))
        expectancy = net / Decimal(str(len(trades)))
        total_fees = sum((t.fees for t in trades), Decimal("0"))
        total_slip = sum((t.slippage_cost for t in trades), Decimal("0"))

        streak = 0
        max_streak = 0
        for t in trades:
            if t.net_pnl <= 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        bar_durations = [
            max(1.0, (t.exit_time - t.entry_time).total_seconds() / 3600) for t in trades
        ]
        avg_bars = sum(bar_durations) / len(bar_durations)

        return BacktestMetrics(
            trade_count=len(trades),
            win_rate=len(wins) / len(trades),
            profit_factor=pf,
            expectancy=expectancy,
            max_drawdown_pct=float(max_dd),
            average_win=gross_profit / Decimal(str(len(wins))) if wins else Decimal("0"),
            average_loss=-gross_loss / Decimal(str(len(losses))) if losses else Decimal("0"),
            largest_win=max((t.net_pnl for t in trades), default=Decimal("0")),
            largest_loss=min((t.net_pnl for t in trades), default=Decimal("0")),
            consecutive_losses=max_streak,
            average_time_in_trade_bars=avg_bars,
            total_fees=total_fees,
            total_slippage=total_slip,
            net_pnl=net,
            return_pct=float(net / assumptions.initial_capital * Decimal("100")),
            ending_equity=ending_equity,
            equity_curve=equity_curve[-200:],
            symbol=assumptions.symbol,
            timeframe=assumptions.timeframe.value,
        )

    @staticmethod
    def _meets_success_criteria(card: StrategyCard, metrics: BacktestMetrics) -> bool:
        if not card.success_criteria:
            return metrics.win_rate >= 0.45 and metrics.profit_factor >= 1.1
        joined = " ".join(card.success_criteria).lower()
        if "win rate" in joined and metrics.win_rate < 0.45:
            return False
        if "profit factor" in joined and metrics.profit_factor < 1.1:
            return False
        return metrics.expectancy > 0 and metrics.trade_count >= 10
