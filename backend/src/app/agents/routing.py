"""Conditional routing for the LangGraph agent workflow."""

from __future__ import annotations

from typing import Literal

from app.agents.analytics_intent import is_analytics_message
from app.agents.state_utils import parse_state
from app.agents.strategy_intent import is_strategy_workflow_intent
from app.schemas.agent import Intent, MessageClass, OperationClass
from app.schemas.common import RiskAction, SafetyVerdict

RouteAfterInjection = Literal["blocked", "continue"]
RouteAfterModeration = Literal["blocked", "continue"]
RouteAfterIntent = Literal["trading_analysis", "analytics", "strategy_workflow", "general"]
RouteAfterRisk = Literal["blocked", "approval", "tools", "respond"]
RouteAfterApproval = Literal["tools", "respond"]

_TRADING_ANALYSIS_INTENTS = {
    Intent.MARKET_ANALYSIS,
    Intent.SETUP_ANALYSIS,
    Intent.PLAN_TRADE,
    Intent.EXECUTE_PAPER_PLAN,
    Intent.MONITOR,
}


def route_after_injection(state: dict) -> RouteAfterInjection:
    agent = parse_state(state)
    if agent.safety_verdict is SafetyVerdict.BLOCK:
        return "blocked"
    return "continue"


def route_after_moderation(state: dict) -> RouteAfterModeration:
    agent = parse_state(state)
    if agent.safety_verdict is SafetyVerdict.BLOCK:
        return "blocked"
    return "continue"


def route_after_intent(state: dict) -> RouteAfterIntent:
    agent = parse_state(state)
    if is_strategy_workflow_intent(agent.intent):
        return "strategy_workflow"
    if agent.intent in {Intent.REVIEW, Intent.REVIEW_TRADE} and is_analytics_message(agent.message):
        return "analytics"
    # MessageClass.COMMAND is tombstoned and must not influence routing.
    trading_classes = {MessageClass.ANALYSIS_REQUEST}
    if agent.intent in _TRADING_ANALYSIS_INTENTS or agent.message_class in trading_classes:
        return "trading_analysis"
    return "general"


def route_after_risk(state: dict) -> RouteAfterRisk:
    agent = parse_state(state)
    if agent.safety_verdict is SafetyVerdict.BLOCK:
        return "blocked"
    if agent.risk_result and agent.risk_result.action is RiskAction.BLOCK:
        return "blocked"
    decision = agent.intent_decision
    if decision is not None:
        if decision.operation_class is OperationClass.READ_ONLY:
            return "respond"
        if decision.operation_class is OperationClass.APPROVAL:
            return "respond"
        if decision.operation_class is OperationClass.EXECUTION:
            if decision.intent is Intent.EXECUTE_PAPER_PLAN:
                return "tools"
            return "respond"
        if decision.operation_class is OperationClass.PLAN and agent.trade_proposal is not None:
            return "approval"
    if agent.trade_proposal is not None:
        return "approval"
    return "respond"


def route_after_approval(state: dict) -> RouteAfterApproval:
    """APPROVE must not execute. Only explicit EXECUTE_PAPER_PLAN may reach tools."""
    agent = parse_state(state)
    if agent.intent in {Intent.APPROVE, Intent.REJECT, Intent.SKIP}:
        return "respond"
    if (
        agent.intent is Intent.EXECUTE_PAPER_PLAN
        and not agent.approval_required
        and agent.risk_result
        and agent.risk_result.action is not RiskAction.BLOCK
    ):
        return "tools"
    return "respond"
