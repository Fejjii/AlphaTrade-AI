"""PostgreSQL adapter for CanonicalTradePlanStore.

Canonical revisions occupy ``trade_plan_revisions`` with
``plan_authority='canonical'``. Lineage lives in a side table so Phase 1
``CanonicalTradePlanContentV1`` hashes stay unchanged. A compatibility
``TradeProposal`` row with ``plan_root_kind='canonical_plan_root'`` satisfies
the existing ``plan_id`` FK without restoring ``ProposalService`` as plan
authority.

``PLAN_CREATED`` runs through ``on_inserted`` in the same transaction as the
plan insert after locking the canonical Candidate. Legacy PVC-backed rows stay
``plan_authority='paper_validation'`` with ``canonical_candidate_id`` NULL.
Not wired into FastAPI, workers, or feature flags.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.canonical_trade_plans import (
    PLAN_AUTHORITY_CANONICAL,
    PLAN_ROOT_CANONICAL,
    CanonicalTradePlanIdempotencyKeyRow,
    CanonicalTradePlanLineageRow,
    CanonicalTradePlanRootRow,
)
from app.db.models import CompiledSetupDefinition
from app.db.models import TradePlanRevision as TradePlanRevisionModel
from app.db.models import TradeProposal as TradeProposalModel
from app.persistence.candidate_postgres import PostgresCandidateRepository, _lock_candidate
from app.persistence.unique import is_unique_violation
from app.schemas.canonical_trade_plan import CanonicalTradePlanLineage, CanonicalTradePlanRevision
from app.schemas.common import ProposalStatus, RiskSeverity, StrategyId, TradeDirection
from app.schemas.trade_plan import EntrySide, TradePlanRevisionSemantic
from app.services.canonical_trade_plan_errors import (
    CanonicalTradePlanLineageError,
    ConflictingTradePlanIdempotencyError,
)
from app.services.mappers.trade_plan_mapper import trade_plan_revision_to_schema
from app.signal_fusion.enums import ActionEligibilityState

_T = TypeVar("_T")

_PLAN_UNIQUES = (
    "uq_canonical_trade_plan_lineage_hash",
    "pk_canonical_trade_plan_lineage",
    "pk_canonical_trade_plan_roots",
    "uq_canonical_trade_plan_roots_scope",
    "pk_canonical_trade_plan_idempotency_keys",
    "pk_trade_plan_revisions",
    "uq_trade_plan_revision_binding",
    "uq_trade_plan_revisions_content_hash",
    "pk_trade_proposals",
    "uq_trade_proposal_tenant_owner",
)


class PostgresCanonicalTradePlanStore:
    """Durable CanonicalTradePlanStore. In-memory remains the unit-test default."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        candidate_repository: PostgresCandidateRepository | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._candidate_repository = candidate_repository
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
                repository = self._candidate_repository
                if repository is not None:
                    with repository.bind_session(session):
                        return work(session)
                return work(session)
        finally:
            session.close()

    def get_by_uniqueness(self, digest: str) -> CanonicalTradePlanRevision | None:
        def work(session: Session) -> CanonicalTradePlanRevision | None:
            return _envelope_by_uniqueness(session, digest)

        return self._run(work)

    def get_by_revision(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        revision_id: UUID,
    ) -> CanonicalTradePlanRevision | None:
        def work(session: Session) -> CanonicalTradePlanRevision | None:
            return _envelope_by_revision(
                session,
                organization_id=organization_id,
                user_id=user_id,
                revision_id=revision_id,
            )

        return self._run(work)

    def get_by_idempotency(
        self, *, organization_id: UUID, idempotency_key: str
    ) -> CanonicalTradePlanRevision | None:
        def work(session: Session) -> CanonicalTradePlanRevision | None:
            key_row = session.get(
                CanonicalTradePlanIdempotencyKeyRow, (organization_id, idempotency_key)
            )
            if key_row is None:
                return None
            return _envelope_by_uniqueness(session, key_row.uniqueness_hash)

        return self._run(work)

    def get_by_candidate_scope(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        account_id: UUID,
        candidate_id: UUID,
    ) -> CanonicalTradePlanRevision | None:
        def work(session: Session) -> CanonicalTradePlanRevision | None:
            root = _root_by_scope(
                session,
                organization_id=organization_id,
                user_id=user_id,
                account_id=account_id,
                candidate_id=candidate_id,
            )
            if root is None:
                return None
            lineage = session.scalars(
                select(CanonicalTradePlanLineageRow).where(
                    CanonicalTradePlanLineageRow.plan_id == root.plan_id,
                    CanonicalTradePlanLineageRow.organization_id == organization_id,
                )
            ).first()
            if lineage is None:
                return None
            return _envelope_by_revision(
                session,
                organization_id=organization_id,
                user_id=user_id,
                revision_id=lineage.revision_id,
            )

        return self._run(work)

    def bind_idempotency(
        self,
        *,
        organization_id: UUID,
        idempotency_key: str,
        digest: str,
    ) -> None:
        def work(session: Session) -> None:
            envelope = _envelope_by_uniqueness(session, digest)
            if envelope is None:
                raise CanonicalTradePlanLineageError(
                    "Cannot bind idempotency to an unknown plan uniqueness digest."
                )
            _insert_idempotency(
                session,
                organization_id=organization_id,
                idempotency_key=idempotency_key,
                digest=digest,
                revision_id=envelope.plan.revision_id,
            )

        self._run(work)

    def insert(
        self,
        digest: str,
        revision: CanonicalTradePlanRevision,
        *,
        idempotency_key: str,
        on_inserted: Callable[[], None] | None = None,
    ) -> CanonicalTradePlanRevision:
        plan = revision.plan

        def work(session: Session) -> CanonicalTradePlanRevision:
            if revision.uniqueness_hash != digest:
                raise CanonicalTradePlanLineageError("Plan uniqueness hash drifted during insert.")
            locked = _lock_candidate(session, plan.organization_id, plan.candidate_id)
            if locked is None:
                raise CanonicalTradePlanLineageError(
                    "Canonical TradePlanRevision cannot persist without a canonical Candidate."
                )
            if locked.setup_definition_id != plan.setup_definition_id:
                raise CanonicalTradePlanLineageError(
                    "Plan setup_definition_id must match the locked Candidate compiled setup."
                )
            existing = _envelope_by_uniqueness(session, digest)
            if existing is not None:
                _insert_idempotency(
                    session,
                    organization_id=plan.organization_id,
                    idempotency_key=idempotency_key,
                    digest=digest,
                    revision_id=existing.plan.revision_id,
                )
                if on_inserted is not None:
                    on_inserted()
                return existing
            occupied = session.get(TradePlanRevisionModel, plan.revision_id)
            if occupied is not None:
                raise ConflictingTradePlanIdempotencyError(
                    "Plan revision id is already bound to a different uniqueness identity."
                )
            bound_scope = _root_by_scope(
                session,
                organization_id=plan.organization_id,
                user_id=plan.user_id,
                account_id=plan.account_id,
                candidate_id=plan.candidate_id,
            )
            if bound_scope is not None:
                raise ConflictingTradePlanIdempotencyError(
                    "This candidate/account scope already has a canonical plan with different "
                    "executable semantics."
                )
            bound_idem = session.get(
                CanonicalTradePlanIdempotencyKeyRow, (plan.organization_id, idempotency_key)
            )
            if bound_idem is not None and bound_idem.uniqueness_hash != digest:
                raise ConflictingTradePlanIdempotencyError(
                    "Plan idempotency key is already bound to a different canonical uniqueness "
                    "fingerprint."
                )
            _require_compiled_setup(session, revision)
            try:
                with session.begin_nested():
                    _insert_canonical_rows(
                        session, digest=digest, revision=revision, idempotency_key=idempotency_key
                    )
                    session.flush()
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_PLAN_UNIQUES):
                    raise
                recovered = _envelope_by_uniqueness(session, digest)
                if recovered is None:
                    raise ConflictingTradePlanIdempotencyError(
                        "Conflicting canonical TradePlanRevision identity could not be persisted."
                    ) from exc
                _insert_idempotency(
                    session,
                    organization_id=plan.organization_id,
                    idempotency_key=idempotency_key,
                    digest=digest,
                    revision_id=recovered.plan.revision_id,
                )
                if on_inserted is not None:
                    on_inserted()
                return recovered
            if on_inserted is not None:
                on_inserted()
            return revision

        return self._run(work)

    def discard(self, digest: str) -> None:
        """Append-only PostgreSQL rows cannot be deleted; the transaction rolls back."""

        del digest


def _envelope_by_uniqueness(session: Session, digest: str) -> CanonicalTradePlanRevision | None:
    lineage = session.scalars(
        select(CanonicalTradePlanLineageRow).where(
            CanonicalTradePlanLineageRow.uniqueness_hash == digest
        )
    ).first()
    if lineage is None:
        return None
    return _envelope_by_revision(
        session,
        organization_id=lineage.organization_id,
        user_id=lineage.user_id,
        revision_id=lineage.revision_id,
    )


def _envelope_by_revision(
    session: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    revision_id: UUID,
) -> CanonicalTradePlanRevision | None:
    plan_row = session.get(TradePlanRevisionModel, revision_id)
    if plan_row is None:
        return None
    if plan_row.organization_id != organization_id or plan_row.user_id != user_id:
        return None
    if plan_row.plan_authority != PLAN_AUTHORITY_CANONICAL:
        return None
    lineage = session.get(CanonicalTradePlanLineageRow, revision_id)
    if lineage is None:
        return None
    return _envelope_from_rows(plan_row, lineage)


def _root_by_scope(
    session: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    account_id: UUID,
    candidate_id: UUID,
) -> CanonicalTradePlanRootRow | None:
    return session.scalars(
        select(CanonicalTradePlanRootRow).where(
            CanonicalTradePlanRootRow.organization_id == organization_id,
            CanonicalTradePlanRootRow.user_id == user_id,
            CanonicalTradePlanRootRow.account_id == account_id,
            CanonicalTradePlanRootRow.candidate_id == candidate_id,
        )
    ).first()


def _require_compiled_setup(session: Session, revision: CanonicalTradePlanRevision) -> None:
    plan = revision.plan
    setup = session.get(CompiledSetupDefinition, plan.setup_definition_id)
    if setup is None:
        raise CanonicalTradePlanLineageError(
            "Canonical TradePlanRevision must bind a tenant-owned compiled setup definition."
        )
    if setup.organization_id != plan.organization_id or setup.user_id != plan.user_id:
        raise CanonicalTradePlanLineageError(
            "Compiled setup definition must belong to the plan tenant."
        )
    if setup.strategy_version_id != plan.strategy_version_id:
        raise CanonicalTradePlanLineageError(
            "Compiled setup definition must bind the plan strategy version."
        )


def _insert_canonical_rows(
    session: Session,
    *,
    digest: str,
    revision: CanonicalTradePlanRevision,
    idempotency_key: str,
) -> None:
    plan = revision.plan
    _ensure_compatibility_proposal(session, revision)
    session.add(_plan_to_row(revision))
    session.flush()
    session.add(
        CanonicalTradePlanRootRow(
            plan_id=plan.plan_id,
            organization_id=plan.organization_id,
            user_id=plan.user_id,
            account_id=plan.account_id,
            candidate_id=plan.candidate_id,
            created_at=plan.created_at,
        )
    )
    session.add(_lineage_to_row(revision, digest=digest))
    session.add(
        CanonicalTradePlanIdempotencyKeyRow(
            organization_id=plan.organization_id,
            idempotency_key=idempotency_key,
            uniqueness_hash=digest,
            revision_id=plan.revision_id,
        )
    )
    proposal = session.get(TradeProposalModel, plan.plan_id)
    if proposal is not None:
        proposal.latest_plan_revision_id = plan.revision_id


def _insert_idempotency(
    session: Session,
    *,
    organization_id: UUID,
    idempotency_key: str,
    digest: str,
    revision_id: UUID,
) -> None:
    existing = session.get(CanonicalTradePlanIdempotencyKeyRow, (organization_id, idempotency_key))
    if existing is not None:
        if existing.uniqueness_hash != digest:
            raise ConflictingTradePlanIdempotencyError(
                "Plan idempotency key is already bound to a different canonical uniqueness "
                "fingerprint."
            )
        return
    try:
        with session.begin_nested():
            session.add(
                CanonicalTradePlanIdempotencyKeyRow(
                    organization_id=organization_id,
                    idempotency_key=idempotency_key,
                    uniqueness_hash=digest,
                    revision_id=revision_id,
                )
            )
            session.flush()
    except IntegrityError as exc:
        if not is_unique_violation(exc, "pk_canonical_trade_plan_idempotency_keys"):
            raise
        current = session.get(
            CanonicalTradePlanIdempotencyKeyRow, (organization_id, idempotency_key)
        )
        if current is None:
            raise
        if current.uniqueness_hash != digest:
            raise ConflictingTradePlanIdempotencyError(
                "Plan idempotency key is already bound to a different canonical uniqueness "
                "fingerprint."
            ) from exc


def _ensure_compatibility_proposal(session: Session, revision: CanonicalTradePlanRevision) -> None:
    plan = revision.plan
    existing = session.get(TradeProposalModel, plan.plan_id)
    if existing is not None:
        if existing.organization_id != plan.organization_id or existing.user_id != plan.user_id:
            raise ConflictingTradePlanIdempotencyError(
                "Canonical plan_id is already bound to a different tenant TradeProposal."
            )
        if existing.plan_root_kind != PLAN_ROOT_CANONICAL:
            raise ConflictingTradePlanIdempotencyError(
                "Canonical plan_id collided with a non-canonical TradeProposal."
            )
        return
    direction = TradeDirection.LONG if plan.side is EntrySide.BUY else TradeDirection.SHORT
    session.add(
        TradeProposalModel(
            id=plan.plan_id,
            organization_id=plan.organization_id,
            user_id=plan.user_id,
            strategy_id=StrategyId.HTF_TREND_PULLBACK,
            symbol=plan.execution_instrument,
            timeframe=plan.timeframe,
            direction=direction,
            entry_price=plan.entry_zone.lower,
            position_size=plan.quantity.value,
            leverage=plan.risk_and_exits.leverage,
            stop_loss=plan.risk_and_exits.stop.value,
            take_profits=[],
            invalidation="canonical-plan-root-compatibility",
            confidence=0.0,
            risk_level=RiskSeverity.MEDIUM,
            rationale=("Canonical TradePlanRevision compatibility root; not plan authority."),
            status=ProposalStatus.DRAFT,
            plan_root_kind=PLAN_ROOT_CANONICAL,
            approval_required=True,
        )
    )
    session.flush()


def _plan_to_row(revision: CanonicalTradePlanRevision) -> TradePlanRevisionModel:
    plan = revision.plan
    semantic = TradePlanRevisionSemantic.model_validate(
        plan.model_dump(
            mode="python",
            exclude={"correlation_id", "content_hash", "created_at", "presentation_metadata"},
        )
    )
    return TradePlanRevisionModel(
        id=plan.revision_id,
        plan_id=plan.plan_id,
        organization_id=plan.organization_id,
        user_id=plan.user_id,
        account_id=plan.account_id,
        exchange_account_id=plan.exchange_account_id,
        schema_version=plan.schema_version,
        operation=plan.operation,
        strategy_version_id=plan.strategy_version_id,
        setup_definition_id=plan.setup_definition_id,
        candidate_id=plan.candidate_id,
        plan_authority=PLAN_AUTHORITY_CANONICAL,
        canonical_candidate_id=plan.candidate_id,
        compiled_setup_definition_id=plan.setup_definition_id,
        expected_account_mode=plan.expected_account_mode,
        permission_attestation_id=plan.permission_attestation_id,
        permission_attestation_version=plan.permission_attestation_version,
        execution_venue=plan.execution_venue,
        execution_instrument=plan.execution_instrument,
        execution_policy_version=plan.execution_policy_version,
        valid_from=plan.valid_from,
        valid_until=plan.valid_until,
        semantic_payload=semantic.model_dump(mode="json"),
        correlation_id=plan.correlation_id,
        content_hash=plan.content_hash,
        presentation_metadata=plan.presentation_metadata.model_dump(mode="json"),
        created_at=plan.created_at,
    )


def _lineage_to_row(
    revision: CanonicalTradePlanRevision, *, digest: str
) -> CanonicalTradePlanLineageRow:
    plan = revision.plan
    lineage = revision.lineage
    return CanonicalTradePlanLineageRow(
        revision_id=plan.revision_id,
        organization_id=plan.organization_id,
        user_id=plan.user_id,
        account_id=plan.account_id,
        plan_id=plan.plan_id,
        candidate_id=lineage.candidate_id,
        candidate_revision=lineage.candidate_revision,
        candidate_content_hash=lineage.candidate_content_hash,
        assessment_id=lineage.assessment_id,
        eligibility_id=lineage.eligibility_id,
        eligibility_content_hash=lineage.eligibility_content_hash,
        eligibility_uniqueness_hash=lineage.eligibility_uniqueness_hash,
        evidence_window_hash=lineage.evidence_window_hash,
        strategy_version_id=lineage.strategy_version_id,
        setup_definition_id=lineage.setup_definition_id,
        compiled_setup_content_hash=lineage.compiled_setup_content_hash,
        fusion_policy_version=lineage.fusion_policy_version,
        uniqueness_hash=digest,
        envelope_content_hash=revision.content_hash,
    )


def _envelope_from_rows(
    plan_row: TradePlanRevisionModel, lineage_row: CanonicalTradePlanLineageRow
) -> CanonicalTradePlanRevision:
    plan = trade_plan_revision_to_schema(plan_row)
    lineage = CanonicalTradePlanLineage(
        candidate_id=lineage_row.candidate_id,
        candidate_revision=lineage_row.candidate_revision,
        candidate_content_hash=lineage_row.candidate_content_hash,
        assessment_id=lineage_row.assessment_id,
        eligibility_id=lineage_row.eligibility_id,
        eligibility_content_hash=lineage_row.eligibility_content_hash,
        eligibility_uniqueness_hash=lineage_row.eligibility_uniqueness_hash,
        eligibility_state=ActionEligibilityState.ELIGIBLE,
        evidence_window_hash=lineage_row.evidence_window_hash,
        strategy_version_id=lineage_row.strategy_version_id,
        setup_definition_id=lineage_row.setup_definition_id,
        compiled_setup_content_hash=lineage_row.compiled_setup_content_hash,
        fusion_policy_version=lineage_row.fusion_policy_version,
    )
    rebuilt = CanonicalTradePlanRevision(
        plan=plan,
        lineage=lineage,
        uniqueness_hash=lineage_row.uniqueness_hash,
        paper_actionable=True,
        live_executable=False,
        content_hash=lineage_row.envelope_content_hash,
    )
    if rebuilt.plan.content_hash != plan_row.content_hash:
        raise CanonicalTradePlanLineageError(
            "Stored trade plan content hash does not match canonical rebuild."
        )
    return rebuilt
