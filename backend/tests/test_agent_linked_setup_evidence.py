"""Fresh read-only linked setup/assessment retrieval and truthful evidence gaps."""

from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.learning_attribution import LearningAttributionRecordRow
from app.db.models import CompiledSetupDefinition, JournalTrade, Membership, User, UserStrategy
from app.db.strategy_brain import BrainSetupEventRow, BrainSetupRow
from app.interactive_agent.contracts import AgentTurnRequest
from app.interactive_agent.conversation import compose_visible_reply
from app.interactive_agent.service import InteractiveAgentService
from app.schemas.common import MembershipRole
from tests.support.phase6_fusion import SETUP_CONTENT_HASH
from tests.support.phase8_runtime import phase8_settings
from tests.support.postgres_persistence import requires_postgres
from tests.test_agent_recorded_trade import _read
from tests.test_journal_plan_targets import historical as historical

pytestmark = requires_postgres


@pytest.fixture(autouse=True)
def consistent_compiled_seed(monkeypatch):
    # Seed consistent evidence at INSERT time; append-only protection stays active.
    monkeypatch.setattr("tests.support.phase7_postgres._HASH", SETUP_CONTENT_HASH)


def _observation(session, envelope, *, revision_id=None):
    plan = envelope.plan
    compiled = session.get(CompiledSetupDefinition, plan.setup_definition_id)
    strategy_id = compiled.strategy_id
    row = BrainSetupRow(
        id=uuid4(),
        organization_id=plan.organization_id,
        strategy_id=strategy_id,
        strategy_version_id=plan.strategy_version_id,
        symbol=plan.execution_instrument,
        state="TRADE_CANDIDATE",
        observed_at=plan.created_at,
        expires_at=plan.valid_until,
        candidate_id=plan.candidate_id,
        assessment_id=envelope.lineage.assessment_id,
        payload={"rule_results": ["CURRENT_PROJECTION_IS_NOT_HISTORICAL_PROOF"]},
    )
    session.add(row)
    session.flush()
    event = BrainSetupEventRow(
        id=uuid4(),
        organization_id=plan.organization_id,
        setup_id=row.id,
        kind="paper_decision",
        occurred_at=plan.created_at,
        payload={
            "candidate_id": str(plan.candidate_id),
            "assessment_id": str(envelope.lineage.assessment_id),
            "trade_plan_revision_id": str(revision_id or plan.revision_id),
            "state": "CONFIRMED",
            "rule_results": ["STORED_NESTED_CONFIRMATION"],
            "bar_references": ["a" * 64],
        },
    )
    session.add(event)
    session.flush()
    return row, event


def test_scoped_setup_and_assessment_summary_reach_agent_facts_with_sources(historical):
    factory, envelope, *_ = historical
    with factory() as session:
        _row, event = _observation(session, envelope)
        trade = session.scalars(select(JournalTrade)).one()
        result = _read(session, trade, latest=True)
        refs = {item.title: item.record_id for item in result.connections}
        assert refs["Compiled setup"] == str(envelope.plan.setup_definition_id)
        assert refs["Setup observation"] == str(event.id)
        assert "Assessment summary" in refs
        assert "STORED_NESTED_CONFIRMATION" in result.recorded_evidence
        assert "CURRENT_PROJECTION_IS_NOT_HISTORICAL_PROOF" not in result.recorded_evidence
        assert "assessment_state" in result.recorded_evidence
        assert "full rule snapshot" in result.recorded_evidence
        assert "temporarily unreadable" not in result.reply

        contexts = []

        class Responder:
            def compose(self, **kwargs):
                contexts.append(kwargs["factual_context"])
                return "Stored setup and assessment summaries are reference evidence."

        session.add(
            Membership(
                organization_id=trade.organization_id,
                user_id=trade.user_id,
                role=MembershipRole.OWNER,
            )
        )
        session.commit()
        agent = InteractiveAgentService(session, settings=phase8_settings(), responder=Responder())
        first = agent.handle_turn(
            AgentTurnRequest(
                message=(
                    "Explain my latest BTCUSDT short paper trade: strategy, entry, stop, "
                    "target, authorization and execution venue."
                )
            ),
            organization_id=trade.organization_id,
            user_id=trade.user_id,
        )
        agent.handle_turn(
            AgentTurnRequest(message="Explain that trade", conversation_id=first.conversation_id),
            organization_id=trade.organization_id,
            user_id=trade.user_id,
        )
        assert len(contexts) == 2
        for facts in contexts:
            assert "STORED_NESTED_CONFIRMATION" in facts[:16000]
            assert "Assessment summary" in facts[:16000]
            assert "Historical planned gross" in facts[:16000]
            assert "CURRENT_PROJECTION_IS_NOT_HISTORICAL_PROOF" not in facts


def test_absent_scoped_records_are_distinct_from_unreadable_store(historical, monkeypatch):
    factory, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        absent = _read(session, trade, latest=True)
        assert "detector setup observation absent from authenticated owner scope" in absent.reply
        original = session.scalar

        def unreadable(statement, *args, **kwargs):
            if statement.column_descriptions[0].get("entity") is CompiledSetupDefinition:
                raise SQLAlchemyError("PRIVATE_DATABASE_ERROR_DETAILS")
            return original(statement, *args, **kwargs)

        monkeypatch.setattr(session, "scalar", unreadable)
        result = _read(session, trade, latest=True)
        assert (
            "compiled setup evidence temporarily unreadable; existence is unknown" in result.reply
        )
        assert "compiled setup record absent" not in result.reply
        assert "PRIVATE_DATABASE_ERROR_DETAILS" not in result.recorded_evidence
        assert "Assessment summary" in {item.title for item in result.connections}


def test_setup_owner_and_exact_plan_version_cannot_be_bypassed(historical):
    factory, envelope, *_ = historical
    with factory() as session:
        row, event = _observation(session, envelope)
        trade = session.scalars(select(JournalTrade)).one()
        other = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="fixture")
        session.add(other)
        session.flush()
        session.get(UserStrategy, row.strategy_id).user_id = other.id
        session.flush()
        result = _read(session, trade, latest=True)
        assert str(event.id) not in {item.record_id for item in result.connections}
        assert "STORED_NESTED_CONFIRMATION" not in result.recorded_evidence
        assert "absent from authenticated owner scope" in result.reply


def test_current_setup_without_an_exact_immutable_decision_is_not_historical_proof(historical):
    factory, envelope, *_ = historical
    with factory() as session:
        row, event = _observation(session, envelope, revision_id=uuid4())
        trade = session.scalars(select(JournalTrade)).one()
        result = _read(session, trade, latest=True)
        assert "immutable setup decision for this plan absent" in result.reply
        assert "CURRENT_PROJECTION_IS_NOT_HISTORICAL_PROOF" not in result.recorded_evidence
        assert str(event.id) not in {item.record_id for item in result.connections}
        assert row.state == "TRADE_CANDIDATE"


def test_corrupt_assessment_snapshot_is_reported_without_using_its_claims(historical):
    factory, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        row = session.scalars(select(LearningAttributionRecordRow)).one()
        payload = deepcopy(row.facts_payload)
        payload["setup_quality"]["reason_codes"] = ["FORGED_PRIVATE_CLAIM"]
        row.facts_payload = payload  # Read under no_autoflush; roll back this test view.
        result = _read(session, trade, latest=True)
        assert "stored assessment summary integrity mismatch" in result.reply
        assert "FORGED_PRIVATE_CLAIM" not in result.recorded_evidence
        session.rollback()


def test_specific_missing_warnings_remain_once_without_a_duplicate_generic_warning(historical):
    factory, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        result = _read(session, trade, latest=True)
        visible = compose_visible_reply(
            result.reply, result.recorded_evidence, required_warnings=result.warnings
        )
        lead = visible.split("\n\nRecorded facts (not a confirmation):", 1)[0]
        assert lead.count("Missing evidence:") == 1
        assert "Stored evidence is unavailable or incomplete" not in lead
        assert "detector setup observation absent" in lead


def test_mismatching_compiled_source_is_reported_and_not_cited(historical):
    factory, envelope, *_ = historical
    with factory() as session:
        compiled = session.get(CompiledSetupDefinition, envelope.plan.setup_definition_id)
        trade = session.scalars(select(JournalTrade)).one()
        compiled.content_hash = "c" * 64  # Corrupt read view only; no autoflush or DB mutation.
        result = _read(session, trade, latest=True)
        assert "compiled setup content conflicts with the approved plan" in result.reply
        assert "Compiled setup" not in {item.title for item in result.connections}
