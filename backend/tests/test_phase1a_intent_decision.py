"""Phase 1A slice 2 — IntentDecision + exact action routing."""

from __future__ import annotations

import uuid

from app.agents.intent_classifier import classify_intent_decision, classify_message_class
from app.agents.runtime import AgentRuntime
from app.core.config import Settings
from app.core.operation_policy import can_issue_authorization
from app.schemas.agent import Intent, MessageClass, OperationClass, RequestedAction
from app.services.agent_service import AgentInvokeContext, AgentService
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService
from app.strategies.registry import build_default_registry
from app.tools.registry import build_default_registry as build_tools

ORG = uuid.UUID("00000000-0000-0000-0000-000000000002")
USER = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _ctx() -> AgentInvokeContext:
    return AgentInvokeContext(request_id="phase1a-intent", user_id=USER, organization_id=ORG)


def _service() -> AgentService:
    settings = Settings(execution_mode="paper", enable_real_trading=False, log_json=False)
    runtime = AgentRuntime(
        settings=settings,
        risk_service=RiskService(),
        strategy_service=StrategyService(registry=build_default_registry()),
        tool_registry=build_tools(settings),
    )
    return AgentService(runtime=runtime)


def test_analyze_btc_15m_is_read_only_with_zero_proposal_mutation() -> None:
    decision = classify_intent_decision("Analyze BTC 15m", organization_id=ORG, user_id=USER)
    assert decision.intent is Intent.MARKET_ANALYSIS
    assert decision.operation_class is OperationClass.READ_ONLY
    assert decision.requires_clarification is False
    response = _service().run("Analyze BTC 15m", _ctx(), symbol="BTCUSDT", timeframe="15m")
    assert response.proposal_id is None
    assert response.approval_id is None
    paper = [o for o in response.tool_outputs if o.tool_name == "paper_execution" and o.success]
    assert paper == []


def test_pattern_match_question_is_setup_analysis_read_only() -> None:
    decision = classify_intent_decision(
        "Does BTC match my pattern?", organization_id=ORG, user_id=USER
    )
    assert decision.intent is Intent.SETUP_ANALYSIS
    assert decision.operation_class is OperationClass.READ_ONLY
    response = _service().run("Does BTC match my pattern?", _ctx(), symbol="BTCUSDT")
    assert response.proposal_id is None


def test_build_a_paper_plan_is_plan_only() -> None:
    decision = classify_intent_decision("Build a paper plan", organization_id=ORG, user_id=USER)
    assert decision.intent is Intent.PLAN_TRADE
    assert decision.operation_class is OperationClass.PLAN
    assert decision.requested_action is RequestedAction.CREATE_PLAN
    assert can_issue_authorization(decision) is False


def test_approve_plan_is_approval_only() -> None:
    decision = classify_intent_decision(
        "Approve plan 123 revision 4", organization_id=ORG, user_id=USER
    )
    assert decision.intent is Intent.APPROVE
    assert decision.operation_class is OperationClass.APPROVAL
    assert decision.requested_action is RequestedAction.APPROVE
    assert can_issue_authorization(decision) is True
    response = _service().run("Approve plan 123 revision 4", _ctx())
    paper = [o for o in response.tool_outputs if o.tool_name == "paper_execution" and o.success]
    assert paper == []


def test_reject_cannot_authorize() -> None:
    decision = classify_intent_decision(
        "Reject plan 123 revision 4", organization_id=ORG, user_id=USER
    )
    assert decision.intent is Intent.REJECT
    assert decision.operation_class is OperationClass.APPROVAL
    assert decision.requested_action is RequestedAction.REJECT
    assert can_issue_authorization(decision) is False


def test_skip_cannot_authorize() -> None:
    decision = classify_intent_decision("Skip this candidate", organization_id=ORG, user_id=USER)
    assert decision.intent is Intent.SKIP
    assert decision.requested_action is RequestedAction.SKIP
    assert can_issue_authorization(decision) is False


def test_approval_cannot_execute() -> None:
    decision = classify_intent_decision("Approve plan abc", organization_id=ORG, user_id=USER)
    assert decision.operation_class is not OperationClass.EXECUTION
    assert decision.intent is not Intent.EXECUTE_PAPER_PLAN


def test_analysis_cannot_infer_execute_paper_plan() -> None:
    for message in (
        "Analyze BTC 15m",
        "analyze btc and execute",
        "Please analyze BTC pullback setup on 4h",
        "[TEST_EXECUTE] paper execute btc",
    ):
        decision = classify_intent_decision(message, organization_id=ORG, user_id=USER)
        assert decision.intent is not Intent.EXECUTE_PAPER_PLAN
        assert decision.operation_class is not OperationClass.EXECUTION


def test_explicit_execute_paper_plan_is_execution() -> None:
    decision = classify_intent_decision(
        "Execute approved paper plan 11111111-1111-1111-1111-111111111111 revision 4",
        organization_id=ORG,
        user_id=USER,
    )
    assert decision.intent is Intent.EXECUTE_PAPER_PLAN
    assert decision.operation_class is OperationClass.EXECUTION
    assert decision.requested_action is RequestedAction.EXECUTE_PAPER_PLAN


def test_ambiguous_mutation_wording_clarifies() -> None:
    decision = classify_intent_decision("Close it", organization_id=ORG, user_id=USER)
    assert decision.operation_class is OperationClass.READ_ONLY
    assert decision.requires_clarification is True
    assert "ambiguous_mutation_missing_target" in decision.ambiguity_reasons


def test_message_class_never_emits_command() -> None:
    for message in ("execute now", "do it", "analyze btc", "approve plan"):
        assert classify_message_class(message) is not MessageClass.COMMAND
