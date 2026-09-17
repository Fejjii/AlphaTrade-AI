"""Fail-closed errors for canonical Candidate Telegram alert composition."""

from __future__ import annotations


class CandidateAlertError(ValueError):
    """Application-boundary failure. Never executes a trade."""

    def __init__(self, message: str, *, details: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class LegacyCandidateAlertAuthorityError(CandidateAlertError):
    """PaperValidationCandidate, PaperSignal, SetupDetection, and TradingViewSignal
    cannot mint or authorize a candidate alert.
    """


class CandidateAlertNotFoundError(CandidateAlertError):
    """Alert intent or canonical candidate is unknown in this tenant scope."""


class CandidateAlertTenantError(CandidateAlertError):
    """Organization, user, account, or binding isolation failed closed."""


class ConflictingCandidateAlertError(CandidateAlertError):
    """Same identity was reused with a conflicting semantic payload."""


class CandidateAlertBindingError(CandidateAlertError):
    """Telegram binding does not match the candidate alert recipient."""
