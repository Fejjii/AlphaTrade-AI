"""Chronological Nested replay using existing backtest fills and metrics.

No provider, wall-clock, database writes, live account, or strategy promotion.
"""

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Any

from app.db.models import HistoricalCandle
from app.market_contracts.catalog import catalog_for_symbols
from app.market_contracts.enums import VenueId
from app.market_contracts.identity import interval_timedelta
from app.market_contracts.ohlcv import OhlcvBar, build_ohlcv_bar
from app.schemas.backtest import (
    BacktestAssumptions,
    BacktestResult,
    BacktestTradeRecord,
    EquityCurvePoint,
)
from app.schemas.common import (
    BacktestRecommendation,
    BacktestSplitLabel,
    RiskAction,
    TradeDirection,
)
from app.schemas.nested_continuation import NestedContinuationSpec
from app.schemas.risk import RiskCheckRequest
from app.schemas.strategy_replay import (
    REPLAY_ENGINE,
    ReplayCandidate,
    ReplayReport,
    ReplaySample,
    StrategyReplayCreate,
)
from app.services.backtest_engine_service import BacktestEngineService, _OpenTrade
from app.services.backtest_hashing import canonical_json_hash
from app.services.risk.engine import RiskEngine
from app.services.risk.limits import RiskLimits
from app.services.risk.rules import RiskEvaluationContext
from app.services.strategy_replay_adapter import NestedReplayAdapter, ReplayAdapter

ZERO = Decimal("0")


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def replay_input_hash(rows: list[HistoricalCandle]) -> str:
    # Existing dataset hash omits close time and stale flags. Bind those too.
    return canonical_json_hash(
        [
            {
                "symbol": r.symbol,
                "exchange": r.exchange,
                "timeframe": r.timeframe,
                "open_time": aware(r.open_time),
                "close_time": aware(r.close_time),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "source": r.source,
                "is_stale": r.is_stale,
            }
            for r in rows
        ]
    )


class StrategyReplayEngine:
    def __init__(self, fills: BacktestEngineService, adapter: ReplayAdapter | None = None) -> None:
        self._fills = fills
        self._adapter = adapter or NestedReplayAdapter()

    def run(
        self,
        *,
        rows: list[HistoricalCandle],
        snapshot: dict[str, Any],
        should_cancel: Callable[[], bool] | None = None,
    ) -> BacktestResult:
        # Freeze Decimal arithmetic even if the caller changed its context.
        with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
            return self._run(rows=rows, snapshot=snapshot, should_cancel=should_cancel)

    def _run(
        self,
        *,
        rows: list[HistoricalCandle],
        snapshot: dict[str, Any],
        should_cancel: Callable[[], bool] | None,
    ) -> BacktestResult:
        request = StrategyReplayCreate.model_validate(snapshot["replay_request"])
        spec = NestedContinuationSpec.model_validate(snapshot["pattern_spec"])
        assumptions = request.assumptions
        raw_limits: dict[str, Any] = {
            key: Decimal(value) if isinstance(getattr(RiskLimits(), key), Decimal) else value
            for key, value in snapshot["risk_limits"].items()
        }
        raw_limits["supported_symbols"] = frozenset(raw_limits["supported_symbols"])
        limits = RiskLimits(**raw_limits)
        risk = RiskEngine(limits)
        report = ReplayReport(
            strategy_version_id=request.strategy_version_id,
            strategy_content_hash=snapshot["strategy_content_hash"],
            parameter_hash=canonical_json_hash(spec.parameters.model_dump(mode="json")),
            input_hash=replay_input_hash(rows),
        )
        all_trades: list[BacktestTradeRecord] = []
        curves: list[EquityCurvePoint] = []
        max_dd = ZERO
        missing: set[str] = {
            "moving_average",
            "higher_timeframe",
            "cvd",
            "order_flow",
            "open_interest",
            "funding",
        }
        if any(row.source == "mock" for row in rows):
            missing.add("synthetic_mock_candles")
        cancelled = False
        processed_bars = 0
        windows = request.windows

        def cancel_probe() -> bool:
            return cancelled or bool(should_cancel and should_cancel())

        for label, start, end in (
            (BacktestSplitLabel.IN_SAMPLE, windows.training_start, windows.training_end),
            (BacktestSplitLabel.OUT_OF_SAMPLE, windows.evaluation_start, windows.evaluation_end),
        ):
            selected = [r for r in rows if start <= aware(r.open_time) < end]
            bars, errors = self._closed_bars(selected, spec, assumptions, start, end, windows.as_of)
            if errors:
                missing.update(errors)
                report.samples.append(
                    ReplaySample(
                        split_label=label,
                        candle_count=len(selected),
                        candidate_count=0,
                        blocked_count=0,
                        trade_count=0,
                        status="missing_data",
                        net_pnl=ZERO,
                    )
                )
                continue
            trades, candidates, curve, dd, segment_cancelled = self._segment(
                bars,
                spec.model_dump(mode="json"),
                label,
                assumptions,
                risk,
                len(all_trades),
                should_cancel=cancel_probe,
            )
            cancelled |= segment_cancelled
            processed_bars += len(curve)
            all_trades.extend(trades)
            report.candidates.extend(candidates)
            curves.extend(curve)
            max_dd = max(max_dd, dd)
            missing.update(e for c in candidates for e in c.missing_evidence)
            confirmed = [
                c
                for c in candidates
                if c.risk_decision is not None or c.state in {"entered", "blocked"}
            ]
            report.samples.append(
                ReplaySample(
                    split_label=label,
                    candle_count=len(bars),
                    candidate_count=len(confirmed),
                    blocked_count=sum(c.state == "blocked" for c in candidates),
                    trade_count=len(trades),
                    status="cancelled"
                    if segment_cancelled
                    else "insufficient_sample"
                    if len(trades) < request.minimum_sample
                    else "descriptive_only",
                    net_pnl=sum((t.net_pnl for t in trades), ZERO),
                    mean_r=sum((t.r_result or ZERO for t in trades), ZERO) / len(trades)
                    if trades
                    else None,
                )
            )
        report.missing_evidence = sorted(missing)
        net = sum((t.net_pnl for t in all_trades), ZERO)
        metrics = self._fills._compute_metrics(
            all_trades,
            assumptions=assumptions,
            equity_curve=curves,
            max_dd=max_dd,
            ending_equity=assumptions.initial_capital + net,
        )
        metrics.average_time_in_trade_bars = (
            sum(t.holding_bars or 0 for t in all_trades) / len(all_trades) if all_trades else 0
        )
        result = BacktestResult(
            metrics=metrics,
            trades=all_trades,
            recommendation=BacktestRecommendation.UNRELIABLE_DATA
            if any(s.status == "missing_data" for s in report.samples)
            else BacktestRecommendation.NEEDS_REVIEW,
            data_quality="unreliable"
            if any(s.status == "missing_data" for s in report.samples)
            else "ok",
            rule_engine_source="nested_causal_adapter",
            engine_version=REPLAY_ENGINE,
            cancelled=cancelled,
            processed_bars=processed_bars,
            total_bars=sum(s.candle_count for s in report.samples),
            replay=report.model_dump(mode="json"),
            limitations=[
                "Descriptive research only; a better replay does not establish improvement.",
                "Independent training/evaluation accounts and detector state; no automatic tuning.",
                "Next-open entries; stop-first ambiguity; first measured target closes full size.",
                "MAE/MFE are full held-bar bounds; intrabar order and exact exit time are unknown.",
                "Constant funding assumption; historical funding and order flow are unavailable.",
                "Missing evidence: " + ", ".join(report.missing_evidence),
                *[
                    f"{s.split_label.value}: {s.status} ({s.trade_count} trades)."
                    for s in report.samples
                ],
            ],
        )
        result.result_hash = canonical_json_hash(
            result.model_dump(mode="json", exclude={"result_hash"})
        )
        return result

    @staticmethod
    def _closed_bars(
        rows: list[HistoricalCandle],
        spec: NestedContinuationSpec,
        assumptions: BacktestAssumptions,
        start: datetime,
        end: datetime,
        as_of: datetime,
    ) -> tuple[tuple[OhlcvBar, ...], list[str]]:
        errors: list[str] = []
        step = interval_timedelta(spec.trigger_timeframe)
        if not rows or aware(rows[0].open_time) != start or aware(rows[-1].open_time) + step != end:
            errors.append("window_coverage_missing")
        for i, row in enumerate(rows):
            if row.is_stale:
                errors.append("stale_candle")
            if aware(row.close_time) not in {
                aware(row.open_time) + step,
                aware(row.open_time) + step - timedelta(seconds=1),
            }:
                errors.append("invalid_candle_close_time")
            if aware(row.open_time) + step > min(end, as_of):
                errors.append("unclosed_candle")
            if i and aware(row.open_time) != aware(rows[i - 1].open_time) + step:
                errors.append("candle_gap_or_duplicate")
            if (row.symbol, row.exchange, row.timeframe) != (
                spec.symbol,
                assumptions.exchange,
                spec.trigger_timeframe.value,
            ):
                errors.append("candle_identity_mismatch")
        if errors:
            return (), sorted(set(errors))
        instrument = catalog_for_symbols(
            [spec.symbol], venue=VenueId(assumptions.exchange)
        ).require(spec.symbol)
        try:
            bars = tuple(
                build_ohlcv_bar(
                    instrument=instrument,
                    timeframe=spec.trigger_timeframe,
                    interval_start=aware(r.open_time),
                    open_=r.open,
                    high=r.high,
                    low=r.low,
                    close=r.close,
                    base_volume=r.volume,
                    quote_volume=r.close * r.volume,
                    evaluated_at=aware(r.open_time) + step,
                    grace=timedelta(0),
                    provider_complete=True,
                    adapter_version=REPLAY_ENGINE,
                )
                for r in rows
            )
        except ValueError:
            return (), ["invalid_ohlcv"]
        return bars, []

    def _segment(
        self,
        bars: tuple[OhlcvBar, ...],
        spec: dict[str, Any],
        label: BacktestSplitLabel,
        assumptions: BacktestAssumptions,
        risk: RiskEngine,
        sequence_start: int,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[
        list[BacktestTradeRecord], list[ReplayCandidate], list[EquityCurvePoint], Decimal, bool
    ]:
        if should_cancel and should_cancel():
            return [], [], [], ZERO, True
        cancelled = False
        scheduled: dict[int, list[ReplayCandidate]] = defaultdict(list)
        previous = -1
        for index, candidate in self._adapter.events(bars, spec, label):
            if (
                index < previous
                or index < 0
                or index >= len(bars)
                or candidate.detected_at != bars[index].interval_end
                or candidate.direction != TradeDirection(spec["direction"])
                or candidate.split_label != label
            ):
                raise ValueError("Adapter events must be chronological closed-candle decisions.")
            scheduled[index].append(candidate)
            previous = index
        equity = peak = assumptions.initial_capital
        max_dd = ZERO
        trades: list[BacktestTradeRecord] = []
        candidates: list[ReplayCandidate] = []
        curve: list[EquityCurvePoint] = []
        pending: ReplayCandidate | None = None
        opened: _OpenTrade | None = None
        owner: ReplayCandidate | None = None
        daily_pnl: dict[date, Decimal] = defaultdict(lambda: ZERO)
        weekly_pnl: dict[tuple[int, int], Decimal] = defaultdict(lambda: ZERO)
        daily_trades: dict[date, int] = defaultdict(int)
        fee, slip = assumptions.fees_bps / 10000, assumptions.slippage_bps / 10000
        sign = (
            Decimal(1) if TradeDirection(spec["direction"]) is TradeDirection.LONG else Decimal(-1)
        )
        for i, bar in enumerate(bars):
            if i and i % 200 == 0 and should_cancel and should_cancel():
                cancelled = True
                break
            if pending:
                candidate, pending = pending, None
                candidate.decision_at = bar.interval_start
                fill = bar.open * (1 + sign * slip)
                reason = None
                if opened:
                    reason = "position_already_open"
                elif len(trades) >= (assumptions.max_trades or 500):
                    reason = "max_trades_reached"
                elif equity <= 0:
                    reason = "account_equity_exhausted"
                elif candidate.stop is None or (fill - candidate.stop) * sign <= 0:
                    reason = "stop_invalid_at_next_open"
                elif not candidate.targets or (candidate.targets[0] - fill) * sign <= 0:
                    reason = "target_invalid_at_next_open"
                else:
                    distance = abs(fill - candidate.stop)
                    size = equity * assumptions.risk_per_trade_pct / 100 / distance
                    day = bar.interval_start.date()
                    week = bar.interval_start.isocalendar()[:2]
                    decision = risk.evaluate(
                        RiskCheckRequest(
                            symbol=spec["symbol"],
                            direction=TradeDirection(spec["direction"]),
                            entry_price=fill,
                            stop_loss=candidate.stop,
                            position_size=size,
                            leverage=Decimal(1),
                            account_equity=equity,
                            risk_percent=assumptions.risk_per_trade_pct,
                        ),
                        context=RiskEvaluationContext(
                            realized_pnl_today=daily_pnl[day],
                            trades_today=daily_trades[day],
                            weekly_loss_pct=max(ZERO, -weekly_pnl[week] / equity * 100),
                            is_weekend=bar.interval_start.weekday() >= 5,
                        ),
                    )
                    candidate.risk_decision = decision
                    if decision.action is RiskAction.BLOCK:
                        reason = "blocked_by_risk"
                    else:
                        candidate.state = "entered"
                        candidate.trade_sequence = sequence_start + len(trades)
                        opened = _OpenTrade(
                            direction=candidate.direction,
                            entry_time=bar.interval_start,
                            entry_price=fill,
                            stop_loss=candidate.stop,
                            size=size,
                            risk_per_unit=distance,
                            tp_levels=candidate.targets,
                            tp_hit=0,
                            use_runner=False,
                            rule_notes=f"replay setup:{candidate.setup_id}",
                            entry_fees=fill * size * fee,
                            entry_slippage=abs(fill - bar.open) * size,
                            entry_idx=i,
                            mfe_price=fill,
                            mae_price=fill,
                        )
                        owner = candidate
                        daily_trades[day] += 1
                if reason:
                    candidate.state = "blocked"
                    candidate.reasons = [*candidate.reasons, reason]
            if opened:
                # Reuse the existing held-bar excursion and funding calculators.
                gap_stop = (bar.open - opened.stop_loss) * sign <= 0
                candle = HistoricalCandle(
                    high=bar.open if gap_stop else bar.high,
                    low=bar.open if gap_stop else bar.low,
                    close=bar.close,
                )
                self._fills._update_excursions(opened, candle)
                if gap_stop:
                    # Exit at the open: no later candle extrema or funding accrue.
                    opened.bars_held -= 1
                else:
                    self._fills._accrue_funding(
                        opened,
                        assumptions.funding_rate_bps_per_8h,
                        Decimal(str(interval_timedelta(bar.timeframe).total_seconds())),
                    )
                price, reason, tp, exit_time = None, None, "none", bar.interval_end
                if gap_stop:
                    price, reason, exit_time = bar.open, "stop_gap", bar.interval_start
                elif bar.low <= opened.stop_loss if sign == 1 else bar.high >= opened.stop_loss:
                    price, reason = opened.stop_loss, "stop_loss"
                elif (
                    bar.high >= opened.tp_levels[0] if sign == 1 else bar.low <= opened.tp_levels[0]
                ):
                    price, reason, tp = opened.tp_levels[0], "take_profit_1", "tp1"
                elif i == len(bars) - 1:
                    price, reason = bar.close, "replay_window_end"
                if price is not None:
                    assert reason is not None and owner is not None
                    record, pnl = self._fills._build_trade_record(
                        opened,
                        exit_time=exit_time,
                        exit_price=price,
                        exit_reason=reason,
                        tp_status=tp,
                        fee_rate=fee,
                        slip_rate=slip,
                        split_label=label,
                        split_index=0 if label is BacktestSplitLabel.IN_SAMPLE else 1,
                        sequence=sequence_start + len(trades),
                        deduct_slippage_cost=False,
                    )
                    record = record.model_copy(
                        update={
                            "setup_id": owner.setup_id,
                            "planned_targets": opened.tp_levels,
                            "r_result": pnl / (opened.risk_per_unit * opened.size),
                            "holding_bars": opened.bars_held,
                            "holding_seconds": int((exit_time - opened.entry_time).total_seconds()),
                        }
                    )
                    trades.append(record)
                    equity += pnl
                    daily_pnl[exit_time.date()] += pnl
                    weekly_pnl[exit_time.isocalendar()[:2]] += pnl
                    peak = max(peak, equity)
                    max_dd = max(max_dd, (peak - equity) / peak * 100)
                    opened = owner = None
            for candidate in scheduled[i]:
                candidates.append(candidate)
                if candidate.state == "confirmed":
                    if pending:
                        candidate.state = "blocked"
                        candidate.reasons.append("another_confirmation_pending")
                    else:
                        pending = candidate
            curve.append(EquityCurvePoint(timestamp=bar.interval_end, equity=equity))
        if pending:
            pending.state = "blocked"
            pending.reasons.append(
                "replay_cancelled" if cancelled else "no_next_closed_candle_in_window"
            )
        if opened and owner and cancelled:
            owner.state = "interrupted"
            owner.reasons.append("cancelled_with_open_position_unvalued")
        return trades, candidates, curve, max_dd, cancelled
