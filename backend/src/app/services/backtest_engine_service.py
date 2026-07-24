"""Deterministic backtest engine v2 (AT-034 — historical simulation only).

Intra-bar ambiguity invariant: when both stop and take-profit are touched
within the same bar, the stop wins (conservative). This matches v1 ordering.

Simulation is a pure function of (assumptions, candle rows, rules): no
wall-clock reads inside the bar loop. Callers freeze start/end dates at the
call boundary; a thin default resolves dates once at ``run()`` entry for
backward compatibility.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import floor
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import BacktestRun as BacktestRunModel
from app.db.models import BacktestTrade as BacktestTradeModel
from app.db.models import HistoricalCandle as HistoricalCandleModel
from app.providers.market_data import TIMEFRAME_SECONDS
from app.repositories.backtest_trades import BacktestTradeRepository
from app.schemas.backtest import (
    BacktestAssumptions,
    BacktestDatasetSummary,
    BacktestMetrics,
    BacktestResult,
    BacktestSplitConfig,
    BacktestSplitMetrics,
    BacktestSplitMode,
    BacktestTradeRecord,
    EquityCurvePoint,
)
from app.schemas.common import (
    BacktestRecommendation,
    BacktestSplitLabel,
    TradeDirection,
)
from app.schemas.strategy_library import StrategyCard
from app.schemas.structured_rules import StructuredRules
from app.services.backtest_dataset_service import BacktestDatasetService
from app.services.backtest_hashing import canonical_json_hash
from app.services.historical_candle_service import HistoricalCandleService
from app.services.strategy_promotion import evaluate_promotion
from app.services.strategy_rule_adapter import ParsedStrategyRules
from app.services.structured_rule_resolver import resolve_backtest_rules

ENGINE_VERSION = "at034-2.0.0"
_CANCEL_CHECK_EVERY = 2000
_MIN_SEGMENT_BARS = 25 + 10  # WARMUP_BARS + 10
_ZERO = Decimal("0")
_FUNDING_PERIOD_SECONDS = Decimal("28800")  # 8 hours


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
    entry_idx: int
    funding_cost: Decimal = _ZERO
    mfe_price: Decimal | None = None
    mae_price: Decimal | None = None
    bars_held: int = 0


@dataclass(frozen=True)
class _Segment:
    label: BacktestSplitLabel
    split_index: int
    start_idx: int
    end_idx: int  # exclusive


@dataclass
class _SimState:
    equity: Decimal
    peak_equity: Decimal
    max_dd: Decimal
    equity_curve: list[EquityCurvePoint] = field(default_factory=list)
    trades: list[BacktestTradeRecord] = field(default_factory=list)
    sequence: int = 0
    processed_bars: int = 0
    cancelled: bool = False


class BacktestEngineService:
    WARMUP_BARS = 25

    def __init__(
        self,
        session: Session,
        candle_service: HistoricalCandleService,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._candles = candle_service
        self._settings = settings or get_settings()
        self._trades = BacktestTradeRepository(session)
        self._datasets = BacktestDatasetService(session, candle_service)

    def run(
        self,
        *,
        run: BacktestRunModel,
        card: StrategyCard,
        setup_type: object,
        structured_rules: StructuredRules | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> BacktestResult:
        assumptions = BacktestAssumptions.model_validate(run.assumptions or {})
        resolved = resolve_backtest_rules(card, setup_type, structured_rules)  # type: ignore[arg-type]
        rules = resolved.rules
        engine_source = resolved.engine_source.value

        if not rules.machine_readable:
            return self._finalize_early(
                run,
                BacktestResult(
                    metrics=self._empty_metrics(assumptions),
                    trades=[],
                    recommendation=BacktestRecommendation.NEEDS_STRUCTURED_RULES,
                    limitations=[rules.limitation or "Rules not machine readable."],
                    data_quality="n/a",
                    rule_engine_source=engine_source,
                    engine_version=ENGINE_VERSION,
                ),
            )

        # Freeze dates once at call boundary (no wall-clock inside the bar loop).
        resolved_start = start_date or assumptions.start_date
        resolved_end = end_date or assumptions.end_date
        if resolved_start is None:
            resolved_start = (datetime.now(UTC) - timedelta(days=90)).date()
        if resolved_end is None:
            resolved_end = datetime.now(UTC).date()

        dataset, candle_rows, data_limitations = self._datasets.ensure_dataset(
            symbol=assumptions.symbol,
            exchange=assumptions.exchange,
            timeframe=assumptions.timeframe,
            start_date=resolved_start,
            end_date=resolved_end,
        )
        run.dataset_id = dataset.id
        dataset_summary = BacktestDatasetSummary(
            dataset_hash=dataset.dataset_hash,
            candle_count=dataset.candle_count,
            gap_count=dataset.gap_count,
            stale_count=dataset.stale_count,
            first_open_time=dataset.first_open_time,
            last_open_time=dataset.last_open_time,
            source_counts=dict(dataset.source_counts or {}),
        )
        data_quality = "ok" if not data_limitations else "degraded"
        max_bars = self._settings.backtest_max_bars
        total_bars = len(candle_rows)
        run.total_bars = total_bars

        if total_bars > max_bars:
            limitations = [
                *data_limitations,
                f"Dataset exceeds backtest_max_bars={max_bars} "
                f"(candle_count={total_bars}); truncate is not allowed.",
            ]
            return self._finalize_early(
                run,
                BacktestResult(
                    metrics=self._empty_metrics(assumptions),
                    trades=[],
                    recommendation=BacktestRecommendation.UNRELIABLE_DATA,
                    limitations=limitations,
                    data_quality="unreliable",
                    rule_engine_source=engine_source,
                    engine_version=ENGINE_VERSION,
                    dataset_summary=dataset_summary,
                    processed_bars=0,
                    total_bars=total_bars,
                ),
            )

        if total_bars < self.WARMUP_BARS + 10:
            limitations = [*data_limitations, "Insufficient candles for backtest v2."]
            return self._finalize_early(
                run,
                BacktestResult(
                    metrics=self._empty_metrics(assumptions),
                    trades=[],
                    recommendation=BacktestRecommendation.UNRELIABLE_DATA,
                    limitations=limitations,
                    data_quality="unreliable",
                    rule_engine_source=engine_source,
                    engine_version=ENGINE_VERSION,
                    dataset_summary=dataset_summary,
                    processed_bars=0,
                    total_bars=total_bars,
                ),
            )

        split_config = assumptions.split_config or BacktestSplitConfig()
        segments = self._build_segments(len(candle_rows), split_config)
        skip_notes: list[str] = []
        runnable: list[_Segment] = []
        for seg in segments:
            length = seg.end_idx - seg.start_idx
            if length < _MIN_SEGMENT_BARS:
                skip_notes.append(
                    f"Skipped segment {seg.label.value}[{seg.split_index}] "
                    f"({length} bars < {_MIN_SEGMENT_BARS})."
                )
                continue
            runnable.append(seg)

        fee_rate = assumptions.fees_bps / Decimal("10000")
        slip_rate = assumptions.slippage_bps / Decimal("10000")
        trail_pct = assumptions.runner_trail_pct / Decimal("100")
        funding_rate = assumptions.funding_rate_bps_per_8h
        tf_seconds = Decimal(str(TIMEFRAME_SECONDS.get(assumptions.timeframe, 3600)))
        max_trades = assumptions.max_trades or 500

        state = _SimState(
            equity=assumptions.initial_capital,
            peak_equity=assumptions.initial_capital,
            max_dd=_ZERO,
        )
        split_trade_buckets: dict[tuple[BacktestSplitLabel, int], list[BacktestTradeRecord]] = {}
        split_equity_start: dict[tuple[BacktestSplitLabel, int], Decimal] = {}
        split_windows: dict[tuple[BacktestSplitLabel, int], tuple[datetime, datetime]] = {}

        for seg in runnable:
            if should_cancel is not None and should_cancel():
                state.cancelled = True
                break

            seg_rows = candle_rows[seg.start_idx : seg.end_idx]
            key = (seg.label, seg.split_index)
            split_equity_start.setdefault(key, state.equity)
            split_windows[key] = (seg_rows[0].open_time, seg_rows[-1].close_time)
            split_trade_buckets.setdefault(key, [])

            seg_trades, cancelled = self._simulate_segment(
                seg_rows,
                assumptions=assumptions,
                rules=rules,
                fee_rate=fee_rate,
                slip_rate=slip_rate,
                trail_pct=trail_pct,
                funding_rate=funding_rate,
                tf_seconds=tf_seconds,
                max_trades=max_trades,
                state=state,
                split_label=seg.label,
                split_index=seg.split_index,
                should_cancel=should_cancel,
            )
            split_trade_buckets[key].extend(seg_trades)
            if cancelled:
                state.cancelled = True
                break

        metrics = self._compute_metrics(
            state.trades,
            assumptions=assumptions,
            equity_curve=state.equity_curve,
            max_dd=state.max_dd,
            ending_equity=state.equity,
        )
        split_metrics = self._build_split_metrics(
            split_trade_buckets,
            split_equity_start,
            split_windows,
        )
        oos_metrics = self._aggregate_oos_metrics(
            state.trades,
            split_equity_start,
            split_windows,
        )

        meets = self._meets_success_criteria(card, metrics)
        promotion = evaluate_promotion(
            metrics=metrics,
            machine_readable=True,
            data_quality=data_quality,
            meets_success_criteria=meets,
        )
        limitations = data_limitations + skip_notes + promotion.limitations
        if metrics.trade_count < 30 and not state.cancelled:
            limitations.append("Small sample size — treat metrics as indicative only.")

        result_hash = self._hash_result(state.trades, metrics)
        result = BacktestResult(
            metrics=metrics,
            trades=state.trades,
            recommendation=promotion.recommendation,
            meets_success_criteria=meets,
            limitations=limitations,
            data_quality=data_quality,
            rule_engine_source=engine_source,
            result_hash=result_hash,
            engine_version=ENGINE_VERSION,
            split_metrics=split_metrics or None,
            oos_metrics=oos_metrics,
            dataset_summary=dataset_summary,
            cancelled=state.cancelled,
            processed_bars=state.processed_bars,
            total_bars=total_bars,
        )

        for trade in state.trades:
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
                    mfe_price=trade.mfe_price,
                    mae_price=trade.mae_price,
                    mfe_amount=trade.mfe_amount,
                    mae_amount=trade.mae_amount,
                    available_profit=trade.available_profit,
                    capture_pct=trade.capture_pct,
                    funding_cost=trade.funding_cost,
                    split_label=trade.split_label.value,
                    split_index=trade.split_index,
                    sequence=trade.sequence,
                )
            )

        run.result = result.model_dump(mode="json")
        run.result_hash = result_hash
        run.engine_version = ENGINE_VERSION
        run.processed_bars = state.processed_bars
        run.total_bars = total_bars
        return result

    def _finalize_early(self, run: BacktestRunModel, result: BacktestResult) -> BacktestResult:
        result_hash = self._hash_result(result.trades, result.metrics)
        result = result.model_copy(
            update={
                "result_hash": result_hash,
                "engine_version": ENGINE_VERSION,
            }
        )
        run.result = result.model_dump(mode="json")
        run.result_hash = result_hash
        run.engine_version = ENGINE_VERSION
        if result.processed_bars is not None:
            run.processed_bars = result.processed_bars
        if result.total_bars is not None:
            run.total_bars = result.total_bars
        return result

    def _simulate_segment(
        self,
        candle_rows: list[HistoricalCandleModel],
        *,
        assumptions: BacktestAssumptions,
        rules: ParsedStrategyRules,
        fee_rate: Decimal,
        slip_rate: Decimal,
        trail_pct: Decimal,
        funding_rate: Decimal,
        tf_seconds: Decimal,
        max_trades: int,
        state: _SimState,
        split_label: BacktestSplitLabel,
        split_index: int,
        should_cancel: Callable[[], bool] | None,
    ) -> tuple[list[BacktestTradeRecord], bool]:
        seg_trades: list[BacktestTradeRecord] = []
        open_trade: _OpenTrade | None = None
        closes = [row.close for row in candle_rows]
        ema20 = self._ema(closes, 20)
        cancelled = False

        for idx in range(self.WARMUP_BARS, len(candle_rows)):
            state.processed_bars += 1
            if (
                should_cancel is not None
                and state.processed_bars % _CANCEL_CHECK_EVERY == 0
                and should_cancel()
            ):
                cancelled = True
                break

            bar = candle_rows[idx]
            state.equity_curve.append(
                EquityCurvePoint(timestamp=bar.open_time, equity=state.equity)
            )

            if open_trade is not None:
                self._update_excursions(open_trade, bar)
                self._accrue_funding(open_trade, funding_rate, tf_seconds)
                closed = self._maybe_close_trade(
                    open_trade,
                    bar=bar,
                    fee_rate=fee_rate,
                    slip_rate=slip_rate,
                    trail_pct=trail_pct,
                    split_label=split_label,
                    split_index=split_index,
                    sequence=state.sequence,
                )
                if closed is not None:
                    trade, pnl = closed
                    state.equity += pnl
                    state.trades.append(trade)
                    seg_trades.append(trade)
                    state.sequence += 1
                    open_trade = None
                    state.peak_equity = max(state.peak_equity, state.equity)
                    if state.peak_equity:
                        dd = (state.peak_equity - state.equity) / state.peak_equity * Decimal("100")
                    else:
                        dd = _ZERO
                    state.max_dd = max(state.max_dd, dd)
                    if len(state.trades) >= max_trades:
                        break

            if open_trade is None and len(state.trades) < max_trades:
                signal = self._entry_signal(rules, candle_rows, idx, ema20)
                if signal:
                    entry_price, stop, notes = signal
                    risk_capital = state.equity * (assumptions.risk_per_trade_pct / Decimal("100"))
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
                        entry_time=bar.close_time,
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
                        entry_idx=idx,
                        mfe_price=fill,
                        mae_price=fill,
                    )
                    self._update_excursions(open_trade, bar)

        if open_trade is not None:
            last = candle_rows[-1]
            if cancelled and state.equity_curve:
                last_ts = state.equity_curve[-1].timestamp
                for row in reversed(candle_rows):
                    if row.open_time == last_ts:
                        last = row
                        break
            self._update_excursions(open_trade, last)
            trade, pnl = self._force_close(
                open_trade,
                bar=last,
                fee_rate=fee_rate,
                slip_rate=slip_rate,
                split_label=split_label,
                split_index=split_index,
                sequence=state.sequence,
            )
            state.equity += pnl
            state.trades.append(trade)
            seg_trades.append(trade)
            state.sequence += 1

        return seg_trades, cancelled

    @staticmethod
    def _build_segments(n_bars: int, split_config: BacktestSplitConfig) -> list[_Segment]:
        mode = split_config.mode
        if mode == BacktestSplitMode.NONE:
            return [
                _Segment(
                    label=BacktestSplitLabel.IN_SAMPLE,
                    split_index=0,
                    start_idx=0,
                    end_idx=n_bars,
                )
            ]

        if mode == BacktestSplitMode.HOLDOUT:
            boundary = floor(n_bars * (1.0 - split_config.oos_fraction))
            return [
                _Segment(
                    label=BacktestSplitLabel.IN_SAMPLE,
                    split_index=0,
                    start_idx=0,
                    end_idx=boundary,
                ),
                _Segment(
                    label=BacktestSplitLabel.OUT_OF_SAMPLE,
                    split_index=1,
                    start_idx=boundary,
                    end_idx=n_bars,
                ),
            ]

        # rolling
        window = split_config.window_bars or 100
        step = split_config.step_bars or 50
        segments: list[_Segment] = []
        window_idx = 0
        start = 0
        while start + window <= n_bars:
            is_end = start + floor(window * (1.0 - split_config.oos_fraction))
            oos_end = start + window
            segments.append(
                _Segment(
                    label=BacktestSplitLabel.IN_SAMPLE,
                    split_index=window_idx,
                    start_idx=start,
                    end_idx=is_end,
                )
            )
            segments.append(
                _Segment(
                    label=BacktestSplitLabel.OUT_OF_SAMPLE,
                    split_index=window_idx,
                    start_idx=is_end,
                    end_idx=oos_end,
                )
            )
            window_idx += 1
            start += step
        return segments

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

        if rules.entry_mode == "pullback_ema":
            if rules.direction == TradeDirection.LONG:
                dipped = prev.low < ema and bar.low <= ema
                reclaimed = close > ema and prev.close <= ema
                if dipped and reclaimed:
                    stop = close * (Decimal("1") - rules.stop_pct)
                    return close, stop, "pullback_ema: reclaim above EMA20"
            elif rules.direction == TradeDirection.SHORT:
                poked = prev.high > ema and bar.high >= ema
                rejected = close < ema and prev.close >= ema
                if poked and rejected:
                    stop = close * (Decimal("1") + rules.stop_pct)
                    return close, stop, "pullback_ema: reject below EMA20"

        if rules.entry_mode == "breakout":
            lookback = rows[max(0, idx - 20) : idx]
            if rules.direction == TradeDirection.LONG:
                prior_high = max(r.high for r in lookback)
                if close > prior_high:
                    stop = close * (Decimal("1") - rules.stop_pct)
                    return close, stop, "breakout: close above 20-bar high"
            elif rules.direction == TradeDirection.SHORT:
                prior_low = min(r.low for r in lookback)
                if close < prior_low:
                    stop = close * (Decimal("1") + rules.stop_pct)
                    return close, stop, "breakout: close below 20-bar low"

        if rules.entry_mode == "liquidity_sweep":
            lookback = rows[max(0, idx - 15) : idx]
            if rules.direction == TradeDirection.LONG:
                swing_low = min(r.low for r in lookback)
                if bar.low < swing_low and close > swing_low:
                    stop = bar.low * (Decimal("1") - rules.stop_pct / Decimal("2"))
                    return close, stop, "liquidity_sweep: sweep and reclaim"
            elif rules.direction == TradeDirection.SHORT:
                swing_high = max(r.high for r in lookback)
                if bar.high > swing_high and close < swing_high:
                    stop = bar.high * (Decimal("1") + rules.stop_pct / Decimal("2"))
                    return close, stop, "liquidity_sweep: sweep high and reject"
        return None

    @staticmethod
    def _update_excursions(trade: _OpenTrade, bar: HistoricalCandleModel) -> None:
        if trade.direction == TradeDirection.LONG:
            trade.mfe_price = (
                bar.high if trade.mfe_price is None else max(trade.mfe_price, bar.high)
            )
            trade.mae_price = bar.low if trade.mae_price is None else min(trade.mae_price, bar.low)
        else:
            trade.mfe_price = bar.low if trade.mfe_price is None else min(trade.mfe_price, bar.low)
            trade.mae_price = (
                bar.high if trade.mae_price is None else max(trade.mae_price, bar.high)
            )
        trade.bars_held += 1

    @staticmethod
    def _accrue_funding(
        trade: _OpenTrade,
        funding_rate_bps_per_8h: Decimal,
        tf_seconds: Decimal,
    ) -> None:
        if funding_rate_bps_per_8h == _ZERO:
            return
        # Positive rate: longs pay (positive cost), shorts receive (negative cost).
        notional = trade.entry_price * trade.size
        period_frac = tf_seconds / _FUNDING_PERIOD_SECONDS
        bar_cost = notional * (funding_rate_bps_per_8h / Decimal("10000")) * period_frac
        if trade.direction == TradeDirection.SHORT:
            bar_cost = -bar_cost
        trade.funding_cost += bar_cost

    def _maybe_close_trade(
        self,
        trade: _OpenTrade,
        *,
        bar: HistoricalCandleModel,
        fee_rate: Decimal,
        slip_rate: Decimal,
        trail_pct: Decimal,
        split_label: BacktestSplitLabel,
        split_index: int,
        sequence: int,
    ) -> tuple[BacktestTradeRecord, Decimal] | None:
        direction = trade.direction
        if direction == TradeDirection.LONG:
            stop_hit = bar.low <= trade.stop_loss
        else:
            stop_hit = bar.high >= trade.stop_loss
        if stop_hit:
            return self._build_trade_record(
                trade,
                exit_time=bar.open_time,
                exit_price=trade.stop_loss,
                exit_reason="stop_loss",
                tp_status="none",
                fee_rate=fee_rate,
                slip_rate=slip_rate,
                split_label=split_label,
                split_index=split_index,
                sequence=sequence,
            )

        for level_idx, tp in enumerate(trade.tp_levels):
            if level_idx < trade.tp_hit:
                continue
            hit = bar.high >= tp if direction == TradeDirection.LONG else bar.low <= tp
            if hit:
                trade.tp_hit = level_idx + 1
                if level_idx < len(trade.tp_levels) - 1 and not trade.use_runner:
                    continue
                return self._build_trade_record(
                    trade,
                    exit_time=bar.open_time,
                    exit_price=tp,
                    exit_reason=f"take_profit_{level_idx + 1}",
                    tp_status=f"tp{level_idx + 1}",
                    fee_rate=fee_rate,
                    slip_rate=slip_rate,
                    split_label=split_label,
                    split_index=split_index,
                    sequence=sequence,
                )

        if trade.use_runner and trade.tp_hit >= 1:
            if direction == TradeDirection.LONG:
                trail = bar.close * (Decimal("1") - trail_pct)
                runner_hit = bar.low <= trail
            else:
                trail = bar.close * (Decimal("1") + trail_pct)
                runner_hit = bar.high >= trail
            if runner_hit:
                return self._build_trade_record(
                    trade,
                    exit_time=bar.close_time,
                    exit_price=bar.close,
                    exit_reason="runner_trail",
                    tp_status=f"tp{trade.tp_hit}+runner",
                    fee_rate=fee_rate,
                    slip_rate=slip_rate,
                    split_label=split_label,
                    split_index=split_index,
                    sequence=sequence,
                )
        return None

    def _force_close(
        self,
        trade: _OpenTrade,
        *,
        bar: HistoricalCandleModel,
        fee_rate: Decimal,
        slip_rate: Decimal,
        split_label: BacktestSplitLabel,
        split_index: int,
        sequence: int,
    ) -> tuple[BacktestTradeRecord, Decimal]:
        return self._build_trade_record(
            trade,
            exit_time=bar.close_time,
            exit_price=bar.close,
            exit_reason="end_of_data",
            tp_status="partial" if trade.tp_hit else "none",
            fee_rate=fee_rate,
            slip_rate=slip_rate,
            split_label=split_label,
            split_index=split_index,
            sequence=sequence,
        )

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
        split_label: BacktestSplitLabel,
        split_index: int,
        sequence: int,
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
        funding = trade.funding_cost
        net = gross - total_fees - total_slip - funding

        mfe_price = trade.mfe_price if trade.mfe_price is not None else trade.entry_price
        mae_price = trade.mae_price if trade.mae_price is not None else trade.entry_price
        if trade.direction == TradeDirection.LONG:
            mfe_amount = (mfe_price - trade.entry_price) * trade.size
            mae_amount = (mae_price - trade.entry_price) * trade.size
        else:
            mfe_amount = (trade.entry_price - mfe_price) * trade.size
            mae_amount = (trade.entry_price - mae_price) * trade.size
        available = mfe_amount if mfe_amount > _ZERO else _ZERO
        capture: Decimal | None
        capture = None if available == _ZERO else net / available * Decimal("100")

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
            mfe_price=mfe_price,
            mae_price=mae_price,
            mfe_amount=mfe_amount,
            mae_amount=mae_amount,
            available_profit=available,
            capture_pct=capture,
            funding_cost=funding,
            split_label=split_label,
            split_index=split_index,
            sequence=sequence,
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
            total_funding=Decimal("0"),
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
        total_funding = sum((t.funding_cost for t in trades), Decimal("0"))

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
            total_funding=total_funding,
            net_pnl=net,
            return_pct=float(net / assumptions.initial_capital * Decimal("100")),
            ending_equity=ending_equity,
            equity_curve=equity_curve[-200:],
            symbol=assumptions.symbol,
            timeframe=assumptions.timeframe.value,
        )

    def _compact_metrics(
        self,
        trades: list[BacktestTradeRecord],
        *,
        split_label: BacktestSplitLabel,
        split_index: int,
        start_time: datetime,
        end_time: datetime,
        start_equity: Decimal,
    ) -> BacktestSplitMetrics:
        if not trades:
            return BacktestSplitMetrics(
                split_label=split_label,
                split_index=split_index,
                start_time=start_time,
                end_time=end_time,
                trade_count=0,
                win_rate=0.0,
                profit_factor=0.0,
                expectancy=_ZERO,
                net_pnl=_ZERO,
                max_drawdown_pct=0.0,
            )
        wins = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl <= 0]
        gross_profit = sum((t.net_pnl for t in wins), _ZERO)
        gross_loss = abs(sum((t.net_pnl for t in losses), _ZERO))
        pf = float(gross_profit / gross_loss) if gross_loss > 0 else float(gross_profit)
        net = sum((t.net_pnl for t in trades), _ZERO)
        equity = start_equity
        peak = start_equity
        max_dd = _ZERO
        for t in trades:
            equity += t.net_pnl
            peak = max(peak, equity)
            if peak:
                dd = (peak - equity) / peak * Decimal("100")
                max_dd = max(max_dd, dd)
        return BacktestSplitMetrics(
            split_label=split_label,
            split_index=split_index,
            start_time=start_time,
            end_time=end_time,
            trade_count=len(trades),
            win_rate=len(wins) / len(trades),
            profit_factor=pf,
            expectancy=net / Decimal(str(len(trades))),
            net_pnl=net,
            max_drawdown_pct=float(max_dd),
        )

    def _build_split_metrics(
        self,
        buckets: dict[tuple[BacktestSplitLabel, int], list[BacktestTradeRecord]],
        equity_start: dict[tuple[BacktestSplitLabel, int], Decimal],
        windows: dict[tuple[BacktestSplitLabel, int], tuple[datetime, datetime]],
    ) -> list[BacktestSplitMetrics]:
        out: list[BacktestSplitMetrics] = []
        for key in sorted(buckets.keys(), key=lambda k: (k[1], k[0].value)):
            label, idx = key
            start_t, end_t = windows[key]
            out.append(
                self._compact_metrics(
                    buckets[key],
                    split_label=label,
                    split_index=idx,
                    start_time=start_t,
                    end_time=end_t,
                    start_equity=equity_start[key],
                )
            )
        return out

    def _aggregate_oos_metrics(
        self,
        trades: list[BacktestTradeRecord],
        equity_start: dict[tuple[BacktestSplitLabel, int], Decimal],
        windows: dict[tuple[BacktestSplitLabel, int], tuple[datetime, datetime]],
    ) -> BacktestSplitMetrics | None:
        oos = [t for t in trades if t.split_label == BacktestSplitLabel.OUT_OF_SAMPLE]
        if not oos:
            return None
        oos_keys = [k for k in equity_start if k[0] == BacktestSplitLabel.OUT_OF_SAMPLE]
        if not oos_keys:
            start_eq = Decimal("10000")
            start_t = oos[0].entry_time
            end_t = oos[-1].exit_time
        else:
            first_key = min(oos_keys, key=lambda k: k[1])
            start_eq = equity_start[first_key]
            times = [windows[k] for k in oos_keys if k in windows]
            start_t = min(t[0] for t in times) if times else oos[0].entry_time
            end_t = max(t[1] for t in times) if times else oos[-1].exit_time
        return self._compact_metrics(
            oos,
            split_label=BacktestSplitLabel.OUT_OF_SAMPLE,
            split_index=0,
            start_time=start_t,
            end_time=end_t,
            start_equity=start_eq,
        )

    @staticmethod
    def _hash_result(trades: list[BacktestTradeRecord], metrics: BacktestMetrics) -> str:
        payload: dict[str, Any] = {
            "trades": [t.model_dump(mode="python") for t in trades],
            "metrics": metrics.model_dump(mode="python"),
        }
        return canonical_json_hash(payload)

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
