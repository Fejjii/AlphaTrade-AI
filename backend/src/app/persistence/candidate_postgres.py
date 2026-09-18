"""PostgreSQL adapter for the existing CandidateRepository port.

Worker-originated writes optionally bind a Watcher lease fence. When bound, the
same transaction ``SELECT ... FOR UPDATE`` locks ``watcher_worker_leases`` for
``(organization_id, scan_scope)`` and proves current owner, epoch, fencing
token, and a non-expired lease *before* inserting or updating Candidate
authority. A stale worker cannot commit Candidate state after losing its lease.

CandidateLifecycleService remains the only Candidate authority. This adapter
does not evaluate setup, mint identity, or enable Watcher/Telegram/live trading.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.canonical_candidates import (
    CanonicalCandidateCreationKeyRow,
    CanonicalCandidateRow,
    CanonicalCandidateTransitionKeyRow,
    CanonicalCandidateTransitionRow,
)
from app.market_contracts.enums import MarketType, VenueId
from app.market_contracts.identity import EvidenceMarketIdentity
from app.persistence.unique import is_unique_violation
from app.persistence.watcher_postgres import _lock_lease, _require_current_lease_authority
from app.schemas.common import Timeframe, TradeDirection
from app.signal_fusion.candidate import (
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
)
from app.signal_fusion.ports import Clock
from app.signal_fusion.repository_rules import (
    project_candidate,
    reject_illegal_candidate_transition,
    transition_intent_matches,
)
from app.signal_fusion.types import ExecutableSetupRef
from app.watcher.contracts import EvaluationCommand
from app.watcher.errors import StaleFenceError

_T = TypeVar("_T")

_CREATE_UNIQUES = (
    "uq_canonical_candidates_uniqueness_hash",
    "uq_canonical_candidates_semantic_key",
    "uq_canonical_candidates_org_candidate",
    "pk_canonical_candidates",
    "uq_canonical_candidate_creation_keys_org_key",
    "pk_canonical_candidate_creation_keys",
)
_TRANSITION_KEY_UNIQUES = (
    "uq_canonical_candidate_transition_keys_org_cand_key",
    "pk_canonical_candidate_transition_keys",
)
_TRANSITION_UNIQUES = (
    "uq_canonical_candidate_transitions_version",
    "uq_canonical_candidate_transitions_org_id",
    "pk_canonical_candidate_transitions",
    *_TRANSITION_KEY_UNIQUES,
)

_STALE_CANDIDATE_MESSAGE = "Stale fence holder cannot persist Candidate authority."


@dataclass(frozen=True, slots=True)
class WorkerCandidateWriteFence:
    """Watcher lease identity that must still be current at Candidate persist."""

    organization_id: UUID
    scan_scope: str
    owner_id: str | None
    lease_epoch: int | None
    fencing_token: int | None


class PostgresCandidateRepository:
    """Durable CandidateRepository. In-memory repository remains the unit-test default."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._local = threading.local()

    def bind_from_evaluation_command(
        self, command: EvaluationCommand
    ) -> AbstractContextManager[None]:
        """Bind worker fence for the duration of CandidateLifecycleService writes."""

        if (
            command.worker_id is None
            and command.lease_epoch is None
            and command.fencing_token is None
        ):
            return nullcontext()
        return self.bind_worker_fence(
            WorkerCandidateWriteFence(
                organization_id=command.request.organization_id,
                scan_scope=command.request.scan_scope,
                owner_id=command.worker_id,
                lease_epoch=command.lease_epoch,
                fencing_token=command.fencing_token,
            )
        )

    @contextmanager
    def bind_worker_fence(self, fence: WorkerCandidateWriteFence) -> Iterator[None]:
        previous = getattr(self._local, "fence", None)
        self._local.fence = fence
        try:
            yield
        finally:
            self._local.fence = previous

    def _run(self, work: Callable[[Session], _T]) -> _T:
        session = self._session_factory()
        try:
            with session.begin():
                return work(session)
        finally:
            session.close()

    def _now(self) -> datetime:
        if self._clock is not None:
            return self._clock.now()
        return datetime.now(UTC)

    def _enforce_bound_fence(self, session: Session, *, organization_id: UUID) -> None:
        fence = getattr(self._local, "fence", None)
        if not isinstance(fence, WorkerCandidateWriteFence):
            return
        if fence.organization_id != organization_id:
            raise StaleFenceError(
                _STALE_CANDIDATE_MESSAGE,
                details={"scan_scope": fence.scan_scope, "cause": "organization_mismatch"},
            )
        if fence.owner_id is None or fence.lease_epoch is None or fence.fencing_token is None:
            raise StaleFenceError(
                _STALE_CANDIDATE_MESSAGE,
                details={"scan_scope": fence.scan_scope, "cause": "incomplete_authority"},
            )
        lease = _lock_lease(session, fence.organization_id, fence.scan_scope)
        _require_current_lease_authority(
            lease,
            owner_id=fence.owner_id,
            lease_epoch=fence.lease_epoch,
            fencing_token=fence.fencing_token,
            now=self._now(),
            scan_scope=fence.scan_scope,
            message=_STALE_CANDIDATE_MESSAGE,
        )

    def get_by_id(self, organization_id: UUID, candidate_id: UUID) -> Candidate | None:
        def work(session: Session) -> Candidate | None:
            row = _load_candidate(session, organization_id, candidate_id)
            return None if row is None else _candidate_from_row(row)

        return self._run(work)

    def get_by_uniqueness(self, key: CandidateUniquenessTuple) -> Candidate | None:
        def work(session: Session) -> Candidate | None:
            row = _load_by_uniqueness(session, key.organization_id, key.canonical_hash())
            return None if row is None else _candidate_from_row(row)

        return self._run(work)

    def list_transitions(
        self, organization_id: UUID, candidate_id: UUID
    ) -> tuple[CandidateTransition, ...]:
        def work(session: Session) -> tuple[CandidateTransition, ...]:
            if _load_candidate(session, organization_id, candidate_id) is None:
                return ()
            rows = session.scalars(
                select(CanonicalCandidateTransitionRow)
                .where(
                    CanonicalCandidateTransitionRow.organization_id == organization_id,
                    CanonicalCandidateTransitionRow.candidate_id == candidate_id,
                )
                .order_by(CanonicalCandidateTransitionRow.transition_version)
            ).all()
            return tuple(_transition_from_row(item) for item in rows)

        return self._run(work)

    def get_or_insert_created(self, candidate: Candidate) -> Candidate:
        uniqueness = candidate.uniqueness_tuple().canonical_hash()

        def work(session: Session) -> Candidate:
            self._enforce_bound_fence(session, organization_id=candidate.organization_id)
            bound = _load_creation_key(
                session, candidate.organization_id, candidate.idempotency_key
            )
            if bound is not None:
                if bound.uniqueness_hash != uniqueness:
                    raise ConflictingCandidateIdempotencyError(
                        "Creation idempotency key is already bound to a different "
                        "canonical uniqueness fingerprint."
                    )
                current = _load_candidate(session, candidate.organization_id, bound.candidate_id)
                if current is None:
                    raise CandidateNotFoundError("Candidate is unknown in this organization.")
                return _candidate_from_row(current)
            existing = _load_by_uniqueness(session, candidate.organization_id, uniqueness)
            if existing is not None:
                _insert_creation_key(
                    session,
                    organization_id=candidate.organization_id,
                    idempotency_key=candidate.idempotency_key,
                    uniqueness_hash=uniqueness,
                    candidate_id=existing.candidate_id,
                )
                return _candidate_from_row(existing)
            occupied = session.get(CanonicalCandidateRow, candidate.candidate_id)
            if occupied is not None:
                if occupied.uniqueness_hash != uniqueness:
                    raise ConflictingCandidateTransitionError(
                        "Candidate ID is already bound to a different uniqueness identity."
                    )
                if occupied.organization_id != candidate.organization_id:
                    raise ConflictingCandidateTransitionError(
                        "Candidate ID is already bound to a different uniqueness identity."
                    )
                _insert_creation_key(
                    session,
                    organization_id=candidate.organization_id,
                    idempotency_key=candidate.idempotency_key,
                    uniqueness_hash=uniqueness,
                    candidate_id=occupied.candidate_id,
                )
                return _candidate_from_row(occupied)
            try:
                with session.begin_nested():
                    session.add(_candidate_to_row(candidate, uniqueness))
                    session.flush()
                    session.add(
                        CanonicalCandidateCreationKeyRow(
                            organization_id=candidate.organization_id,
                            idempotency_key=candidate.idempotency_key,
                            uniqueness_hash=uniqueness,
                            candidate_id=candidate.candidate_id,
                        )
                    )
                    session.flush()
                return candidate
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_CREATE_UNIQUES):
                    raise
                return _recover_created(session, candidate, uniqueness)

        return self._run(work)

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
        def work(session: Session) -> Candidate:
            self._enforce_bound_fence(session, organization_id=organization_id)
            current_row = _lock_candidate(session, organization_id, candidate_id)
            if current_row is None:
                raise CandidateNotFoundError("Candidate is unknown in this organization.")
            current = _candidate_from_row(current_row)
            stored = _load_transition_for_key(
                session, organization_id, candidate_id, idempotency_key
            )
            if stored is not None:
                if not transition_intent_matches(
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
                established_row = _establishing_transition_row(session, candidate_id)
                established = (
                    None if established_row is None else _transition_from_row(established_row)
                )
                if established is not None and transition_intent_matches(
                    established,
                    new_state=new_state,
                    reason_codes=reason_codes,
                    correlation_id=correlation_id,
                    occurred_at=occurred_at,
                ):
                    assert established_row is not None
                    _insert_transition_key(
                        session,
                        organization_id=organization_id,
                        candidate_id=candidate_id,
                        idempotency_key=idempotency_key,
                        transition_id=established_row.transition_id,
                    )
                    return current
                raise ConflictingCandidateTransitionError(
                    "A different idempotency key requested an already-applied candidate "
                    "state with a conflicting semantic payload."
                )
            reject_illegal_candidate_transition(current, new_state)
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
            projection = project_candidate(
                current, state=new_state, transition_version=next_version
            )
            try:
                with session.begin_nested():
                    transition_row = _transition_to_row(
                        transition,
                        organization_id=organization_id,
                        candidate_id=candidate_id,
                    )
                    session.add(transition_row)
                    session.flush()
                    session.add(
                        CanonicalCandidateTransitionKeyRow(
                            organization_id=organization_id,
                            candidate_id=candidate_id,
                            idempotency_key=idempotency_key,
                            transition_id=transition_row.transition_id,
                        )
                    )
                    _apply_projection(current_row, projection)
                    session.flush()
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_TRANSITION_UNIQUES):
                    raise
                return _recover_transition(
                    session,
                    organization_id=organization_id,
                    candidate_id=candidate_id,
                    new_state=new_state,
                    reason_codes=reason_codes,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    occurred_at=occurred_at,
                )
            return projection

        return self._run(work)


def _recover_created(session: Session, candidate: Candidate, uniqueness: str) -> Candidate:
    bound = _load_creation_key(session, candidate.organization_id, candidate.idempotency_key)
    if bound is not None:
        if bound.uniqueness_hash != uniqueness:
            raise ConflictingCandidateIdempotencyError(
                "Creation idempotency key is already bound to a different "
                "canonical uniqueness fingerprint."
            )
        current = _load_candidate(session, candidate.organization_id, bound.candidate_id)
        if current is None:
            raise CandidateNotFoundError("Candidate is unknown in this organization.")
        return _candidate_from_row(current)
    existing = _load_by_uniqueness(session, candidate.organization_id, uniqueness)
    if existing is not None:
        _insert_creation_key(
            session,
            organization_id=candidate.organization_id,
            idempotency_key=candidate.idempotency_key,
            uniqueness_hash=uniqueness,
            candidate_id=existing.candidate_id,
        )
        return _candidate_from_row(existing)
    occupied = session.get(CanonicalCandidateRow, candidate.candidate_id)
    if occupied is None:
        raise ConflictingCandidateTransitionError(
            "Candidate ID is already bound to a different uniqueness identity."
        )
    if (
        occupied.uniqueness_hash != uniqueness
        or occupied.organization_id != candidate.organization_id
    ):
        raise ConflictingCandidateTransitionError(
            "Candidate ID is already bound to a different uniqueness identity."
        )
    _insert_creation_key(
        session,
        organization_id=candidate.organization_id,
        idempotency_key=candidate.idempotency_key,
        uniqueness_hash=uniqueness,
        candidate_id=occupied.candidate_id,
    )
    return _candidate_from_row(occupied)


def _recover_transition(
    session: Session,
    *,
    organization_id: UUID,
    candidate_id: UUID,
    new_state: CandidateState,
    reason_codes: tuple[CandidateReasonCode, ...],
    idempotency_key: str,
    correlation_id: UUID,
    occurred_at: datetime | None,
) -> Candidate:
    current_row = _lock_candidate(session, organization_id, candidate_id)
    if current_row is None:
        raise CandidateNotFoundError("Candidate is unknown in this organization.")
    current = _candidate_from_row(current_row)
    stored = _load_transition_for_key(session, organization_id, candidate_id, idempotency_key)
    if stored is not None:
        if not transition_intent_matches(
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
        established_row = _establishing_transition_row(session, candidate_id)
        established = None if established_row is None else _transition_from_row(established_row)
        if established is not None and transition_intent_matches(
            established,
            new_state=new_state,
            reason_codes=reason_codes,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
        ):
            assert established_row is not None
            _insert_transition_key(
                session,
                organization_id=organization_id,
                candidate_id=candidate_id,
                idempotency_key=idempotency_key,
                transition_id=established_row.transition_id,
            )
            return current
    raise ConflictingCandidateTransitionError(
        "A different idempotency key requested an already-applied candidate "
        "state with a conflicting semantic payload."
    )


def _insert_creation_key(
    session: Session,
    *,
    organization_id: UUID,
    idempotency_key: str,
    uniqueness_hash: str,
    candidate_id: UUID,
) -> None:
    existing = _load_creation_key(session, organization_id, idempotency_key)
    if existing is not None:
        if existing.uniqueness_hash != uniqueness_hash:
            raise ConflictingCandidateIdempotencyError(
                "Creation idempotency key is already bound to a different "
                "canonical uniqueness fingerprint."
            )
        return
    try:
        with session.begin_nested():
            session.add(
                CanonicalCandidateCreationKeyRow(
                    organization_id=organization_id,
                    idempotency_key=idempotency_key,
                    uniqueness_hash=uniqueness_hash,
                    candidate_id=candidate_id,
                )
            )
            session.flush()
    except IntegrityError as exc:
        if not is_unique_violation(exc, *_CREATE_UNIQUES):
            raise
        current = _load_creation_key(session, organization_id, idempotency_key)
        if current is None:
            raise
        if current.uniqueness_hash != uniqueness_hash:
            raise ConflictingCandidateIdempotencyError(
                "Creation idempotency key is already bound to a different "
                "canonical uniqueness fingerprint."
            ) from exc


def _insert_transition_key(
    session: Session,
    *,
    organization_id: UUID,
    candidate_id: UUID,
    idempotency_key: str,
    transition_id: UUID,
) -> None:
    existing = session.get(
        CanonicalCandidateTransitionKeyRow,
        (organization_id, candidate_id, idempotency_key),
    )
    if existing is not None:
        if existing.transition_id != transition_id:
            raise ConflictingCandidateIdempotencyError(
                "Transition idempotency key is already bound to a different "
                "semantic transition fingerprint."
            )
        return
    try:
        with session.begin_nested():
            session.add(
                CanonicalCandidateTransitionKeyRow(
                    organization_id=organization_id,
                    candidate_id=candidate_id,
                    idempotency_key=idempotency_key,
                    transition_id=transition_id,
                )
            )
            session.flush()
    except IntegrityError as exc:
        if not is_unique_violation(exc, *_TRANSITION_KEY_UNIQUES):
            raise
        current = session.get(
            CanonicalCandidateTransitionKeyRow,
            (organization_id, candidate_id, idempotency_key),
        )
        if current is None:
            raise
        if current.transition_id != transition_id:
            raise ConflictingCandidateIdempotencyError(
                "Transition idempotency key is already bound to a different "
                "semantic transition fingerprint."
            ) from exc


def _load_candidate(
    session: Session, organization_id: UUID, candidate_id: UUID
) -> CanonicalCandidateRow | None:
    return session.scalars(
        select(CanonicalCandidateRow).where(
            CanonicalCandidateRow.candidate_id == candidate_id,
            CanonicalCandidateRow.organization_id == organization_id,
        )
    ).first()


def _lock_candidate(
    session: Session, organization_id: UUID, candidate_id: UUID
) -> CanonicalCandidateRow | None:
    return session.scalars(
        select(CanonicalCandidateRow)
        .where(
            CanonicalCandidateRow.candidate_id == candidate_id,
            CanonicalCandidateRow.organization_id == organization_id,
        )
        .with_for_update()
    ).first()


def _load_by_uniqueness(
    session: Session, organization_id: UUID, uniqueness_hash: str
) -> CanonicalCandidateRow | None:
    return session.scalars(
        select(CanonicalCandidateRow).where(
            CanonicalCandidateRow.uniqueness_hash == uniqueness_hash,
            CanonicalCandidateRow.organization_id == organization_id,
        )
    ).first()


def _load_creation_key(
    session: Session, organization_id: UUID, idempotency_key: str
) -> CanonicalCandidateCreationKeyRow | None:
    return session.get(CanonicalCandidateCreationKeyRow, (organization_id, idempotency_key))


def _load_transition_for_key(
    session: Session, organization_id: UUID, candidate_id: UUID, idempotency_key: str
) -> CandidateTransition | None:
    key_row = session.get(
        CanonicalCandidateTransitionKeyRow,
        (organization_id, candidate_id, idempotency_key),
    )
    if key_row is None:
        return None
    row = session.get(CanonicalCandidateTransitionRow, key_row.transition_id)
    if row is None:
        return None
    if row.organization_id != organization_id or row.candidate_id != candidate_id:
        return None
    return _transition_from_row(row)


def _establishing_transition_row(
    session: Session, candidate_id: UUID
) -> CanonicalCandidateTransitionRow | None:
    return session.scalars(
        select(CanonicalCandidateTransitionRow)
        .where(CanonicalCandidateTransitionRow.candidate_id == candidate_id)
        .order_by(CanonicalCandidateTransitionRow.transition_version.desc())
        .limit(1)
    ).first()


def _candidate_to_row(candidate: Candidate, uniqueness_hash: str) -> CanonicalCandidateRow:
    return CanonicalCandidateRow(
        candidate_id=candidate.candidate_id,
        organization_id=candidate.organization_id,
        uniqueness_hash=uniqueness_hash,
        schema_version=candidate.schema_version,
        strategy_version_id=candidate.strategy_version_id,
        setup_definition_id=candidate.setup_definition_id,
        fusion_policy_version=candidate.fusion_policy_version,
        direction=candidate.direction.value,
        evidence_venue=candidate.evidence_venue.value,
        evidence_market=candidate.evidence_market.value,
        evidence_instrument=candidate.evidence_instrument,
        timeframe=candidate.timeframe.value,
        evidence_window_hash=candidate.evidence_window_hash,
        assessment_id=candidate.assessment_id,
        executable_setup=dict(candidate.executable_setup.model_dump(mode="json")),
        evidence_identity=dict(candidate.evidence_identity.model_dump(mode="json")),
        state=candidate.state.value,
        created_at=candidate.created_at,
        valid_until=candidate.valid_until,
        transition_version=candidate.transition_version,
        idempotency_key=candidate.idempotency_key,
        correlation_id=candidate.correlation_id,
        content_hash=candidate.content_hash,
    )


def _apply_projection(row: CanonicalCandidateRow, projection: Candidate) -> None:
    row.state = projection.state.value
    row.transition_version = projection.transition_version
    row.content_hash = projection.content_hash


def _candidate_from_row(row: CanonicalCandidateRow) -> Candidate:
    rebuilt = build_candidate(
        candidate_id=row.candidate_id,
        organization_id=row.organization_id,
        strategy_version_id=row.strategy_version_id,
        executable_setup=ExecutableSetupRef.model_validate(row.executable_setup),
        fusion_policy_version=row.fusion_policy_version,
        direction=TradeDirection(row.direction),
        assessment_id=row.assessment_id,
        evidence_window_hash=row.evidence_window_hash,
        evidence_identity=EvidenceMarketIdentity.model_validate(row.evidence_identity),
        evidence_venue=VenueId(row.evidence_venue),
        evidence_market=MarketType(row.evidence_market),
        evidence_instrument=row.evidence_instrument,
        timeframe=Timeframe(row.timeframe),
        state=CandidateState(row.state),
        created_at=row.created_at,
        valid_until=row.valid_until,
        transition_version=row.transition_version,
        idempotency_key=row.idempotency_key,
        correlation_id=row.correlation_id,
    )
    if rebuilt.content_hash != row.content_hash:
        raise ConflictingCandidateTransitionError(
            "Stored candidate projection content hash does not match canonical rebuild."
        )
    if rebuilt.schema_version != row.schema_version:
        raise ConflictingCandidateTransitionError(
            "Stored candidate schema version does not match canonical rebuild."
        )
    return rebuilt


def _transition_to_row(
    transition: CandidateTransition, *, organization_id: UUID, candidate_id: UUID
) -> CanonicalCandidateTransitionRow:
    return CanonicalCandidateTransitionRow(
        transition_id=uuid4(),
        organization_id=organization_id,
        candidate_id=candidate_id,
        previous_state=transition.previous_state.value,
        new_state=transition.new_state.value,
        transition_version=transition.transition_version,
        reason_codes=[code.value for code in transition.reason_codes],
        occurred_at=transition.occurred_at,
        correlation_id=transition.correlation_id,
        idempotency_key=transition.idempotency_key,
        content_hash=transition.content_hash,
    )


def _transition_from_row(row: CanonicalCandidateTransitionRow) -> CandidateTransition:
    rebuilt = build_candidate_transition(
        previous_state=CandidateState(row.previous_state),
        new_state=CandidateState(row.new_state),
        transition_version=row.transition_version,
        reason_codes=tuple(CandidateReasonCode(item) for item in row.reason_codes),
        occurred_at=row.occurred_at,
        correlation_id=row.correlation_id,
        idempotency_key=row.idempotency_key,
    )
    if rebuilt.content_hash != row.content_hash:
        raise ConflictingCandidateTransitionError(
            "Stored candidate transition content hash does not match canonical rebuild."
        )
    return rebuilt
