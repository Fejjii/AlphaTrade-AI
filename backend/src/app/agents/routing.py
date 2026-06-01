"""Conditional routing for the LangGraph agent workflow."""

from __future__ import annotations

from typing import Literal

from app.agents.state_utils import parse_state
from app.schemas.agent import Intent, MessageClass
from app.schemas.common import RiskAction, SafetyVerdict

RouteAfterInjection = Literal["blocked", "continue"]
RouteAfterModeration = Literal["blocked", "continue"]
RouteAfterIntent = Literal["trading_analysis", "general"]
RouteAfterRisk = Literal["blocked", "approval", "tools", "respond"]
RouteAfterApproval = Literal["tools", "respond"]


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
    trading_intents = {
        Intent.MONITOR,
        Intent.PLAN_TRADE,
        Intent.EXECUTE,
    }
    trading_classes = {MessageClass.ANALYSIS_REQUEST, MessageClass.COMMAND}
    if agent.intent in trading_intents or agent.message_class in trading_classes:
        return "trading_analysis"
    return "general"


def route_after_risk(state: dict) -> RouteAfterRisk:
    agent = parse_state(state)
    if agent.safety_verdict is SafetyVerdict.BLOCK:
        return "blocked"
    if agent.risk_result and agent.risk_result.action is RiskAction.BLOCK:
        return "blocked"
    if agent.trade_proposal is not None:
        return "approval"
    if (
        agent.intent is Intent.EXECUTE
        and agent.risk_result
        and agent.risk_result.action is RiskAction.ALLOW
    ):
        return "tools"
    return "respond"


def route_after_approval(state: dict) -> RouteAfterApproval:
    agent = parse_state(state)
    if (
        agent.intent is Intent.EXECUTE
        and not agent.approval_required
        and agent.risk_result
        and agent.risk_result.action is not RiskAction.BLOCK
    ):
        return "tools"
    if agent.intent is Intent.EXECUTE and agent.approval_required:
        return "respond"
    return "respond"
