"""Errors for the paper evaluation measurement layer.

This package does not evaluate setups, mint Candidates, authorize plans, or
dispatch execution. Activation of a refinement is always forbidden.
"""

from __future__ import annotations

from typing import Any

from app.core.errors import AppError, ConflictError, ForbiddenError


class PaperEvaluationError(AppError):
    """Base measurement-layer error."""

    code = "paper_evaluation_error"
    status_code = 400

    def __init__(
        self,
        message: str = "Paper evaluation measurement failed.",
        *,
        status_code: int | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, code=code, details=details)


class CrossTenantPaperEvaluationError(ForbiddenError):
    code = "paper_evaluation_cross_tenant"

    def __init__(
        self,
        message: str = "Paper evaluation facts belong to a different organization.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class PaperEvaluationConflictError(ConflictError):
    code = "paper_evaluation_conflict"

    def __init__(
        self,
        message: str = "Paper evaluation source identity replayed with conflicting facts.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class NarrativeCannotRewriteEvaluationFactsError(PaperEvaluationError):
    code = "paper_evaluation_narrative_not_fact"
    status_code = 400

    def __init__(
        self,
        message: str = "LLM narrative cannot rewrite deterministic paper-evaluation facts.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class RefinementActivationForbiddenError(ForbiddenError):
    code = "paper_evaluation_refinement_activation_forbidden"

    def __init__(
        self,
        message: str = "AI refinement suggestions cannot be activated by the evaluation layer.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class PaperEvaluationNotTradingAuthorityError(ForbiddenError):
    code = "paper_evaluation_not_trading_authority"

    def __init__(
        self,
        message: str = "Paper evaluation cannot mint Candidates, place orders, or evaluate setups.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
