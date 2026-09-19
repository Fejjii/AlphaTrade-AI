"""Tenant seed for Phase 7 PostgreSQL TradePlan / eligibility tests."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    CompiledSetupDefinition,
    ExecutionAccount,
    Organization,
    User,
    UserStrategy,
    UserStrategyVersion,
)
from app.persistence.candidate_postgres import PostgresCandidateRepository
from app.persistence.composition import (
    build_postgres_action_eligibility,
    build_postgres_canonical_trade_plan_store,
)
from app.schemas.common import SetupCompileStatus, StrategyId
from app.schemas.trade_plan import AccountMode, ExecutionMode
from app.services.canonical_trade_plan import CanonicalTradePlanService
from app.signal_fusion.action_eligibility import ActionEligibilityService
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.signal_fusion.memory import FrozenClock
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_eligibility import eligibility_command
from tests.support.phase6_fusion import (
    ACCOUNT_ID,
    COMPILED_SETUP_ID,
    ORG_ID,
    STRATEGY_VERSION_ID,
    USER_ID,
    make_assessment,
    make_creation_command,
    make_evidence_window,
)
from tests.support.phase7_trade_plan import CanonicalPlanWorld

_HASH = "c" * 64


def seed_phase7_tenancy(session: Session) -> None:
    session.add(Organization(id=ORG_ID, name=f"Phase7 {ORG_ID}"))
    session.add(
        User(
            id=USER_ID,
            email=f"phase7-{USER_ID}@example.com",
            hashed_password="not-a-real-hash",
        )
    )
    session.flush()
    strategy = UserStrategy(
        organization_id=ORG_ID,
        user_id=USER_ID,
        name="Phase 7 compiled setup strategy",
        setup_type=StrategyId.HTF_TREND_PULLBACK,
    )
    session.add(strategy)
    session.flush()
    session.add(
        UserStrategyVersion(
            id=STRATEGY_VERSION_ID,
            strategy_id=strategy.id,
            version=1,
            card={"strategy_name": "Phase 7"},
        )
    )
    session.flush()
    session.add(
        CompiledSetupDefinition(
            id=COMPILED_SETUP_ID,
            organization_id=ORG_ID,
            user_id=USER_ID,
            strategy_id=strategy.id,
            strategy_version_id=STRATEGY_VERSION_ID,
            compiler_version="test-compiler/v1",
            grammar_version="test-grammar/v1",
            compiled_ast={"kind": "test"},
            content_hash=_HASH,
            compile_status=SetupCompileStatus.EXECUTABLE,
        )
    )
    session.add(
        ExecutionAccount(
            id=ACCOUNT_ID,
            organization_id=ORG_ID,
            user_id=USER_ID,
            name="Phase 7 paper account",
            execution_mode=ExecutionMode.PAPER,
            account_mode=AccountMode.NET,
        )
    )
    session.flush()


def postgres_plan_world(factory: sessionmaker[Session]) -> CanonicalPlanWorld:
    session = factory()
    try:
        seed_phase7_tenancy(session)
        session.commit()
    finally:
        session.close()
    clock = FrozenClock(EVALUATED_AT)
    repository = PostgresCandidateRepository(factory, clock=clock)
    lifecycle = CandidateLifecycleService(repository=repository, clock=clock)
    eligibility: ActionEligibilityService = build_postgres_action_eligibility(factory, clock=clock)
    plans = CanonicalTradePlanService(
        store=build_postgres_canonical_trade_plan_store(factory, candidate_repository=repository),
        lifecycle=lifecycle,
        eligibility=eligibility,
        clock=clock,
    )
    window = make_evidence_window()
    assessment = make_assessment(window)
    candidate = lifecycle.create_from_confirmed_setup(
        make_creation_command(window=window, assessment=assessment)
    )
    evaluation = eligibility.evaluate(
        eligibility_command(window=window, assessment=assessment, candidate=candidate)
    )
    return CanonicalPlanWorld(
        lifecycle=lifecycle,
        eligibility=eligibility,
        plans=plans,
        candidate=candidate,
        evaluation=evaluation,
    )
