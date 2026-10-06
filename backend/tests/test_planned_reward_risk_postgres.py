"""Persisted pre-policy plans cannot acquire fresh authorization or exposure."""

import pytest
from sqlalchemy import func, select

from app.core.errors import TradingPolicyError
from app.db.models import ApprovalAuthorization, RiskReservation, VenueSubmitEffect
from app.db.models import TradePlanRevision as PlanRow
from app.schemas.trade_plan import AuthorizationState
from tests.support.phase7_postgres import postgres_plan_world
from tests.support.phase7_trade_plan import plan_command
from tests.support.phase8_runtime import authorize_canonical_plan, seed_paper_capacity
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres
from tests.test_phase8_canonical_paper_execution import _execute
from tests.test_planned_reward_risk import terms

pytestmark = requires_postgres


@pytest.fixture
def legacy(monkeypatch):
    factory = phase7_plan_session_factory()
    world = postgres_plan_world(factory)
    source = terms(entry="85111.40", stop="85720.80", targets=("84714.10",))
    # Reproduce the historical release without the new gate; never mutate stored plans.
    with monkeypatch.context() as historical:
        historical.setattr(
            "app.services.canonical_trade_plan.planned_reward_risk", lambda _terms: None
        )
        historical.setattr(
            "app.services.planned_reward_risk.planned_reward_risk", lambda _terms: None
        )
        envelope = world.plans.create(plan_command(world, terms=source))
        with factory() as session:
            authorization = authorize_canonical_plan(session, envelope, plans=world.plans)
            seed_paper_capacity(session, envelope)
            session.commit()
    return factory, world, envelope, authorization


def test_legacy_authorization_cannot_be_reissued_and_claim_is_durably_blocked(legacy):
    factory, world, envelope, authorization = legacy
    with factory() as session:
        before = dict(session.get(PlanRow, envelope.plan.revision_id).semantic_payload)
        with pytest.raises(TradingPolicyError) as error:
            authorize_canonical_plan(session, envelope, plans=world.plans)
        assert error.value.details["reason"] == "planned_reward_risk_below_minimum"
        session.rollback()
    first, session, *_ = _execute(factory, envelope, authorization, key="legacy-rr-block")
    try:
        assert first.outcome.value == "BLOCKED"
        assert first.blocked_reason_code == "planned_reward_risk_below_minimum"
        assert (
            session.get(ApprovalAuthorization, authorization.authorization_id).state
            == AuthorizationState.AVAILABLE
        )
        assert session.scalar(select(func.count()).select_from(RiskReservation)) == 0
        assert session.scalar(select(func.count()).select_from(VenueSubmitEffect)) == 0
        assert session.get(PlanRow, envelope.plan.revision_id).semantic_payload == before
    finally:
        session.close()
    repeated, session, *_ = _execute(factory, envelope, authorization, key="legacy-rr-block")
    try:
        assert repeated.replayed and repeated.command_id == first.command_id
        assert repeated.outcome.value == "BLOCKED"
    finally:
        session.close()
