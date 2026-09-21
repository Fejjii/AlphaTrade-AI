"""Production WatcherScanEvidencePort backed by the live/read-only assembler.

Not wired into the worker loop. Watcher flags remain false.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.canonical import is_first_slice_read_projection
from app.market_contracts.errors import MarketContractError
from app.services.canonical_strategy_evaluation import resolve_executable_strategy_policy
from app.signal_fusion.enums import EvidenceAdapterKind
from app.signal_fusion.errors import StrategyEvaluationPolicyError
from app.signal_fusion.strategy_evaluation_policy import ExecutableStrategyPolicy
from app.watcher.contracts import EvaluationCommand
from app.watcher.errors import WatcherTenantMismatchError
from app.watcher.fusion_evaluation import WatcherCanonicalScanEvidence
from app.watcher.ports import WatcherStore

ExecutableResolver = Callable[[EvaluationCommand], ExecutableStrategyPolicy | None]


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
    """

    def __init__(
        self,
        assembler: FirstSliceEvidenceAssembler,
        *,
        executable_resolver: ExecutableResolver | None = None,
        session: Session | None = None,
        watcher_store: WatcherStore | None = None,
        symbol: str = "BTCUSDT",
    ) -> None:
        self._assembler = assembler
        self._executable_resolver = executable_resolver
        self._session = session
        self._store = watcher_store
        self._symbol = symbol

    def load(self, command: EvaluationCommand) -> WatcherCanonicalScanEvidence | None:
        organization_id = command.request.organization_id
        executable = self._resolve_executable(command)
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
        try:
            assembled = self._assembler.assemble(
                organization_id=organization_id,
                symbol=self._symbol,
                policy=policy,
                adapter_kind=EvidenceAdapterKind.WATCHER,
            )
        except MarketContractError:
            return None
        if assembled.organization_id != organization_id:
            raise WatcherTenantMismatchError(
                "Assembled evidence belongs to a different organization."
            )
        if assembled.assessment_command.organization_id != organization_id:
            raise WatcherTenantMismatchError(
                "Assessment command organization_id does not match the scan tenant."
            )
        return WatcherCanonicalScanEvidence(
            organization_id=organization_id,
            policy=policy,
            executable_policy=executable,
            assessment_command=assembled.assessment_command,
            evidence=assembled.bundle,
            evaluated_at=assembled.evaluated_at,
        )

    def _resolve_executable(self, command: EvaluationCommand) -> ExecutableStrategyPolicy | None:
        if self._session is not None and self._store is not None:
            return resolve_watcher_scan_policy(self._session, command, store=self._store)
        if self._executable_resolver is None:
            return None
        resolved = self._executable_resolver(command)
        if resolved is None:
            return None
        if is_first_slice_read_projection(
            strategy_version_id=resolved.strategy_version_id,
            setup_definition_id=resolved.compiled_setup_definition_id,
        ):
            return None
        return resolved
