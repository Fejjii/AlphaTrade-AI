"""Validate lineage without mutating SetupAssessment, Candidate, or TradePlan."""

from __future__ import annotations

from app.core.errors import ValidationAppError
from app.learning_attribution.contracts import AttributionCommand
from app.learning_attribution.errors import (
    CrossTenantAttributionError,
    ExecutedOutcomeForbiddenError,
    LearningAttributionConflictError,
    MarketTruthMutationError,
)
from app.learning_attribution.identity import require_matching_hashes
from app.schemas.common import JournalLifecycleEventType
from app.signal_fusion.candidate import TERMINAL_CANDIDATE_STATES
from app.signal_fusion.enums import SetupAssessmentState

_EXECUTING_EVENTS = frozenset(
    {
        JournalLifecycleEventType.APPROVED_PLAN,
        JournalLifecycleEventType.FILL,
        JournalLifecycleEventType.CLOSE,
        JournalLifecycleEventType.RECONCILE,
    }
)
_NON_OUTCOME_EVENTS = frozenset(
    {
        JournalLifecycleEventType.CANDIDATE_CONFIRMED,
        JournalLifecycleEventType.REJECT,
        JournalLifecycleEventType.SKIP,
    }
)


def validate_attribution_command(command: AttributionCommand) -> None:
    """Fail closed on tenant, identity, and outcome-eligibility violations."""
    lineage = command.lineage
    candidate = lineage.candidate
    assessment = lineage.assessment
    event = command.event

    if candidate.organization_id != command.organization_id:
        raise CrossTenantAttributionError()
    if assessment.organization_id != command.organization_id:
        raise CrossTenantAttributionError()
    if event.account_id != lineage.account_id:
        raise LearningAttributionConflictError(
            "Attribution account does not match lineage account.",
            details={"reason": "account_mismatch", "account_id": str(event.account_id)},
        )
    if lineage.trade_plan is not None and lineage.trade_plan.account_id != lineage.account_id:
        raise LearningAttributionConflictError(
            "TradePlan lineage account does not match attribution account.",
            details={"reason": "plan_account_mismatch"},
        )

    try:
        require_matching_hashes(
            assessment=assessment,
            candidate=candidate,
            trade_plan=lineage.trade_plan,
        )
    except ValueError as exc:
        raise LearningAttributionConflictError(
            str(exc),
            details={"reason": "lineage_identity_mismatch"},
        ) from exc

    event_lifecycle = event.execution_lifecycle_id
    lineage_lifecycle = lineage.execution_lifecycle_id
    if (
        event_lifecycle is not None
        and lineage_lifecycle is not None
        and event_lifecycle != lineage_lifecycle
    ):
        raise LearningAttributionConflictError(
            "Execution lifecycle on the event does not match lineage.",
            details={"reason": "lifecycle_mismatch"},
        )

    if event.event_type in _EXECUTING_EVENTS:
        lifecycle_id = event_lifecycle or lineage_lifecycle
        if lifecycle_id is None:
            raise ValidationAppError(
                "Approved-plan/fill/close/reconcile attribution requires an execution lifecycle.",
                details={"reason": "missing_execution_lifecycle"},
            )
        if assessment.state is not SetupAssessmentState.CONFIRMED_SETUP:
            raise ExecutedOutcomeForbiddenError(
                "Non-confirmed SetupAssessment cannot produce an executed trade outcome.",
                details={"reason": "setup_not_confirmed", "state": assessment.state.value},
            )
        if candidate.state in TERMINAL_CANDIDATE_STATES:
            raise ExecutedOutcomeForbiddenError(
                "REJECT/SKIP/terminal candidates cannot produce executed trade outcomes.",
                details={"reason": "terminal_candidate", "state": candidate.state.value},
            )
        if lineage.trade_plan is None:
            raise ValidationAppError(
                "Executing lifecycle attribution requires TradePlan lineage.",
                details={"reason": "missing_trade_plan_lineage"},
            )

    if event.event_type in _NON_OUTCOME_EVENTS and assessment.state not in {
        SetupAssessmentState.CONFIRMED_SETUP,
        SetupAssessmentState.INVALIDATED,
        SetupAssessmentState.EXPIRED,
    }:
        raise ValidationAppError(
            "Candidate learning events require a confirmed or terminal SetupAssessment.",
            details={"reason": "assessment_not_attributable", "state": assessment.state.value},
        )


def refuse_market_truth_rewrite(
    *,
    original_assessment_hash: str,
    original_window_hash: str,
    facts_assessment_hash: str,
    facts_window_hash: str,
) -> None:
    """Learning facts must copy setup truth, never replace it."""
    if (
        original_assessment_hash != facts_assessment_hash
        or original_window_hash != facts_window_hash
    ):
        raise MarketTruthMutationError(
            "Learning facts cannot rewrite SetupAssessment or evidence-window hashes.",
            details={"reason": "market_truth_immutable"},
        )
