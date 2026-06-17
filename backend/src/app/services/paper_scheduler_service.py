"""Paper validation scheduler (Slice 40 — disabled by default, paper only)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ValidationAppError
from app.repositories.paper_scheduler import (
    PaperRuntimeHistoryRepository,
    PaperSchedulerConfigRepository,
)
from app.repositories.paper_validation import PaperValidationRunRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperObservabilityEventType,
    PaperRuntimeCycleMode,
    PaperRuntimeCycleStatus,
    PaperValidationRecommendation,
    PaperValidationStatus,
    Timeframe,
)
from app.schemas.paper_scheduler import (
    PaginatedPaperRuntimeHistory,
    PaperSchedulerConfig,
    PaperSchedulerConfigUpdate,
    PaperSchedulerStatus,
    PaperSchedulerTickResult,
)
from app.services.audit_service import AuditService
from app.services.paper_alert_service import PaperAlertService
from app.services.paper_eligibility_service import PaperEligibilityService
from app.services.paper_observability_service import PaperObservabilityService
from app.services.paper_validation_runtime_service import PaperValidationRuntimeService

logger = structlog.get_logger("paper_scheduler")

MIN_RUNTIME_WINDOWS = 2


class PaperSchedulerService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        *,
        audit_service: AuditService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._config_repo = PaperSchedulerConfigRepository(session)
        self._history_repo = PaperRuntimeHistoryRepository(session)
        self._runs = PaperValidationRunRepository(session)
        self._runtime = PaperValidationRuntimeService(session, self._settings)
        self._observability = PaperObservabilityService(session)
        self._alerts = PaperAlertService(session)
        self._audit = audit_service or AuditService(session)

    def get_status(self, *, organization_id: uuid.UUID) -> PaperSchedulerStatus:
        cfg_row = self._config_repo.get_or_create(organization_id)
        config = self._to_config_schema(cfg_row)
        env_enabled = self._settings.enable_paper_scheduler
        tenant_enabled = cfg_row.enabled
        return PaperSchedulerStatus(
            env_enabled=env_enabled,
            tenant_enabled=tenant_enabled,
            effective_enabled=env_enabled and tenant_enabled,
            config=config,
            last_tick_at=cfg_row.last_tick_at,
            last_tick_status=cfg_row.last_tick_status,
            real_trading_enabled=self._settings.real_trading_enabled,
        )

    def update_config(
        self,
        payload: PaperSchedulerConfigUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperSchedulerStatus:
        if not self._settings.enable_paper_scheduler and payload.enabled is True:
            raise ValidationAppError(
                "Paper scheduler env flag ENABLE_PAPER_SCHEDULER is false. "
                "Enable it before turning on tenant scheduler."
            )
        row = self._config_repo.get_or_create(organization_id)
        if payload.enabled is not None:
            row.enabled = payload.enabled
        if payload.interval_seconds is not None:
            row.interval_seconds = payload.interval_seconds
        if payload.max_runs_per_cycle is not None:
            row.max_runs_per_cycle = payload.max_runs_per_cycle
        if payload.max_scans_per_minute is not None:
            row.max_scans_per_minute = payload.max_scans_per_minute
        trace_id = str(uuid.uuid4())
        self._audit.record(
            AuditRecordCreate(
                request_id=f"paper-scheduler-{organization_id}",
                trace_id=trace_id,
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_SCHEDULER_TICK,
                resource_type="paper_scheduler_config",
                resource_id=str(organization_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"action": "config_update", "enabled": row.enabled},
            )
        )
        return self.get_status(organization_id=organization_id)

    def tick(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperSchedulerTickResult:
        now = datetime.now(UTC)
        status = self.get_status(organization_id=organization_id)
        decisions: list[str] = []
        cfg_row = self._config_repo.get_or_create(organization_id)

        self._observability.emit(
            organization_id=organization_id,
            event_type=PaperObservabilityEventType.SCHEDULER_TICK_STARTED,
            metadata={"env_enabled": status.env_enabled, "tenant_enabled": status.tenant_enabled},
        )

        if not status.env_enabled:
            decisions.append("Scheduler disabled: ENABLE_PAPER_SCHEDULER=false.")
            cfg_row.last_tick_at = now
            cfg_row.last_tick_status = "disabled_env"
            self._finish_tick(organization_id, user_id, decisions, now)
            return PaperSchedulerTickResult(
                ticked_at=now,
                env_enabled=False,
                effective_enabled=False,
                decisions=decisions,
            )

        if not status.tenant_enabled:
            decisions.append("Scheduler disabled: tenant config not enabled.")
            cfg_row.last_tick_at = now
            cfg_row.last_tick_status = "disabled_tenant"
            self._finish_tick(organization_id, user_id, decisions, now)
            return PaperSchedulerTickResult(
                ticked_at=now,
                env_enabled=True,
                effective_enabled=False,
                decisions=decisions,
            )

        since = now - timedelta(minutes=1)
        recent_scans = self._history_repo.count_recent_scans(organization_id, since=since)
        if recent_scans >= cfg_row.max_scans_per_minute:
            decisions.append(
                f"Rate limit: {recent_scans} scans in last minute "
                f"(max {cfg_row.max_scans_per_minute})."
            )
            cfg_row.last_tick_at = now
            cfg_row.last_tick_status = "rate_limited"
            self._finish_tick(organization_id, user_id, decisions, now)
            return PaperSchedulerTickResult(
                ticked_at=now,
                env_enabled=True,
                effective_enabled=True,
                decisions=decisions,
            )

        active_runs = self._runs.list_active_for_org(
            organization_id, limit=cfg_row.max_runs_per_cycle
        )
        if not active_runs:
            decisions.append("No active paper validation runs to process.")
            cfg_row.last_tick_at = now
            cfg_row.last_tick_status = "no_runs"
            self._finish_tick(organization_id, user_id, decisions, now)
            return PaperSchedulerTickResult(
                ticked_at=now,
                env_enabled=True,
                effective_enabled=True,
                decisions=decisions,
            )

        runs_processed = 0
        runs_skipped = 0
        scans_executed = 0
        ticks_executed = 0
        alerts_created = 0

        for run in active_runs:
            skip_reason = self._should_skip_run(
                run, organization_id=organization_id, user_id=user_id
            )
            if skip_reason:
                runs_skipped += 1
                decisions.append(f"Skipped run {run.id}: {skip_reason}")
                builder = self._observability.start_history(
                    organization_id=organization_id,
                    mode=PaperRuntimeCycleMode.SCHEDULER_TICK,
                    run_id=run.id,
                    strategy_id=run.strategy_id,
                )
                builder.reason = skip_reason
                builder.blockers = list(run.blockers or [])
                self._observability.record_history(builder, PaperRuntimeCycleStatus.SKIPPED)
                self._observability.emit(
                    organization_id=organization_id,
                    event_type=PaperObservabilityEventType.SCAN_SKIPPED,
                    run_id=run.id,
                    strategy_id=run.strategy_id,
                    metadata={"reason": skip_reason},
                )
                continue

            try:
                scan = self._runtime.scan(run.id, organization_id=organization_id, user_id=user_id)
                scans_executed += 1
                tick = self._runtime.tick(run.id, organization_id=organization_id, user_id=user_id)
                ticks_executed += 1
                runs_processed += 1
                triggered = scan.signal.triggered if scan.signal else False
                decisions.append(
                    f"Processed run {run.id}: scan triggered={triggered}, "
                    f"closed={tick.trades_closed}."
                )
                if scan.signal and scan.signal.triggered:
                    decisions.append(f"Processed run {run.id}: setup signal (alert via runtime).")
                if scan.trade_created:
                    decisions.append(f"Processed run {run.id}: trade opened (alert via runtime).")
                if tick.trades_closed > 0:
                    decisions.append(
                        f"Processed run {run.id}: {tick.trades_closed} trade(s) closed "
                        "(alerts via runtime)."
                    )
            except Exception as exc:
                runs_skipped += 1
                msg = type(exc).__name__
                decisions.append(f"Failed run {run.id}: {msg}")
                logger.warning("scheduler_run_failed", run_id=str(run.id), error_type=msg)
                builder = self._observability.start_history(
                    organization_id=organization_id,
                    mode=PaperRuntimeCycleMode.SCHEDULER_TICK,
                    run_id=run.id,
                    strategy_id=run.strategy_id,
                )
                builder.error_type = msg
                builder.error_message = str(exc)
                self._observability.record_history(builder, PaperRuntimeCycleStatus.FAILED)
                self._observability.emit(
                    organization_id=organization_id,
                    event_type=PaperObservabilityEventType.RUNTIME_ERROR,
                    run_id=run.id,
                    strategy_id=run.strategy_id,
                    metadata={"error_type": msg},
                )

        cfg_row.last_tick_at = now
        cfg_row.last_tick_status = "completed"
        self._finish_tick(organization_id, user_id, decisions, now)

        return PaperSchedulerTickResult(
            ticked_at=now,
            env_enabled=True,
            effective_enabled=True,
            runs_processed=runs_processed,
            runs_skipped=runs_skipped,
            scans_executed=scans_executed,
            ticks_executed=ticks_executed,
            alerts_created=alerts_created,
            decisions=decisions,
        )

    def list_history(
        self,
        *,
        organization_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedPaperRuntimeHistory:
        items, total = self._observability.list_history(
            organization_id, run_id=run_id, limit=limit, offset=offset
        )
        return PaginatedPaperRuntimeHistory(items=items, total=total, limit=limit, offset=offset)

    def _should_skip_run(
        self,
        run,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        if run.status not in {PaperValidationStatus.IN_PROGRESS, PaperValidationStatus.NOT_STARTED}:
            return "Paper validation run is stopped or completed."

        eligibility = PaperEligibilityService(self._session, self._settings).evaluate(
            run.strategy_id, organization_id=organization_id, user_id=user_id
        )
        if not eligibility.paper_eligible and eligibility.blockers:
            return f"Strategy blocked: {eligibility.blockers[0]}"

        if run.recommendation in {
            PaperValidationRecommendation.RESTRICT.value,
            PaperValidationRecommendation.RETIRE.value,
        }:
            return f"Paper validation restricted ({run.recommendation})."

        stale_reason = self._check_data_stale(run)
        if stale_reason:
            return stale_reason

        return None

    def _check_data_stale(self, run) -> str | None:
        from app.schemas.paper_validation import PaperValidationConfig

        config = PaperValidationConfig.model_validate(run.config or {})
        now = datetime.now(UTC)
        max_age = timedelta(minutes=self._settings.paper_scheduler_stale_data_max_age_minutes)

        if run.last_scan_at:
            scanned = run.last_scan_at
            if scanned.tzinfo is None:
                scanned = scanned.replace(tzinfo=UTC)
            if now - scanned < max_age:
                return None

        lookback_days = self._runtime._engine.default_lookback_days(config.timeframe)
        candle_rows, limitations = self._runtime._candles.ensure_candles_for_backtest(
            symbol=config.symbol,
            exchange=config.exchange,
            timeframe=Timeframe(config.timeframe),
            start_date=(now - timedelta(days=lookback_days)).date(),
            end_date=now.date(),
        )
        if not candle_rows:
            return "No candle data available (stale or missing)."
        latest = candle_rows[-1]
        if getattr(latest, "is_stale", False):
            return "Market data reported stale."
        if any("stale" in str(note).lower() for note in limitations):
            return "Provider reported stale data."
        bar_time = latest.open_time
        if bar_time.tzinfo is None:
            bar_time = bar_time.replace(tzinfo=UTC)
        if now - bar_time > max_age:
            return (
                f"Latest bar older than "
                f"{self._settings.paper_scheduler_stale_data_max_age_minutes}m."
            )
        return None

    def _finish_tick(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        decisions: list[str],
        now: datetime,
    ) -> None:
        self._observability.emit(
            organization_id=organization_id,
            event_type=PaperObservabilityEventType.SCHEDULER_TICK_COMPLETED,
            metadata={"decisions": decisions[:20]},
        )
        self._audit.record(
            AuditRecordCreate(
                request_id=f"paper-scheduler-tick-{organization_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_SCHEDULER_TICK,
                resource_type="paper_scheduler",
                resource_id=str(organization_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"decisions": decisions[:20], "paper_only": True},
            )
        )
        logger.info(
            "paper_scheduler_tick",
            organization_id=str(organization_id),
            decisions=len(decisions),
            at=now.isoformat(),
        )

    @staticmethod
    def _to_config_schema(row) -> PaperSchedulerConfig:
        return PaperSchedulerConfig(
            enabled=row.enabled,
            interval_seconds=row.interval_seconds,
            max_runs_per_cycle=row.max_runs_per_cycle,
            max_scans_per_minute=row.max_scans_per_minute,
        )
