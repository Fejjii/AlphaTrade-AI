"""Compatibility adapter *contracts* only.

Watcher, detector, and TradingView adapters feed one AssessmentCommand.
PaperValidationCandidate is a downstream validation reference, not a source
adapter or competing candidate identity. No adapter implementation lives here.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.models import CanonicalModel
from app.market_contracts.observation import PublicMarketObservation
from app.schemas.common import TradeDirection
from app.signal_fusion.enums import EvidenceAdapterKind, EvidenceRole
from app.signal_fusion.evidence_window import (
    CanonicalEvidenceWindowV1,
    build_canonical_evidence_window_v1,
)
from app.signal_fusion.observation import TenantExternalAssertion
from app.signal_fusion.policy import DEFAULT_CORRECTION_SELECTION_POLICY
from app.signal_fusion.types import (
    ExecutableSetupRef,
    HalfOpenInterval,
    ManualLevelRevisionRef,
    PolicyVersion,
    PresentationEvidenceRef,
    SelectedPublicObservation,
    SemanticSourceIdentity,
    TenantAssertionRef,
    TriggerIdentity,
    selected_observation_from_public,
)


class AssessmentCommand(CanonicalModel):
    """Source-agnostic fusion input produced by every evidence adapter."""

    organization_id: UUID
    strategy_version_id: UUID
    executable_setup: ExecutableSetupRef
    fusion_policy_version: PolicyVersion
    finality_policy_version: PolicyVersion
    freshness_policy_version: PolicyVersion
    direction: TradeDirection
    evidence_identity: EvidenceMarketIdentity
    interval: HalfOpenInterval
    trigger: TriggerIdentity
    mandatory_evidence_roles: tuple[EvidenceRole, ...]
    public_observations: tuple[PublicMarketObservation, ...]
    selected_roles: tuple[EvidenceRole, ...]
    tenant_assertions: tuple[TenantExternalAssertion, ...] = ()
    manual_level_revision: ManualLevelRevisionRef | None = None
    source_set: tuple[SemanticSourceIdentity, ...]
    correction_selection_policy: PolicyVersion = DEFAULT_CORRECTION_SELECTION_POLICY
    adapter_kind: EvidenceAdapterKind
    scan_id: UUID | None = None
    action_id: UUID | None = None
    correlation_id: UUID | None = None
    presentation_evidence: tuple[PresentationEvidenceRef, ...] = ()


class DownstreamPaperValidationCandidateRef(CanonicalModel):
    """PaperValidationCandidate remains a downstream queue, not a source identity."""

    paper_validation_candidate_id: UUID
    canonical_candidate_id: UUID
    note: str = Field(
        default=(
            "Downstream validation/evaluation queue referencing the canonical candidate; "
            "not a source adapter or competing identity."
        )
    )


def selected_observations_for_command(
    command: AssessmentCommand,
) -> tuple[SelectedPublicObservation, ...]:
    if len(command.public_observations) != len(command.selected_roles):
        raise ValueError("Each public observation must be paired with exactly one selected role.")
    return tuple(
        selected_observation_from_public(observation, role=role)
        for observation, role in zip(
            command.public_observations, command.selected_roles, strict=True
        )
    )


def evidence_window_from_assessment_command(
    command: AssessmentCommand,
) -> CanonicalEvidenceWindowV1:
    """Project an AssessmentCommand into CanonicalEvidenceWindowV1.

    Adapter kind, scan/action/correlation IDs, and presentation evidence are
    accepted on the command and excluded from the window hash.
    """
    tenant_refs = tuple(
        TenantAssertionRef(assertion_id=item.assertion_id, content_hash=item.content_hash)
        for item in command.tenant_assertions
    )
    return build_canonical_evidence_window_v1(
        organization_id=command.organization_id,
        strategy_version_id=command.strategy_version_id,
        compiled_setup_definition_id=command.executable_setup.setup_definition_id,
        compiled_setup_content_hash=command.executable_setup.content_hash,
        fusion_policy_version=command.fusion_policy_version,
        finality_policy_version=command.finality_policy_version,
        freshness_policy_version=command.freshness_policy_version,
        direction=command.direction,
        evidence_identity=command.evidence_identity,
        interval=command.interval,
        trigger=command.trigger,
        mandatory_evidence_roles=command.mandatory_evidence_roles,
        selected_public_observations=selected_observations_for_command(command),
        source_set=command.source_set,
        tenant_assertions=tenant_refs,
        manual_level_revision=command.manual_level_revision,
        correction_selection_policy=command.correction_selection_policy,
        scan_id=command.scan_id,
        action_id=command.action_id,
        correlation_id=command.correlation_id,
        presentation_evidence=command.presentation_evidence,
        adapter_kind=command.adapter_kind.value,
    )
