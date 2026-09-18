"""Typed port and in-memory store for canonical TradePlanRevision authority.

PostgreSQL cannot bind this port until Agent 1 remaps
``trade_plan_revisions.candidate_id`` away from ``paper_validation_candidates``
and adds Candidate / ActionEligibility lineage columns. This slice never writes
the existing ORM table.
"""

from __future__ import annotations

from threading import RLock
from typing import Protocol
from uuid import UUID

from app.schemas.canonical_trade_plan import CanonicalTradePlanRevision
from app.services.canonical_trade_plan_errors import (
    CanonicalTradePlanLineageError,
    ConflictingTradePlanIdempotencyError,
)


class CanonicalTradePlanStore(Protocol):
    """Tenant-scoped immutable plan store. History is append-only."""

    def get_by_uniqueness(self, digest: str) -> CanonicalTradePlanRevision | None: ...

    def get_by_revision(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        revision_id: UUID,
    ) -> CanonicalTradePlanRevision | None: ...

    def get_by_idempotency(
        self, *, organization_id: UUID, idempotency_key: str
    ) -> CanonicalTradePlanRevision | None: ...

    def get_by_candidate_scope(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        account_id: UUID,
        candidate_id: UUID,
    ) -> CanonicalTradePlanRevision | None: ...

    def bind_idempotency(
        self,
        *,
        organization_id: UUID,
        idempotency_key: str,
        digest: str,
    ) -> None: ...

    def insert(
        self,
        digest: str,
        revision: CanonicalTradePlanRevision,
        *,
        idempotency_key: str,
    ) -> CanonicalTradePlanRevision: ...

    def discard(self, digest: str) -> None: ...


class InMemoryCanonicalTradePlanStore:
    """Thread-safe substitute for PostgreSQL. Identical uniqueness converges."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_uniqueness: dict[str, CanonicalTradePlanRevision] = {}
        self._by_revision: dict[UUID, CanonicalTradePlanRevision] = {}
        self._by_idempotency: dict[tuple[UUID, str], str] = {}
        self._by_candidate_scope: dict[tuple[UUID, UUID, UUID, UUID], str] = {}

    def get_by_uniqueness(self, digest: str) -> CanonicalTradePlanRevision | None:
        with self._lock:
            return self._by_uniqueness.get(digest)

    def get_by_revision(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        revision_id: UUID,
    ) -> CanonicalTradePlanRevision | None:
        with self._lock:
            revision = self._by_revision.get(revision_id)
            if revision is None:
                return None
            plan = revision.plan
            if plan.organization_id != organization_id or plan.user_id != user_id:
                return None
            return revision

    def get_by_idempotency(
        self, *, organization_id: UUID, idempotency_key: str
    ) -> CanonicalTradePlanRevision | None:
        with self._lock:
            digest = self._by_idempotency.get((organization_id, idempotency_key))
            if digest is None:
                return None
            return self._by_uniqueness.get(digest)

    def get_by_candidate_scope(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        account_id: UUID,
        candidate_id: UUID,
    ) -> CanonicalTradePlanRevision | None:
        with self._lock:
            digest = self._by_candidate_scope.get(
                (organization_id, user_id, account_id, candidate_id)
            )
            if digest is None:
                return None
            return self._by_uniqueness.get(digest)

    def bind_idempotency(
        self,
        *,
        organization_id: UUID,
        idempotency_key: str,
        digest: str,
    ) -> None:
        key = (organization_id, idempotency_key)
        with self._lock:
            bound = self._by_idempotency.get(key)
            if bound is not None and bound != digest:
                raise ConflictingTradePlanIdempotencyError(
                    "Plan idempotency key is already bound to a different canonical uniqueness "
                    "fingerprint."
                )
            if digest not in self._by_uniqueness:
                raise CanonicalTradePlanLineageError(
                    "Cannot bind idempotency to an unknown plan uniqueness digest."
                )
            self._by_idempotency[key] = digest

    def insert(
        self,
        digest: str,
        revision: CanonicalTradePlanRevision,
        *,
        idempotency_key: str,
    ) -> CanonicalTradePlanRevision:
        plan = revision.plan
        scope = (plan.organization_id, plan.user_id, plan.account_id, plan.candidate_id)
        idem_key = (plan.organization_id, idempotency_key)
        with self._lock:
            existing = self._by_uniqueness.get(digest)
            if existing is not None:
                return existing
            occupied = self._by_revision.get(plan.revision_id)
            if occupied is not None:
                raise ConflictingTradePlanIdempotencyError(
                    "Plan revision id is already bound to a different uniqueness identity."
                )
            bound_scope = self._by_candidate_scope.get(scope)
            if bound_scope is not None and bound_scope != digest:
                raise ConflictingTradePlanIdempotencyError(
                    "This candidate/account scope already has a canonical plan with different "
                    "executable semantics."
                )
            bound_idem = self._by_idempotency.get(idem_key)
            if bound_idem is not None and bound_idem != digest:
                raise ConflictingTradePlanIdempotencyError(
                    "Plan idempotency key is already bound to a different canonical uniqueness "
                    "fingerprint."
                )
            if revision.uniqueness_hash != digest:
                raise CanonicalTradePlanLineageError("Plan uniqueness hash drifted during insert.")
            self._by_uniqueness[digest] = revision
            self._by_revision[plan.revision_id] = revision
            self._by_candidate_scope[scope] = digest
            self._by_idempotency[idem_key] = digest
            return revision

    def discard(self, digest: str) -> None:
        with self._lock:
            revision = self._by_uniqueness.pop(digest, None)
            if revision is None:
                return
            plan = revision.plan
            self._by_revision.pop(plan.revision_id, None)
            self._by_candidate_scope.pop(
                (plan.organization_id, plan.user_id, plan.account_id, plan.candidate_id),
                None,
            )
            stale = [key for key, bound in self._by_idempotency.items() if bound == digest]
            for key in stale:
                del self._by_idempotency[key]
