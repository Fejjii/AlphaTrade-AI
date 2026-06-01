"""Structured observability emitters for agent, guardrail, risk, and tool flows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.agents.state_utils import dump_partial
from app.guardrails.redaction import redact_mapping
from app.guardrails.types import GuardrailResult, GuardrailSeverity
from app.observability.context import get_bound_identity, get_or_create_trace_id
from app.schemas.agent import AgentState
from app.schemas.audit import AuditEvent, AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    RiskAction,
)
from app.schemas.usage import UsageEventCreate
from app.services.audit_service import AuditService
from app.services.usage_service import UsageService

logger = structlog.get_logger("observability")


class ObservabilityEmitter:
    """Emit redacted audit, usage, and log events."""

    def __init__(
        self,
        audit_service: AuditService,
        usage_service: UsageService,
    ) -> None:
        self._audit = audit_service
        self._usage = usage_service

    def _base_fields(self, agent: AgentState) -> dict[str, Any]:
        user_id, org_id = get_bound_identity()
        return {
            "request_id": agent.request_id,
            "trace_id": get_or_create_trace_id(),
            "user_id": str(agent.user_id) if agent.user_id else user_id,
            "organization_id": str(agent.organization_id) if agent.organization_id else org_id,
        }

    def _log(self, message: str, **fields: Any) -> None:
        redacted = redact_mapping({k: v for k, v in fields.items() if v is not None})
        logger.info(message, **redacted)

    def _record(
        self,
        agent: AgentState,
        *,
        event_type: AuditEventType,
        resource_type: str,
        metadata: dict[str, Any],
        actor_type: ActorType = ActorType.SYSTEM,
        result: AuditResult = AuditResult.SUCCESS,
        severity: AuditSeverity = AuditSeverity.INFO,
        resource_id: str | None = None,
    ) -> dict:
        """Persist audit record, log, and return state patch for audit_events."""
        base = self._base_fields(agent)
        record = self._audit.record(
            AuditRecordCreate(
                request_id=agent.request_id,
                trace_id=base["trace_id"],
                user_id=agent.user_id,
                organization_id=agent.organization_id,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                actor_type=actor_type,
                result=result,
                severity=severity,
                metadata=metadata,
            )
        )
        self._log(
            event_type.value,
            audit_event_type=event_type.value,
            resource_type=resource_type,
            result=result.value,
            severity=severity.value,
            safety_verdict=agent.safety_verdict.value if agent.safety_verdict else None,
            risk_level=agent.risk_level.value if agent.risk_level else None,
            **{k: v for k, v in base.items() if k in {"request_id", "trace_id", "user_id"}},
            **redact_mapping(metadata),
        )
        legacy = AuditEvent(
            actor=actor_type.value,
            action=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=agent.request_id,
            trace_id=base["trace_id"],
            timestamp=record.timestamp if record else datetime.now(UTC),
            after=record.redacted_metadata if record else metadata,
            user_id=agent.user_id,
            organization_id=agent.organization_id,
        )
        return dump_partial(legacy)

    def append_audit(self, agent: AgentState, patch: dict) -> dict:
        return {**patch, "audit_events": [*agent.audit_events, patch.get("_audit_event")]}

    def emit_agent_run_started(self, agent: AgentState) -> None:
        self._log(
            "agent_run_started",
            endpoint="agent_chat",
            **self._base_fields(agent),
        )

    def emit_agent_run_completed(self, agent: AgentState, *, latency_ms: float | None) -> None:
        self._log(
            "agent_run_completed",
            endpoint="agent_chat",
            latency_ms=latency_ms,
            safety_verdict=agent.safety_verdict.value if agent.safety_verdict else None,
            fallback_used=any(o.used_fallback for o in agent.tool_outputs),
            **self._base_fields(agent),
        )

    def emit_guardrail_blocked(
        self, agent: AgentState, result: GuardrailResult, *, reason: str
    ) -> dict:
        severity = _map_guardrail_severity(result.severity)
        event = self._record(
            agent,
            event_type=AuditEventType.GUARDRAIL_BLOCK,
            resource_type="chat_message",
            metadata={"reason": reason, "rules": result.triggered_rules},
            result=AuditResult.BLOCKED,
            severity=severity,
        )
        return event

    def emit_guardrail_warned(
        self, agent: AgentState, result: GuardrailResult, *, reason: str
    ) -> dict:
        event = self._record(
            agent,
            event_type=AuditEventType.GUARDRAIL_WARNING,
            resource_type="chat_message",
            metadata={"reason": reason, "rules": result.triggered_rules},
            result=AuditResult.WARNING,
            severity=AuditSeverity.MEDIUM,
        )
        return event

    def emit_risk_checked(self, agent: AgentState, *, action: RiskAction, rules: int) -> dict:
        event_type = (
            AuditEventType.RISK_BLOCK if action is RiskAction.BLOCK else AuditEventType.RISK_WARNING
        )
        result = AuditResult.BLOCKED if action is RiskAction.BLOCK else AuditResult.WARNING
        severity = AuditSeverity.HIGH if action is RiskAction.BLOCK else AuditSeverity.MEDIUM
        return self._record(
            agent,
            event_type=event_type,
            resource_type="trade_proposal",
            metadata={"action": action.value, "rules": rules},
            result=result,
            severity=severity,
        )

    def emit_tool_called(
        self,
        agent: AgentState,
        *,
        tool_name: str,
        success: bool,
        latency_ms: float | None = None,
        used_fallback: bool = False,
    ) -> dict:
        event_type = AuditEventType.TOOL_CALLED if success else AuditEventType.TOOL_FAILED
        result = AuditResult.SUCCESS if success else AuditResult.FAILURE
        event = self._record(
            agent,
            event_type=event_type,
            resource_type="tool",
            resource_id=tool_name,
            metadata={
                "tool_name": tool_name,
                "success": success,
                "latency_ms": latency_ms,
                "fallback_used": used_fallback,
            },
            actor_type=ActorType.TOOL,
            result=result,
            severity=AuditSeverity.LOW,
        )
        if used_fallback:
            self._record(
                agent,
                event_type=AuditEventType.PROVIDER_FALLBACK_USED,
                resource_type="tool",
                resource_id=tool_name,
                metadata={"tool_name": tool_name},
                result=AuditResult.WARNING,
                severity=AuditSeverity.MEDIUM,
            )
        return event

    def emit_approval_required(self, agent: AgentState, *, reason: str | None) -> dict:
        return self._record(
            agent,
            event_type=AuditEventType.APPROVAL_REQUIRED,
            resource_type="trade_proposal",
            metadata={"reason": reason},
            result=AuditResult.WARNING,
            severity=AuditSeverity.MEDIUM,
        )

    def emit_trade_proposal_created(self, agent: AgentState, *, symbol: str) -> dict:
        return self._record(
            agent,
            event_type=AuditEventType.TRADE_PROPOSAL_CREATED,
            resource_type="trade_proposal",
            resource_id=symbol,
            metadata={"symbol": symbol},
            result=AuditResult.SUCCESS,
            severity=AuditSeverity.INFO,
        )

    def emit_paper_execution_attempted(
        self, agent: AgentState, *, success: bool, error: str | None = None
    ) -> dict:
        if success:
            return self._record(
                agent,
                event_type=AuditEventType.PAPER_ORDER_CREATED,
                resource_type="order",
                metadata={"mode": "paper"},
                actor_type=ActorType.USER if agent.user_id else ActorType.SYSTEM,
            )
        return self._record(
            agent,
            event_type=AuditEventType.PAPER_ORDER_REJECTED,
            resource_type="order",
            metadata={"mode": "paper", "error": error},
            result=AuditResult.FAILURE,
            severity=AuditSeverity.MEDIUM,
        )

    def emit_narrative_fallback(
        self,
        agent: AgentState,
        *,
        provider: str,
        rules: list[str],
    ) -> dict:
        return self._record(
            agent,
            event_type=AuditEventType.GUARDRAIL_WARNING,
            resource_type="chat_message",
            metadata={
                "reason": "narrative_validation_fallback",
                "provider": provider,
                "rules": rules,
            },
            result=AuditResult.WARNING,
            severity=AuditSeverity.MEDIUM,
        )

    def persist_usage(
        self,
        agent: AgentState,
        *,
        model: str,
        provider: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        fallback_used: bool | None = None,
        latency_ms: float | None = None,
        feature: str = "agent_chat",
    ) -> None:
        latency = latency_ms or sum(o.latency_ms or 0 for o in agent.tool_outputs) or None
        provider_meta: dict[str, int | float | str | bool] = {}
        for output in agent.tool_outputs:
            if output.result and "usage" in output.result:
                usage = output.result["usage"]
                if isinstance(usage, dict):
                    provider_meta.update(usage)

        from app.schemas.common import UsageStatus

        resolved_fallback = (
            fallback_used
            if fallback_used is not None
            else any(o.used_fallback for o in agent.tool_outputs)
        )
        resolved_input = (
            input_tokens if input_tokens is not None else max(len(agent.message) // 4, 1)
        )
        resolved_output = output_tokens if output_tokens is not None else 64
        from app.schemas.common import CostSource
        from app.services.usage_cost import build_provider_metadata

        meta = dict(provider_meta)
        if "cost_source" not in meta:
            meta = build_provider_metadata(
                input_tokens=resolved_input,
                output_tokens=resolved_output,
                cost_source=(
                    CostSource.TOKENIZER_ESTIMATED
                    if resolved_input or resolved_output
                    else CostSource.UNAVAILABLE
                ),
                fallback_used=resolved_fallback,
                **{k: v for k, v in meta.items() if k not in {"input_tokens", "output_tokens"}},
            )

        self._usage.record(
            UsageEventCreate(
                request_id=agent.request_id,
                user_id=agent.user_id,
                organization_id=agent.organization_id,
                feature=feature,
                model=model,
                provider=provider,
                input_tokens=resolved_input,
                output_tokens=resolved_output,
                tool_calls=len(agent.tool_calls),
                fallback_used=resolved_fallback,
                latency_ms=latency,
                status=UsageStatus.SUCCESS,
                provider_metadata=meta,
            )
        )
        self._log(
            "usage_recorded",
            feature=feature,
            provider=provider,
            model=model,
            tool_calls=len(agent.tool_calls),
            latency_ms=latency,
            fallback_used=any(o.used_fallback for o in agent.tool_outputs),
            **self._base_fields(agent),
        )


def _map_guardrail_severity(severity: GuardrailSeverity) -> AuditSeverity:
    mapping = {
        GuardrailSeverity.INFO: AuditSeverity.INFO,
        GuardrailSeverity.LOW: AuditSeverity.LOW,
        GuardrailSeverity.MEDIUM: AuditSeverity.MEDIUM,
        GuardrailSeverity.HIGH: AuditSeverity.HIGH,
        GuardrailSeverity.CRITICAL: AuditSeverity.CRITICAL,
    }
    return mapping.get(severity, AuditSeverity.HIGH)
