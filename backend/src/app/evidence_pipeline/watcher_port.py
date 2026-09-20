"""Production WatcherScanEvidencePort backed by the live/read-only assembler.

Not wired into the worker loop. Watcher flags remain false.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.canonical import first_slice_read_policy
from app.market_contracts.errors import MarketContractError
from app.signal_fusion.enums import EvidenceAdapterKind
from app.signal_fusion.policy import FusionPolicy
from app.watcher.contracts import EvaluationCommand
from app.watcher.errors import WatcherTenantMismatchError
from app.watcher.fusion_evaluation import WatcherCanonicalScanEvidence

PolicyFactory = Callable[[UUID], FusionPolicy]


class AssemblingWatcherScanEvidence:
    """Loads freshly assembled first-slice evidence for one tenant scan."""

    def __init__(
        self,
        assembler: FirstSliceEvidenceAssembler,
        *,
        policy_factory: PolicyFactory | None = None,
        symbol: str = "BTCUSDT",
    ) -> None:
        self._assembler = assembler
        self._policy_factory = policy_factory or first_slice_read_policy
        self._symbol = symbol

    def load(self, command: EvaluationCommand) -> WatcherCanonicalScanEvidence | None:
        organization_id = command.request.organization_id
        policy = self._policy_factory(organization_id)
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
            assessment_command=assembled.assessment_command,
            evidence=assembled.bundle,
            evaluated_at=assembled.evaluated_at,
        )
