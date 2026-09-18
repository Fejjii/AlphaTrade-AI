"""Shared CandidateRepository write rules.

In-memory and PostgreSQL adapters must apply the same projection, idempotency
fingerprint, and terminal-state checks so persistence cannot fork Candidate
authority.
"""

from __future__ import annotations

from uuid import UUID

from app.signal_fusion.candidate import (
    ALLOWED_CANDIDATE_TRANSITIONS,
    TERMINAL_CANDIDATE_STATES,
    Candidate,
    CandidateTransition,
    build_candidate,
)
from app.signal_fusion.enums import CandidateReasonCode, CandidateState
from app.signal_fusion.errors import (
    ConflictingCandidateTransitionError,
    IllegalCandidateTransitionError,
)


def project_candidate(
    candidate: Candidate, *, state: CandidateState, transition_version: int
) -> Candidate:
    payload = candidate.model_dump()
    payload["state"] = state
    payload["transition_version"] = transition_version
    return build_candidate(**payload)


def transition_intent_matches(
    stored: CandidateTransition,
    *,
    new_state: CandidateState,
    reason_codes: tuple[CandidateReasonCode, ...],
    correlation_id: UUID,
    occurred_at: object,
) -> bool:
    if stored.new_state is not new_state:
        return False
    if stored.reason_codes != reason_codes:
        return False
    if stored.correlation_id != correlation_id:
        return False
    return occurred_at is None or stored.occurred_at == occurred_at


def reject_illegal_candidate_transition(current: Candidate, new_state: CandidateState) -> None:
    if current.state in TERMINAL_CANDIDATE_STATES:
        if new_state in TERMINAL_CANDIDATE_STATES:
            raise ConflictingCandidateTransitionError(
                f"Conflicting terminal transition {current.state.value} -> {new_state.value}."
            )
        raise IllegalCandidateTransitionError(
            f"Terminal candidate state {current.state.value} cannot be resurrected "
            f"to {new_state.value}."
        )
    if new_state is CandidateState.ACTIVE:
        raise IllegalCandidateTransitionError(
            "Candidate ACTIVE is the initial confirmed state and cannot be resurrected."
        )
    allowed = ALLOWED_CANDIDATE_TRANSITIONS.get(current.state, frozenset())
    if new_state not in allowed:
        raise IllegalCandidateTransitionError(
            f"Illegal candidate transition {current.state.value} -> {new_state.value}."
        )
