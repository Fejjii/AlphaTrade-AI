"""Production WatcherScanEvidencePort backed by the live/read-only assembler.

The live monitor gates current-quote and trade-stream freshness. Canonical
``FirstSliceEvidenceAssembler`` is the sole CanonicalEvidenceWindowV1 authority.
Wired into the paper Watcher worker through ``default_paper_evidence_factory``.
Staging/production Watcher flags stay false.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.canonical import is_first_slice_read_projection
from app.evidence_pipeline.manual_resistance import persisted_resistance_evidence
from app.evidence_pipeline.types import AssembledCanonicalEvidence
from app.market_contracts.enums import SourceFamily
from app.market_contracts.errors import (
    MarketContractError,
    RegionalProviderFailureError,
    StaleEvidenceError,
)
from app.market_contracts.request_progress import notify_market_request_progress
from app.market_monitor.monitor import PerpetualMarketMonitor
from app.market_monitor.types import MarketMode, SymbolMonitorSnapshot
from app.market_monitor.watcher_gate import watcher_evidence_error_for_monitor
from app.market_monitor.watcher_port import MarketMonitorWatcherPort
from app.services.canonical_strategy_evaluation import resolve_executable_strategy_policy
from app.signal_fusion.enums import EvidenceAdapterKind
from app.signal_fusion.errors import StrategyEvaluationPolicyError
from app.signal_fusion.first_slice_types import ManualResistanceEvidence
from app.signal_fusion.strategy_evaluation_policy import ExecutableStrategyPolicy
from app.watcher.contracts import EvaluationCommand
from app.watcher.errors import WatcherEvidenceUnavailableError, WatcherTenantMismatchError
from app.watcher.fusion_evaluation import ExecutablePolicyAuthority, WatcherCanonicalScanEvidence
from app.watcher.ports import WatcherStore

ExecutableResolver = Callable[[EvaluationCommand], ExecutableStrategyPolicy | None]
MonitorPort = PerpetualMarketMonitor | MarketMonitorWatcherPort


def resolve_watcher_scan_policy(
    session: Session,
    command: EvaluationCommand,
    *,
    store: WatcherStore,
) -> ExecutableStrategyPolicy | None:
    """Resolve the tenant-scoped approved compiled strategy for one scan."""

    version = store.get_policy_version(command.request.policy_id, command.request.policy_version)
    if version is None or version.strategy_version_id is None:
        return None
    if not version.enabled:
        return None
    if version.identity.organization_id != command.request.organization_id:
        raise WatcherTenantMismatchError(
            "Watcher policy organization_id does not match the scan tenant."
        )
    try:
        return resolve_executable_strategy_policy(
            session,
            organization_id=command.request.organization_id,
            strategy_version_id=version.strategy_version_id,
        )
    except (StrategyEvaluationPolicyError, NotFoundError):
        return None


class AssemblingWatcherScanEvidence:
    """Loads freshly assembled first-slice evidence for one tenant scan.

    Read-projection placeholders never become WatcherCanonicalScanEvidence.
    The optional monitor is the current-quote / stream gate; the assembler is
    the sole CanonicalEvidenceWindowV1 producer.
    """

    def __init__(
        self,
        assembler: FirstSliceEvidenceAssembler,
        *,
        executable_resolver: ExecutableResolver | None = None,
        session: Session | None = None,
        watcher_store: WatcherStore | None = None,
        symbol: str = "BTCUSDT",
        monitor: MonitorPort | None = None,
    ) -> None:
        self._assembler = assembler
        self._executable_resolver = executable_resolver
        self._session = session
        self._store = watcher_store
        self._symbol = symbol
        self._monitor = monitor
        self._load_cache: dict[tuple[str, str, str], WatcherCanonicalScanEvidence | None] = {}
        self._last_assembly: tuple[AssembledCanonicalEvidence, ExecutableStrategyPolicy] | None = (
            None
        )

    def load(self, command: EvaluationCommand) -> WatcherCanonicalScanEvidence | None:
        """Return one assembled snapshot twice for evaluate and Candidate persist.

        The key is the scan's evaluation input, organization, and symbol. A
        later bar or tenant does not reuse this entry. Assessment still
        recomputes from the cached evidence.
        """

        notify_market_request_progress()
        key = (
            str(command.request.organization_id),
            command.evaluation_input_hash,
            self._symbol,
        )
        if key in self._load_cache:
            return self._load_cache[key]
        self._last_assembly = None
        loaded = self._load_uncached(command)
        self._load_cache[key] = loaded
        return loaded

    def last_assembly(self) -> tuple[AssembledCanonicalEvidence, ExecutableStrategyPolicy] | None:
        """Last successful assembly for this scan. Empty after a failed load."""

        return self._last_assembly

    def _load_uncached(self, command: EvaluationCommand) -> WatcherCanonicalScanEvidence | None:
        organization_id = command.request.organization_id
        production_authority = self._session is not None and self._store is not None
        if production_authority and self._monitor is None:
            raise WatcherEvidenceUnavailableError(
                "Production Watcher Candidate authority requires a market monitor.",
                reason_code="missing_monitor",
            )
        monitor_snapshot = self._monitor_snapshot()
        if monitor_snapshot is not None:
            gated = watcher_evidence_error_for_monitor(monitor_snapshot)
            if gated is not None:
                raise gated
        executable = self._resolve_executable(command)
        authority = (
            ExecutablePolicyAuthority.PERSISTED_APPROVED_COMPILED
            if self._session is not None and self._store is not None
            else ExecutablePolicyAuthority.IN_MEMORY_TEST_HELPER
        )
        if executable is None:
            return None
        if executable.organization_id != organization_id:
            raise WatcherTenantMismatchError(
                "Executable strategy policy organization_id does not match the scan tenant."
            )
        if is_first_slice_read_projection(
            strategy_version_id=executable.strategy_version_id,
            setup_definition_id=executable.compiled_setup_definition_id,
        ):
            return None
        policy = executable.fusion_policy
        if policy.organization_id != organization_id:
            raise WatcherTenantMismatchError(
                "Fusion policy organization_id does not match the scan tenant."
            )
        resistances: tuple[ManualResistanceEvidence, ...] = ()
        if self._session is not None:
            resistances = persisted_resistance_evidence(
                self._session,
                organization_id=organization_id,
                symbol=self._symbol,
            )
        try:
            assembled = self._assembler.assemble(
                organization_id=organization_id,
                symbol=self._symbol,
                policy=policy,
                adapter_kind=EvidenceAdapterKind.WATCHER,
                resistances=resistances,
            )
        except StaleEvidenceError as exc:
            raise WatcherEvidenceUnavailableError(
                "Canonical scan evidence is stale.",
                reason_code="stale_evidence",
            ) from exc
        except RegionalProviderFailureError as exc:
            raise WatcherEvidenceUnavailableError(
                "Perpetual market provider is unavailable.",
                reason_code="provider_outage",
            ) from exc
        except MarketContractError as exc:
            raise WatcherEvidenceUnavailableError(
                "Canonical scan evidence is unavailable.",
                reason_code="canonical_evidence_unavailable",
            ) from exc
        if assembled.organization_id != organization_id:
            raise WatcherTenantMismatchError(
                "Assembled evidence belongs to a different organization."
            )
        if assembled.assessment_command.organization_id != organization_id:
            raise WatcherTenantMismatchError(
                "Assessment command organization_id does not match the scan tenant."
            )
        _reconcile_monitor_and_assembled(
            monitor_snapshot,
            assembled.replay,
            assembled.identity.source.family,
        )
        self._last_assembly = (assembled, executable)
        return WatcherCanonicalScanEvidence(
            organization_id=organization_id,
            policy=policy,
            executable_policy=executable,
            assessment_command=assembled.assessment_command,
            evidence=assembled.bundle,
            evaluated_at=assembled.evaluated_at,
            policy_authority=authority,
        )

    def _resolve_executable(self, command: EvaluationCommand) -> ExecutableStrategyPolicy | None:
        if self._session is not None and self._store is not None:
            return resolve_watcher_scan_policy(self._session, command, store=self._store)
        if self._executable_resolver is None:
            return None
        # Injected resolvers are test helpers. They never become persisted authority.
        resolved = self._executable_resolver(command)
        if resolved is None:
            return None
        if is_first_slice_read_projection(
            strategy_version_id=resolved.strategy_version_id,
            setup_definition_id=resolved.compiled_setup_definition_id,
        ):
            return None
        return resolved

    def _monitor_snapshot(self) -> SymbolMonitorSnapshot | None:
        if self._monitor is None:
            return None
        snapshot = self._monitor.latest(self._symbol)
        if not isinstance(snapshot, SymbolMonitorSnapshot):
            raise WatcherEvidenceUnavailableError(
                "Canonical scan evidence is unavailable.",
                reason_code="canonical_evidence_unavailable",
            )
        return snapshot


def _reconcile_monitor_and_assembled(
    monitor_snapshot: SymbolMonitorSnapshot | None,
    assembled_replay: bool,
    assembled_family: SourceFamily | None = None,
) -> None:
    """Shared source must not split live vs replay authority or venue."""

    if monitor_snapshot is None:
        return
    monitor_replay = monitor_snapshot.mode is MarketMode.REPLAY
    if assembled_family is None:
        assembled_family = (
            SourceFamily.REPLAY_FIXTURE
            if assembled_replay
            else SourceFamily.BINANCE_USDM_FUTURES_PUBLIC
        )
    family_matches = monitor_snapshot.source_family is assembled_family
    if monitor_replay != assembled_replay or not family_matches:
        raise WatcherEvidenceUnavailableError(
            "Watcher monitor mode does not match canonical evidence replay flag.",
            reason_code="wrong_source",
        )
