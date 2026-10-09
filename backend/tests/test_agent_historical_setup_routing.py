"""Historical qualification must use recorded lineage, never a forming setup."""

import pytest

from app.interactive_agent.action_registry import route_action
from app.interactive_agent.contracts import AgentTurnRequest
from tests.support.postgres_persistence import requires_postgres

QUESTION = (
    "Explain why my latest BTC short qualified as a Nested setup. "
    "Show the recorded conditions and candle evidence. "
    "Would that same plan pass the current minimum reward to risk rule?"
)
CURRENT = "Explain the current forming BTCUSDT short Nested setup and its candle evidence."
FOLLOWUP = "Would that same plan pass the current minimum reward to risk rule?"


@pytest.mark.parametrize("ui_symbol", [None, "ETHUSDT"])
@pytest.mark.parametrize(
    "message",
    [
        QUESTION,
        (
            "Explain why my latest BTC short qualified as a Nested setup and whether "
            "it passes the current minimum reward to risk rule?"
        ),
    ],
)
def test_exact_historical_question_routes_bare_asset_ahead_of_ui_market(ui_symbol, message):
    routed = route_action(AgentTurnRequest(message=message, symbol=ui_symbol))
    assert routed is not None and routed.name == "paper_trade.read_recorded"
    assert routed.arguments["market_name"] == "BTC"
    assert routed.arguments["symbol"] is None
    assert routed.arguments["direction"] == "short"
    assert routed.arguments["latest"]


def test_explicit_current_setup_remains_on_the_current_setup_read_path():
    assert route_action(AgentTurnRequest(message=CURRENT)) is None


@pytest.fixture
def recorded_nested(monkeypatch):
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal
    from uuid import uuid4

    from sqlalchemy import select

    from app.db.models import CompiledSetupDefinition, JournalTrade, Membership, UserStrategyVersion
    from app.db.strategy_brain import BrainSetupEventRow, BrainSetupRow
    from app.schemas.common import MembershipRole
    from app.schemas.nested_continuation import NestedContinuationSpec
    from tests.support.phase6_fusion import SETUP_CONTENT_HASH
    from tests.support.phase7_postgres import postgres_plan_world
    from tests.support.phase7_trade_plan import plan_command
    from tests.support.phase8_runtime import (
        EXECUTE_AT,
        authorize_canonical_plan,
        seed_paper_capacity,
    )
    from tests.support.postgres_persistence import phase7_plan_session_factory
    from tests.test_interactive_agent_foundation import _card
    from tests.test_phase8_canonical_paper_execution import _execute
    from tests.test_planned_reward_risk import terms

    def seed_nested_version(**values):
        # Real validated card at INSERT time; no immutable version edits.
        card = _card().model_dump(mode="json")
        card["strategy_name"] = "Recorded Nested short"
        card["entry_conditions"] = ["closed structural break", "controlled pullback confirmed"]
        return UserStrategyVersion(
            **{
                **values,
                "card": card,
                "pattern_spec": NestedContinuationSpec(
                    symbol="BTCUSDT", direction="short"
                ).model_dump(mode="json"),
            }
        )

    monkeypatch.setattr("tests.support.phase7_postgres.UserStrategyVersion", seed_nested_version)
    monkeypatch.setattr("tests.support.phase7_postgres._HASH", SETUP_CONTENT_HASH)
    factory = phase7_plan_session_factory()
    world = postgres_plan_world(factory)
    # Reproduce pre-policy authorization/execution at insertion, without rewriting history.
    with monkeypatch.context() as old_release:
        for module in ("canonical_trade_plan", "planned_reward_risk"):
            old_release.setattr(f"app.services.{module}.planned_reward_risk", lambda _terms: None)
        old_release.setattr(
            "app.services.execution_claim.execution_reward_risk", lambda _terms: None
        )
        envelope = world.plans.create(
            plan_command(
                world,
                terms=terms(entry="85111.40", stop="85720.80", targets=("84714.10",)),
            )
        )
        with factory() as session:
            authorization = authorize_canonical_plan(session, envelope, plans=world.plans)
            seed_paper_capacity(session, envelope)
            session.commit()
        result, session, service, _runtime = _execute(
            factory, envelope, authorization, key="historical-nested-qualification"
        )
        try:
            assert result.outcome.value == "ALLOW"
            service.apply_paper_plan_fill(
                command_id=result.command_id,
                fill_quantity=Decimal("1"),
                fill_price=Decimal("85111.30"),
                source_identity="historical-qualification-fill",
                occurred_at=EXECUTE_AT,
            )
            session.commit()
        finally:
            session.close()
    with factory() as session:
        plan = envelope.plan
        strategy_id = session.get(CompiledSetupDefinition, plan.setup_definition_id).strategy_id
        session.add(
            Membership(
                organization_id=plan.organization_id,
                user_id=plan.user_id,
                role=MembershipRole.OWNER,
            )
        )
        recorded = BrainSetupRow(
            id=uuid4(),
            organization_id=plan.organization_id,
            strategy_id=strategy_id,
            strategy_version_id=plan.strategy_version_id,
            symbol="BTCUSDT",
            state="TRADE_CANDIDATE",
            observed_at=plan.created_at,
            expires_at=plan.valid_until,
            candidate_id=plan.candidate_id,
            assessment_id=envelope.lineage.assessment_id,
            payload={
                "stage": "MUTABLE_SETUP_NOT_HISTORICAL_PROOF",
                "strategy_version_id": str(plan.strategy_version_id),
            },
        )
        current = BrainSetupRow(
            id=uuid4(),
            organization_id=plan.organization_id,
            strategy_id=strategy_id,
            strategy_version_id=plan.strategy_version_id,
            symbol="BTCUSDT",
            state="FORMING",
            observed_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            payload={
                "stage": "CURRENT_FORMING_SETUP",
                "strategy_version_id": str(plan.strategy_version_id),
                "instrument": "BTCUSDT",
                "direction": "short",
                "timeframe": "15m",
                "reason_codes": ["forming"],
            },
        )
        session.add_all([recorded, current])
        session.flush()
        decision = BrainSetupEventRow(
            id=uuid4(),
            organization_id=plan.organization_id,
            setup_id=recorded.id,
            kind="paper_trade_opened",
            occurred_at=plan.created_at,
            payload={
                "candidate_id": str(plan.candidate_id),
                "assessment_id": str(envelope.lineage.assessment_id),
                "trade_plan_revision_id": str(plan.revision_id),
                "state": "CONFIRMED",
                "stage": "closed_continuation",
                "direction": "short",
                "timeframe": "15m",
                "reason_codes": ["closed_structural_break", "controlled_pullback_confirmed"],
                "rule_results": ["closed_structural_break", "controlled_pullback_confirmed"],
                "anchor_index": 2,
                "impulse_index": 5,
                "pullback_index": 8,
                "confirmed_index": 11,
                "event_index": 11,
                "quality_components": {"retracement": "0.4"},
                "bar_references": ["a" * 64, "b" * 64],
            },
        )
        session.add(decision)
        trade = session.scalars(select(JournalTrade)).one()
        from tests.test_interactive_agent_foundation import _add_chunk

        _add_chunk(
            session,
            organization_id=plan.organization_id,
            user_id=plan.user_id,
            title="Proposed playbook risk guidance",
            content="Nested BTC short minimum reward to risk 0.5:1: DOCUMENT_IS_NOT_POLICY",
        )
        identities = (trade.id, decision.id, current.id)
        session.commit()
    return factory, envelope, identities


class CaptureResponder:
    def __init__(self):
        self.contexts = []

    def compose(self, **kwargs):
        self.contexts.append(kwargs["factual_context"])
        # Deliberately omit policy/candle prose: deterministic material facts must survive.
        return "The stored conditions are available in Stored evidence."


def _agent(session, responder):
    from app.interactive_agent.service import InteractiveAgentService
    from tests.support.phase8_runtime import phase8_settings

    return InteractiveAgentService(session, settings=phase8_settings(), responder=responder)


@requires_postgres
def test_exact_question_followup_and_current_setup_use_distinct_authorities(recorded_nested):
    factory, envelope, (trade_id, decision_id, current_id) = recorded_nested
    responder = CaptureResponder()
    with factory() as session:
        agent = _agent(session, responder)
        scope = {"organization_id": envelope.plan.organization_id, "user_id": envelope.plan.user_id}
        first = agent.handle_turn(AgentTurnRequest(message=QUESTION), **scope)
        second = agent.handle_turn(
            AgentTurnRequest(
                message=FOLLOWUP,
                conversation_id=first.conversation_id,
            ),
            **scope,
        )
        for result, facts in zip((first, second), responder.contexts, strict=True):
            assert str(trade_id) in {ref.record_id for ref in result.connections}
            assert str(decision_id) in {ref.record_id for ref in result.connections}
            assert str(current_id) not in {ref.record_id for ref in result.connections}
            assert "CURRENT_FORMING_SETUP" not in facts
            assert "MUTABLE_SETUP_NOT_HISTORICAL_PROOF" not in facts
            assert "closed_structural_break" in facts[:16000]
            assert "controlled_pullback_confirmed" in facts[:16000]
            assert "pullback_index" in facts and "quality_components" in facts
            assert "Assessment summary" in facts and "TradePlan" in facts
            assert "bar_references" in facts and "stored candle hashes only" in facts
            assert "app.services.planned_reward_risk" in facts
            assert "DOCUMENT_IS_NOT_POLICY" not in facts
            assert "planned-gross-weighted-rr/v1" in facts
            assert "minimum_gross_allocation_weighted_R=1" in facts
            lead = result.reply.split("\n\nRecorded facts", 1)[0]
            assert "0.65R" in lead and "fails that minimum" in lead and "1:1" in lead
            assert "current eligibility" in lead and "historical authorization" in lead
            assert "historical candle OHLCV values unavailable" in lead
            assert not result.execution_attempted and not result.authority_mutated
            assert not result.knowledge and not result.proposals
        current = agent.handle_turn(
            AgentTurnRequest(
                message=CURRENT,
                conversation_id=first.conversation_id,
            ),
            **scope,
        )
        assert "CURRENT_FORMING_SETUP" in responder.contexts[-1]
        assert str(current_id) in {ref.record_id for ref in current.connections}
        assert str(trade_id) not in {ref.record_id for ref in current.connections}
        assert "minimum_gross_allocation_weighted_R" not in responder.contexts[-1]


@requires_postgres
def test_plan_followup_without_a_selected_trade_does_not_guess_a_current_setup(recorded_nested):
    factory, envelope, _ = recorded_nested
    responder = CaptureResponder()
    with factory() as session:
        result = _agent(session, responder).handle_turn(
            AgentTurnRequest(message=FOLLOWUP),
            organization_id=envelope.plan.organization_id,
            user_id=envelope.plan.user_id,
        )
        assert "Which trade do you mean?" in result.reply
        assert not result.connections and not responder.contexts


@requires_postgres
def test_immutable_decision_remains_readable_after_mutable_setup_identity_changes(recorded_nested):
    from uuid import uuid4

    from sqlalchemy import select

    from app.db.strategy_brain import BrainSetupRow
    from app.interactive_agent.actions import RecordedTradeInput
    from app.interactive_agent.recorded_trade import read_recorded_trade

    factory, envelope, (trade_id, decision_id, _current_id) = recorded_nested
    with factory() as session:
        row = session.scalars(
            select(BrainSetupRow).where(
                BrainSetupRow.candidate_id == envelope.plan.candidate_id,
            )
        ).one()
        row.candidate_id = uuid4()
        row.assessment_id = uuid4()
        row.state = "COMPLETED"
        session.flush()  # Mutable projection changes do not rewrite the decision.
        result = read_recorded_trade(
            session,
            RecordedTradeInput(journal_trade_id=trade_id),
            organization_id=envelope.plan.organization_id,
            user_id=envelope.plan.user_id,
        )
        assert str(decision_id) in {ref.record_id for ref in result.connections}
        assert "closed_structural_break" in result.recorded_evidence
        assert "MUTABLE_SETUP_NOT_HISTORICAL_PROOF" not in result.recorded_evidence


@requires_postgres
def test_current_minimum_and_source_version_are_read_from_application_authority(
    recorded_nested, monkeypatch
):
    from fractions import Fraction

    from app.interactive_agent.actions import RecordedTradeInput
    from app.interactive_agent.recorded_trade import read_recorded_trade
    from app.services import planned_reward_risk as policy

    factory, envelope, (trade_id, *_rest) = recorded_nested
    monkeypatch.setattr(policy, "MINIMUM_REWARD_RISK", Fraction(2))
    monkeypatch.setattr(policy, "POLICY_VERSION", "test-current-authority/v2")
    with factory() as session:
        result = read_recorded_trade(
            session,
            RecordedTradeInput(journal_trade_id=trade_id),
            organization_id=envelope.plan.organization_id,
            user_id=envelope.plan.user_id,
        )
        assert "of at least 2:1" in result.reply
        assert "minimum_gross_allocation_weighted_R=2" in result.recorded_evidence
        assert "test-current-authority/v2" in {ref.record_id for ref in result.connections}
        assert "DOCUMENT_IS_NOT_POLICY" not in result.recorded_evidence
