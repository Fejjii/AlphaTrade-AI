"""Recorded canonical trades must be discoverable without an Agent confirmation capture."""

import pytest
from sqlalchemy import select

from app.db.models import JournalTrade, Membership
from app.interactive_agent.contracts import AgentTurnRequest
from app.interactive_agent.service import InteractiveAgentService
from app.schemas.common import MembershipRole
from tests import test_journal_plan_targets as target_tests
from tests.support.phase8_runtime import phase8_settings
from tests.support.postgres_persistence import requires_postgres


@pytest.fixture
def historical(monkeypatch):
    return target_tests.historical.__wrapped__(monkeypatch)


pytestmark = requires_postgres


def test_latest_canonical_trade_without_capture_supplies_plan_and_fill(historical):
    factory, envelope, _authorization, _result, _scope, _snapshot = historical
    contexts = []

    class Responder:
        def compose(self, **kwargs):
            contexts.append(kwargs["factual_context"])
            return "Recorded paper trade; approved plan targets differ from the Journal projection."

    with factory() as session:
        session.add(
            Membership(
                organization_id=envelope.plan.organization_id,
                user_id=envelope.plan.user_id,
                role=MembershipRole.OWNER,
            )
        )
        from tests.test_interactive_agent_foundation import _add_chunk

        _add_chunk(
            session,
            organization_id=envelope.plan.organization_id,
            user_id=envelope.plan.user_id,
            title="Master Playbook v1",
            content="BTCUSDT paper trade strategy authorization: PLAYBOOK_IS_NOT_APPROVAL.",
        )
        session.commit()
        trade = session.scalars(select(JournalTrade)).one()
        result = InteractiveAgentService(
            session, settings=phase8_settings(), responder=Responder()
        ).handle_turn(
            AgentTurnRequest(
                message=(
                    f"Explain my latest {trade.symbol} {trade.direction.value} paper trade: "
                    "strategy, entry, stop, target, authorization and execution venue."
                )
            ),
            organization_id=trade.organization_id,
            user_id=trade.user_id,
        )
        assert str(trade.id) in {ref.record_id for ref in result.connections}
        assert contexts and "planned entry" in contexts[0].lower()
        assert "PLAYBOOK_IS_NOT_APPROVAL" not in contexts[0] and not result.knowledge
        assert "100000" in contexts[0] and "fill" in contexts[0].lower()
        assert "Journal targets are empty" in contexts[0]
        assert "phase1-fake-venue" in contexts[0] and "conflicting evidence" in contexts[0]
        assert (
            not result.execution_attempted and not result.authority_mutated and not result.proposals
        )


def _new_trade(session, template, **overrides):
    from datetime import timedelta
    from uuid import uuid4

    row = JournalTrade(
        id=uuid4(),
        organization_id=template.organization_id,
        user_id=template.user_id,
        account_id=template.account_id,
        source=template.source,
        status=template.status,
        symbol="BTCUSDT",
        timeframe="15m",
        direction=template.direction,
        entry_time=template.entry_time + timedelta(seconds=1),
        **overrides,
    )
    session.add(row)
    session.flush()
    return row


def _read(session, trade, **selectors):
    from app.interactive_agent.actions import RecordedTradeInput
    from app.interactive_agent.recorded_trade import read_recorded_trade

    return read_recorded_trade(
        session,
        RecordedTradeInput(**selectors),
        organization_id=trade.organization_id,
        user_id=trade.user_id,
    )


def test_latest_selection_filters_direction_symbol_and_accounts_before_limiting(historical):
    from datetime import timedelta

    from app.schemas.common import TradeDirection

    factory, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        latest = _new_trade(session, trade)
        opposite = _new_trade(session, trade)
        opposite.direction = TradeDirection.LONG
        opposite.entry_time += timedelta(days=1)
        for _ in range(21):
            unrelated = _new_trade(session, trade)
            unrelated.symbol = "ETHUSDT"
            unrelated.entry_time += timedelta(days=2)
        session.flush()
        result = _read(session, trade, symbol="BTCUSDT", direction="short", latest=True)
        assert result.connections[0].record_id == str(latest.id)
        assert (
            "Missing evidence:" in result.reply
            and "linked immutable canonical plan" in result.reply
        )
        assert str(trade.id) not in result.recorded_evidence


@pytest.mark.parametrize("different_tenant", [False, True])
def test_account_and_tenant_isolation_even_for_explicit_foreign_ids(historical, different_tenant):
    from uuid import uuid4

    from app.db.models import ExecutionAccount, Organization, User

    factory, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        foreign_user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="fixture")
        session.add(foreign_user)
        foreign_org = Organization(id=uuid4(), name="other") if different_tenant else None
        if foreign_org:
            session.add(foreign_org)
        session.flush()
        account = ExecutionAccount(
            id=uuid4(),
            organization_id=foreign_org.id if foreign_org else trade.organization_id,
            user_id=foreign_user.id,
            name="other",
        )
        session.add(account)
        session.flush()
        foreign_trade = _new_trade(session, trade)
        foreign_trade.organization_id = account.organization_id
        foreign_trade.user_id = account.user_id
        foreign_trade.account_id = account.id
        foreign_trade.thesis = "foreign-private-marker"
        session.flush()
        for selectors in (
            {"latest": True},
            {"account_id": account.id},
            {"journal_trade_id": foreign_trade.id},
        ):
            result = _read(session, trade, **selectors)
            assert "foreign-private-marker" not in result.recorded_evidence
            assert str(foreign_trade.id) not in {ref.record_id for ref in result.connections}
            if "latest" in selectors:
                assert result.connections[0].record_id == str(trade.id)
            else:
                assert "No recorded Journal trade" in result.reply
        # A tampered query-helper account cannot make a colleague's account visible.
        deceptive = _new_trade(session, trade)
        deceptive.account_id = account.id
        session.flush()
        assert (
            "No recorded Journal trade"
            in _read(session, trade, journal_trade_id=deceptive.id).reply
        )


def test_only_genuine_multi_account_or_trade_ambiguity_asks_a_question(historical):
    from uuid import uuid4

    from app.db.models import ExecutionAccount

    factory, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        second = _new_trade(session, trade)
        assert "Which Journal trade UUID" in _read(session, trade).reply
        assert _read(session, trade, latest=True).connections[0].record_id == str(second.id)
        account = ExecutionAccount(
            id=uuid4(),
            organization_id=trade.organization_id,
            user_id=trade.user_id,
            name="second owned",
        )
        session.add(account)
        session.flush()
        second.account_id = account.id
        session.flush()
        assert "Which account UUID" in _read(session, trade, latest=True).reply
        assert _read(session, trade, account_id=trade.account_id, latest=True).connections[
            0
        ].record_id == str(trade.id)
        second.account_id = trade.account_id
        second.entry_time = trade.entry_time
        session.flush()
        assert "Which Journal trade UUID" in _read(session, trade, latest=True).reply


@pytest.mark.parametrize("missing", ["plan", "command"])
def test_missing_lineage_stays_missing_and_does_not_use_playbook(historical, missing):
    factory, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        if missing == "plan":
            trade.trade_plan_revision_id = None
        else:
            trade.execution_lifecycle_id = None
        session.flush()
        result = _read(session, trade, latest=True)
        assert "unavailable" in result.reply and "Missing evidence:" in result.reply
        assert "fill" in result.reply.lower()
        assert not any(ref.title == "Authorization" for ref in result.connections)
        assert "never establishes authorization" in result.recorded_evidence


def test_foreign_plan_pointer_cannot_load_lineage(historical):
    from uuid import uuid4

    from app.db.models import ExecutionAccount, Organization, User

    factory, envelope, *_ = historical
    with factory() as session:
        original = session.scalars(select(JournalTrade)).one()
        org = Organization(id=uuid4(), name="other")
        owner = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="fixture")
        session.add_all([org, owner])
        session.flush()
        account = ExecutionAccount(
            id=uuid4(), organization_id=org.id, user_id=owner.id, name="other"
        )
        session.add(account)
        session.flush()
        row = _new_trade(session, original)
        row.organization_id, row.user_id, row.account_id = org.id, owner.id, account.id
        row.trade_plan_revision_id = envelope.plan.revision_id
        session.flush()
        result = _read(session, row, latest=True)
        assert [ref.title for ref in result.connections] == ["Journal"]
        assert "linked immutable canonical plan" in result.reply
        assert envelope.plan.content_hash not in result.recorded_evidence


def test_plan_entry_is_not_fill_and_targets_keep_plan_order_without_repair(historical):
    factory, envelope, _authorization, _command, _scope, snapshot = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        result = _read(session, trade, latest=True)
        assert (
            f"Planned entry: {envelope.plan.entry_zone.lower} to {envelope.plan.entry_zone.upper}"
            in result.reply
        )
        from app.db.models import ExecutionFillFact

        fill = session.scalars(select(ExecutionFillFact)).one()
        assert f"recorded fill: {fill.quantity} {fill.unit} at {fill.price}" in result.reply
        for target in envelope.plan.risk_and_exits.targets:
            assert f"{target.price.value} ({target.quantity_fraction} allocation)" in result.reply
        assert "Journal targets are empty" in result.reply
        assert "detailed captured RiskEngine decision" in result.reply
        assert trade.planned_targets == []
        assert target_tests._snapshot(session) == snapshot


@pytest.mark.parametrize(
    "planned,sources,expected",
    [
        ("PAPER_INTERNAL", ["paper_internal"], "internal paper simulator"),
        ("BLOFIN_DEMO", ["blofin_demo"], "BloFin demo (actual recorded venue fills)"),
        ("BLOFIN_DEMO", ["paper_internal"], "conflicting evidence"),
        ("BLOFIN_DEMO", ["phase1-fake-venue"], "conflicting evidence"),
        ("PAPER_INTERNAL", ["paper_internal", "blofin_demo"], "conflicting evidence"),
        ("BLOFIN_DEMO", [], "actual venue unavailable"),
    ],
)
def test_venue_requires_actual_fill_source_and_never_uses_planned_venue_as_execution(
    planned, sources, expected
):
    from types import SimpleNamespace

    from app.interactive_agent.recorded_trade import _Evidence, _venue

    evidence = _Evidence()
    result = _venue(planned, [SimpleNamespace(venue_source=s) for s in sources], evidence)
    assert expected in result
    if expected == "conflicting evidence":
        assert evidence.missing


@pytest.mark.parametrize(
    "message",
    [
        (
            "Explain my latest BTCUSDT short paper trade: "
            "strategy, entry, stop, target, authorization and execution venue."
        ),
        "Using my Master Playbook, explain my last recorded BTCUSDT trade.",
        "What strategy generated my most recent BTCUSDT short trade and why was it allowed?",
    ],
)
def test_historical_trade_routing_takes_precedence_over_strategy_and_knowledge(message):
    from app.interactive_agent.action_registry import resolve_action, route_action
    from app.interactive_agent.actions import RecordedTradeInput

    action = route_action(AgentTurnRequest(message=message))
    assert action.name == "paper_trade.read_recorded"
    tool, selectors = resolve_action(action)
    assert tool.behavior == "read" and tool.kind.value == "none"
    assert isinstance(selectors, RecordedTradeInput) and selectors.symbol == "BTCUSDT"


@pytest.mark.parametrize(
    "message",
    ["Execute my latest paper trade", "Approve my latest paper trade", "Create my latest trade"],
)
def test_recorded_read_does_not_route_execution_or_approval_requests(message):
    from app.interactive_agent.recorded_trade import route_recorded_trade

    assert route_recorded_trade(message, symbol=None) is None


def test_allow_receipt_without_fills_does_not_imply_execution():
    from tests.support.phase8_runtime import prepared_authorized_canonical
    from tests.support.postgres_persistence import phase7_plan_session_factory
    from tests.test_phase8_canonical_paper_execution import _execute

    factory = phase7_plan_session_factory()
    _, envelope, authorization = prepared_authorized_canonical(factory)
    _, session, _, _ = _execute(factory, envelope, authorization, key="explanation-without-fill")
    try:
        trade = session.scalars(select(JournalTrade)).one()
        result = _read(session, trade, latest=True)
        assert "recorded fill: unavailable" in result.reply
        assert "actual venue unavailable" in result.reply
        assert "immutable fill evidence" in result.reply
        assert any(ref.title == "Authorization" for ref in result.connections)
        assert "Acknowledgment/ALLOW alone does not prove a fill" in result.recorded_evidence
    finally:
        session.close()


def test_read_api_authentication_and_scope_come_from_owner_not_action_arguments(
    historical, monkeypatch
):
    from fastapi.testclient import TestClient

    from app.db.models import User
    from app.db.session import get_session
    from app.interactive_agent.conversation import MODEL_REPLY_UNAVAILABLE
    from app.main import create_app
    from app.security.tokens import create_access_token

    factory, envelope, *_ = historical
    settings = phase8_settings()
    monkeypatch.setattr(
        "app.interactive_agent.conversation.ModelConversationalResponder.compose",
        lambda *a, **k: MODEL_REPLY_UNAVAILABLE,
    )
    with factory() as session:
        owner = session.get(User, envelope.plan.user_id)
        owner.email_verified = True
        session.add(
            Membership(
                organization_id=envelope.plan.organization_id,
                user_id=owner.id,
                role=MembershipRole.OWNER,
            )
        )
        session.commit()
        token, _ = create_access_token(
            user_id=owner.id,
            organization_id=envelope.plan.organization_id,
            email=owner.email,
            settings=settings,
        )
    app = create_app(settings=settings)

    def db_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = db_session
    try:
        with TestClient(app) as client:
            body = {"message": "Explain my latest BTCUSDT short paper trade."}
            assert client.post("/agent/turns", json=body).status_code == 401
            headers = {"Authorization": f"Bearer {token}"}
            response = client.post("/agent/turns", json=body, headers=headers)
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["proposals"] == [] and not result["execution_attempted"]
            assert "Journal targets are empty" in result["reply"]
            # Identity spoofing cannot be accepted through the closed typed read contract.
            injected = {
                **body,
                "action": {
                    "name": "paper_trade.read_recorded",
                    "arguments": {"organization_id": str(envelope.plan.organization_id)},
                },
            }
            assert client.post("/agent/turns", json=injected, headers=headers).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_conflicting_projection_lineage_refuses_without_authorization_inference(historical):
    from uuid import uuid4

    from app.core.errors import ValidationAppError

    factory, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        trade.candidate_id = uuid4()
        session.flush()
        with pytest.raises(ValidationAppError, match="Journal/plan lineage does not match"):
            _read(session, trade, latest=True)


def test_ambiguous_selection_remains_a_targeted_question_without_model_inference(historical):
    factory, envelope, *_ = historical

    class ForbiddenResponder:
        def compose(self, **kwargs):
            pytest.fail("A model must not choose an ambiguous trade.")

    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        _new_trade(session, trade)
        session.add(
            Membership(
                organization_id=envelope.plan.organization_id,
                user_id=envelope.plan.user_id,
                role=MembershipRole.OWNER,
            )
        )
        session.commit()
        result = InteractiveAgentService(
            session, settings=phase8_settings(), responder=ForbiddenResponder()
        ).handle_turn(
            AgentTurnRequest(message="Explain my recorded BTCUSDT short paper trade."),
            organization_id=trade.organization_id,
            user_id=trade.user_id,
        )
        assert "Which Journal trade UUID" in result.reply
        assert not result.connections and not result.proposals
