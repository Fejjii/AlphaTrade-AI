"""Market watcher → paper validation bridge (Slice 42 — paper scan only, no execution)."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import MarketWatcherBridgeDecision as BridgeDecisionModel
from app.db.models import MarketWatcherObservation as ObservationModel
from app.repositories.market_watcher import MarketWatcherObservationRepository
from app.repositories.market_watcher_bridge import MarketWatcherBridgeRepository
from app.repositories.paper_validation import PaperValidationRunRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    MarketWatcherBridgeDecisionType,
    MarketWatcherObservationStatus,
    PaperAlertSeverity,
    PaperAlertSource,
    PaperAlertType,
    PaperObservabilityEventType,
    PaperValidationRecommendation,
    PaperValidationStatus,
)
from app.schemas.market_watcher import (
    MarketWatcherBridgeDecision,
    MarketWatcherBridgeStatus,
    MarketWatcherBridgeTickResult,
    PaginatedMarketWatcherBridgeHistory,
)
from app.schemas.paper_validation import PaperValidationConfig
from app.services.audit_service import AuditService
from app.services.paper_alert_service import PaperAlertService
from app.services.paper_eligibility_service import PaperEligibilityService
from app.services.paper_observability_service import PaperObservabilityService
from app.services.paper_validation_runtime_service import PaperValidationRuntimeService

logger = structlog.get_logger("market_watcher_bridge")


class MarketWatcherBridgeService:
    """Connect read-only market observations to eligible paper validation scans."""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        *,
        audit_service: AuditService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._observations = MarketWatcherObservationRepository(session)
        self._decisions = MarketWatcherBridgeRepository(session)
        self._runs = PaperValidationRunRepository(session)
        self._runtime = PaperValidationRuntimeService(session, self._settings)
        self._alerts = PaperAlertService(session)
        self._audit = audit_service or AuditService(session)
        self._observability = PaperObservabilityService(session)
        self._last_tick: dict[uuid.UUID, MarketWatcherBridgeTickResult] = {}

    def get_status(self, *, organization_id: uuid.UUID) -> MarketWatcherBridgeStatus:
        last = self._last_tick.get(organization_id)
        return MarketWatcherBridgeStatus(
            env_enabled=self._settings.market_watcher_bridge_enabled,
            auto_tick_enabled=self._settings.market_watcher_bridge_auto_tick,
            effective_enabled=self._settings.market_watcher_bridge_enabled,
            last_tick_at=last.ticked_at if last else None,
            last_tick_status="completed" if last and last.effective_enabled else "disabled",
            decisions_last_tick=len(last.decisions) if last else 0,
            scans_triggered_last_tick=last.scans_triggered if last else 0,
            paper_only=True,
            real_trading_enabled=self._settings.real_trading_enabled,
        )

    def tick(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MarketWatcherBridgeTickResult:
        started = time.perf_counter()
        now = datetime.now(UTC)
        summary_decisions: list[str] = []

        self._observability.emit(
            organization_id=organization_id,
            event_type=PaperObservabilityEventType.MARKET_WATCHER_BRIDGE_TICK,
            metadata={"env_enabled": self._settings.market_watcher_bridge_enabled},
        )

        if not self._settings.market_watcher_bridge_enabled:
            self._record_decision(
                organization_id=organization_id,
                decision=MarketWatcherBridgeDecisionType.SKIPPED_DISABLED,
                reason="Bridge disabled: MARKET_WATCHER_BRIDGE_ENABLED=false.",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            summary_decisions.append("Bridge disabled: MARKET_WATCHER_BRIDGE_ENABLED=false.")
            result = MarketWatcherBridgeTickResult(
                ticked_at=now,
                env_enabled=False,
                effective_enabled=False,
                decisions=summary_decisions,
            )
            self._finish_tick(organization_id, user_id, summary_decisions, now)
            self._last_tick[organization_id] = result
            return result

        max_obs = self._settings.market_watcher_bridge_max_observations_per_cycle
        max_scans = self._settings.market_watcher_bridge_max_scans_per_cycle
        observations = self._load_recent_observations(organization_id, limit=max_obs)
        active_runs = self._runs.list_active_for_org(organization_id, limit=max_scans * 2)

        if not observations:
            summary_decisions.append("No market watcher observations to process.")
        if not active_runs:
            summary_decisions.append("No active paper validation runs.")

        scans_triggered = 0
        for obs in observations:
            if scans_triggered >= max_scans:
                summary_decisions.append(f"Scan limit reached ({max_scans} per cycle).")
                break

            matching = [run for run in active_runs if self._matches_observation(obs, run)]
            if not matching:
                reason = f"No matching paper run for {obs.symbol}."
                self._record_decision(
                    organization_id=organization_id,
                    observation=obs,
                    decision=MarketWatcherBridgeDecisionType.SKIPPED_NO_MATCHING_RUN,
                    reason=reason,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                summary_decisions.append(reason)
                continue

            if obs.status in {
                MarketWatcherObservationStatus.STALE,
                MarketWatcherObservationStatus.UNAVAILABLE,
            }:
                reason = f"Observation stale/unavailable for {obs.symbol}."
                alert = self._alerts.create(
                    organization_id=organization_id,
                    alert_type=PaperAlertType.DATA_STALE,
                    severity=PaperAlertSeverity.WARNING,
                    message=reason,
                    strategy_id=obs.related_strategy_id,
                    paper_validation_run_id=obs.related_paper_validation_run_id,
                    metadata={"source": PaperAlertSource.MARKET_WATCHER_BRIDGE.value},
                )
                self._record_decision(
                    organization_id=organization_id,
                    observation=obs,
                    decision=MarketWatcherBridgeDecisionType.SKIPPED_STALE_DATA,
                    reason=reason,
                    created_alert_id=alert.id if alert else None,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                summary_decisions.append(reason)
                continue

            run = matching[0]
            skip_reason, blockers = self._should_skip_run(
                run, organization_id=organization_id, user_id=user_id
            )
            if skip_reason:
                alert = self._alerts.create(
                    organization_id=organization_id,
                    alert_type=PaperAlertType.STRATEGY_BLOCKED,
                    severity=PaperAlertSeverity.WARNING,
                    message=f"Bridge skipped scan: {skip_reason}",
                    strategy_id=run.strategy_id,
                    paper_validation_run_id=run.id,
                    metadata={
                        "source": PaperAlertSource.MARKET_WATCHER_BRIDGE.value,
                        "blockers": blockers,
                    },
                )
                self._record_decision(
                    organization_id=organization_id,
                    observation=obs,
                    run=run,
                    decision=MarketWatcherBridgeDecisionType.SKIPPED_BLOCKED_STRATEGY,
                    reason=skip_reason,
                    blockers=blockers,
                    created_alert_id=alert.id if alert else None,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                summary_decisions.append(f"Skipped run {run.id}: {skip_reason}")
                continue

            try:
                scan = self._runtime.scan(run.id, organization_id=organization_id, user_id=user_id)
                scans_triggered += 1
                triggered = scan.signal.triggered if scan.signal else False
                msg = (
                    f"Bridge triggered paper scan for {obs.symbol} "
                    f"(run {run.id}, triggered={triggered})."
                )
                alert = self._alerts.create(
                    organization_id=organization_id,
                    alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
                    severity=PaperAlertSeverity.INFO,
                    message=msg,
                    strategy_id=run.strategy_id,
                    paper_validation_run_id=run.id,
                    metadata={
                        "source": PaperAlertSource.MARKET_WATCHER_BRIDGE.value,
                        "observation_id": str(obs.id),
                        "triggered": triggered,
                        "trade_created": scan.trade_created,
                    },
                )
                signal_id = scan.signal.id if scan.signal else None
                self._record_decision(
                    organization_id=organization_id,
                    observation=obs,
                    run=run,
                    decision=MarketWatcherBridgeDecisionType.TRIGGERED_SCAN,
                    reason=msg,
                    blockers=list(scan.blockers or []),
                    triggered_scan_id=signal_id,
                    created_alert_id=alert.id if alert else None,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                self._observability.emit(
                    organization_id=organization_id,
                    event_type=PaperObservabilityEventType.MARKET_WATCHER_BRIDGE_SCAN_TRIGGERED,
                    run_id=run.id,
                    strategy_id=run.strategy_id,
                    metadata={
                        "observation_id": str(obs.id),
                        "triggered": triggered,
                        "paper_only": True,
                    },
                )
                summary_decisions.append(msg)
            except Exception as exc:
                msg = f"Bridge scan failed for run {run.id}: {type(exc).__name__}"
                logger.warning(
                    "bridge_scan_failed",
                    run_id=str(run.id),
                    error_type=type(exc).__name__,
                )
                self._record_decision(
                    organization_id=organization_id,
                    observation=obs,
                    run=run,
                    decision=MarketWatcherBridgeDecisionType.FAILED,
                    reason=msg,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                summary_decisions.append(msg)

        result = MarketWatcherBridgeTickResult(
            ticked_at=now,
            env_enabled=True,
            effective_enabled=True,
            observations_processed=len(observations),
            scans_triggered=scans_triggered,
            decisions=summary_decisions
            or [f"Processed {len(observations)} observation(s), no scans triggered."],
        )
        self._finish_tick(organization_id, user_id, summary_decisions, now)
        self._last_tick[organization_id] = result
        return result

    def list_history(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedMarketWatcherBridgeHistory:
        rows, total = self._decisions.list_for_org(organization_id, limit=limit, offset=offset)
        return PaginatedMarketWatcherBridgeHistory(
            items=[self._to_schema(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def _load_recent_observations(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int,
    ) -> list[ObservationModel]:
        rows, _ = self._observations.list_for_org(organization_id, limit=limit * 3, offset=0)
        seen: set[str] = set()
        unique: list[ObservationModel] = []
        for row in rows:
            if row.symbol in seen:
                continue
            seen.add(row.symbol)
            unique.append(row)
            if len(unique) >= limit:
                break
        return unique

    @staticmethod
    def _matches_observation(obs: ObservationModel, run) -> bool:
        try:
            config = PaperValidationConfig.model_validate(run.config or {})
        except Exception:
            return False
        return (
            obs.symbol == config.symbol
            and obs.exchange.lower() == config.exchange.lower()
            and obs.timeframe == config.timeframe
        )

    def _should_skip_run(
        self,
        run,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[str | None, list[str]]:
        blockers: list[str] = list(run.blockers or [])
        if run.status not in {
            PaperValidationStatus.IN_PROGRESS,
            PaperValidationStatus.NOT_STARTED,
        }:
            return "Paper validation run is stopped or completed.", blockers

        eligibility = PaperEligibilityService(self._session, self._settings).evaluate(
            run.strategy_id, organization_id=organization_id, user_id=user_id
        )
        if not eligibility.paper_eligible and eligibility.blockers:
            blockers = list(eligibility.blockers)
            return f"Strategy blocked: {eligibility.blockers[0]}", blockers

        if run.recommendation in {
            PaperValidationRecommendation.RESTRICT.value,
            PaperValidationRecommendation.RETIRE.value,
        }:
            return f"Paper validation restricted ({run.recommendation}).", blockers

        stale_reason = self._check_data_stale(run)
        if stale_reason:
            return stale_reason, blockers

        return None, blockers

    def _check_data_stale(self, run) -> str | None:
        config = PaperValidationConfig.model_validate(run.config or {})
        now = datetime.now(UTC)
        max_age = timedelta(minutes=self._settings.market_watcher_stale_data_max_age_minutes)

        if run.last_scan_at:
            scanned = run.last_scan_at
            if scanned.tzinfo is None:
                scanned = scanned.replace(tzinfo=UTC)
            if now - scanned < max_age:
                return None

        from app.schemas.common import Timeframe

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
        if any("stale" in str(note).lower() for note in limitations):
            return "Provider reported stale data."
        return None

    def _record_decision(
        self,
        *,
        organization_id: uuid.UUID,
        decision: MarketWatcherBridgeDecisionType,
        reason: str | None = None,
        observation: ObservationModel | None = None,
        run=None,
        blockers: list[str] | None = None,
        triggered_scan_id: uuid.UUID | None = None,
        created_alert_id: uuid.UUID | None = None,
        latency_ms: int | None = None,
    ) -> BridgeDecisionModel:
        row = BridgeDecisionModel(
            organization_id=organization_id,
            observation_id=observation.id if observation else None,
            strategy_id=(
                run.strategy_id
                if run
                else (observation.related_strategy_id if observation else None)
            ),
            paper_validation_run_id=(
                run.id
                if run
                else (observation.related_paper_validation_run_id if observation else None)
            ),
            symbol=observation.symbol if observation else None,
            exchange=observation.exchange if observation else None,
            timeframe=observation.timeframe if observation else None,
            decision=decision,
            reason=reason,
            blockers=blockers,
            triggered_scan_id=triggered_scan_id,
            created_alert_id=created_alert_id,
            latency_ms=latency_ms,
        )
        self._decisions.add(row)
        return row

    def _finish_tick(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        decisions: list[str],
        now: datetime,
    ) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id=f"market-watcher-bridge-{organization_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="market_watcher_bridge",
                resource_id=str(organization_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={
                    "action": "market_watcher_bridge_tick",
                    "decisions": decisions[:20],
                    "paper_only": True,
                },
            )
        )
        logger.info(
            "market_watcher_bridge_tick",
            organization_id=str(organization_id),
            decisions=len(decisions),
            at=now.isoformat(),
        )

    @staticmethod
    def _to_schema(row: BridgeDecisionModel) -> MarketWatcherBridgeDecision:
        return MarketWatcherBridgeDecision(
            id=row.id,
            organization_id=row.organization_id,
            observation_id=row.observation_id,
            strategy_id=row.strategy_id,
            paper_validation_run_id=row.paper_validation_run_id,
            symbol=row.symbol,
            exchange=row.exchange,
            timeframe=row.timeframe,
            decision=row.decision.value,
            reason=row.reason,
            blockers=list(row.blockers or []),
            triggered_scan_id=row.triggered_scan_id,
            created_alert_id=row.created_alert_id,
            latency_ms=row.latency_ms,
            created_at=row.created_at,
        )
