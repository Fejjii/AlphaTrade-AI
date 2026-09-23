"""Continuous paper-only Watcher runtime.

Approved compiled strategy → read-only market evidence → WatcherOrchestrator
scan → evaluate_canonical_strategy → Candidate only on CONFIRMED_SETUP.

Never places orders and never starts Telegram. Local paper monitoring stays
opt-in. Staging scans only after the paper-activation preflight clears, and
production stays dark. Candidate persistence still requires persisted approved
compiled authority.
"""

from __future__ import annotations

import signal
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import FrameType
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Environment, ExecutionMode, Settings
from app.runtime_safety.paper_actions import (
    automated_paper_actions_blocked,
    read_kill_switch_active,
)
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.watcher.contracts import (
    EvaluationMode,
    ScanRequest,
    WatcherPolicyIdentity,
    WatcherPolicyVersion,
    WatcherRuntimeConfig,
    WorkerCycleResult,
    WorkerCycleStatus,
)
from app.watcher.fusion_evaluation import (
    BoundEvaluationClock,
    CandidatePersistenceFence,
    EvaluationOutcomeObserver,
    WatcherDiscussionSnapshot,
    WatcherFusionEvaluationService,
    WatcherScanEvidencePort,
    build_fusion_evaluation_service,
)
from app.watcher.hashing import policy_content_hash
from app.watcher.memory import SideEffectProbe
from app.watcher.orchestrator import WatcherOrchestrator
from app.watcher.paper_metrics import (
    observe_candidates,
    observe_cycle,
    observe_scan,
    set_runtime_active,
)
from app.watcher.ports import Clock, SideEffectPorts, WatcherStore
from app.workers.watcher_paper_targets import (
    FIRST_SLICE_SYMBOL,
    PaperScanTarget,
    list_paper_scan_targets,
    normalize_paper_symbols,
)

if TYPE_CHECKING:
    from app.market_monitor.monitor import PerpetualMarketMonitor

logger = structlog.get_logger("workers.watcher_paper")

PaperEvidenceFactory = Callable[[Session | None, WatcherStore, str], WatcherScanEvidencePort]
PaperTargetLoader = Callable[[Session | None], tuple[PaperScanTarget, ...]]
KillSwitchProbe = Callable[[UUID], bool]
ActivationGate = Callable[[], object]
EvaluationObserverFactory = Callable[
    [Session | None, PaperScanTarget], EvaluationOutcomeObserver | None
]


@dataclass(frozen=True, slots=True)
class WatcherPaperScanReport:
    organization_id: UUID
    scan_scope: str
    symbol: str
    status: str
    reason_code: str
    replayed: bool
    published: bool
    candidate_ids: tuple[UUID, ...]
    kill_switch_active: bool
    lease_owner: str | None = None
    health_state: str = "unknown"
    user_id: UUID | None = None
    request_hash: str | None = None
    lineage_id: UUID | None = None
    discussion: WatcherDiscussionSnapshot | None = None


@dataclass(frozen=True, slots=True)
class WatcherPaperCycleReport:
    reason_code: str
    enabled: bool
    scans: tuple[WatcherPaperScanReport, ...]
    candidates_created: int
    kill_switch_active: bool


@dataclass
class WatcherPaperStatusState:
    enabled: bool
    running: bool = False
    stopping: bool = False
    worker_id: str = "watcher-paper-1"
    symbols: tuple[str, ...] = (FIRST_SLICE_SYMBOL,)
    poll_interval_seconds: float = 15.0
    max_scopes_per_cycle: int = 20
    last_cycle_at: datetime | None = None
    last_reason_code: str = "idle"
    cycles_completed: int = 0
    scans_succeeded: int = 0
    scans_failed: int = 0
    scans_skipped: int = 0
    scans_blocked: int = 0
    candidates_created: int = 0
    kill_switch_active: bool = False
    last_scans: tuple[WatcherPaperScanReport, ...] = field(default_factory=tuple)


def last_closed_interval_end(moment: datetime, *, minutes: int = 15) -> datetime:
    """Interval end of the last fully closed ``minutes`` bar (UTC)."""

    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    aware = aware.astimezone(UTC)
    floored = aware.replace(second=0, microsecond=0)
    remainder = floored.minute % minutes
    return floored - timedelta(minutes=remainder)


def new_worker_instance_id(configured_id: str) -> str:
    """Unique process identity. Autostart and the dedicated worker never share one."""

    prefix = configured_id.strip()
    if not prefix:
        raise ValueError("watcher worker id is required")
    return f"{prefix[:80]}:{uuid4().hex[:16]}"


def paper_lease_ttl_seconds(settings: Settings) -> int:
    """Floor the lease for several Binance timeouts plus bounded backoff.

    The floor is ``timeout * 4 + max_backoff + 15``, capped at 3600. Callers
    that pass ``lease_ttl_seconds`` explicitly keep that value. The default
    30 second setting is unchanged for non-Binance evidence.
    """

    configured = int(settings.watcher_lease_ttl_seconds)
    if settings.perpetual_evidence_source.strip().lower() != "binance_usdm":
        return configured
    timeout = float(settings.perpetual_evidence_timeout_seconds)
    backoff = float(settings.binance_request_max_backoff_seconds)
    floor = int(timeout * 4 + backoff + 15)
    return min(3600, max(configured, floor))


def paper_runtime_enabled(settings: Settings) -> bool:
    """True only for local paper monitoring. Staging uses the activation gate."""

    return (
        bool(settings.watcher_orchestration_enabled)
        and settings.environment is Environment.LOCAL
        and settings.execution_mode is ExecutionMode.PAPER
        and not settings.enable_real_trading
        and not settings.real_trading_enabled
    )


def resolve_runtime_enabled(
    settings: Settings,
    *,
    enabled: bool | None = None,
    activation_cleared: bool = False,
) -> bool:
    """Local override stays explicit. Staging scans only after preflight clearance."""

    if settings.environment is Environment.STAGING:
        if not enabled or not activation_cleared:
            return False
        from app.workers.watcher_activation import staging_static_arm_ok

        return staging_static_arm_ok(settings)
    if enabled is not None:
        return enabled
    return paper_runtime_enabled(settings)


class WatcherPaperRuntime:
    """Bounded polling worker. One active lease holder per tenant scan scope."""

    def __init__(
        self,
        *,
        store: WatcherStore,
        lifecycle: CandidateLifecycleService,
        clock: Clock,
        enabled: bool,
        worker_id: str = "watcher-paper-1",
        symbols: Sequence[str] = (FIRST_SLICE_SYMBOL,),
        poll_interval_seconds: float = 15.0,
        max_scopes_per_cycle: int = 20,
        lease_ttl_seconds: int = 30,
        heartbeat_stale_after_seconds: int = 90,
        session_factory: sessionmaker[Session] | None = None,
        evidence_factory: PaperEvidenceFactory | None = None,
        target_loader: PaperTargetLoader | None = None,
        kill_switch_probe: KillSwitchProbe | None = None,
        persistence_fence: CandidatePersistenceFence | None = None,
        side_effects: SideEffectPorts | None = None,
        settings: Settings | None = None,
        evaluation_clock: BoundEvaluationClock | None = None,
        scan_notification_hook: Callable[[WatcherPaperScanReport], None] | None = None,
        evaluation_observer_factory: EvaluationObserverFactory | None = None,
        activation_gate: ActivationGate | None = None,
    ) -> None:
        self._store = store
        self._lifecycle = lifecycle
        self._clock = clock
        self._enabled = enabled
        self._worker_id = worker_id
        self._symbols = normalize_paper_symbols(symbols)
        self._poll_interval_seconds = poll_interval_seconds
        self._max_scopes_per_cycle = max_scopes_per_cycle
        self._lease_ttl_seconds = lease_ttl_seconds
        self._heartbeat_stale_after_seconds = heartbeat_stale_after_seconds
        self._session_factory = session_factory
        self._evidence_factory = evidence_factory
        self._target_loader = target_loader
        self._kill_switch_probe = kill_switch_probe
        self._persistence_fence = persistence_fence
        self._side_effects = side_effects if side_effects is not None else SideEffectProbe()
        self._settings = settings
        self._eval_clock = _shared_evaluation_clock(lifecycle, evaluation_clock)
        self._scan_notification_hook = scan_notification_hook
        self._activation_gate = activation_gate
        self._observer_factory = (
            self._evaluation_observer
            if evaluation_observer_factory is None
            else evaluation_observer_factory
        )
        if self._eval_clock is not getattr(lifecycle, "_clock", None):
            repository = getattr(lifecycle, "_repository", None)
            if repository is not None:
                self._lifecycle = CandidateLifecycleService(
                    repository=repository, clock=self._eval_clock
                )
        self._stop = threading.Event()
        self._market_source = ""
        self._freshness_seconds: float | None = None
        self._gate_refusals = 0
        self._thread: threading.Thread | None = None
        self._status_lock = threading.Lock()
        self._held_fencing_tokens: dict[str, int] = {}
        self._status = WatcherPaperStatusState(
            enabled=enabled,
            worker_id=worker_id,
            symbols=self._symbols,
            poll_interval_seconds=poll_interval_seconds,
            max_scopes_per_cycle=max_scopes_per_cycle,
        )

    @property
    def store(self) -> WatcherStore:
        return self._store

    @property
    def side_effects(self) -> SideEffectPorts:
        return self._side_effects

    def snapshot(self) -> WatcherPaperStatusState:
        with self._status_lock:
            current = self._status
            return WatcherPaperStatusState(
                enabled=current.enabled,
                running=current.running,
                stopping=current.stopping,
                worker_id=current.worker_id,
                symbols=current.symbols,
                poll_interval_seconds=current.poll_interval_seconds,
                max_scopes_per_cycle=current.max_scopes_per_cycle,
                last_cycle_at=current.last_cycle_at,
                last_reason_code=current.last_reason_code,
                cycles_completed=current.cycles_completed,
                scans_succeeded=current.scans_succeeded,
                scans_failed=current.scans_failed,
                scans_skipped=current.scans_skipped,
                scans_blocked=current.scans_blocked,
                candidates_created=current.candidates_created,
                kill_switch_active=current.kill_switch_active,
                last_scans=current.last_scans,
            )

    def note_market_observation(self, *, source: str, freshness_seconds: float | None) -> None:
        """Remember the latest provider probe. This does not mint a Candidate."""

        self._market_source = source
        self._freshness_seconds = freshness_seconds

    def stop(self) -> None:
        self._stop.set()
        with self._status_lock:
            self._status.stopping = True
            self._status.running = False
        set_runtime_active(False)
        logger.info("watcher_paper_runtime_stop", worker_id=self._worker_id)

    def run_loop(self, *, max_cycles: int | None = None) -> int:
        """Run bounded poll cycles until stopped. Interruptible sleep."""

        cycles = 0
        self._stop.clear()
        with self._status_lock:
            self._status.running = True
            self._status.stopping = False
        set_runtime_active(True)
        logger.info(
            "watcher_paper_runtime_start",
            worker_id=self._worker_id,
            enabled=self._enabled,
            symbols=list(self._symbols),
            poll_interval_seconds=self._poll_interval_seconds,
            paper_only=True,
            real_trading_enabled=False,
        )
        try:
            while not self._stop.is_set():
                try:
                    report = self.run_cycle()
                except Exception:
                    logger.error("watcher_paper_cycle_error", exc_info=True)
                    observe_cycle("failed")
                    report = None
                cycles += 1
                if max_cycles is not None and cycles >= max_cycles:
                    break
                wait = self._poll_interval_seconds if report is None else self._wait_seconds(report)
                self._stop.wait(wait)
        finally:
            with self._status_lock:
                self._status.running = False
            set_runtime_active(False)
        return cycles

    def start_background_thread(self) -> threading.Thread:
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop.clear()
        thread = threading.Thread(
            target=self.run_loop,
            name="watcher-paper-runtime",
            daemon=True,
        )
        thread.start()
        self._thread = thread
        return thread

    def run_forever(self) -> int:
        """Block until SIGINT/SIGTERM. Dedicated process entry."""

        def _handle(_signum: int, _frame: FrameType | None) -> None:
            self.stop()

        signal.signal(signal.SIGINT, _handle)
        signal.signal(signal.SIGTERM, _handle)
        return self.run_loop()

    def run_cycle(self) -> WatcherPaperCycleReport:
        refused = self._activation_refusal()
        if refused is not None:
            return refused
        if not self._enabled:
            report = WatcherPaperCycleReport(
                reason_code="watcher_disabled",
                enabled=False,
                scans=(),
                candidates_created=0,
                kill_switch_active=False,
            )
            observe_cycle("watcher_disabled")
            self._remember_cycle(report)
            return report

        session: Session | None = None
        close_session = False
        if self._session_factory is not None:
            session = self._session_factory()
            close_session = True
        try:
            targets = self._load_targets(session)
            scans: list[WatcherPaperScanReport] = []
            any_kill = False
            created = 0
            for target in targets:
                scan = self._scan_one(session, target)
                scans.append(scan)
                created += len(scan.candidate_ids)
                any_kill = any_kill or scan.kill_switch_active
        finally:
            if close_session and session is not None:
                session.close()

        reason = "idle" if not scans else "completed"
        report = WatcherPaperCycleReport(
            reason_code=reason,
            enabled=True,
            scans=tuple(scans),
            candidates_created=created,
            kill_switch_active=any_kill,
        )
        observe_cycle(reason)
        observe_candidates(created)
        self._remember_cycle(report)
        logger.info(
            "watcher_paper_cycle",
            worker_id=self._worker_id,
            scans=len(scans),
            candidates_created=created,
            kill_switch_active=any_kill,
            reason_code=reason,
        )
        return report

    def _activation_refusal(self) -> WatcherPaperCycleReport | None:
        gate = self._activation_gate
        if gate is None:
            return None
        try:
            decision = gate()
        except Exception:
            logger.error(
                "watcher_paper_activation_gate_error",
                worker_id=self._worker_id,
            )
            reason = "activation_gate_error"
        else:
            reason_or_none = _gate_refusal_reason(decision)
            if reason_or_none is None:
                return None
            reason = reason_or_none
        report = WatcherPaperCycleReport(
            reason_code=reason,
            enabled=False,
            scans=(),
            candidates_created=0,
            kill_switch_active=False,
        )
        observe_cycle("activation_refused")
        self._remember_cycle(report)
        logger.warning(
            "watcher_paper_activation_rollback",
            worker_id=self._worker_id,
            reason_code=reason,
            paper_only=True,
        )
        return report

    def _load_targets(self, session: Session | None) -> tuple[PaperScanTarget, ...]:
        if self._target_loader is not None:
            return self._target_loader(session)[: self._max_scopes_per_cycle]
        if session is None:
            return ()
        return list_paper_scan_targets(
            session,
            symbols=self._symbols,
            limit=self._max_scopes_per_cycle,
        )

    def _scan_one(self, session: Session | None, target: PaperScanTarget) -> WatcherPaperScanReport:
        try:
            # Candidate writes lock watcher_worker_leases in their own transaction
            # and commit before the orchestrator heartbeats that same row. Binding
            # this scan session across run_worker holds that lock and deadlocks.
            report = self._scan_target(session, target)
            if session is not None:
                session.commit()
            return report
        except Exception:
            if session is not None:
                session.rollback()
            logger.error(
                "watcher_paper_scan_error",
                worker_id=self._worker_id,
                organization_id=str(target.organization_id),
                scan_scope=target.scan_scope,
                symbol=target.symbol,
                exc_info=True,
            )
            observe_scan("failed")
            return WatcherPaperScanReport(
                organization_id=target.organization_id,
                scan_scope=target.scan_scope,
                symbol=target.symbol,
                status="failed",
                reason_code="evaluation_exception",
                replayed=False,
                published=False,
                candidate_ids=(),
                kill_switch_active=self._kill_switch_is_active(session, target.organization_id),
                user_id=target.user_id,
            )

    def _scan_target(
        self, session: Session | None, target: PaperScanTarget
    ) -> WatcherPaperScanReport:
        kill_active = self._kill_switch_is_active(session, target.organization_id)
        if automated_paper_actions_blocked(kill_active):
            report = WatcherPaperScanReport(
                organization_id=target.organization_id,
                scan_scope=target.scan_scope,
                symbol=target.symbol,
                status="blocked",
                reason_code="kill_switch_active",
                replayed=False,
                published=False,
                candidate_ids=(),
                kill_switch_active=True,
                user_id=target.user_id,
            )
            observe_scan(report.reason_code)
            logger.info(
                "watcher_paper_scan",
                worker_id=self._worker_id,
                organization_id=str(target.organization_id),
                scan_scope=target.scan_scope,
                symbol=target.symbol,
                status=report.status,
                reason_code=report.reason_code,
                kill_switch_active=True,
                paper_only=True,
            )
            return report
        policy = self._materialize_policy(target)
        request = ScanRequest(
            organization_id=target.organization_id,
            principal_id=None,
            scan_scope=target.scan_scope,
            policy_id=policy.identity.policy_id,
            policy_version=policy.version,
            policy_content_hash=policy.content_hash,
            watchlist_item_ids=(policy.identity.watchlist_item_id,),
            timeframe=target.timeframe,
            idempotency_key=self._idempotency_key(target),
        )
        evidence = self._build_evidence(session, target.symbol)
        evaluator = build_fusion_evaluation_service(
            evidence=evidence,
            lifecycle=self._lifecycle,
            clock=self._eval_clock,
            persistence_fence=self._persistence_fence,
            outcome_observer=self._observer_factory(session, target),
        )
        orchestrator = WatcherOrchestrator(
            store=self._store,
            evaluator=evaluator,
            clock=self._clock,
            config=WatcherRuntimeConfig(
                enabled=True,
                lease_ttl_seconds=self._lease_ttl_seconds,
                heartbeat_stale_after_seconds=self._heartbeat_stale_after_seconds,
            ),
            side_effects=self._side_effects,
        )
        result = orchestrator.run_worker(
            request,
            worker_id=self._worker_id,
            held_fencing_token=self._held_fencing_tokens.get(target.scan_scope),
        )
        if result.fencing_token is not None:
            self._held_fencing_tokens[target.scan_scope] = result.fencing_token
        report = _report_from_cycle(
            target=target,
            result=result,
            kill_switch_active=kill_active,
            evaluator=evaluator,
        )
        self._notify_scan(report)
        observe_scan(report.reason_code)
        logger.info(
            "watcher_paper_scan",
            worker_id=self._worker_id,
            organization_id=str(target.organization_id),
            scan_scope=target.scan_scope,
            symbol=target.symbol,
            status=report.status,
            reason_code=report.reason_code,
            replayed=report.replayed,
            published=report.published,
            candidates=len(report.candidate_ids),
            kill_switch_active=kill_active,
            mode=EvaluationMode.PERSIST_EVIDENCE.value,
            paper_only=True,
        )
        return report

    def _build_evidence(self, session: Session | None, symbol: str) -> WatcherScanEvidencePort:
        if self._evidence_factory is None:
            raise RuntimeError("Paper Watcher evidence factory is required.")
        return self._evidence_factory(session, self._store, symbol)

    def _evaluation_observer(
        self, session: Session | None, target: PaperScanTarget
    ) -> EvaluationOutcomeObserver | None:
        if session is None:
            return None
        from app.paper_evaluation.recorder import PaperEvaluationRecorder
        from app.paper_evaluation.watcher_observer import WatcherPaperEvaluationObserver
        from app.persistence.paper_evaluation_postgres import PostgresPaperEvaluationStore

        recorder = PaperEvaluationRecorder(PostgresPaperEvaluationStore(session))
        return WatcherPaperEvaluationObserver(
            recorder,
            strategy_version_id=target.strategy_version_id,
            setup_definition_id=target.compiled_setup_definition_id,
        )

    def _materialize_policy(self, target: PaperScanTarget) -> WatcherPolicyVersion:
        identity = WatcherPolicyIdentity(
            policy_id=target.policy_id,
            organization_id=target.organization_id,
            user_id=target.user_id,
            watchlist_item_id=target.watchlist_item_id,
        )
        draft = WatcherPolicyVersion(
            identity=identity,
            version=1,
            timeframe=target.timeframe,
            strategy_version_id=target.strategy_version_id,
            setup_definition_id=target.compiled_setup_definition_id,
            fusion_policy_version=target.fusion_policy_version,
            enabled=True,
            created_by=target.user_id,
            created_at=self._clock.now(),
            content_hash="0" * 64,
        )
        hashed = draft.model_copy(update={"content_hash": policy_content_hash(draft)})
        return self._store.put_policy_version(hashed)

    def _idempotency_key(self, target: PaperScanTarget) -> str:
        closed = last_closed_interval_end(self._clock.now())
        stamp = closed.strftime("%Y%m%dT%H%M%SZ")
        return f"watcher-paper:{target.policy_id}:{target.symbol}:{stamp}"

    def _kill_switch_is_active(self, session: Session | None, organization_id: UUID) -> bool:
        if self._kill_switch_probe is not None:
            try:
                return bool(self._kill_switch_probe(organization_id))
            except Exception:
                logger.warning(
                    "watcher_paper_kill_switch_unavailable",
                    organization_id=str(organization_id),
                )
                return True
        try:
            return read_kill_switch_active(session, self._settings, organization_id)
        except Exception:
            logger.warning(
                "watcher_paper_kill_switch_unavailable",
                organization_id=str(organization_id),
            )
            return True

    def _notify_scan(self, report: WatcherPaperScanReport) -> None:
        """Optional paper notification. Default hook is unset, so scans do not send."""

        hook = self._scan_notification_hook
        if hook is None:
            return
        try:
            hook(report)
        except Exception:
            logger.warning(
                "watcher_paper_notification_hook_failed",
                organization_id=str(report.organization_id),
                scan_scope=report.scan_scope,
                reason_code=report.reason_code,
            )

    def _remember_cycle(self, report: WatcherPaperCycleReport) -> None:
        succeeded = failed = skipped = blocked = 0
        for scan in report.scans:
            if scan.status in {"succeeded"}:
                succeeded += 1
            elif scan.status in {"failed"}:
                failed += 1
            elif scan.status in {"skipped"}:
                skipped += 1
            elif scan.status in {"blocked"}:
                blocked += 1
            else:
                failed += 1
        with self._status_lock:
            self._status.last_cycle_at = self._clock.now()
            self._status.last_reason_code = report.reason_code
            self._status.cycles_completed += 1
            self._status.scans_succeeded += succeeded
            self._status.scans_failed += failed
            self._status.scans_skipped += skipped
            self._status.scans_blocked += blocked
            self._status.candidates_created += report.candidates_created
            self._status.kill_switch_active = report.kill_switch_active
            self._status.last_scans = report.scans
        self._publish_observed_status(report)

    def _wait_seconds(self, report: WatcherPaperCycleReport) -> float:
        refusal = (not report.enabled) and report.reason_code != "watcher_disabled"
        if not refusal:
            self._gate_refusals = 0
            return self._poll_interval_seconds
        self._gate_refusals += 1
        scaled = float(self._poll_interval_seconds) * float(2 ** min(self._gate_refusals, 3))
        return min(60.0, scaled)

    def _publish_observed_status(self, report: WatcherPaperCycleReport) -> None:
        if self._session_factory is None:
            return
        from app.market_contracts.adapters.request_budget import market_request_metrics
        from app.persistence.runtime_status import (
            WATCHER_COMPONENT,
            RuntimeStatusWrite,
            publish_runtime_status,
        )

        metrics = market_request_metrics()
        lease_owner = ""
        lease_epoch = 0
        for scan in report.scans:
            if scan.lease_owner:
                lease_owner = scan.lease_owner
                lease_epoch = int(self._held_fencing_tokens.get(scan.scan_scope, 0))
                break
        if report.kill_switch_active:
            state = "monitoring"
        elif not report.enabled and report.reason_code != "watcher_disabled":
            state = "refused"
        elif report.enabled:
            state = "running"
        else:
            state = "disarmed"
        inbound = "off"
        if self._settings is not None:
            inbound = self._settings.telegram_inbound_mode.value
        try:
            publish_runtime_status(
                self._session_factory,
                RuntimeStatusWrite(
                    component=WATCHER_COMPONENT,
                    worker_id=self._worker_id,
                    heartbeat_at=self._clock.now(),
                    activation_state=state,
                    lease_owner=lease_owner,
                    lease_epoch=lease_epoch,
                    fence_held=bool(lease_owner),
                    last_scan_at=self._clock.now(),
                    last_scan_reason=report.reason_code,
                    market_source=self._market_source,
                    freshness_seconds=self._freshness_seconds,
                    telegram_runtime_state="absent",
                    inbound_mode=inbound,
                    kill_switch_active=report.kill_switch_active,
                    request_count=metrics.requests,
                    request_weight=metrics.weight_used,
                    rate_limited_count=metrics.rate_limited,
                    cache_hits=metrics.cache_hits,
                ),
            )
        except Exception:
            logger.warning(
                "watcher_runtime_status_unpublished",
                worker_id=self._worker_id,
            )


def _gate_refusal_reason(decision: object) -> str | None:
    allowed = getattr(decision, "allowed", None)
    if allowed is True:
        return None
    reason = getattr(decision, "primary_reason", None)
    if isinstance(reason, str) and reason and reason != "cleared":
        return reason
    return "activation_gate_error"


def _report_from_cycle(
    *,
    target: PaperScanTarget,
    result: WorkerCycleResult,
    kill_switch_active: bool,
    evaluator: WatcherFusionEvaluationService,
) -> WatcherPaperScanReport:
    outcome = result.outcome
    candidate_ids = () if outcome is None else outcome.candidate_ids
    reason = result.reason_code
    if outcome is not None and outcome.reason_code:
        reason = outcome.reason_code
        if result.replayed:
            reason = "replay"
    status = result.status.value
    if result.status is WorkerCycleStatus.SUCCEEDED:
        status = "succeeded"
    elif result.status is WorkerCycleStatus.SKIPPED:
        status = "skipped"
    elif result.status is WorkerCycleStatus.BLOCKED:
        status = "blocked"
    elif result.status is WorkerCycleStatus.REJECTED_STALE_FENCE:
        status = "failed"
        reason = result.reason_code
    elif result.status is WorkerCycleStatus.FAILED:
        status = "failed"
    health = result.health
    discussion = evaluator.discussion_snapshot
    if discussion is not None and discussion.candidate.candidate_id not in candidate_ids:
        discussion = None
    return WatcherPaperScanReport(
        organization_id=target.organization_id,
        scan_scope=target.scan_scope,
        symbol=target.symbol,
        status=status,
        reason_code=reason,
        replayed=result.replayed,
        published=result.published,
        candidate_ids=candidate_ids,
        kill_switch_active=kill_switch_active,
        lease_owner=None if health is None else health.lease_owner,
        health_state=status if health is None else health.state.value,
        user_id=target.user_id,
        request_hash=result.request_hash,
        lineage_id=result.lineage_id,
        discussion=discussion,
    )


def _shared_evaluation_clock(
    lifecycle: CandidateLifecycleService,
    evaluation_clock: BoundEvaluationClock | None,
) -> BoundEvaluationClock:
    """Candidate persist must use evidence time, not wall-clock UtcClock."""

    if evaluation_clock is not None:
        return evaluation_clock
    existing = getattr(lifecycle, "_clock", None)
    if isinstance(existing, BoundEvaluationClock):
        return existing
    return BoundEvaluationClock()


def default_paper_evidence_factory(
    settings: Settings,
    *,
    monitor: PerpetualMarketMonitor | None = None,
) -> PaperEvidenceFactory:
    """Assemble live/read-only evidence through one monitor + canonical assembler."""

    from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
    from app.evidence_pipeline.setup_lifetime import SetupLifetimeStore
    from app.evidence_pipeline.watcher_port import AssemblingWatcherScanEvidence
    from app.market_contracts.adapters.factory import (
        perpetual_source_is_replay,
        resolve_perpetual_evidence_source,
    )
    from app.market_contracts.catalog import default_perpetual_catalog
    from app.market_monitor.factory import build_perpetual_market_monitor
    from app.market_monitor.watcher_port import MarketMonitorWatcherPort
    from app.persistence.setup_lifetime import SqlAlchemySetupLifetimeStore

    catalog = default_perpetual_catalog()
    source = resolve_perpetual_evidence_source(settings, catalog=catalog)
    replay = perpetual_source_is_replay(settings)
    resolved_monitor = monitor or build_perpetual_market_monitor(
        settings, source=source, catalog=catalog
    )
    gate = MarketMonitorWatcherPort(resolved_monitor)

    def factory(
        session: Session | None, store: WatcherStore, symbol: str
    ) -> WatcherScanEvidencePort:
        lifetime = (
            SqlAlchemySetupLifetimeStore(session) if session is not None else SetupLifetimeStore()
        )
        assembler = FirstSliceEvidenceAssembler(
            source, replay=replay, catalog=catalog, lifetime=lifetime
        )
        return AssemblingWatcherScanEvidence(
            assembler,
            session=session,
            watcher_store=store,
            symbol=symbol,
            monitor=gate,
        )

    return factory


def build_watcher_paper_runtime(
    settings: Settings,
    session_factory: sessionmaker[Session],
    *,
    store: WatcherStore | None = None,
    lifecycle: CandidateLifecycleService | None = None,
    clock: Clock | None = None,
    evidence_factory: PaperEvidenceFactory | None = None,
    target_loader: PaperTargetLoader | None = None,
    kill_switch_probe: KillSwitchProbe | None = None,
    persistence_fence: CandidatePersistenceFence | None = None,
    side_effects: SideEffectPorts | None = None,
    monitor: PerpetualMarketMonitor | None = None,
    worker_id: str | None = None,
    scan_notification_hook: Callable[[WatcherPaperScanReport], None] | None = None,
    evaluation_observer_factory: EvaluationObserverFactory | None = None,
    enabled: bool | None = None,
    activation_cleared: bool = False,
    activation_gate: ActivationGate | None = None,
) -> WatcherPaperRuntime:
    """Compose the paper runtime. Does not enable staging/production flags.

    The scan hook stays unset unless the caller supplies one. Telegram and
    live trading are not started here.
    """

    from app.persistence.composition import build_postgres_watcher_store
    from app.runtime.canonical import build_production_canonical_runtime
    from app.signal_fusion.memory import UtcClock

    resolved_clock = clock if clock is not None else UtcClock()
    canonical = build_production_canonical_runtime(
        session_factory, settings=settings, clock=resolved_clock
    )
    resolved_store = store if store is not None else build_postgres_watcher_store(session_factory)
    eval_clock = BoundEvaluationClock()
    resolved_lifecycle = (
        lifecycle
        if lifecycle is not None
        else CandidateLifecycleService(
            repository=canonical.candidate_repository,
            clock=eval_clock,
        )
    )
    resolved_fence = (
        persistence_fence if persistence_fence is not None else canonical.candidate_repository
    )
    return WatcherPaperRuntime(
        store=resolved_store,
        lifecycle=resolved_lifecycle,
        clock=resolved_clock,
        enabled=resolve_runtime_enabled(
            settings, enabled=enabled, activation_cleared=activation_cleared
        ),
        worker_id=worker_id
        if worker_id is not None
        else new_worker_instance_id(settings.watcher_paper_worker_id),
        symbols=settings.watcher_paper_symbols,
        poll_interval_seconds=settings.watcher_paper_poll_interval_seconds,
        max_scopes_per_cycle=settings.watcher_paper_max_scopes_per_cycle,
        lease_ttl_seconds=paper_lease_ttl_seconds(settings),
        heartbeat_stale_after_seconds=settings.watcher_heartbeat_stale_after_seconds,
        session_factory=session_factory,
        evidence_factory=evidence_factory
        or default_paper_evidence_factory(settings, monitor=monitor),
        target_loader=target_loader,
        kill_switch_probe=kill_switch_probe,
        persistence_fence=resolved_fence,
        side_effects=side_effects,
        settings=settings,
        evaluation_clock=eval_clock,
        scan_notification_hook=scan_notification_hook,
        evaluation_observer_factory=evaluation_observer_factory,
        activation_gate=activation_gate,
    )


def publish_idle_watcher_status(
    settings: Settings,
    session_factory: sessionmaker[Session],
    *,
    worker_id: str,
    reason: str,
    now: datetime,
) -> None:
    """Heartbeat a refused or disarmed Watcher. Does not scan or open Telegram."""

    from app.persistence.runtime_status import (
        WATCHER_COMPONENT,
        RuntimeStatusWrite,
        publish_runtime_status,
    )

    state = "disarmed" if reason == "activation_disarmed" else "refused"
    publish_runtime_status(
        session_factory,
        RuntimeStatusWrite(
            component=WATCHER_COMPONENT,
            worker_id=worker_id,
            heartbeat_at=now,
            activation_state=state,
            last_scan_reason=reason,
            market_source=settings.perpetual_evidence_source,
            telegram_runtime_state="absent",
            inbound_mode=settings.telegram_inbound_mode.value,
        ),
    )


def idle_until_signal(
    settings: Settings,
    session_factory: sessionmaker[Session],
    *,
    reason: str,
) -> None:
    """Stay up and heartbeat when staging is disarmed or refused. Does not scan."""

    from app.signal_fusion.memory import UtcClock

    stop = threading.Event()

    def _handle(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    worker_id = new_worker_instance_id(settings.watcher_paper_worker_id)
    clock = UtcClock()
    logger.warning(
        "watcher_paper_idle",
        worker_id=worker_id,
        reason_code=reason,
        paper_only=True,
    )
    while not stop.is_set():
        try:
            publish_idle_watcher_status(
                settings,
                session_factory,
                worker_id=worker_id,
                reason=reason,
                now=clock.now(),
            )
        except Exception:
            logger.warning("watcher_runtime_status_unpublished", worker_id=worker_id)
        stop.wait(settings.watcher_paper_poll_interval_seconds)


def run_watcher_paper_process(*, once: bool = False) -> str:
    """Start the paper Watcher, or idle when staging is disarmed.

    Disarmed startup constructs Settings and returns ``disarmed`` without
    opening PostgreSQL, Redis, or provider clients. ``once`` skips the idle
    wait so tests can observe the posture. Armed staging still requires every
    operational dependency and fails closed when one is missing.
    """

    from app.core.disarmed_worker_boot import (
        WorkerBootRole,
        idle_disarmed_until_signal,
        load_worker_process_settings,
        settings_are_disarmed_paper_worker,
    )
    from app.core.logging import configure_logging
    from app.core.paper_safety import assert_execution_capable_composition_root

    settings = load_worker_process_settings(WorkerBootRole.WATCHER_PAPER)
    configure_logging(log_level=settings.log_level, json_logs=settings.log_json)
    assert_execution_capable_composition_root(settings)
    if settings_are_disarmed_paper_worker(settings):
        logger.warning(
            "watcher_paper_idle",
            reason_code="activation_disarmed",
            posture="disarmed",
            paper_only=True,
            enable_real_trading=settings.enable_real_trading,
            real_trading_enabled=settings.real_trading_enabled,
        )
        if not once:
            idle_disarmed_until_signal(settings, component="watcher_paper")
        return "disarmed"
    from app.db.session import get_session_factory

    if settings.environment is Environment.STAGING:
        from app.workers.watcher_activation import run_staging_activation

        decision = run_staging_activation(settings)
        if not decision.allowed:
            idle_until_signal(
                settings,
                get_session_factory(),
                reason=decision.primary_reason,
            )
            return decision.primary_reason
        return "armed"
    if not paper_runtime_enabled(settings):
        logger.warning(
            "watcher_paper_runtime_disabled",
            watcher_orchestration_enabled=settings.watcher_orchestration_enabled,
            environment=settings.environment.value,
            hint="local paper only; staging starts only after the paper activation preflight",
        )
        return "disabled"
    runtime = build_watcher_paper_runtime(settings, get_session_factory())
    if once:
        return "local_paper"
    runtime.run_forever()
    return "local_paper"


def main() -> None:
    run_watcher_paper_process(once=False)


if __name__ == "__main__":
    main()
