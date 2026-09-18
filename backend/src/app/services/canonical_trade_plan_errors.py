"""Fail-closed errors for canonical TradePlanRevision creation."""

from __future__ import annotations


class CanonicalTradePlanError(ValueError):
    """Base error for illegal canonical plan construction."""


class CanonicalTradePlanLineageError(CanonicalTradePlanError):
    """Candidate, eligibility, and plan identities do not bind."""


class CanonicalTradePlanAuthorityError(CanonicalTradePlanError):
    """Only an ACTIVE canonical Candidate may create a plan."""


class CanonicalTradePlanNotEligibleError(CanonicalTradePlanError):
    """ActionEligibility is missing, not ELIGIBLE, or no longer paper-actionable."""


class CanonicalTradePlanNotFoundError(CanonicalTradePlanError):
    """Canonical plan, candidate, or eligibility identity is unknown in scope."""


class ConflictingTradePlanIdempotencyError(CanonicalTradePlanError):
    """Idempotency key reused with a conflicting semantic payload."""


class CanonicalTradePlanImmutableError(CanonicalTradePlanError):
    """Approval or any later step cannot change executable plan semantics."""


class LegacyPaperValidationCannotMintPlanError(CanonicalTradePlanAuthorityError):
    """PaperValidationCandidate cannot mint canonical TradePlanRevision authority."""


class CanonicalTradePlanPersistenceNotBoundError(CanonicalTradePlanError):
    """PostgreSQL TradePlanRevision rows cannot store canonical Candidate identity yet."""
