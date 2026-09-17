"""Deterministic in-memory candidate repository.

Thread-safe substitute for PostgreSQL. One re-entrant lock covers uniqueness
insert and append-only transitions so concurrent duplicate confirmations
converge on a single candidate identity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from uuid import UUID

from app.signal_fusion.candidate import (
    TERMINAL_CANDIDATE_STATES,
    Candidate,
    CandidateTransition,
    CandidateUniquenessTuple,
)
from app.signal_fusion.enums import CandidateState
from app.signal_fusion.errors import (
    CandidateNotFoundError,
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


class InMemoryCandidateRepository:
    """Append-only candidate store keyed by CandidateUniquenessTuple."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_id: dict[UUID, Candidate] = {}
        self._by_uniqueness: dict[str, UUID] = {}
        self._history: dict[UUID, list[CandidateTransition]] = {}

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
        key = candidate.uniqueness_tuple().canonical_hash()
        with self._lock:
            existing_id = self._by_uniqueness.get(key)
            if existing_id is not None:
                return self._by_id[existing_id]
            occupied = self._by_id.get(candidate.candidate_id)
            if occupied is not None:
                raise ConflictingCandidateTransitionError(
                    "Candidate ID is already bound to a different uniqueness identity."
                )
            self._by_id[candidate.candidate_id] = candidate
            self._by_uniqueness[key] = candidate.candidate_id
            self._history[candidate.candidate_id] = []
            return candidate

    def commit_transition(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
        expected_version: int,
        new_state: CandidateState,
        previous_state: CandidateState,
        transition: CandidateTransition,
        projection: Candidate,
    ) -> Candidate:
        requested = new_state
        expected_previous = previous_state
        with self._lock:
            current = self._scoped_get(organization_id, candidate_id)
            if current is None:
                raise CandidateNotFoundError("Candidate is unknown in this organization.")
            if current.state is requested:
                return current
            if current.state in TERMINAL_CANDIDATE_STATES:
                if requested in TERMINAL_CANDIDATE_STATES:
                    raise ConflictingCandidateTransitionError(
                        f"Conflicting terminal transition {current.state.value} -> "
                        f"{requested.value}."
                    )
                raise IllegalCandidateTransitionError(
                    f"Terminal candidate state {current.state.value} cannot be resurrected "
                    f"to {requested.value}."
                )
            if (
                current.transition_version != expected_version
                or current.state is not expected_previous
            ):
                raise ConflictingCandidateTransitionError(
                    "Candidate transition version or previous state conflict."
                )
            if projection.candidate_id != candidate_id:
                raise ConflictingCandidateTransitionError(
                    "Transition projection does not match candidate identity."
                )
            if projection.organization_id != organization_id:
                raise ConflictingCandidateTransitionError(
                    "Transition projection organization does not match tenant scope."
                )
            history = self._history[candidate_id]
            history.append(transition)
            self._by_id[candidate_id] = projection
            return projection

    def _scoped_get(self, organization_id: UUID, candidate_id: UUID) -> Candidate | None:
        candidate = self._by_id.get(candidate_id)
        if candidate is None or candidate.organization_id != organization_id:
            return None
        return candidate
