"""Helpers to apply guardrail verdicts to LangGraph state patches."""

from __future__ import annotations

from app.agents.runtime import AgentRuntime
from app.guardrails.types import GuardrailResult
from app.schemas.agent import AgentState
from app.schemas.common import SafetyVerdict


def merge_safety_verdict(current: SafetyVerdict | None, result: GuardrailResult) -> SafetyVerdict:
    """Combine existing graph verdict with a new guardrail result."""
    new = result.to_safety_verdict()
    if current is SafetyVerdict.BLOCK or new is SafetyVerdict.BLOCK:
        return SafetyVerdict.BLOCK
    if current is SafetyVerdict.FLAG or new is SafetyVerdict.FLAG:
        return SafetyVerdict.FLAG
    return SafetyVerdict.PASS


def build_guardrail_updates(
    agent: AgentState,
    result: GuardrailResult,
    runtime: AgentRuntime,
    *,
    audit_reason: str,
    set_final_answer_on_block: bool = True,
) -> dict:
    """Build a state patch from a guardrail verdict with observability emission."""
    verdict = merge_safety_verdict(agent.safety_verdict, result)
    updates: dict = {"safety_verdict": verdict}
    if result.blocked and set_final_answer_on_block and result.safe_message:
        updates["final_answer"] = result.safe_message

    audit_events = list(agent.audit_events)
    if result.audit_required and (result.blocked or result.triggered_rules):
        if result.blocked:
            audit_events.append(
                runtime.observability.emit_guardrail_blocked(agent, result, reason=audit_reason)
            )
        else:
            audit_events.append(
                runtime.observability.emit_guardrail_warned(agent, result, reason=audit_reason)
            )
        updates["audit_events"] = audit_events
    return updates
