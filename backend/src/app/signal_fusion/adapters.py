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
from app.signal_fusion.enums import EvidenceAdapterKind, EvidenceRole, TenantAssertionRole
from app.signal_fusion.errors import TenantAssertionSelectionError
from app.signal_fusion.evidence_window import (
    CanonicalEvidenceWindowV1,
    build_canonical_evidence_window_v1,
)
from app.signal_fusion.observation import TenantExternalAssertion
from app.signal_fusion.policy import (
    DEFAULT_CORRECTION_SELECTION_POLICY,
    first_slice_role_timeframes,
)
from app.signal_fusion.types import (
    ExecutableSetupRef,
    HalfOpenInterval,
    ManualLevelRevisionRef,
    PolicyVersion,
    PresentationEvidenceRef,
    RoleTimeframeBinding,
    SelectedPublicObservation,
    SelectedTenantAssertion,
    SemanticSourceIdentity,
    TriggerIdentity,
    require_observation_matches_evidence,
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
    assertion_roles: tuple[TenantAssertionRole, ...] = ()
    required_assertion_roles: tuple[TenantAssertionRole, ...] = ()
    identity_assertion_roles: tuple[TenantAssertionRole, ...] = ()
    role_timeframes: tuple[RoleTimeframeBinding, ...] = Field(
        default_factory=first_slice_role_timeframes
    )
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
    selected: list[SelectedPublicObservation] = []
    for observation, role in zip(command.public_observations, command.selected_roles, strict=True):
        require_observation_matches_evidence(
            observation,
            evidence_identity=command.evidence_identity,
            role=role,
            role_timeframes=command.role_timeframes,
        )
        selected.append(selected_observation_from_public(observation, role=role))
    return tuple(selected)


def selected_tenant_assertions_for_command(
    command: AssessmentCommand,
) -> tuple[SelectedTenantAssertion, ...]:
    """Pair adapter-supplied assertions with explicit roles.

    Unpaired tenant assertions remain transport-only and cannot enter the
    evidence-window hash unless a role is supplied.
    """
    if not command.assertion_roles:
        return ()
    if len(command.tenant_assertions) != len(command.assertion_roles):
        raise TenantAssertionSelectionError(
            "Each tenant assertion must be paired with exactly one assertion role."
        )
    return tuple(
        SelectedTenantAssertion(
            role=role,
            assertion_id=item.assertion_id,
            content_hash=item.content_hash,
        )
        for item, role in zip(command.tenant_assertions, command.assertion_roles, strict=True)
    )


def evidence_window_from_assessment_command(
    command: AssessmentCommand,
) -> CanonicalEvidenceWindowV1:
    """Project an AssessmentCommand into CanonicalEvidenceWindowV1.

    Adapter kind, scan/action/correlation IDs, and presentation evidence are
    accepted on the command and excluded from the window hash. Arbitrary
    adapter-supplied tenant assertions are hashed only when required or
    explicitly selected by the command's semantic policy.
    """
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
        tenant_assertions=selected_tenant_assertions_for_command(command),
        required_assertion_roles=command.required_assertion_roles,
        identity_assertion_roles=command.identity_assertion_roles,
        role_timeframes=command.role_timeframes,
        manual_level_revision=command.manual_level_revision,
        correction_selection_policy=command.correction_selection_policy,
        scan_id=command.scan_id,
        action_id=command.action_id,
        correlation_id=command.correlation_id,
        presentation_evidence=command.presentation_evidence,
        adapter_kind=command.adapter_kind.value,
    )
