"""Paper validation runtime loop (Slice 39 — paper only, no exchange orders)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import PaperSignal as PaperSignalModel
from app.db.models import PaperTrade as PaperTradeModel
from app.db.models import PaperTradeEvent as PaperTradeEventModel
from app.db.models import PaperValidationMetricSnapshot as MetricSnapshotModel
from app.db.models import PaperValidationRun as PaperValidationRunModel
from app.providers.factory import resolve_market_data_provider
from app.repositories.backtest import BacktestRunRepository
from app.repositories.paper_runtime import (
    PaperMetricSnapshotRepository,
    PaperSignalRepository,
    PaperTradeRepository,
)
from app.repositories.paper_validation import PaperValidationRunRepository
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import (
    BacktestRunStatus,
    BacktestStatus,
    PaperAlertSeverity,
    PaperAlertType,
    PaperObservabilityEventType,
    PaperRuntimeCycleMode,
    PaperRuntimeCycleStatus,
    PaperSignalStatus,
    PaperTradeStatus,
    PaperValidationRuntimeMode,
    PaperValidationStatus,
    StrategyValidationStatus,
    Timeframe,
)
from app.schemas.paper_validation import (
    PaginatedPaperSignals,
    PaginatedPaperTrades,
    PaperPosition,
    PaperScanResult,
    PaperSignalResult,
    PaperTickResult,
    PaperTradeRecord,
    PaperValidationConfig,
    PaperValidationMetrics,
    PaperValidationRun,
    PaperValidationRunStart,
)
from app.schemas.strategy_library import StrategyCard
from app.schemas.structured_rules import StructuredRules
from app.services.historical_candle_service import HistoricalCandleService
from app.services.paper_alert_service import PaperAlertService
from app.services.paper_bot_engine import PaperBotEngine, _OpenPaperTrade
from app.services.paper_eligibility_service import PaperEligibilityService
from app.services.paper_observability_service import PaperObservabilityService
from app.services.paper_sample_window_service import PaperSampleWindowService
from app.services.paper_validation_promotion import (
    compute_max_drawdown,
    evaluate_paper_promotion,
    sort_closed_trades_chronologically,
)
from app.services.structured_rule_resolver import resolve_backtest_rules


@dataclass
class _RunContext:
    card: StrategyCard
    setup_type: object
    structured: StructuredRules | None
    config: PaperValidationConfig
    no_trade_rules: list[str]


class PaperValidationRuntimeService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._runs = PaperValidationRunRepository(session)
        self._signals = PaperSignalRepository(session)
        self._trades = PaperTradeRepository(session)
        self._snapshots = PaperMetricSnapshotRepository(session)
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)
        provider = resolve_market_data_provider(self._settings)
        self._candles = HistoricalCandleService(session, provider, self._settings)
        self._engine = PaperBotEngine()
        self._observability = PaperObservabilityService(session)
        self._alerts = PaperAlertService(session)
        self._sample_windows = PaperSampleWindowService(session)

    def start(
        self,
        strategy_id: uuid.UUID,
        payload: PaperValidationRunStart | None,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperValidationRun:
        start_payload = payload or PaperValidationRunStart()
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")

        eligibility = PaperEligibilityService(self._session, self._settings).evaluate(
            strategy_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        version = self._versions.latest(strategy_id)
        bt_rows, _ = BacktestRunRepository(self._session).list_for_strategy(
            strategy_id, organization_id=organization_id, limit=1
        )
        has_backtest = bool(bt_rows) and bt_rows[0].status == BacktestRunStatus.COMPLETED
        if not has_backtest and version is not None:
            has_backtest = version.backtest_status == BacktestStatus.COMPLETED
        in_review = version is not None and version.validation_status in {
            StrategyValidationStatus.IN_REVIEW,
            StrategyValidationStatus.VALIDATED,
        }
        can_start = (
            eligibility.paper_eligible or strategy.paper_eligible or has_backtest or in_review
        )
        if not can_start:
            raise ValidationAppError(
                "Strategy is not paper eligible. Resolve blockers before starting validation."
            )
        config = start_payload.config or PaperValidationConfig()
        blockers = list(eligibility.blockers)

        if version is not None:
            version.paper_validation_status = PaperValidationStatus.IN_PROGRESS

        initial_metrics = self._empty_metrics()
        from app.services.paper_validation_service import PaperValidationService

        initial_rec = PaperValidationService._recommend(
            initial_metrics,
            eligible=eligibility.paper_eligible or strategy.paper_eligible,
        )

        run = PaperValidationRunModel(
            strategy_id=strategy_id,
            strategy_version_id=version.id if version else None,
            organization_id=organization_id,
            user_id=user_id,
            status=PaperValidationStatus.IN_PROGRESS,
            runtime_mode=start_payload.runtime_mode,
            paper_eligible=eligibility.paper_eligible or strategy.paper_eligible,
            notes="Paper validation runtime — simulated trades only, no exchange orders.",
            config=config.model_dump(mode="json"),
            blockers=blockers,
            metrics=initial_metrics.model_dump(mode="json"),
            recommendation=initial_rec.value,
        )
        self._runs.add(run)
        return self._to_schema(run)

    def scan(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperScanResult:
        run = self._get_active_run(run_id, organization_id=organization_id)
        ctx = self._load_context(run, organization_id=organization_id, user_id=user_id)
        config = ctx.config
        now = datetime.now(UTC)
        builder = self._observability.start_history(
            organization_id=organization_id,
            mode=PaperRuntimeCycleMode.SCAN,
            run_id=run.id,
            strategy_id=run.strategy_id,
            symbol=config.symbol,
        )

        lookback_days = self._engine.default_lookback_days(config.timeframe)
        candle_rows, data_limitations = self._candles.ensure_candles_for_backtest(
            symbol=config.symbol,
            exchange=config.exchange,
            timeframe=Timeframe(config.timeframe),
            start_date=(now - timedelta(days=lookback_days)).date(),
            end_date=now.date(),
        )
        data_stale = any("stale" in str(note).lower() for note in data_limitations)
        if data_stale:
            builder.warnings.extend(data_limitations)
            builder.data_freshness = "stale"
            self._observability.emit(
                organization_id=organization_id,
                event_type=PaperObservabilityEventType.DATA_STALE,
                run_id=run.id,
                strategy_id=run.strategy_id,
                metadata={"limitations": data_limitations},
            )
            self._alerts.create(
                organization_id=organization_id,
                alert_type=PaperAlertType.DATA_STALE,
                severity=PaperAlertSeverity.WARNING,
                message=f"Stale data detected during scan for run {run.id}.",
                strategy_id=run.strategy_id,
                paper_validation_run_id=run.id,
            )
        elif candle_rows:
            builder.data_freshness = "fresh"

        resolved = resolve_backtest_rules(ctx.card, ctx.setup_type, ctx.structured)
        rules = resolved.rules
        engine_source = resolved.engine_source.value

        blocked_filters = self._engine.evaluate_no_trade_filters(
            rules,
            no_trade_rules=ctx.no_trade_rules,
        )
        evaluation = self._engine.evaluate_entry(rules, candle_rows, engine_source=engine_source)

        signal_status = PaperSignalStatus.DETECTED
        triggered = evaluation.triggered and not blocked_filters
        limitations = list(data_limitations)

        if not rules.machine_readable:
            signal_status = PaperSignalStatus.NOT_TESTABLE
            triggered = False
            run.blockers = list(set((run.blockers or []) + ["Rules not machine testable."]))
            limitations.append("Improve structured rules before paper trades.")
        elif blocked_filters:
            signal_status = PaperSignalStatus.BLOCKED_FILTER
            triggered = False

        tp_plan = {"r_multiples": [str(m) for m in rules.tp_r_multiples]}
        runner_plan = {"use_runner": rules.use_runner} if rules.use_runner else None

        signal_row = PaperSignalModel(
            paper_validation_run_id=run.id,
            strategy_id=run.strategy_id,
            strategy_version_id=run.strategy_version_id,
            organization_id=organization_id,
            user_id=user_id,
            symbol=config.symbol,
            exchange=config.exchange,
            timeframe=config.timeframe,
            direction=rules.direction,
            triggered=triggered,
            status=signal_status,
            matched_entry_blocks=evaluation.matched_blocks,
            blocked_no_trade_filters=blocked_filters,
            confidence=0.75 if triggered else 0.0,
            suggested_entry=evaluation.entry_price,
            stop_loss=evaluation.stop_loss,
            invalidation=ctx.card.invalidation[0] if ctx.card.invalidation else None,
            tp_plan=tp_plan,
            runner_plan=runner_plan,
            reason=evaluation.notes,
            limitations=limitations,
            rule_engine_source=engine_source,
        )
        self._signals.add(signal_row)

        trade_created = False
        open_count = len(self._trades.list_open_for_run(run.id, organization_id=organization_id))
        if (
            run.runtime_mode == PaperValidationRuntimeMode.AUTO_PAPER
            and triggered
            and signal_status == PaperSignalStatus.DETECTED
            and evaluation.entry_price is not None
            and evaluation.stop_loss is not None
            and open_count < config.max_open_trades
        ):
            size = self._compute_size(
                evaluation.entry_price,
                evaluation.stop_loss,
                config,
            )
            fee_rate = config.fees_bps / Decimal("10000")
            slip_rate = config.slippage_bps / Decimal("10000")
            open_state = self._engine.open_trade_state(
                direction=rules.direction,
                entry_time=candle_rows[-1].close_time,
                entry_price=evaluation.entry_price,
                stop_loss=evaluation.stop_loss,
                size=size,
                rules=rules,
                fee_rate=fee_rate,
                slip_rate=slip_rate,
            )
            trade_row = self._create_trade_from_state(
                run,
                open_state,
                signal_row=signal_row,
                rules=rules,
                engine_source=engine_source,
                organization_id=organization_id,
                user_id=user_id,
                config=config,
            )
            signal_row.status = PaperSignalStatus.CONSUMED
            self._record_event(trade_row.id, "opened", {"mode": "auto_paper"})
            trade_created = True

        scan_result = {
            "triggered": triggered,
            "signal_id": str(signal_row.id),
            "trade_created": trade_created,
            "limitations": limitations,
        }
        run.last_scan_at = now
        run.last_scan_result = scan_result

        builder.signals_created = 1
        if trade_created:
            builder.trades_opened = 1
        builder.blockers = list(run.blockers or [])
        cycle_status = (
            PaperRuntimeCycleStatus.PARTIAL if data_stale else PaperRuntimeCycleStatus.SUCCESS
        )
        self._observability.record_history(builder, cycle_status)
        self._observability.emit(
            organization_id=organization_id,
            event_type=PaperObservabilityEventType.SIGNAL_CREATED,
            run_id=run.id,
            strategy_id=run.strategy_id,
            metadata={"triggered": triggered, "trade_created": trade_created},
        )
        if triggered:
            self._alerts.create(
                organization_id=organization_id,
                alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
                message=f"Paper setup signal detected for {config.symbol}.",
                strategy_id=run.strategy_id,
                paper_validation_run_id=run.id,
            )
        if trade_created:
            self._alerts.create(
                organization_id=organization_id,
                alert_type=PaperAlertType.PAPER_TRADE_OPENED,
                message=f"Paper trade opened for {config.symbol}.",
                strategy_id=run.strategy_id,
                paper_validation_run_id=run.id,
            )
            self._observability.emit(
                organization_id=organization_id,
                event_type=PaperObservabilityEventType.PAPER_TRADE_OPENED,
                run_id=run.id,
                strategy_id=run.strategy_id,
            )

        return PaperScanResult(
            run_id=run.id,
            signal=self._signal_to_schema(signal_row),
            trade_created=trade_created,
            blockers=list(run.blockers or []),
            scanned_at=now,
        )

    def tick(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperTickResult:
        run = self._get_active_run(run_id, organization_id=organization_id)
        ctx = self._load_context(run, organization_id=organization_id, user_id=user_id)
        config = ctx.config
        now = datetime.now(UTC)
        builder = self._observability.start_history(
            organization_id=organization_id,
            mode=PaperRuntimeCycleMode.TICK,
            run_id=run.id,
            strategy_id=run.strategy_id,
            symbol=config.symbol,
        )
        prior_rec = run.recommendation

        lookback_days = self._engine.default_lookback_days(config.timeframe)
        candle_rows, data_limitations = self._candles.ensure_candles_for_backtest(
            symbol=config.symbol,
            exchange=config.exchange,
            timeframe=Timeframe(config.timeframe),
            start_date=(now - timedelta(days=lookback_days)).date(),
            end_date=now.date(),
        )
        data_stale = any("stale" in str(note).lower() for note in data_limitations)
        if data_stale:
            builder.warnings.extend(data_limitations)
            builder.data_freshness = "stale"
        if not candle_rows:
            raise ValidationAppError("No candles available for paper tick.")

        latest_bar = candle_rows[-1]
        fee_rate = config.fees_bps / Decimal("10000")
        slip_rate = config.slippage_bps / Decimal("10000")
        closed_count = 0

        open_trades = self._trades.list_open_for_run(run.id, organization_id=organization_id)
        closed_details: list[tuple[PaperTradeModel, object]] = []
        for trade_row in open_trades:
            open_state = self._trade_to_open_state(trade_row, config)
            close = self._engine.monitor_bar(
                open_state,
                latest_bar,
                fee_rate=fee_rate,
                slip_rate=slip_rate,
                timeout_bars=config.trade_timeout_bars,
            )
            if close is None:
                self._persist_open_trade_state(trade_row, open_state)
                continue
            self._apply_close(trade_row, close)
            closed_details.append((trade_row, close))
            self._record_event(
                trade_row.id,
                "closed",
                {
                    "exit_reason": close.exit_reason,
                    "net_pnl": str(close.net_pnl),
                },
            )
            closed_count += 1

        metrics = self._aggregate_metrics(run.id, organization_id=organization_id, config=config)
        self._sample_windows.refresh_for_run(run.id, organization_id=organization_id)
        promotion = self._evaluate_promotion(
            run, metrics, organization_id, user_id, data_stale=data_stale
        )
        run.metrics = metrics.model_dump(mode="json")
        run.recommendation = promotion.recommendation.value
        run.blockers = promotion.blockers
        run.last_tick_at = now

        if promotion.paper_validated:
            run.status = PaperValidationStatus.PASSED
            run.ended_at = now
            version = self._versions.latest(run.strategy_id)
            if version is not None:
                version.paper_validation_status = PaperValidationStatus.PASSED
        elif promotion.status == PaperValidationStatus.FAILED:
            run.status = PaperValidationStatus.FAILED
            run.ended_at = now

        if closed_count > 0:
            self._snapshots.add(
                MetricSnapshotModel(
                    paper_validation_run_id=run.id,
                    metrics=metrics.model_dump(mode="json"),
                    trigger_trade_id=None,
                )
            )

        remaining_open = len(
            self._trades.list_open_for_run(run.id, organization_id=organization_id)
        )

        builder.trades_closed = closed_count
        builder.blockers = list(run.blockers or [])
        cycle_status = (
            PaperRuntimeCycleStatus.PARTIAL if data_stale else PaperRuntimeCycleStatus.SUCCESS
        )
        self._observability.record_history(builder, cycle_status)
        self._observability.emit(
            organization_id=organization_id,
            event_type=PaperObservabilityEventType.METRICS_UPDATED,
            run_id=run.id,
            strategy_id=run.strategy_id,
            metadata={
                "trades_closed": closed_count,
                "paper_trades_count": metrics.paper_trades_count,
            },
        )
        if prior_rec != promotion.recommendation.value:
            self._observability.emit(
                organization_id=organization_id,
                event_type=PaperObservabilityEventType.PROMOTION_STATUS_CHANGED,
                run_id=run.id,
                strategy_id=run.strategy_id,
                metadata={"from": prior_rec, "to": promotion.recommendation.value},
            )
            self._alerts.create(
                organization_id=organization_id,
                alert_type=PaperAlertType.PROMOTION_STATUS_CHANGED,
                message=(
                    f"Paper validation recommendation changed to {promotion.recommendation.value}."
                ),
                strategy_id=run.strategy_id,
                paper_validation_run_id=run.id,
            )
        for trade_row, close in closed_details:
            alert_type = PaperAlertService.alert_type_for_exit(close.exit_reason)
            self._alerts.create(
                organization_id=organization_id,
                alert_type=alert_type,
                message=f"Paper trade closed ({close.exit_reason}) on {trade_row.symbol}.",
                strategy_id=run.strategy_id,
                paper_validation_run_id=run.id,
                paper_trade_id=trade_row.id,
            )
            self._observability.emit(
                organization_id=organization_id,
                event_type=PaperObservabilityEventType.PAPER_TRADE_CLOSED,
                run_id=run.id,
                strategy_id=run.strategy_id,
                metadata={"exit_reason": close.exit_reason},
            )
        if metrics.paper_trades_count > 50 and metrics.win_rate < 0.3:
            self._alerts.create(
                organization_id=organization_id,
                alert_type=PaperAlertType.OVERTRADING_WARNING,
                severity=PaperAlertSeverity.WARNING,
                message="Overtrading warning: high trade count with low win rate.",
                strategy_id=run.strategy_id,
                paper_validation_run_id=run.id,
            )
        if metrics.consecutive_losses >= 5:
            self._alerts.create(
                organization_id=organization_id,
                alert_type=PaperAlertType.DAILY_LOSS_LOCK_WARNING,
                severity=PaperAlertSeverity.WARNING,
                message=f"Loss streak warning: {metrics.consecutive_losses} consecutive losses.",
                strategy_id=run.strategy_id,
                paper_validation_run_id=run.id,
            )

        return PaperTickResult(
            run_id=run.id,
            trades_closed=closed_count,
            trades_open=remaining_open,
            metrics=metrics,
            recommendation=promotion.recommendation,
            ticked_at=now,
        )

    def stop(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRun:
        run = self._runs.get_scoped(run_id, organization_id=organization_id)
        if run is None:
            raise NotFoundError("Paper validation run not found.")
        run.status = PaperValidationStatus.FAILED
        run.ended_at = datetime.now(UTC)
        run.notes = (run.notes or "") + " Stopped manually."
        version = self._versions.latest(run.strategy_id)
        if version is not None:
            version.paper_validation_status = PaperValidationStatus.FAILED
        return self._to_schema(run)

    def get_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRun:
        row = self._runs.get_scoped(run_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Paper validation run not found.")
        return self._to_schema(row)

    def list_signals(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedPaperSignals:
        self._ensure_run(run_id, organization_id=organization_id)
        rows, total = self._signals.list_for_run(
            run_id, organization_id=organization_id, limit=limit, offset=offset
        )
        return PaginatedPaperSignals(
            items=[self._signal_to_schema(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def list_trades(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        status: PaperTradeStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedPaperTrades:
        self._ensure_run(run_id, organization_id=organization_id)
        rows, total = self._trades.list_for_run(
            run_id,
            organization_id=organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return PaginatedPaperTrades(
            items=[self._trade_to_schema(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def list_open_positions(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> list[PaperPosition]:
        rows = self._trades.list_open_for_run(run_id, organization_id=organization_id)
        return [PaperPosition.model_validate(self._trade_to_schema(r).model_dump()) for r in rows]

    def get_metrics(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationMetrics:
        run = self._ensure_run(run_id, organization_id=organization_id)
        if run.metrics:
            return PaperValidationMetrics.model_validate(run.metrics)
        config = PaperValidationConfig.model_validate(run.config or {})
        return self._aggregate_metrics(run_id, organization_id=organization_id, config=config)

    def _load_context(
        self,
        run: PaperValidationRunModel,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> _RunContext:
        strategy = self._strategies.get_scoped(
            run.strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")
        version = (
            self._versions.get_by_id(run.strategy_version_id)
            if run.strategy_version_id
            else self._versions.latest(run.strategy_id)
        )
        if version is None:
            raise ValidationAppError("Strategy version not found.")
        card = StrategyCard.model_validate(version.card)
        structured: StructuredRules | None = None
        if version.structured_rules:
            structured = StructuredRules.model_validate(version.structured_rules)
        config = PaperValidationConfig.model_validate(run.config or {})
        no_trade = list(card.no_trade_rules)
        if structured and structured.no_trade_rules:
            no_trade.extend(str(r) for r in structured.no_trade_rules)
        return _RunContext(
            card=card,
            setup_type=strategy.setup_type,
            structured=structured,
            config=config,
            no_trade_rules=no_trade,
        )

    def _get_active_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRunModel:
        run = self._ensure_run(run_id, organization_id=organization_id)
        if run.status not in {PaperValidationStatus.IN_PROGRESS, PaperValidationStatus.NOT_STARTED}:
            raise ValidationAppError("Paper validation run is not active.")
        if run.status == PaperValidationStatus.NOT_STARTED:
            run.status = PaperValidationStatus.IN_PROGRESS
        return run

    def _ensure_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRunModel:
        row = self._runs.get_scoped(run_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Paper validation run not found.")
        return row

    @staticmethod
    def _compute_size(entry: Decimal, stop: Decimal, config: PaperValidationConfig) -> Decimal:
        risk_capital = config.initial_capital * (config.risk_per_trade_pct / Decimal("100"))
        risk_per_unit = abs(entry - stop)
        if risk_per_unit <= 0:
            return Decimal("0.001")
        return risk_capital / risk_per_unit

    def _create_trade_from_state(
        self,
        run: PaperValidationRunModel,
        state: _OpenPaperTrade,
        *,
        signal_row: PaperSignalModel,
        rules: object,
        engine_source: str,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        config: PaperValidationConfig,
    ) -> PaperTradeModel:
        from app.services.strategy_rule_adapter import ParsedStrategyRules

        parsed = rules if isinstance(rules, ParsedStrategyRules) else None
        tp_plan = {"r_multiples": [str(m) for m in (parsed.tp_r_multiples if parsed else ())]}
        runner_plan = {"use_runner": parsed.use_runner} if parsed and parsed.use_runner else {}
        if not isinstance(runner_plan, dict):
            runner_plan = {}
        runner_plan.setdefault("bars_open", 0)
        row = PaperTradeModel(
            paper_validation_run_id=run.id,
            strategy_id=run.strategy_id,
            strategy_version_id=run.strategy_version_id,
            organization_id=organization_id,
            user_id=user_id,
            created_from_signal_id=signal_row.id,
            symbol=config.symbol,
            exchange=config.exchange,
            timeframe=config.timeframe,
            direction=state.direction,
            entry_price=state.entry_price,
            entry_time=state.entry_time,
            size=state.size,
            stop_loss=state.stop_loss,
            invalidation=signal_row.invalidation,
            tp_plan=tp_plan,
            runner_plan=runner_plan,
            status=PaperTradeStatus.OPEN,
            fees=state.entry_fees,
            slippage=state.entry_slippage,
            rule_engine_source=engine_source,
        )
        self._trades.add(row)
        return row

    @staticmethod
    def _trade_to_open_state(
        trade_row: PaperTradeModel,
        config: PaperValidationConfig,
    ) -> _OpenPaperTrade:
        from app.services.strategy_rule_adapter import ParsedStrategyRules

        tp_multiples = (Decimal("1"), Decimal("2"))
        use_runner = False
        if trade_row.tp_plan and "r_multiples" in trade_row.tp_plan:
            tp_multiples = tuple(Decimal(v) for v in trade_row.tp_plan["r_multiples"])
        if trade_row.runner_plan:
            use_runner = bool(trade_row.runner_plan.get("use_runner"))
        bars_open = 0
        last_bar_open_time: datetime | None = None
        if trade_row.runner_plan:
            bars_open = int(trade_row.runner_plan.get("bars_open", 0))
            raw_last = trade_row.runner_plan.get("last_bar_open_time")
            if raw_last:
                last_bar_open_time = datetime.fromisoformat(str(raw_last))
        rules = ParsedStrategyRules(
            machine_readable=True,
            limitation=None,
            direction=trade_row.direction,
            entry_mode="pullback_ema",
            stop_pct=Decimal("0.02"),
            tp_r_multiples=tp_multiples,
            use_runner=use_runner,
            matched_tokens=(),
        )
        fee_rate = config.fees_bps / Decimal("10000")
        slip_rate = config.slippage_bps / Decimal("10000")
        engine = PaperBotEngine()
        state = engine.open_trade_state(
            direction=trade_row.direction,
            entry_time=trade_row.entry_time or datetime.now(UTC),
            entry_price=trade_row.entry_price or Decimal("0"),
            stop_loss=trade_row.stop_loss or Decimal("0"),
            size=trade_row.size or Decimal("0"),
            rules=rules,
            fee_rate=fee_rate,
            slip_rate=slip_rate,
        )
        state.bars_open = bars_open
        state.last_bar_open_time = last_bar_open_time
        return state

    @staticmethod
    def _persist_open_trade_state(trade_row: PaperTradeModel, state: _OpenPaperTrade) -> None:
        plan = dict(trade_row.runner_plan or {})
        plan["bars_open"] = state.bars_open
        if state.last_bar_open_time is not None:
            plan["last_bar_open_time"] = state.last_bar_open_time.isoformat()
        trade_row.runner_plan = plan

    @staticmethod
    def _apply_close(trade_row: PaperTradeModel, close: object) -> None:
        from app.services.paper_bot_engine import CloseEvaluation

        assert isinstance(close, CloseEvaluation)
        trade_row.status = PaperTradeStatus.CLOSED
        trade_row.exit_price = close.exit_price
        trade_row.exit_time = close.exit_time
        trade_row.exit_reason = close.exit_reason
        trade_row.gross_pnl = close.gross_pnl
        trade_row.net_pnl = close.net_pnl
        trade_row.fees = close.fees
        trade_row.slippage = close.slippage

    def _record_event(
        self,
        trade_id: uuid.UUID,
        event_type: str,
        payload: dict | None,
    ) -> None:
        self._session.add(
            PaperTradeEventModel(
                paper_trade_id=trade_id,
                event_type=event_type,
                payload=payload,
            )
        )

    def _aggregate_metrics(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        config: PaperValidationConfig,
    ) -> PaperValidationMetrics:
        rows, _ = self._trades.list_for_run(
            run_id, organization_id=organization_id, status=PaperTradeStatus.CLOSED, limit=500
        )
        if not rows:
            return self._empty_metrics()

        ordered = sort_closed_trades_chronologically(rows)
        pnls = [r.net_pnl or Decimal("0") for r in ordered]
        gross_pnls = [r.gross_pnl or Decimal("0") for r in ordered]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p <= 0]
        gross_profit = sum(wins, Decimal("0"))
        gross_loss = sum(losses, Decimal("0"))
        pf = float(gross_profit / gross_loss) if gross_loss > 0 else float(gross_profit)
        net = sum(pnls, Decimal("0"))
        gross = sum(gross_pnls, Decimal("0"))
        count = len(ordered)
        total_fees = sum((r.fees or Decimal("0") for r in rows), Decimal("0"))
        total_slip = sum((r.slippage or Decimal("0") for r in rows), Decimal("0"))

        equity = config.initial_capital
        equity_curve: list[Decimal] = [equity]
        for pnl in pnls:
            equity += pnl
            equity_curve.append(equity)
        max_dd = compute_max_drawdown(equity_curve)

        streak = 0
        max_streak = 0
        for pnl in pnls:
            if pnl <= 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        durations = []
        for r in ordered:
            if r.entry_time and r.exit_time:
                hours = max(0.01, (r.exit_time - r.entry_time).total_seconds() / 3600)
                durations.append(hours)
        avg_hold = sum(durations) / len(durations) if durations else 0.0

        stop_respected = sum(1 for r in ordered if r.exit_reason == "stop_loss")
        early_exit = sum(1 for r in ordered if r.exit_reason == "runner_trail")
        runner_helped = sum(1 for r in ordered if r.exit_reason and "runner" in r.exit_reason)

        return PaperValidationMetrics(
            paper_trades_count=count,
            win_rate=len(wins) / count if count else 0.0,
            net_pnl=net,
            gross_pnl=gross,
            profit_factor=pf,
            expectancy=net / Decimal(str(count)) if count else Decimal("0"),
            max_drawdown_pct=max_dd,
            total_fees=total_fees,
            total_slippage=total_slip,
            average_win=gross_profit / Decimal(str(len(wins))) if wins else Decimal("0"),
            average_loss=-gross_loss / Decimal(str(len(losses))) if losses else Decimal("0"),
            consecutive_losses=max_streak,
            average_holding_time_hours=avg_hold,
            early_exit_count=early_exit,
            stop_respected_count=stop_respected,
            runner_helped_count=runner_helped,
        )

    def _evaluate_promotion(
        self,
        run: PaperValidationRunModel,
        metrics: PaperValidationMetrics,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        data_stale: bool = False,
    ):
        eligibility = PaperEligibilityService(self._session, self._settings).evaluate(
            run.strategy_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        has_critical = any("critical" in b.lower() for b in eligibility.blockers) or bool(
            eligibility.unresolved_lesson_candidates
        )
        severe_overtrading = metrics.paper_trades_count > 50 and metrics.win_rate < 0.3
        enough_samples = metrics.paper_trades_count >= 5
        min_days = enough_samples
        if run.created_at:
            created = run.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            min_days = (datetime.now(UTC) - created).days >= 1 or enough_samples
        windows_count = self._sample_windows.count_windows(run.id, organization_id=organization_id)
        provider_failures = bool(
            run.last_scan_result and run.last_scan_result.get("provider_failure")
        )
        return evaluate_paper_promotion(
            metrics=metrics,
            paper_eligible=run.paper_eligible,
            has_critical_lesson_blockers=has_critical,
            severe_overtrading=severe_overtrading,
            min_runtime_days_met=min_days,
            runtime_windows_count=windows_count,
            data_stale=data_stale,
            provider_failures=provider_failures,
        )

    @staticmethod
    def _empty_metrics() -> PaperValidationMetrics:
        return PaperValidationMetrics(
            paper_trades_count=0,
            win_rate=0.0,
            net_pnl=Decimal("0"),
            gross_pnl=Decimal("0"),
            profit_factor=0.0,
            expectancy=Decimal("0"),
            max_drawdown_pct=0.0,
        )

    @staticmethod
    def _signal_to_schema(row: PaperSignalModel) -> PaperSignalResult:
        return PaperSignalResult(
            id=row.id,
            paper_validation_run_id=row.paper_validation_run_id,
            strategy_id=row.strategy_id,
            triggered=row.triggered,
            status=row.status,
            symbol=row.symbol,
            exchange=row.exchange,
            timeframe=row.timeframe,
            direction=row.direction,
            matched_entry_blocks=list(row.matched_entry_blocks or []),
            blocked_no_trade_filters=list(row.blocked_no_trade_filters or []),
            confidence=row.confidence,
            suggested_entry=row.suggested_entry,
            stop_loss=row.stop_loss,
            invalidation=row.invalidation,
            tp_plan=row.tp_plan,
            runner_plan=row.runner_plan,
            reason=row.reason,
            limitations=list(row.limitations or []),
            rule_engine_source=row.rule_engine_source,
            created_at=row.created_at,
        )

    @staticmethod
    def _trade_to_schema(row: PaperTradeModel) -> PaperTradeRecord:
        return PaperTradeRecord(
            id=row.id,
            paper_validation_run_id=row.paper_validation_run_id,
            strategy_id=row.strategy_id,
            strategy_version_id=row.strategy_version_id,
            created_from_signal_id=row.created_from_signal_id,
            symbol=row.symbol,
            exchange=row.exchange,
            timeframe=row.timeframe,
            direction=row.direction,
            entry_price=row.entry_price,
            entry_time=row.entry_time,
            size=row.size,
            stop_loss=row.stop_loss,
            invalidation=row.invalidation,
            tp_plan=row.tp_plan,
            runner_plan=row.runner_plan,
            status=row.status,
            exit_price=row.exit_price,
            exit_time=row.exit_time,
            exit_reason=row.exit_reason,
            gross_pnl=row.gross_pnl,
            net_pnl=row.net_pnl,
            fees=row.fees,
            slippage=row.slippage,
            rule_engine_source=row.rule_engine_source,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_schema(self, row: PaperValidationRunModel) -> PaperValidationRun:
        metrics = None
        if row.metrics:
            metrics = PaperValidationMetrics.model_validate(row.metrics)
        recommendation = None
        if row.recommendation:
            from app.schemas.common import PaperValidationRecommendation

            recommendation = PaperValidationRecommendation(row.recommendation)
        config = None
        if row.config:
            config = PaperValidationConfig.model_validate(row.config)
        return PaperValidationRun(
            id=row.id,
            strategy_id=row.strategy_id,
            strategy_version_id=row.strategy_version_id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            status=row.status,
            runtime_mode=row.runtime_mode,
            paper_eligible=row.paper_eligible,
            notes=row.notes,
            config=config,
            blockers=list(row.blockers or []),
            last_scan_at=row.last_scan_at,
            last_tick_at=row.last_tick_at,
            last_scan_result=row.last_scan_result,
            ended_at=row.ended_at,
            metrics=metrics,
            recommendation=recommendation,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
