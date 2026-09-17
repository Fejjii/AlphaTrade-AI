"""Canonical Phase 6 candidate lifecycle application service.

Candidate authority is exclusive to this service. A candidate may originate only
from SetupAssessment state CONFIRMED_SETUP, its exact CanonicalEvidenceWindowV1,
and the tenant-owned CompiledSetupDefinition on that assessment.

PaperValidationCandidate is a downstream compatibility consumer and cannot mint
canonical identity. This module does not evaluate fusion, persist to PostgreSQL,
or activate execution.
"""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn
from uuid import UUID, uuid5

from pydantic import Field

from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.models import CanonicalModel
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import (
    Candidate,
    CandidateTransition,
    CandidateUniquenessTuple,
    build_confirmed_candidate,
)
from app.signal_fusion.enums import CandidateReasonCode, CandidateState, SetupAssessmentState
from app.signal_fusion.errors import (
    CandidateCreationAuthorityError,
    EvidenceWindowContractError,
    ExpiredCandidateAssessmentError,
    IllegalCandidateTransitionError,
    LegacyCandidateAuthorityError,
)
from app.signal_fusion.evidence_window import (
    CanonicalEvidenceWindowV1,
    hash_canonical_evidence_window,
)
from app.signal_fusion.memory import FrozenClock, InMemoryCandidateRepository, UtcClock
from app.signal_fusion.ports import CandidateRepository, Clock
from app.signal_fusion.types import ExecutableSetupRef, PolicyVersion

# Stable namespace for deterministic candidate IDs derived from the uniqueness tuple.
CANDIDATE_IDENTITY_NAMESPACE = UUID("a11fa7de-0006-4000-a000-c0a1d16a7e01")

_NON_CONFIRMED_SETUP_STATES = frozenset(
    {
        SetupAssessmentState.NO_SETUP,
        SetupAssessmentState.WATCH,
        SetupAssessmentState.PARTIAL_MATCH,
        SetupAssessmentState.EXPIRED,
        SetupAssessmentState.INVALIDATED,
    }
)

_STATE_REASON_CODE: dict[CandidateState, CandidateReasonCode] = {
    CandidateState.PLAN_CREATED: CandidateReasonCode.PLAN_CREATED,
    CandidateState.REJECTED: CandidateReasonCode.REJECTED,
    CandidateState.SKIPPED: CandidateReasonCode.SKIPPED,
    CandidateState.EXPIRED: CandidateReasonCode.EXPIRED,
    CandidateState.INVALIDATED: CandidateReasonCode.INVALIDATED,
}


class CandidateCreationCommand(CanonicalModel):
    """Idempotent creation boundary for a confirmed-setup candidate."""

    assessment: SetupAssessment
    evidence_window: CanonicalEvidenceWindowV1
    executable_setup: ExecutableSetupRef
    evidence_identity: EvidenceMarketIdentity
    idempotency_key: str = Field(min_length=8, max_length=120)
    correlation_id: UUID


class CandidateLifecycleService:
    """Single candidate authority: create, converge, transition, and project."""

    def __init__(self, *, repository: CandidateRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def create_from_confirmed_setup(self, command: CandidateCreationCommand) -> Candidate:
        """Insert or converge an ACTIVE candidate for the canonical uniqueness tuple."""
        self._validate_creation_authority(command)
        uniqueness = uniqueness_from_confirmed(
            command.assessment, command.evidence_window, command.executable_setup
        )
        candidate = build_confirmed_candidate(
            candidate_id=deterministic_candidate_id(uniqueness),
            organization_id=command.assessment.organization_id,
            strategy_version_id=command.assessment.strategy_version_id,
            executable_setup=command.executable_setup,
            fusion_policy_version=command.assessment.fusion_policy_version,
            direction=command.evidence_window.direction,
            assessment_id=command.assessment.assessment_id,
            evidence_window_hash=command.evidence_window.content_hash,
            evidence_identity=command.evidence_identity,
            evidence_venue=command.evidence_window.evidence_venue,
            evidence_market=command.evidence_window.evidence_market,
            evidence_instrument=command.evidence_window.evidence_instrument,
            timeframe=command.evidence_window.timeframe,
            created_at=command.assessment.assessed_at,
            valid_until=command.assessment.valid_until,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        return self._repository.get_or_insert_created(candidate)

    def create_from_paper_validation_candidate(self, source: object) -> NoReturn:
        """Legacy queue records cannot become canonical candidate authority."""
        del source
        raise LegacyCandidateAuthorityError(
            "PaperValidationCandidate is a downstream validation/evaluation queue "
            "and cannot create canonical Candidate identity."
        )

    def transition(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
        new_state: CandidateState,
        reason_codes: tuple[CandidateReasonCode, ...],
        idempotency_key: str,
        correlation_id: UUID,
        occurred_at: datetime | None = None,
    ) -> Candidate:
        """Apply a descendant transition under candidate-scoped idempotency.

        Exact replay of the same idempotency key and semantic payload returns the
        original candidate. Reuse of that key with a changed payload fails closed.
        A different key requesting an already-applied state converges only when the
        semantic fingerprint matches the original transition record.
        """
        if new_state is CandidateState.ACTIVE:
            raise IllegalCandidateTransitionError(
                "Candidate ACTIVE is the initial confirmed state and cannot be resurrected."
            )
        required_reason = _STATE_REASON_CODE[new_state]
        if required_reason not in reason_codes:
            raise IllegalCandidateTransitionError(
                f"Transition to {new_state.value} requires reason {required_reason.value}."
            )
        return self._repository.apply_transition(
            organization_id=organization_id,
            candidate_id=candidate_id,
            new_state=new_state,
            reason_codes=reason_codes,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            now=self._clock.now(),
        )

    def get_by_candidate_id(self, organization_id: UUID, candidate_id: UUID) -> Candidate | None:
        return self._repository.get_by_id(organization_id, candidate_id)

    def get_by_uniqueness(self, key: CandidateUniquenessTuple) -> Candidate | None:
        return self._repository.get_by_uniqueness(key)

    def latest_projection(self, organization_id: UUID, candidate_id: UUID) -> Candidate | None:
        return self._repository.get_by_id(organization_id, candidate_id)

    def transition_history(
        self, organization_id: UUID, candidate_id: UUID
    ) -> tuple[CandidateTransition, ...]:
        return self._repository.list_transitions(organization_id, candidate_id)

    def _validate_creation_authority(self, command: CandidateCreationCommand) -> None:
        assessment = command.assessment
        window = command.evidence_window
        setup = command.executable_setup
        identity = command.evidence_identity
        if hash_canonical_evidence_window(window) != window.content_hash:
            raise EvidenceWindowContractError(
                "CanonicalEvidenceWindowV1 content hash is not the §26 preimage digest."
            )
        if assessment.state in _NON_CONFIRMED_SETUP_STATES:
            if assessment.state is SetupAssessmentState.EXPIRED:
                raise ExpiredCandidateAssessmentError(
                    "EXPIRED assessment cannot create an ACTIVE candidate."
                )
            if assessment.state is SetupAssessmentState.INVALIDATED:
                raise CandidateCreationAuthorityError(
                    "INVALIDATED assessment cannot create an ACTIVE candidate."
                )
            raise CandidateCreationAuthorityError(
                f"{assessment.state.value} cannot create a canonical candidate; "
                "only CONFIRMED_SETUP may."
            )
        if assessment.state is not SetupAssessmentState.CONFIRMED_SETUP:
            raise CandidateCreationAuthorityError(
                "A candidate may originate only from SetupAssessment state CONFIRMED_SETUP."
            )
        now = self._clock.now()
        if assessment.valid_until <= now:
            raise ExpiredCandidateAssessmentError(
                "Elapsed assessment validity cannot create an ACTIVE candidate."
            )
        if setup != assessment.executable_setup:
            raise CandidateCreationAuthorityError(
                "Executable setup identity must match the confirmed SetupAssessment exactly."
            )
        if setup.setup_definition_id != window.compiled_setup_definition_id:
            raise CandidateCreationAuthorityError(
                "CompiledSetupDefinition id must match CanonicalEvidenceWindowV1 exactly."
            )
        if setup.content_hash != window.compiled_setup_content_hash:
            raise CandidateCreationAuthorityError(
                "CompiledSetupDefinition content hash must match CanonicalEvidenceWindowV1."
            )
        if assessment.organization_id != window.organization_id:
            raise CandidateCreationAuthorityError(
                "Assessment organization_id must match CanonicalEvidenceWindowV1."
            )
        if assessment.strategy_version_id != window.strategy_version_id:
            raise CandidateCreationAuthorityError(
                "Assessment strategy_version_id must match CanonicalEvidenceWindowV1."
            )
        if assessment.fusion_policy_version != window.fusion_policy_version:
            raise CandidateCreationAuthorityError(
                "Assessment fusion_policy_version must match CanonicalEvidenceWindowV1."
            )
        if assessment.evidence_window_hash != window.content_hash:
            raise CandidateCreationAuthorityError(
                "SetupAssessment evidence_window_hash must equal CanonicalEvidenceWindowV1."
            )
        _require_identity_matches_window(identity, window)


def uniqueness_from_confirmed(
    assessment: SetupAssessment,
    window: CanonicalEvidenceWindowV1,
    executable_setup: ExecutableSetupRef,
) -> CandidateUniquenessTuple:
    """Build the frozen §5 uniqueness tuple from confirmed setup inputs."""
    fusion_policy_version: PolicyVersion = assessment.fusion_policy_version
    return CandidateUniquenessTuple(
        organization_id=assessment.organization_id,
        strategy_version_id=assessment.strategy_version_id,
        setup_definition_id=executable_setup.setup_definition_id,
        fusion_policy_version=fusion_policy_version,
        direction=window.direction,
        evidence_venue=window.evidence_venue,
        evidence_market=window.evidence_market,
        evidence_instrument=window.evidence_instrument,
        timeframe=window.timeframe,
        evidence_window_hash=window.content_hash,
    )


def deterministic_candidate_id(key: CandidateUniquenessTuple) -> UUID:
    """UUID5 of the canonical uniqueness hash. Duplicate confirmations share one ID."""
    return uuid5(CANDIDATE_IDENTITY_NAMESPACE, key.canonical_hash())


def in_memory_candidate_lifecycle(
    *,
    now: datetime | None = None,
    repository: CandidateRepository | None = None,
) -> CandidateLifecycleService:
    """Factory for tests and local paper use. No network, no PostgreSQL."""
    clock: Clock = FrozenClock(now) if now is not None else UtcClock()
    return CandidateLifecycleService(
        repository=repository or InMemoryCandidateRepository(),
        clock=clock,
    )


def _require_identity_matches_window(
    identity: EvidenceMarketIdentity, window: CanonicalEvidenceWindowV1
) -> None:
    if identity.venue is not window.evidence_venue:
        raise CandidateCreationAuthorityError(
            "evidence_identity.venue must match CanonicalEvidenceWindowV1."
        )
    if identity.market_type is not window.evidence_market:
        raise CandidateCreationAuthorityError(
            "evidence_identity.market_type must match CanonicalEvidenceWindowV1."
        )
    if identity.instrument.instrument_id != window.evidence_instrument:
        raise CandidateCreationAuthorityError(
            "evidence_identity.instrument must match CanonicalEvidenceWindowV1."
        )
    if identity.timeframe is None or identity.timeframe is not window.timeframe:
        raise CandidateCreationAuthorityError(
            "evidence_identity.timeframe must match CanonicalEvidenceWindowV1."
        )


__all__ = [
    "CANDIDATE_IDENTITY_NAMESPACE",
    "CandidateCreationCommand",
    "CandidateLifecycleService",
    "deterministic_candidate_id",
    "in_memory_candidate_lifecycle",
    "uniqueness_from_confirmed",
]
