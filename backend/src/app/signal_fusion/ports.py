"""Candidate lifecycle persistence and clock ports.

PostgreSQL adapters bind these interfaces in a later phase. This slice uses a
deterministic in-memory repository only. No Alembic, no SQLAlchemy models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.signal_fusion.candidate import Candidate, CandidateTransition, CandidateUniquenessTuple
from app.signal_fusion.enums import CandidateState


class Clock(Protocol):
    def now(self) -> datetime: ...


class CandidateRepository(Protocol):
    """Tenant-scoped candidate authority store. History is append-only."""

    def get_by_id(self, organization_id: UUID, candidate_id: UUID) -> Candidate | None: ...

    def get_by_uniqueness(self, key: CandidateUniquenessTuple) -> Candidate | None: ...

    def list_transitions(
        self, organization_id: UUID, candidate_id: UUID
    ) -> tuple[CandidateTransition, ...]: ...

    def get_or_insert_created(self, candidate: Candidate) -> Candidate: ...

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
    ) -> Candidate: ...
