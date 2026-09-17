"""Fail-closed errors for Phase 6 signal-fusion contracts."""

from __future__ import annotations


class SignalFusionContractError(ValueError):
    """Base error for illegal fusion, assessment, or candidate contracts."""


class TenantAssertionNotPublicError(SignalFusionContractError):
    """Tenant-owned assertions cannot enter PublicMarketObservation."""


class FormingObservationMutationError(SignalFusionContractError):
    """FORMING observations cannot become FINAL by mutation."""


class FormingObservationNotExecutableError(SignalFusionContractError):
    """FORMING observations cannot occupy an executable evidence role."""


class IllegalSetupIdentityError(SignalFusionContractError):
    """Legacy global SetupDefinition identities cannot occupy executable fields."""


class IllegalAssessmentTransitionError(SignalFusionContractError):
    """Setup-assessment transition is not in the architecture state machine."""


class IllegalCandidateTransitionError(SignalFusionContractError):
    """Candidate transition is illegal, including terminal resurrection to ACTIVE."""


class EvidenceWindowContractError(SignalFusionContractError):
    """CanonicalEvidenceWindowV1 preimage is incomplete or non-canonical."""
