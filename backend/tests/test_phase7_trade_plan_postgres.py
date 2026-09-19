"""PostgreSQL canonical TradePlanRevision binding: discriminator, lineage, PLAN_CREATED."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.canonical_trade_plans import (
    PLAN_AUTHORITY_CANONICAL,
    PLAN_AUTHORITY_PAPER_VALIDATION,
    PLAN_ROOT_CANONICAL,
    CanonicalTradePlanHistoryImmutabilityError,
    CanonicalTradePlanLineageRow,
    CanonicalTradePlanRootRow,
)
from app.db.models import PaperValidationCandidate
from app.db.models import TradePlanRevision as TradePlanRevisionModel
from app.db.models import TradeProposal as TradeProposalModel
from app.persistence.candidate_postgres import PostgresCandidateRepository
from app.persistence.composition import (
    build_postgres_action_eligibility,
    build_postgres_canonical_trade_plan_store,
)
from app.schemas.trade_plan import TradePlanRevisionSemantic
from app.services.canonical_serialization import canonical_sha256
from app.services.canonical_trade_plan import CanonicalTradePlanService
from app.services.canonical_trade_plan_errors import ConflictingTradePlanIdempotencyError
from app.signal_fusion.enums import CandidateState
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.signal_fusion.memory import FrozenClock
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_fusion import ACCOUNT_ID, ORG_ID, USER_ID
from tests.support.phase7_postgres import postgres_plan_world
from tests.support.phase7_trade_plan import plan_command, plan_terms
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres


def _factory() -> sessionmaker[Session]:
    return phase7_plan_session_factory()


@requires_postgres
def test_canonical_plan_persists_with_discriminator_and_lineage() -> None:
    factory = _factory()
    world = postgres_plan_world(factory)
    created = world.plans.create(plan_command(world))
    assert created.live_executable is False
    assert created.plan.candidate_id == world.candidate.candidate_id
    semantic = TradePlanRevisionSemantic.model_validate(
        created.plan.model_dump(
            mode="python",
            exclude={"correlation_id", "content_hash", "created_at", "presentation_metadata"},
        )
    )
    assert canonical_sha256(semantic) == created.plan.content_hash
    projected = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert projected is not None
    assert projected.state is CandidateState.PLAN_CREATED
    session = factory()
    try:
        row = session.get(TradePlanRevisionModel, created.plan.revision_id)
        assert row is not None
        assert row.plan_authority == PLAN_AUTHORITY_CANONICAL
        assert row.canonical_candidate_id == world.candidate.candidate_id
        assert row.candidate_id == world.candidate.candidate_id
        assert row.compiled_setup_definition_id == world.candidate.setup_definition_id
        assert row.setup_definition_id == world.candidate.setup_definition_id
        pvc = session.get(PaperValidationCandidate, world.candidate.candidate_id)
        assert pvc is None
        proposal = session.get(TradeProposalModel, created.plan.plan_id)
        assert proposal is not None
        assert proposal.plan_root_kind == PLAN_ROOT_CANONICAL
        lineage = session.get(CanonicalTradePlanLineageRow, created.plan.revision_id)
        assert lineage is not None
        assert lineage.uniqueness_hash == created.uniqueness_hash
        assert lineage.eligibility_id == world.evaluation.eligibility.eligibility_id
        root = session.scalars(select(CanonicalTradePlanRootRow)).first()
        assert root is not None
        assert root.candidate_id == world.candidate.candidate_id
        assert root.account_id == ACCOUNT_ID
        assert root.user_id == USER_ID
    finally:
        session.close()


@requires_postgres
def test_identical_requests_converge_after_store_restart() -> None:
    factory = _factory()
    world = postgres_plan_world(factory)
    first = world.plans.create(plan_command(world))
    second = world.plans.create(plan_command(world, idempotency_key="canonical-plan-create-2"))
    assert first.plan.revision_id == second.plan.revision_id
    clock = FrozenClock(EVALUATED_AT)
    repository = PostgresCandidateRepository(factory, clock=clock)
    restarted = CanonicalTradePlanService(
        store=build_postgres_canonical_trade_plan_store(factory, candidate_repository=repository),
        lifecycle=CandidateLifecycleService(repository=repository, clock=clock),
        eligibility=build_postgres_action_eligibility(factory, clock=clock),
        clock=clock,
    )
    replay = restarted.create(plan_command(world, idempotency_key="canonical-plan-create-3"))
    assert replay.plan.revision_id == first.plan.revision_id
    assert replay.content_hash == first.content_hash
    projected = restarted._lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert projected is not None
    assert projected.state is CandidateState.PLAN_CREATED
    assert len(restarted._lifecycle.transition_history(ORG_ID, world.candidate.candidate_id)) == 1


@requires_postgres
def test_conflicting_semantics_fail_closed() -> None:
    world = postgres_plan_world(_factory())
    world.plans.create(plan_command(world))
    with pytest.raises(ConflictingTradePlanIdempotencyError):
        world.plans.create(
            plan_command(
                world,
                idempotency_key="canonical-plan-create-other",
                terms=plan_terms(world.candidate, quantity={"value": "3.000", "unit": "CONTRACTS"}),
            )
        )
    projected = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert projected is not None
    assert projected.state is CandidateState.PLAN_CREATED


@requires_postgres
def test_lineage_is_append_only() -> None:
    factory = _factory()
    world = postgres_plan_world(factory)
    created = world.plans.create(plan_command(world))
    session = factory()
    try:
        row = session.get(CanonicalTradePlanLineageRow, created.plan.revision_id)
        assert row is not None
        row.envelope_content_hash = "d" * 64
        with pytest.raises(CanonicalTradePlanHistoryImmutabilityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


@requires_postgres
def test_legacy_paper_validation_authority_remains_distinct() -> None:
    mapper = inspect(TradePlanRevisionModel)
    names = {column.key for column in mapper.columns}
    assert "plan_authority" in names
    assert "canonical_candidate_id" in names
    assert "compiled_setup_definition_id" in names
    assert "eligibility_id" not in names
    assert list(TradePlanRevisionModel.__table__.c.candidate_id.foreign_keys) == []
    canonical = list(TradePlanRevisionModel.__table__.c.canonical_candidate_id.foreign_keys)
    assert canonical[0].column.table.name == "canonical_candidates"
    compiled = list(TradePlanRevisionModel.__table__.c.compiled_setup_definition_id.foreign_keys)
    assert compiled[0].column.table.name == "compiled_setup_definitions"
    assert PLAN_AUTHORITY_PAPER_VALIDATION == "paper_validation"


@requires_postgres
def test_concurrent_identical_creates_converge() -> None:
    world = postgres_plan_world(_factory())
    command = plan_command(world)

    def _run(_: int) -> str:
        return world.plans.create(command).content_hash

    with ThreadPoolExecutor(max_workers=8) as pool:
        hashes = list(pool.map(_run, range(8)))
    assert len(set(hashes)) == 1
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.PLAN_CREATED
    assert len(world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id)) == 1
