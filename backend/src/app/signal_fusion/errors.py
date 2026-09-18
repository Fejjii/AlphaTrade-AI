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


class EvidenceIdentityMismatchError(SignalFusionContractError):
    """Selected public observation does not match authoritative evidence identity."""


class TenantAssertionSelectionError(SignalFusionContractError):
    """Tenant assertion is missing, presentation-only, or not policy-selected."""


class ConflictingSemanticInputError(EvidenceWindowContractError):
    """Duplicate semantic inputs conflict or cannot be canonicalized."""


class CandidateCreationAuthorityError(SignalFusionContractError):
    """Canonical candidates originate only from CONFIRMED_SETUP + exact evidence window."""


class ExpiredCandidateAssessmentError(CandidateCreationAuthorityError):
    """Elapsed or EXPIRED assessments cannot mint an ACTIVE candidate."""


class LegacyCandidateAuthorityError(CandidateCreationAuthorityError):
    """PaperValidationCandidate and other legacy records cannot mint canonical candidates."""


class CandidateNotFoundError(SignalFusionContractError):
    """Candidate identity is unknown in the requested tenant scope."""


class ConflictingCandidateTransitionError(IllegalCandidateTransitionError):
    """A competing non-idempotent candidate transition was rejected."""


class ConflictingCandidateIdempotencyError(SignalFusionContractError):
    """Idempotency key reused with a conflicting organization-scoped semantic payload."""


class ActionEligibilityLineageError(SignalFusionContractError):
    """Candidate, assessment, and evidence-window identities do not bind."""


class ConflictingActionEligibilityError(SignalFusionContractError):
    """Reused eligibility identities were bound to a conflicting semantic payload.""" ""
