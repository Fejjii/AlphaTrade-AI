"""Deterministic in-memory candidate repository.

Thread-safe substitute for PostgreSQL. One re-entrant lock covers uniqueness
insert, organization-scoped creation idempotency, and append-only transitions
so concurrent duplicate confirmations converge on a single candidate identity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from uuid import UUID

from app.signal_fusion.candidate import (
    ALLOWED_CANDIDATE_TRANSITIONS,
    TERMINAL_CANDIDATE_STATES,
    Candidate,
    CandidateTransition,
    CandidateUniquenessTuple,
    build_candidate,
    build_candidate_transition,
)
from app.signal_fusion.enums import CandidateReasonCode, CandidateState
from app.signal_fusion.errors import (
    CandidateNotFoundError,
    ConflictingCandidateIdempotencyError,
    ConflictingCandidateTransitionError,
    IllegalCandidateTransitionError,
)


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Test clock. Time does not move unless the caller replaces the instance."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


def _project(candidate: Candidate, *, state: CandidateState, transition_version: int) -> Candidate:
    payload = candidate.model_dump()
    payload["state"] = state
    payload["transition_version"] = transition_version
    return build_candidate(**payload)


def _intent_matches(
    stored: CandidateTransition,
    *,
    new_state: CandidateState,
    reason_codes: tuple[CandidateReasonCode, ...],
    correlation_id: UUID,
    occurred_at: datetime | None,
) -> bool:
    if stored.new_state is not new_state:
        return False
    if stored.reason_codes != reason_codes:
        return False
    if stored.correlation_id != correlation_id:
        return False
    return occurred_at is None or stored.occurred_at == occurred_at


class InMemoryCandidateRepository:
    """Append-only candidate store keyed by CandidateUniquenessTuple."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_id: dict[UUID, Candidate] = {}
        self._by_uniqueness: dict[str, UUID] = {}
        self._history: dict[UUID, list[CandidateTransition]] = {}
        self._creation_by_key: dict[tuple[UUID, str], str] = {}
        self._transition_by_key: dict[tuple[UUID, UUID, str], CandidateTransition] = {}

    def get_by_id(self, organization_id: UUID, candidate_id: UUID) -> Candidate | None:
        with self._lock:
            return self._scoped_get(organization_id, candidate_id)

    def get_by_uniqueness(self, key: CandidateUniquenessTuple) -> Candidate | None:
        with self._lock:
            candidate_id = self._by_uniqueness.get(key.canonical_hash())
            if candidate_id is None:
                return None
            candidate = self._by_id[candidate_id]
            if candidate.organization_id != key.organization_id:
                return None
            return candidate

    def list_transitions(
        self, organization_id: UUID, candidate_id: UUID
    ) -> tuple[CandidateTransition, ...]:
        with self._lock:
            if self._scoped_get(organization_id, candidate_id) is None:
                return ()
            return tuple(self._history.get(candidate_id, ()))

    def get_or_insert_created(self, candidate: Candidate) -> Candidate:
        uniqueness = candidate.uniqueness_tuple().canonical_hash()
        creation_key = (candidate.organization_id, candidate.idempotency_key)
        with self._lock:
            bound = self._creation_by_key.get(creation_key)
            if bound is not None:
                if bound != uniqueness:
                    raise ConflictingCandidateIdempotencyError(
                        "Creation idempotency key is already bound to a different "
                        "canonical uniqueness fingerprint."
                    )
                return self._by_id[self._by_uniqueness[bound]]
            existing_id = self._by_uniqueness.get(uniqueness)
            if existing_id is not None:
                self._creation_by_key[creation_key] = uniqueness
                return self._by_id[existing_id]
            occupied = self._by_id.get(candidate.candidate_id)
            if occupied is not None:
                raise ConflictingCandidateTransitionError(
                    "Candidate ID is already bound to a different uniqueness identity."
                )
            self._by_id[candidate.candidate_id] = candidate
            self._by_uniqueness[uniqueness] = candidate.candidate_id
            self._creation_by_key[creation_key] = uniqueness
            self._history[candidate.candidate_id] = []
            return candidate

    def apply_transition(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
        new_state: CandidateState,
        reason_codes: tuple[CandidateReasonCode, ...],
        idempotency_key: str,
        correlation_id: UUID,
        occurred_at: datetime | None,
        now: datetime,
    ) -> Candidate:
        with self._lock:
            current = self._scoped_get(organization_id, candidate_id)
            if current is None:
                raise CandidateNotFoundError("Candidate is unknown in this organization.")
            key = (organization_id, candidate_id, idempotency_key)
            stored = self._transition_by_key.get(key)
            if stored is not None:
                if not _intent_matches(
                    stored,
                    new_state=new_state,
                    reason_codes=reason_codes,
                    correlation_id=correlation_id,
                    occurred_at=occurred_at,
                ):
                    raise ConflictingCandidateIdempotencyError(
                        "Transition idempotency key is already bound to a different "
                        "semantic transition fingerprint."
                    )
                return current
            if current.state is new_state:
                established = self._establishing_transition(candidate_id)
                if established is not None and _intent_matches(
                    established,
                    new_state=new_state,
                    reason_codes=reason_codes,
                    correlation_id=correlation_id,
                    occurred_at=occurred_at,
                ):
                    self._transition_by_key[key] = established
                    return current
                raise ConflictingCandidateTransitionError(
                    "A different idempotency key requested an already-applied candidate "
                    "state with a conflicting semantic payload."
                )
            self._reject_illegal_transition(current, new_state)
            stamped = occurred_at if occurred_at is not None else now
            next_version = current.transition_version + 1
            transition = build_candidate_transition(
                previous_state=current.state,
                new_state=new_state,
                transition_version=next_version,
                reason_codes=reason_codes,
                occurred_at=stamped,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )
            projection = _project(current, state=new_state, transition_version=next_version)
            history = self._history[candidate_id]
            history.append(transition)
            self._by_id[candidate_id] = projection
            self._transition_by_key[key] = transition
            return projection

    def _establishing_transition(self, candidate_id: UUID) -> CandidateTransition | None:
        history = self._history.get(candidate_id, ())
        if not history:
            return None
        return history[-1]

    def _reject_illegal_transition(self, current: Candidate, new_state: CandidateState) -> None:
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

    def _scoped_get(self, organization_id: UUID, candidate_id: UUID) -> Candidate | None:
        candidate = self._by_id.get(candidate_id)
        if candidate is None or candidate.organization_id != organization_id:
            return None
        return candidate
