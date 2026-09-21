"""Read-only Watcher PAPER MONITORING aggregation.

Exposes existing runtime status. Does not start Watcher, evaluate strategies,
send Telegram, or place trades.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import (
    CompiledSetupDefinition,
    KillSwitchState,
    MarketWatcherObservation,
    StrategyLifecycleEvent,
    UserStrategy,
    UserStrategyVersion,
    WorkerHeartbeat,
)
from app.db.watcher_orchestration import (
    WatcherHeartbeatRow,
    WatcherObservabilityEventRow,
    WatcherScanAttemptRow,
    WatcherWorkerLeaseRow,
)
from app.guardrails.redaction import redact_text
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.providers.registry import get_provider_registry
from app.repositories.market_watcher_scan import MarketWatcherScanRepository
from app.runtime.canonical import ProductionCanonicalRuntime
from app.schemas.common import SetupCompileStatus, StrategyLifecycleState
from app.schemas.watcher_monitoring import (
    PaperMonitoringPosture,
    WatcherApprovedStrategy,
    WatcherCanonicalCandidateSummary,
    WatcherConfigFlags,
    WatcherDetectedCandidateSummary,
    WatcherLeaseHealth,
    WatcherMarketFreshness,
    WatcherMonitoringRuntimeState,
    WatcherMonitoringSnapshot,
    WatcherProviderHealthItem,
    WatcherRecentError,
    WatcherSetupAssessmentSummary,
    WatcherWorkerHealth,
)
from app.services.market_watcher_service import MarketWatcherService
from app.services.watcher_monitoring_state import (
    WatcherMonitoringDecision,
    WatcherMonitoringEvidence,
    project_watcher_monitoring_state,
)
from app.signal_fusion.enums import SetupAssessmentState
from app.watcher.contracts import (
    EvaluationMode,
    RecoveryDisposition,
    ScanAttempt,
    ScanAttemptStatus,
    ScanTrigger,
    WatcherHealthSnapshot,
    WatcherHeartbeat,
    WatcherRuntimeConfig,
    WorkerLease,
)
from app.watcher.health import project_health
from app.watcher.settings import runtime_config_from_settings

logger = structlog.get_logger("watcher_monitoring")

_APPROVED_STATES = frozenset({StrategyLifecycleState.APPROVED, StrategyLifecycleState.ACTIVE})
_ERROR_EVENT_MARKERS = ("fail", "error", "blocked", "degraded", "stale", "reject")


class _ProviderStatusSource(Protocol):
    def statuses(self) -> list[ProviderStatus]: ...


class WatcherMonitoringService:
    """Assemble a truthful operator snapshot from existing stores."""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        *,
        providers: _ProviderStatusSource | None = None,
        canonical_runtime: ProductionCanonicalRuntime | None = None,
        market_watcher: MarketWatcherService | None = None,
        now: datetime | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._providers = providers
        self._canonical_runtime = canonical_runtime
        self._market_watcher = market_watcher or MarketWatcherService(session, self._settings)
        self._now = now

    def get_snapshot(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WatcherMonitoringSnapshot:
        now = self._now or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        settings = self._settings
        config = runtime_config_from_settings(settings)
        watcher_status = self._market_watcher.get_status(
            organization_id=organization_id, user_id=user_id
        )
        summary = self._market_watcher.get_summary(organization_id=organization_id, user_id=user_id)
        last_scan = MarketWatcherScanRepository(self._session).latest_for_org(organization_id)
        observation = self._latest_observation(organization_id)
        worker = self._worker_health(now)
        leases, orchestration_snapshot = self._orchestration_health(
            organization_id=organization_id, config=config, now=now
        )
        providers = self._provider_health()
        market_data_health = _worst_market_data_health(providers)
        kill_blocked, kill_reason = self._kill_switch(organization_id)
        approved = self._approved_strategies(organization_id)
        assessments, canonical_candidates, candidate_limitations = self._canonical_lineage(
            organization_id
        )
        recent_errors = self._recent_errors(
            organization_id=organization_id,
            last_scan_error=summary.last_scan_error,
            last_scan_at=summary.last_scan_at,
            worker=worker,
            providers=providers,
        )

        primary_lease = leases[0] if leases else None
        evidence = WatcherMonitoringEvidence(
            execution_mode=settings.execution_mode.value,
            real_trading_enabled=bool(settings.real_trading_enabled),
            kill_switch_blocked=kill_blocked,
            kill_switch_reason=kill_reason,
            market_watcher_enabled=settings.market_watcher_enabled,
            watcher_orchestration_enabled=settings.watcher_orchestration_enabled,
            worker_enabled=settings.worker_enabled,
            worker_heartbeat_live=worker.heartbeat_live,
            orchestration_health_state=(
                None if orchestration_snapshot is None else orchestration_snapshot.state.value
            ),
            orchestration_reason_code=(
                None if orchestration_snapshot is None else orchestration_snapshot.reason_code
            ),
            orchestration_lease_fenced=bool(primary_lease.fenced) if primary_lease else False,
            orchestration_heartbeat_fresh=(
                bool(primary_lease.heartbeat_fresh) if primary_lease else False
            ),
            last_scan_status=summary.last_scan_status,
            last_observation_status=None if observation is None else str(observation.status),
            market_data_health=market_data_health,
            generated_at=now,
        )
        decision = project_watcher_monitoring_state(evidence)
        next_scan_at, next_scan_basis = _next_scan(
            decision=decision,
            settings=settings,
            worker=worker,
            primary_lease=primary_lease,
            now=now,
        )
        freshness = _market_freshness(
            observation=observation,
            stale_after_minutes=settings.market_watcher_stale_data_max_age_minutes,
        )
        warnings = list(decision.warnings)
        if not approved:
            warnings.append("no_approved_strategies")
        limitations = list(candidate_limitations)
        if last_scan is None:
            limitations.append("No persisted Watcher scan has run for this organization.")

        paper_posture = PaperMonitoringPosture(
            execution_mode=settings.execution_mode.value,
            real_trading_enabled=bool(settings.real_trading_enabled),
            kill_switch_blocked=kill_blocked,
            kill_switch_reason_code=kill_reason,
            telegram_enabled=_telegram_enabled(settings),
            watcher_config_enabled=_config_enabled(settings),
            runtime_evidence=decision.runtime_evidence,
        )
        return WatcherMonitoringSnapshot(
            watcher_status=decision.state,
            paper_monitoring_status=decision.state,
            reason_code=decision.reason_code,
            block_reasons=list(decision.block_reasons),
            warnings=list(dict.fromkeys(warnings)),
            paper_posture=paper_posture,
            config_flags=WatcherConfigFlags(
                market_watcher_enabled=settings.market_watcher_enabled,
                watcher_orchestration_enabled=settings.watcher_orchestration_enabled,
                worker_enabled=settings.worker_enabled,
                market_watcher_bridge_enabled=settings.market_watcher_bridge_enabled,
                market_watcher_bridge_auto_tick=settings.market_watcher_bridge_auto_tick,
                telegram_alerts_enabled=settings.telegram_alerts_enabled,
                telegram_interaction_enabled=settings.telegram_interaction_enabled,
                automatic_telegram_delivery_enabled=settings.automatic_telegram_delivery_enabled,
            ),
            symbols_monitored=list(watcher_status.watched_symbols),
            approved_strategies=approved,
            last_scan_at=summary.last_scan_at,
            last_scan_status=summary.last_scan_status,
            next_scan_at=next_scan_at,
            next_scan_basis=next_scan_basis,
            market_freshness=freshness,
            provider_health=providers,
            setup_assessments=assessments,
            scanner_candidates=WatcherDetectedCandidateSummary(
                count=summary.last_scan_candidate_count,
                conditions=list(summary.last_scan_conditions_found),
                last_scan_at=summary.last_scan_at,
            ),
            canonical_candidates=canonical_candidates,
            leases=leases,
            worker=worker,
            recent_errors=recent_errors,
            limitations=limitations,
            generated_at=now,
        )

    def _latest_observation(self, organization_id: uuid.UUID) -> MarketWatcherObservation | None:
        return self._session.scalar(
            select(MarketWatcherObservation)
            .where(MarketWatcherObservation.organization_id == organization_id)
            .order_by(MarketWatcherObservation.observed_at.desc())
            .limit(1)
        )

    def _worker_health(self, now: datetime) -> WatcherWorkerHealth:
        settings = self._settings
        row = self._session.scalar(
            select(WorkerHeartbeat).where(WorkerHeartbeat.worker_name == settings.worker_name)
        )
        if row is None:
            return WatcherWorkerHealth(
                name=settings.worker_name,
                worker_enabled=settings.worker_enabled,
                heartbeat_live=False,
            )
        last_beat = _aware(row.last_beat_at)
        liveness_window = settings.worker_scan_interval_seconds * 3
        live = (
            last_beat is not None
            and (now - last_beat).total_seconds() <= liveness_window
            and row.status != "error"
            and not row.paused
        )
        return WatcherWorkerHealth(
            name=settings.worker_name,
            worker_enabled=settings.worker_enabled,
            heartbeat_live=live,
            last_beat_at=last_beat,
            status=row.status,
            paused=row.paused,
            detail=_sanitize(row.detail),
        )

    def _orchestration_health(
        self,
        *,
        organization_id: uuid.UUID,
        config: WatcherRuntimeConfig,
        now: datetime,
    ) -> tuple[list[WatcherLeaseHealth], WatcherHealthSnapshot | None]:
        leases = list(
            self._session.scalars(
                select(WatcherWorkerLeaseRow)
                .where(WatcherWorkerLeaseRow.organization_id == organization_id)
                .order_by(WatcherWorkerLeaseRow.scan_scope)
            ).all()
        )
        heartbeats = {
            row.scan_scope: row
            for row in self._session.scalars(
                select(WatcherHeartbeatRow).where(
                    WatcherHeartbeatRow.organization_id == organization_id
                )
            ).all()
        }
        attempts = _latest_attempts_by_scope(self._session, organization_id)
        if not leases and not heartbeats:
            return [], None

        scopes = sorted({row.scan_scope for row in leases} | set(heartbeats))
        items: list[WatcherLeaseHealth] = []
        snapshots: list[WatcherHealthSnapshot] = []
        for scope in scopes:
            lease_row = next((row for row in leases if row.scan_scope == scope), None)
            beat_row = heartbeats.get(scope)
            lease = None if lease_row is None else _lease_from_row(lease_row)
            heartbeat = None if beat_row is None else _heartbeat_from_row(beat_row)
            attempt = attempts.get(scope)
            snapshot = project_health(
                organization_id=organization_id,
                scan_scope=scope,
                config=config,
                now=now,
                lease=lease,
                heartbeat=heartbeat,
                latest_attempt=attempt,
            )
            snapshots.append(snapshot)
            fenced = snapshot.lease_owner is not None
            fresh = (
                snapshot.seconds_since_beat is not None
                and snapshot.seconds_since_beat <= float(config.heartbeat_stale_after_seconds)
            )
            items.append(
                WatcherLeaseHealth(
                    scan_scope=scope,
                    owner_id=snapshot.lease_owner,
                    lease_epoch=snapshot.lease_epoch,
                    fencing_token=snapshot.fencing_token,
                    expires_at=snapshot.lease_expires_at,
                    last_beat_at=snapshot.last_beat_at,
                    seconds_since_beat=snapshot.seconds_since_beat,
                    fenced=fenced,
                    heartbeat_fresh=fresh,
                    orchestration_state=snapshot.state.value,
                    reason_code=snapshot.reason_code,
                )
            )
        return items, _worst_orchestration_snapshot(snapshots)

    def _provider_health(self) -> list[WatcherProviderHealthItem]:
        registry: _ProviderStatusSource = (
            self._providers if self._providers is not None else get_provider_registry()
        )
        items: list[WatcherProviderHealthItem] = []
        try:
            statuses = registry.statuses()
        except Exception:
            logger.warning("watcher_monitoring_provider_status_failed", exc_info=True)
            return []
        for status in statuses:
            items.append(
                WatcherProviderHealthItem(
                    name=status.name,
                    kind=(
                        status.kind.value
                        if isinstance(status.kind, ProviderKind)
                        else str(status.kind)
                    ),
                    health=(
                        status.health.value
                        if isinstance(status.health, ProviderHealth)
                        else str(status.health)
                    ),
                    using_fallback=status.using_fallback,
                    is_mock=status.is_mock,
                    detail=_sanitize(status.detail),
                    error_message=_sanitize(status.error_message),
                )
            )
        return items

    def _kill_switch(self, organization_id: uuid.UUID) -> tuple[bool, str | None]:
        if self._settings.global_kill_switch_active:
            return True, "global_kill_switch_active"
        try:
            row = self._session.scalar(
                select(KillSwitchState).where(KillSwitchState.organization_id == organization_id)
            )
        except Exception:
            logger.warning("watcher_monitoring_kill_switch_read_failed", exc_info=True)
            return True, "kill_switch_unavailable"
        if row is not None and row.active:
            return True, "kill_switch_active"
        return False, None

    def _approved_strategies(self, organization_id: uuid.UUID) -> list[WatcherApprovedStrategy]:
        compiled_rows = list(
            self._session.scalars(
                select(CompiledSetupDefinition)
                .where(
                    CompiledSetupDefinition.organization_id == organization_id,
                    CompiledSetupDefinition.compile_status == SetupCompileStatus.EXECUTABLE,
                )
                .order_by(CompiledSetupDefinition.created_at.desc())
                .limit(50)
            ).all()
        )
        approved: list[WatcherApprovedStrategy] = []
        for compiled in compiled_rows:
            event = self._latest_lifecycle(compiled.strategy_version_id)
            if event is None or event.new_state not in _APPROVED_STATES:
                continue
            strategy = self._session.get(UserStrategy, compiled.strategy_id)
            version = self._session.get(UserStrategyVersion, compiled.strategy_version_id)
            if strategy is None or version is None:
                continue
            if strategy.organization_id != organization_id:
                continue
            approved.append(
                WatcherApprovedStrategy(
                    strategy_id=strategy.id,
                    strategy_version_id=version.id,
                    name=strategy.name,
                    lifecycle_state=event.new_state.value,
                    compiled=True,
                )
            )
        return approved

    def _latest_lifecycle(self, strategy_version_id: uuid.UUID) -> StrategyLifecycleEvent | None:
        return self._session.scalar(
            select(StrategyLifecycleEvent)
            .where(StrategyLifecycleEvent.strategy_version_id == strategy_version_id)
            .order_by(
                StrategyLifecycleEvent.occurred_at.desc(),
                StrategyLifecycleEvent.created_at.desc(),
            )
            .limit(1)
        )

    def _canonical_lineage(
        self, organization_id: uuid.UUID
    ) -> tuple[
        list[WatcherSetupAssessmentSummary],
        list[WatcherCanonicalCandidateSummary],
        list[str],
    ]:
        runtime = self._canonical_runtime
        if runtime is None:
            return [], [], []
        limitations: list[str] = []
        try:
            items, _total = runtime.candidate_repository.list_for_organization(
                organization_id, limit=10, offset=0
            )
        except Exception:
            logger.warning("watcher_monitoring_canonical_candidates_failed", exc_info=True)
            return [], [], ["Canonical Candidate lineage unavailable."]
        assessments: list[WatcherSetupAssessmentSummary] = []
        candidates: list[WatcherCanonicalCandidateSummary] = []
        seen_assessments: set[uuid.UUID] = set()
        for candidate in items:
            candidates.append(
                WatcherCanonicalCandidateSummary(
                    candidate_id=candidate.candidate_id,
                    assessment_id=candidate.assessment_id,
                    state=candidate.state.value,
                    instrument=candidate.evidence_instrument,
                    timeframe=candidate.timeframe.value,
                    strategy_version_id=candidate.strategy_version_id,
                    created_at=candidate.created_at,
                )
            )
            if candidate.assessment_id in seen_assessments:
                continue
            seen_assessments.add(candidate.assessment_id)
            assessments.append(
                WatcherSetupAssessmentSummary(
                    assessment_id=candidate.assessment_id,
                    candidate_id=candidate.candidate_id,
                    state=SetupAssessmentState.CONFIRMED_SETUP,
                    strategy_version_id=candidate.strategy_version_id,
                    instrument=candidate.evidence_instrument,
                    timeframe=candidate.timeframe.value,
                    valid_until=candidate.valid_until,
                )
            )
        if not items:
            limitations.append("No persisted canonical Candidates or SetupAssessments.")
        return assessments, candidates, limitations

    def _recent_errors(
        self,
        *,
        organization_id: uuid.UUID,
        last_scan_error: str | None,
        last_scan_at: datetime | None,
        worker: WatcherWorkerHealth,
        providers: list[WatcherProviderHealthItem],
    ) -> list[WatcherRecentError]:
        errors: list[WatcherRecentError] = []
        if last_scan_error:
            errors.append(
                WatcherRecentError(
                    source="market_watcher_scan",
                    message=last_scan_error,
                    at=last_scan_at,
                    reason_code="last_scan_error",
                )
            )
        if worker.status == "error" and worker.detail:
            errors.append(
                WatcherRecentError(
                    source="worker",
                    message=worker.detail,
                    at=worker.last_beat_at,
                    reason_code="worker_error",
                )
            )
        for provider in providers:
            if provider.health in {"degraded", "unavailable"} and (
                provider.error_message or provider.detail
            ):
                errors.append(
                    WatcherRecentError(
                        source=f"provider:{provider.name}",
                        message=provider.error_message or provider.detail or provider.health,
                        reason_code=provider.health,
                    )
                )
        event_rows = list(
            self._session.scalars(
                select(WatcherObservabilityEventRow)
                .where(WatcherObservabilityEventRow.organization_id == organization_id)
                .order_by(WatcherObservabilityEventRow.at.desc())
                .limit(20)
            ).all()
        )
        for event in event_rows:
            lowered = event.name.lower()
            if not any(marker in lowered for marker in _ERROR_EVENT_MARKERS):
                continue
            field_error = None
            if isinstance(event.fields, dict):
                raw = event.fields.get("error") or event.fields.get("reason_code")
                field_error = str(raw) if raw is not None else None
            errors.append(
                WatcherRecentError(
                    source="watcher_observability",
                    message=_sanitize(field_error) or event.name,
                    at=event.at,
                    reason_code=event.name,
                )
            )
        return errors[:10]


def _config_enabled(settings: Settings) -> bool:
    return bool(
        settings.market_watcher_enabled
        or settings.watcher_orchestration_enabled
        or (settings.market_watcher_enabled and settings.worker_enabled)
    )


def _telegram_enabled(settings: Settings) -> bool:
    return bool(
        settings.telegram_alerts_enabled
        or settings.telegram_interaction_enabled
        or settings.automatic_telegram_delivery_enabled
    )


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _sanitize(value: str | None) -> str | None:
    if not value:
        return None
    return redact_text(value)[:255]


def _lease_from_row(row: WatcherWorkerLeaseRow) -> WorkerLease:
    return WorkerLease(
        scan_scope=row.scan_scope,
        organization_id=row.organization_id,
        owner_id=row.owner_id,
        lease_epoch=row.lease_epoch,
        fencing_token=row.fencing_token,
        acquired_at=_aware(row.acquired_at),
        renewed_at=_aware(row.renewed_at),
        expires_at=_aware(row.expires_at),
    )


def _heartbeat_from_row(row: WatcherHeartbeatRow) -> WatcherHeartbeat | None:
    last_beat = _aware(row.last_beat_at)
    if last_beat is None:
        return None
    return WatcherHeartbeat(
        organization_id=row.organization_id,
        scan_scope=row.scan_scope,
        owner_id=row.owner_id,
        lease_epoch=row.lease_epoch,
        fencing_token=row.fencing_token,
        last_beat_at=last_beat,
        detail=row.detail,
    )


def _attempt_from_row(row: WatcherScanAttemptRow) -> ScanAttempt | None:
    started_at = _aware(row.started_at)
    heartbeat_at = _aware(row.heartbeat_at)
    if started_at is None or heartbeat_at is None:
        return None
    return ScanAttempt(
        attempt_id=row.attempt_id,
        lineage_id=row.lineage_id,
        attempt_number=row.attempt_number,
        worker_id=row.worker_id,
        lease_epoch=row.lease_epoch,
        fencing_token=row.fencing_token,
        trigger=ScanTrigger(row.trigger),
        mode=EvaluationMode(row.mode),
        status=ScanAttemptStatus(row.status),
        started_at=started_at,
        heartbeat_at=heartbeat_at,
        finished_at=_aware(row.finished_at),
        sanitized_error=row.sanitized_error,
        recovery_disposition=RecoveryDisposition(row.recovery_disposition),
        recovered_from_attempt_id=row.recovered_from_attempt_id,
        outcome_reason_code=row.outcome_reason_code,
        evaluation_input_hash=row.evaluation_input_hash,
    )


def _latest_attempts_by_scope(
    session: Session, organization_id: uuid.UUID
) -> dict[str, ScanAttempt]:
    rows = list(
        session.scalars(
            select(WatcherScanAttemptRow)
            .where(WatcherScanAttemptRow.organization_id == organization_id)
            .order_by(
                WatcherScanAttemptRow.started_at.desc(),
                WatcherScanAttemptRow.attempt_number.desc(),
            )
        ).all()
    )
    latest: dict[str, ScanAttempt] = {}
    for row in rows:
        if row.scan_scope in latest:
            continue
        try:
            attempt = _attempt_from_row(row)
        except (ValueError, TypeError):
            logger.warning(
                "watcher_monitoring_attempt_unreadable",
                scan_scope=row.scan_scope,
                attempt_id=str(row.attempt_id),
            )
            continue
        if attempt is None:
            continue
        latest[row.scan_scope] = attempt
    return latest


def _worst_orchestration_snapshot(
    snapshots: list[WatcherHealthSnapshot],
) -> WatcherHealthSnapshot | None:
    if not snapshots:
        return None
    rank = {"blocked": 4, "stale": 3, "degraded": 2, "healthy": 1}
    return max(snapshots, key=lambda item: rank.get(item.state.value, 0))


def _worst_market_data_health(providers: list[WatcherProviderHealthItem]) -> str | None:
    market = [item for item in providers if item.kind == ProviderKind.MARKET_DATA.value]
    if not market:
        return None
    if any(item.health == "unavailable" for item in market):
        return "unavailable"
    if any(item.health == "degraded" for item in market):
        return "degraded"
    return "healthy"


def _market_freshness(
    *,
    observation: MarketWatcherObservation | None,
    stale_after_minutes: int,
) -> WatcherMarketFreshness:
    if observation is None:
        return WatcherMarketFreshness(
            status="unknown",
            stale_after_minutes=stale_after_minutes,
        )
    status = str(observation.status)
    freshness_status = status if status in {"fresh", "stale", "unavailable"} else "unknown"
    return WatcherMarketFreshness(
        status=freshness_status,  # type: ignore[arg-type]
        observed_at=_aware(observation.observed_at),
        symbol=observation.symbol,
        data_freshness=observation.data_freshness,
        stale_after_minutes=stale_after_minutes,
    )


def _next_scan(
    *,
    decision: WatcherMonitoringDecision,
    settings: Settings,
    worker: WatcherWorkerHealth,
    primary_lease: WatcherLeaseHealth | None,
    now: datetime,
) -> tuple[datetime | None, Literal["worker_interval", "lease_ttl", "bridge_interval"] | None]:
    if decision.state in {
        WatcherMonitoringRuntimeState.STOPPED,
        WatcherMonitoringRuntimeState.BLOCKED,
    }:
        return None, None
    if not decision.runtime_evidence:
        return None, None
    if (
        settings.market_watcher_bridge_auto_tick
        and settings.market_watcher_bridge_enabled
        and primary_lease is not None
        and primary_lease.last_beat_at is not None
    ):
        return (
            primary_lease.last_beat_at
            + timedelta(seconds=settings.market_watcher_bridge_interval_seconds),
            "bridge_interval",
        )
    if (
        settings.watcher_orchestration_enabled
        and primary_lease is not None
        and primary_lease.last_beat_at is not None
    ):
        return (
            primary_lease.last_beat_at + timedelta(seconds=settings.watcher_lease_ttl_seconds),
            "lease_ttl",
        )
    if worker.heartbeat_live and worker.last_beat_at is not None:
        return (
            worker.last_beat_at + timedelta(seconds=settings.worker_scan_interval_seconds),
            "worker_interval",
        )
    _ = now
    return None, None
