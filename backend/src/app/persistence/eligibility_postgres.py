"""PostgreSQL adapter for ActionEligibilityStore.

Evaluations are immutable and keyed by uniqueness hash. Identity bindings fail
closed. Candidate rows are locked in the same transaction so revision history
is append-safe. Not wired into FastAPI, workers, or feature flags.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.canonical_eligibility import (
    ActionEligibilityEvaluationRow,
    ActionEligibilityIdentityBindingRow,
)
from app.persistence.candidate_postgres import _lock_candidate
from app.persistence.unique import is_unique_violation
from app.signal_fusion.action_eligibility import (
    ActionEligibilityCommand,
    ActionEligibilityEvaluation,
    eligibility_identity_bindings,
    reject_eligibility_identity_conflicts,
)
from app.signal_fusion.errors import (
    ActionEligibilityLineageError,
    ConflictingActionEligibilityError,
)

_T = TypeVar("_T")

_ELIGIBILITY_UNIQUES = (
    "uq_action_eligibility_evaluations_hash",
    "pk_action_eligibility_evaluations",
    "uq_action_eligibility_evaluations_lineage_revision",
)
_BINDING_UNIQUES = ("pk_action_eligibility_identity_bindings",)


class PostgresActionEligibilityStore:
    """Durable ActionEligibilityStore. In-memory remains the unit-test default."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._local = threading.local()

    @contextmanager
    def bind_session(self, session: Session) -> Iterator[None]:
        previous = getattr(self._local, "session", None)
        self._local.session = session
        try:
            yield
        finally:
            self._local.session = previous

    def _run(self, work: Callable[[Session], _T]) -> _T:
        bound = getattr(self._local, "session", None)
        if isinstance(bound, Session):
            return work(bound)
        session = self._session_factory()
        try:
            with session.begin():
                return work(session)
        finally:
            session.close()

    def get(self, digest: str) -> ActionEligibilityEvaluation | None:
        def work(session: Session) -> ActionEligibilityEvaluation | None:
            return _evaluation_by_hash(session, digest)

        return self._run(work)

    def history(
        self, *, organization_id: UUID, account_id: UUID, candidate_id: UUID
    ) -> tuple[ActionEligibilityEvaluation, ...]:
        def work(session: Session) -> tuple[ActionEligibilityEvaluation, ...]:
            rows = session.scalars(
                select(ActionEligibilityEvaluationRow)
                .where(
                    ActionEligibilityEvaluationRow.organization_id == organization_id,
                    ActionEligibilityEvaluationRow.account_id == account_id,
                    ActionEligibilityEvaluationRow.candidate_id == candidate_id,
                )
                .order_by(ActionEligibilityEvaluationRow.evaluation_revision)
            ).all()
            return tuple(_evaluation_from_row(row) for row in rows)

        return self._run(work)

    def get_or_insert(
        self,
        command: ActionEligibilityCommand,
        digest: str,
        factory: Callable[[int], ActionEligibilityEvaluation],
    ) -> ActionEligibilityEvaluation:
        def work(session: Session) -> ActionEligibilityEvaluation:
            existing = _evaluation_by_hash(session, digest)
            if existing is not None:
                return existing
            locked = _lock_candidate(
                session, command.candidate.organization_id, command.candidate.candidate_id
            )
            if locked is None:
                raise ActionEligibilityLineageError(
                    "ActionEligibility cannot persist without a canonical Candidate."
                )
            existing = _evaluation_by_hash(session, digest)
            if existing is not None:
                return existing
            reject_eligibility_identity_conflicts(
                command, lambda key: _binding_fingerprint(session, key)
            )
            revision = _next_revision(
                session,
                organization_id=command.account.organization_id,
                account_id=command.account.account_id,
                candidate_id=command.candidate.candidate_id,
            )
            produced = factory(revision)
            if produced.uniqueness_hash != digest:
                raise ActionEligibilityLineageError(
                    "Eligibility uniqueness hash drifted during insert."
                )
            try:
                with session.begin_nested():
                    session.add(_evaluation_to_row(produced))
                    for kind, key, fingerprint in eligibility_identity_bindings(command):
                        _insert_binding(session, kind=kind, key=key, fingerprint=fingerprint)
                    session.flush()
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_ELIGIBILITY_UNIQUES, *_BINDING_UNIQUES):
                    raise
                recovered = _evaluation_by_hash(session, digest)
                if recovered is not None:
                    return recovered
                reject_eligibility_identity_conflicts(
                    command, lambda item: _binding_fingerprint(session, item)
                )
                raise ConflictingActionEligibilityError(
                    "Conflicting ActionEligibility identity could not be persisted."
                ) from exc
            return produced

        return self._run(work)


def _evaluation_by_hash(session: Session, digest: str) -> ActionEligibilityEvaluation | None:
    row = session.scalars(
        select(ActionEligibilityEvaluationRow).where(
            ActionEligibilityEvaluationRow.uniqueness_hash == digest
        )
    ).first()
    return None if row is None else _evaluation_from_row(row)


def _next_revision(
    session: Session, *, organization_id: UUID, account_id: UUID, candidate_id: UUID
) -> int:
    current = session.scalar(
        select(func.max(ActionEligibilityEvaluationRow.evaluation_revision)).where(
            ActionEligibilityEvaluationRow.organization_id == organization_id,
            ActionEligibilityEvaluationRow.account_id == account_id,
            ActionEligibilityEvaluationRow.candidate_id == candidate_id,
        )
    )
    return int(current or 0) + 1


def _binding_fingerprint(session: Session, key: tuple[str, str]) -> str | None:
    row = session.get(ActionEligibilityIdentityBindingRow, key)
    return None if row is None else row.fingerprint


def _insert_binding(session: Session, *, kind: str, key: str, fingerprint: str) -> None:
    existing = session.get(ActionEligibilityIdentityBindingRow, (kind, key))
    if existing is not None:
        if existing.fingerprint != fingerprint:
            raise ConflictingActionEligibilityError(
                "ActionEligibility identity binding is already bound to a different fingerprint."
            )
        return
    session.add(
        ActionEligibilityIdentityBindingRow(
            binding_kind=kind, binding_key=key, fingerprint=fingerprint
        )
    )


def _evaluation_to_row(evaluation: ActionEligibilityEvaluation) -> ActionEligibilityEvaluationRow:
    eligibility = evaluation.eligibility
    return ActionEligibilityEvaluationRow(
        eligibility_id=eligibility.eligibility_id,
        organization_id=eligibility.organization_id,
        user_id=eligibility.user_id,
        account_id=eligibility.account_id,
        candidate_id=eligibility.candidate_id,
        candidate_revision=eligibility.candidate_revision,
        uniqueness_hash=evaluation.uniqueness_hash,
        evaluation_revision=evaluation.evaluation_revision,
        state=eligibility.state.value,
        paper_actionable=evaluation.paper_actionable,
        live_executable=evaluation.live_executable,
        content_hash=evaluation.content_hash,
        payload=dict(evaluation.model_dump(mode="json")),
        created_at=eligibility.checked_at,
    )


def _evaluation_from_row(row: ActionEligibilityEvaluationRow) -> ActionEligibilityEvaluation:
    rebuilt = ActionEligibilityEvaluation.model_validate(row.payload)
    if rebuilt.content_hash != row.content_hash:
        raise ActionEligibilityLineageError(
            "Stored ActionEligibility content hash does not match canonical rebuild."
        )
    if rebuilt.uniqueness_hash != row.uniqueness_hash:
        raise ActionEligibilityLineageError(
            "Stored ActionEligibility uniqueness hash does not match canonical rebuild."
        )
    return rebuilt
