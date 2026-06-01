"""Agent orchestration service — runs the LangGraph workflow."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agents.graph import compile_agent_graph
from app.agents.runtime import AgentRuntime
from app.agents.state_utils import parse_state, state_to_dict
from app.core.config import Settings, get_settings
from app.observability.context import bind_identity, get_or_create_trace_id, set_trace_id
from app.providers.factory import resolve_market_data_provider
from app.schemas.agent import AgentState
from app.schemas.chat import AgentMessageResponse
from app.schemas.common import RiskAction, SafetyVerdict, Timeframe
from app.services.indicator_service import IndicatorService
from app.services.market_cache import MarketDataCache
from app.services.market_data_service import MarketDataService
from app.services.rag_service import build_rag_service
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService
from app.strategies.registry import get_strategy_registry
from app.tools.registry import build_default_registry as build_tool_registry


@dataclass(frozen=True)
class AgentInvokeContext:
    """Identity context supplied by the API layer (not loaded from DB here)."""

    request_id: str
    user_id: uuid.UUID
    organization_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    trace_id: str | None = None


class AgentService:
    """Runs the compiled LangGraph agent with injected runtime boundaries."""

    def __init__(self, runtime: AgentRuntime | None = None) -> None:
        if runtime is None:
            settings = get_settings()
            rag = build_rag_service(settings)
            strategy_service = StrategyService(registry=get_strategy_registry())
            market_data_service = MarketDataService(
                resolve_market_data_provider(settings),
                cache=MarketDataCache(settings),
                indicator_service=IndicatorService(),
                strategy_service=strategy_service,
            )
            runtime = AgentRuntime(
                settings=settings,
                risk_service=RiskService(),
                strategy_service=strategy_service,
                tool_registry=build_tool_registry(
                    settings,
                    rag_service=rag,
                    market_data_service=market_data_service,
                ),
                market_data_service=market_data_service,
                rag_service=rag,
            )
        self._runtime = runtime
        self._graph = compile_agent_graph(self._runtime)

    @property
    def runtime(self) -> AgentRuntime:
        return self._runtime

    def run(
        self,
        message: str,
        context: AgentInvokeContext,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> AgentMessageResponse:
        if context.trace_id:
            set_trace_id(context.trace_id)
        else:
            get_or_create_trace_id()
        bind_identity(
            user_id=str(context.user_id),
            organization_id=str(context.organization_id),
        )

        initial = AgentState(
            request_id=context.request_id,
            user_id=context.user_id,
            organization_id=context.organization_id,
            conversation_id=context.conversation_id,
            message=message,
            symbol=symbol,  # type: ignore[arg-type]
            timeframe=Timeframe(timeframe) if timeframe else None,
        )
        self._runtime.observability.emit_agent_run_started(initial)
        started = time.perf_counter()
        result_dict = self._graph.invoke(state_to_dict(initial))
        agent = parse_state(result_dict)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self._runtime.observability.emit_agent_run_completed(agent, latency_ms=elapsed_ms)

        if self._runtime.workflow_persistence is not None:
            persisted = self._runtime.workflow_persistence.persist_agent_outcome(agent)
            if persisted.proposal_id is not None:
                agent = agent.model_copy(update={"proposal_id": persisted.proposal_id})
            if persisted.approval_id is not None:
                agent = agent.model_copy(update={"approval_id": persisted.approval_id})
            self._runtime.session.commit()  # type: ignore[union-attr]

        return self._to_response(agent, context)

    def _to_response(self, agent: AgentState, ctx: AgentInvokeContext) -> AgentMessageResponse:
        limitations = [
            "Analysis and education only — not financial advice.",
            "Real exchange execution is disabled by default.",
            "Deterministic risk engine is the final authority.",
        ]
        approval_status = "blocked"
        if agent.safety_verdict is not SafetyVerdict.BLOCK:
            if agent.risk_result and agent.risk_result.action is RiskAction.BLOCK:
                approval_status = "blocked"
            elif agent.approval_required:
                approval_status = "pending"
            else:
                approval_status = "not_required"

        conversation_id = (
            str(ctx.conversation_id) if ctx.conversation_id else f"conv-{ctx.request_id[:8]}"
        )
        return AgentMessageResponse(
            conversation_id=conversation_id,
            request_id=agent.request_id,
            reply=agent.final_answer or "No response generated.",
            risk_level=agent.risk_level,
            confidence=agent.confidence,
            approval_required=agent.approval_required,
            approval_status=approval_status,
            approval_reason=agent.approval_reason,
            proposal_id=str(agent.proposal_id) if agent.proposal_id else None,
            approval_id=str(agent.approval_id) if agent.approval_id else None,
            citations=agent.citations,
            tool_outputs=agent.tool_outputs,
            risk_result=agent.risk_result,
            limitations=limitations,
            usage=agent.usage_metadata,
            analysis=agent.analysis_detail,
            narrative=agent.narrative_detail,
            narrative_meta=agent.narrative_metadata,
        )


def build_agent_service(
    settings: Settings | None = None,
    session: Session | None = None,
) -> AgentService:
    settings = settings or get_settings()
    risk = RiskService()
    strategies = StrategyService(registry=get_strategy_registry())
    if session is not None:
        runtime = AgentRuntime.from_session(
            session,
            settings=settings,
            risk_service=risk,
            strategy_service=strategies,
            strict_observability=settings.observability_strict_mode,
        )
    else:
        rag = build_rag_service(settings)
        tools = build_tool_registry(settings, rag_service=rag)
        runtime = AgentRuntime(
            settings=settings,
            risk_service=risk,
            strategy_service=strategies,
            tool_registry=tools,
            rag_service=rag,
        )
    return AgentService(runtime=runtime)
