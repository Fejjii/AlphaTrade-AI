"""Projection targets are facts, never protection or filled exits."""

from copy import deepcopy
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import ConversationMessage, JournalTrade
from app.interactive_agent.actions import RecordedTradeInput
from app.interactive_agent.contracts import AgentTurnRequest
from app.interactive_agent.recorded_trade import (
    _Evidence,
    _journal_target_evidence,
    read_recorded_trade,
)
from app.interactive_agent.service import InteractiveAgentService
from app.services.audit_service import AuditService
from app.services.canonical_execution_journal import journal_planned_targets
from app.services.journal_lifecycle_projector import JournalLifecycleProjector
from tests import test_agent_historical_setup_routing as historical_setup
from tests import test_journal_plan_targets as target_tests
from tests.support.phase8_runtime import phase8_settings
from tests.support.postgres_persistence import requires_postgres


@pytest.fixture
def historical(monkeypatch):
    return target_tests.historical.__wrapped__(monkeypatch)


@pytest.fixture
def recorded_nested(monkeypatch):
    return historical_setup.recorded_nested.__wrapped__(monkeypatch)


def _read(session, trade):
    return read_recorded_trade(
        session,
        RecordedTradeInput(journal_trade_id=trade.id),
        organization_id=trade.organization_id,
        user_id=trade.user_id,
    )


@requires_postgres
def test_audited_repaired_targets_confirm_match_without_writing_history(historical):
    factory, envelope, _authorization, _result, scope, snapshot = historical
    with factory() as session:
        JournalLifecycleProjector(session, AuditService(session)).repair_planned_targets(
            **scope, dry_run=False
        )
        session.commit()
        trade = session.scalars(select(JournalTrade)).one()
        before = deepcopy(trade.planned_targets)
        result = _read(session, trade)
        assert "Journal target comparison: match" in result.recorded_evidence
        for target in envelope.plan.risk_and_exits.targets:
            assert f"TP{target.order}: price {target.price.value}" in result.recorded_evidence
            assert (
                f"allocation {Decimal(str(float(target.quantity_fraction)))}"
                in result.recorded_evidence
            )
        assert "match the linked immutable plan" in result.reply
        assert "not verified protection or exit fills" in result.reply
        assert not any(
            "Journal targets are empty" in warning or "Journal targets differ" in warning
            for warning in result.warnings
        )
        assert trade.planned_targets == before
        assert target_tests._snapshot(session) == snapshot
        assert any(
            ref.title == "Journal" and ref.record_id == str(trade.id) for ref in result.connections
        )
        assert any(
            ref.title == "TradePlan" and ref.record_id == str(envelope.plan.revision_id)
            for ref in result.connections
        )


@requires_postgres
def test_numeric_representation_differences_do_not_claim_a_projection_mismatch(historical):
    factory, envelope, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        targets = journal_planned_targets(envelope.plan)
        trade.planned_targets = [
            {**t, "price": f"{Decimal(t['price']):.8f}", "size_fraction": str(t["size_fraction"])}
            for t in targets
        ]
        session.flush()
        result = _read(session, trade)
        assert "Journal target comparison: match" in result.recorded_evidence
        assert "Journal targets differ" not in result.recorded_evidence


@requires_postgres
def test_missing_journal_targets_preserves_projection_warning_and_plan_source(historical):
    factory, envelope, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        result = _read(session, trade)
        assert "Journal planned targets in stored order: none recorded" in result.recorded_evidence
        assert "Journal target comparison: missing" in result.recorded_evidence
        assert "Journal targets are empty" in result.reply
        assert "Journal targets are empty" in " ".join(result.warnings)
        assert "match the linked immutable plan" not in result.reply
        assert trade.planned_targets == []
        assert str(envelope.plan.risk_and_exits.targets[0].price.value) in result.recorded_evidence


@requires_postgres
@pytest.mark.parametrize("difference", ["price", "allocation", "order", "label"])
def test_mismatched_projection_exposes_its_values_and_preserves_warning(historical, difference):
    factory, envelope, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        targets = journal_planned_targets(envelope.plan)
        if difference == "price":
            targets[0]["price"] = "123.45"
        elif difference == "allocation":
            targets[0]["size_fraction"] = 0.123
        elif difference == "label":
            targets[0]["label"] = "changed"
        else:
            assert len(targets) > 1
            targets.reverse()
        trade.planned_targets = targets
        session.flush()
        result = _read(session, trade)
        assert "Journal target comparison: mismatch" in result.recorded_evidence
        assert "Journal targets differ" in " ".join(result.warnings)
        assert "match the linked immutable plan" not in result.reply
        assert "planned targets are not filled exits" in " ".join(result.warnings)
        if difference == "price":
            assert "TP1: price 123.45" in result.recorded_evidence
        if difference == "allocation":
            assert "allocation 0.123" in result.recorded_evidence
        assert trade.planned_targets == targets


@requires_postgres
def test_no_linked_plan_leaves_journal_values_visible_but_comparison_unverified(historical):
    factory, envelope, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        trade.planned_targets = journal_planned_targets(envelope.plan)
        trade.trade_plan_revision_id = None
        session.flush()
        result = _read(session, trade)
        assert "Journal planned targets in stored order: TP1: price" in result.recorded_evidence
        assert "Journal target comparison: unverified" in result.recorded_evidence
        assert "match the linked immutable plan" not in result.reply


def test_target_display_is_bounded_and_comparison_includes_hidden_targets():
    evidence = _Evidence()
    raw = [{"price": str(100 + i), "size_fraction": 0.01, "label": f"TP{i + 1}"} for i in range(11)]
    detail, normalized = _journal_target_evidence(raw, evidence)
    assert "TP10: price 109" in detail and "TP11" not in detail
    assert "1 additional Journal targets not displayed" in detail
    assert normalized is not None and len(normalized) == 11
    assert normalized[-1].price == Decimal("110")
    _, excessive = _journal_target_evidence(raw * 10, evidence)
    assert excessive is None and evidence.missing


@pytest.mark.parametrize(
    "target",
    [
        {"price": "1", "label": "missing allocation"},
        {"price": "NaN", "size_fraction": 1},
        {"price": "1e99999", "size_fraction": 1},
        {"price": "-1", "size_fraction": 1},
        {"price": "1", "size_fraction": True},
        {"price": "1", "size_fraction": 2},
    ],
)
def test_unreadable_terms_are_reported_without_defaulting_allocation(target):
    evidence = _Evidence()
    detail, normalized = _journal_target_evidence([target], evidence)
    assert normalized is None and evidence.missing
    assert "unreadable price or allocation" in detail


@requires_postgres
def test_known_historical_short_match_reaches_agent_and_followup(recorded_nested):
    factory, _envelope, (trade_id, *_rest) = recorded_nested
    responder = historical_setup.CaptureResponder()
    with factory() as session:
        trade = session.get(JournalTrade, trade_id)
        assert trade.planned_targets == [
            {"price": "84714.10", "size_fraction": 1.0, "label": "TP1"}
        ]
        before = deepcopy(trade.planned_targets)
        agent = InteractiveAgentService(session, settings=phase8_settings(), responder=responder)
        first = agent.handle_turn(
            AgentTurnRequest(message=historical_setup.QUESTION),
            organization_id=trade.organization_id,
            user_id=trade.user_id,
        )
        second = agent.handle_turn(
            AgentTurnRequest(
                message="Explain that trade and its planned target evidence.",
                conversation_id=first.conversation_id,
            ),
            organization_id=trade.organization_id,
            user_id=trade.user_id,
        )
        for context, turn in zip(responder.contexts, (first, second), strict=True):
            assert "TP1: price 84714.10, allocation 1.0" in context
            assert "Journal target comparison: match" in context
            assert turn.recorded_evidence == context
            payload = session.get(ConversationMessage, turn.assistant_message_id).payload[
                "interactive_agent"
            ]
            assert payload["recorded_evidence"] == context
            assert any(ref["title"] == "Journal" for ref in payload["sources"])
            assert any(ref["title"] == "TradePlan" for ref in payload["sources"])
            assert "match the linked immutable plan" in turn.reply
            assert "not verified protection or exit fills" in turn.reply
            assert "fails that minimum" in turn.reply
            assert not turn.authority_mutated and not turn.execution_attempted
        assert trade.planned_targets == before


@requires_postgres
def test_incomplete_allocation_keeps_discrepancy_warning_and_unverified_comparison(historical):
    factory, *_ = historical
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        trade.planned_targets = [{"price": "99999", "quantity_fraction": "1"}]
        session.flush()
        result = _read(session, trade)
        assert "Journal targets differ" in result.recorded_evidence
        assert "Journal target comparison is unverified" in result.reply
        assert "complete target agreement is unverified" in " ".join(result.warnings)
        assert "Journal targets differ" in " ".join(result.warnings)
        assert "match the linked immutable plan" not in result.reply
