"""LangGraph node implementations (orchestration only).

Nodes call :class:`~app.agents.runtime.AgentRuntime` services and tools. They
never touch providers or the database directly.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.agents.response_builder import build_trading_analysis, format_reply_from_analysis
from app.agents.runtime import AgentRuntime
from app.agents.state_utils import dump_partial, parse_state, patch_state
from app.agents.strategy_intent import classify_strategy_workflow
from app.guardrails.apply import build_guardrail_updates, merge_safety_verdict
from app.guardrails.testing import FORCE_INVALID_OUTPUT
from app.guardrails.types import GuardrailInput
from app.providers.llm import LLMCompletionRequest, LLMMessage
from app.schemas.agent import AgentState, Intent, MessageClass
from app.schemas.common import (
    CostSource,
    DocumentSourceType,
    ProposalStatus,
    RiskAction,
    RiskSeverity,
    SafetyVerdict,
    StrategyId,
    Timeframe,
    TradeDirection,
)
from app.schemas.market import IndicatorContext, MarketSnapshot
from app.schemas.proposal import ExitCriteria, TakeProfitLevel, TradeProposal
from app.schemas.rag import Citation
from app.schemas.risk import RiskCheckRequest
from app.schemas.tools import ToolInput, ToolOutput
from app.schemas.usage import UsageEvent
from app.services.narrative_service import format_reply_with_narrative
from app.services.risk.rules import RiskEvaluationContext
from app.strategies.base import StrategyEvaluationInput


def receive_request(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    if not agent.message.strip():
        return patch_state(state, {"final_answer": "Empty message received."})
    return patch_state(state, {})


def auth_context(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    if agent.user_id is None or agent.organization_id is None:
        return patch_state(
            state,
            {
                "final_answer": "Authentication context is required.",
                "safety_verdict": SafetyVerdict.BLOCK,
            },
        )
    return patch_state(state, {})


def quota_check(state: dict, runtime: AgentRuntime) -> dict:
    if runtime.quota_exceeded:
        return patch_state(
            state,
            {
                "safety_verdict": SafetyVerdict.BLOCK,
                "final_answer": "Quota exceeded for this organization.",
            },
        )
    return patch_state(state, {})


def rate_limit_check(state: dict, runtime: AgentRuntime) -> dict:
    if runtime.rate_limited:
        return patch_state(
            state,
            {
                "safety_verdict": SafetyVerdict.BLOCK,
                "final_answer": "Rate limit exceeded. Please retry later.",
            },
        )
    return patch_state(state, {})


def prompt_injection_check(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    result = runtime.guardrails.check_prompt_injection(GuardrailInput.from_agent_state(agent))
    if result.blocked:
        return patch_state(
            state,
            build_guardrail_updates(agent, result, runtime, audit_reason="prompt_injection"),
        )
    verdict = merge_safety_verdict(agent.safety_verdict, result)
    return patch_state(state, {"safety_verdict": verdict})


def moderation_check(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    if agent.safety_verdict is SafetyVerdict.BLOCK:
        return patch_state(state, {})
    result = runtime.guardrails.check_moderation(GuardrailInput.from_agent_state(agent))
    if result.blocked:
        return patch_state(
            state,
            build_guardrail_updates(agent, result, runtime, audit_reason="moderation"),
        )
    updates: dict = {"safety_verdict": merge_safety_verdict(agent.safety_verdict, result)}
    if result.triggered_rules and not result.blocked:
        updates["audit_events"] = [
            *agent.audit_events,
            runtime.observability.emit_guardrail_warned(agent, result, reason="moderation"),
        ]
    return patch_state(state, updates)


def trading_policy_check(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    if agent.safety_verdict is SafetyVerdict.BLOCK:
        return patch_state(state, {})
    result = runtime.guardrails.check_trading_policy(GuardrailInput.from_agent_state(agent))
    if result.blocked:
        return patch_state(
            state,
            build_guardrail_updates(agent, result, runtime, audit_reason="trading_policy"),
        )
    return patch_state(state, {})


def message_classification(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    lowered = agent.message.lower()
    if "approve" in lowered or "reject" in lowered:
        msg_class = MessageClass.APPROVAL_RESPONSE
    elif any(w in lowered for w in ("journal", "mistake", "lesson")):
        msg_class = MessageClass.JOURNAL_ENTRY
    elif any(w in lowered for w in ("analyze", "setup", "plan", "trade", "btc", "eth")):
        msg_class = MessageClass.ANALYSIS_REQUEST
    elif lowered.endswith("?"):
        msg_class = MessageClass.QUESTION
    else:
        msg_class = MessageClass.UNKNOWN
    return patch_state(state, {"message_class": msg_class})


def intent_classification(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    lowered = agent.message.lower()
    workflow_intent = classify_strategy_workflow(agent.message)
    if "[test_execute]" in lowered or ("execute" in lowered and "paper" in lowered):
        intent = Intent.EXECUTE
    elif workflow_intent is not None:
        intent = workflow_intent
    elif any(w in lowered for w in ("analyze", "plan", "setup", "pullback", "entry")):
        intent = Intent.PLAN_TRADE
    elif "watch" in lowered or "monitor" in lowered:
        intent = Intent.MONITOR
    elif "review" in lowered or "journal" in lowered:
        intent = Intent.REVIEW
    elif "rule" in lowered and "update" in lowered:
        intent = Intent.UPDATE_RULE
    elif agent.message_class is MessageClass.QUESTION:
        intent = Intent.EXPLAIN
    else:
        intent = Intent.UNKNOWN
    return patch_state(state, {"intent": intent})


_SOURCE_OF_TRUTH = "SOURCE OF TRUTH (deterministic):"


def _format_tool_answer(tool_name: str, summary: str) -> str:
    return f"{_SOURCE_OF_TRUTH} [{tool_name}] {summary}"


def strategy_workflow_tools(state: dict, runtime: AgentRuntime) -> dict:
    """Route Slice 33 tools for strategy library, pre-trade, sizing, and comparison."""
    agent = parse_state(state)
    if agent.organization_id is None or agent.user_id is None:
        return patch_state(state, {"final_answer": "Authentication context is required."})

    org = str(agent.organization_id)
    user = str(agent.user_id)
    symbol = agent.symbol or _extract_symbol(agent.message) or "BTCUSDT"
    timeframe = agent.timeframe or Timeframe.H4
    tool_outputs: list = list(agent.tool_outputs)
    tool_calls: list = list(agent.tool_calls)
    audit_events: list = list(agent.audit_events)
    answer_lines: list[str] = []

    def _run_tool(name: str, args: dict) -> ToolOutput:
        output = runtime.tool_registry.execute(name, args)
        tool_audit = runtime.observability.emit_tool_called(
            agent,
            tool_name=name,
            success=output.success,
            latency_ms=output.latency_ms,
            used_fallback=output.used_fallback,
        )
        tool_outputs.append(dump_partial(output))
        tool_calls.append(dump_partial(ToolInput(tool_name=name, arguments=args)))
        audit_events.append(tool_audit)
        return output

    intent = agent.intent

    if intent is Intent.STRATEGY_CARD:
        idea = agent.message.strip()[:500] or "Workspace strategy idea"
        output = _run_tool(
            "strategy_library_tool",
            {
                "action": "create",
                "organization_id": org,
                "user_id": user,
                "name": idea[:80],
                "setup_type": StrategyId.HTF_TREND_PULLBACK.value,
                "card": {
                    "strategy_name": idea[:120],
                    "entry_conditions": [idea],
                    "invalidation": ["Close below defined invalidation level"],
                    "stop_loss": ["Below invalidation swing"],
                    "confirmation_conditions": ["Await confirmation per playbook"],
                    "take_profit_plan": ["TP1 at prior resistance"],
                    "asset_universe": [symbol],
                    "timeframes": [timeframe.value],
                },
            },
        )
        if output.success and output.result:
            answer_lines.append(
                _format_tool_answer(
                    "strategy_library_tool",
                    f"Strategy card created: {output.result.get('name', 'strategy')}.",
                )
            )
        else:
            answer_lines.append(f"Strategy card creation failed: {output.error}")

    elif intent in {Intent.PRE_TRADE, Intent.INVALIDATION_QUERY}:
        output = _run_tool(
            "pretrade_analysis_tool",
            {
                "organization_id": org,
                "user_id": user,
                "symbol": symbol,
                "exchange": "mock",
                "direction": "long",
                "timeframe": timeframe.value,
                "account_size": "10000",
                "max_risk_per_trade": "1",
            },
        )
        if output.success and output.result:
            rec = output.result.get("final_recommendation", "n/a")
            stop = output.result.get("suggested_stop_loss")
            inv = output.result.get("invalidation_summary") or output.result.get("invalidation")
            answer_lines.append(
                _format_tool_answer(
                    "pretrade_analysis_tool",
                    f"Recommendation: {rec}. Stop: {stop}. Invalidation: {inv}.",
                )
            )
            if intent is Intent.INVALIDATION_QUERY and stop:
                answer_lines.append(
                    _format_tool_answer(
                        "pretrade_analysis_tool",
                        f"Stop loss reference: {stop}.",
                    )
                )
        else:
            answer_lines.append(f"Pre-trade analysis failed: {output.error}")

    elif intent in {Intent.POSITION_SIZE, Intent.LOSS_ACCEPTANCE}:
        close = agent.market_context.close if agent.market_context else Decimal("60000")
        invalidation = close * Decimal("0.97")
        sizing_out = _run_tool(
            "position_sizing_tool",
            {
                "request": {
                    "entry_price": str(close),
                    "invalidation_level": str(invalidation),
                    "account_balance": "10000",
                    "max_risk_percent": "1",
                    "confidence_score": 70,
                },
            },
        )
        if sizing_out.success and sizing_out.result:
            planned = sizing_out.result.get("planned_loss_amount")
            stop_dist = sizing_out.result.get("stop_loss_distance")
            max_loss = sizing_out.result.get("maximum_acceptable_loss")
            answer_lines.append(
                _format_tool_answer(
                    "position_sizing_tool",
                    f"Planned loss {planned}; stop {stop_dist}; max loss {max_loss}.",
                )
            )
            if intent is Intent.LOSS_ACCEPTANCE:
                answer_lines.append(
                    _format_tool_answer(
                        "loss_acceptance",
                        "Confirm calmly whether planned loss is acceptable before paper execution.",
                    )
                )
        else:
            answer_lines.append(f"Position sizing failed: {sizing_out.error}")

    elif intent is Intent.MANUAL_LEVELS:
        output = _run_tool(
            "manual_levels_tool",
            {
                "action": "list",
                "organization_id": org,
                "user_id": user,
                "symbol": symbol,
            },
        )
        if output.success and output.result:
            items = output.result.get("items", [])
            total = output.result.get("total", 0)
            labels = [f"{i.get('level_type')} @ {i.get('price') or 'zone'}" for i in items[:5]]
            answer_lines.append(
                _format_tool_answer(
                    "manual_levels_tool",
                    f"{total} level(s) for {symbol}: {', '.join(labels) or 'none'}.",
                )
            )
        else:
            answer_lines.append(f"Manual levels lookup failed: {output.error}")

    elif intent is Intent.HUMAN_VS_SYSTEM:
        trade_match = re.search(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            agent.message,
            re.I,
        )
        if trade_match is None:
            answer_lines.append(
                "Provide a journal or proposal trade ID to compare human vs system plan."
            )
        else:
            output = _run_tool(
                "human_vs_system_tool",
                {
                    "trade_id": trade_match.group(0),
                    "organization_id": org,
                    "user_id": user,
                },
            )
            if output.success and output.result:
                score = output.result.get("plan_adherence_score")
                answer_lines.append(
                    _format_tool_answer(
                        "human_vs_system_tool",
                        f"Plan adherence score {score}/100.",
                    )
                )
            else:
                answer_lines.append(f"Comparison failed: {output.error}")

    elif intent is Intent.STRATEGY_STATUS:
        output = _run_tool(
            "strategy_library_tool",
            {"action": "list", "organization_id": org, "user_id": user},
        )
        if output.success and output.result:
            items = output.result.get("items", [])
            validated = [
                i.get("name")
                for i in items
                if (i.get("validation_status") or i.get("latest_card", {}).get("validation_status"))
                == "validated"
            ]
            answer_lines.append(
                _format_tool_answer(
                    "strategy_library_tool",
                    f"Validated strategies: {', '.join(validated) or 'none yet'}.",
                )
            )
        else:
            answer_lines.append(f"Strategy list failed: {output.error}")

    elif intent is Intent.BACKTEST_QUEUE:
        output = _run_tool(
            "strategy_library_tool",
            {"action": "list", "organization_id": org, "user_id": user},
        )
        if output.success and output.result:
            items = output.result.get("items", [])
            pending = next(
                (
                    i
                    for i in items
                    if (i.get("backtest_status") or "not_run") not in {"complete", "completed"}
                ),
                None,
            )
            if pending:
                answer_lines.append(
                    _format_tool_answer(
                        "strategy_library_tool",
                        f"Next backtest: {pending.get('name')} ({pending.get('backtest_status')}).",
                    )
                )
            else:
                answer_lines.append(
                    _format_tool_answer(
                        "strategy_library_tool",
                        "All strategies have backtest runs or none exist.",
                    )
                )
        else:
            answer_lines.append(f"Strategy list failed: {output.error}")

    elif intent is Intent.BACKTEST_RUN:
        list_out = _run_tool(
            "strategy_library_tool",
            {"action": "list", "organization_id": org, "user_id": user},
        )
        strategy_id = None
        if list_out.success and list_out.result:
            items = list_out.result.get("items", [])
            strategy_id = items[0].get("id") if items else None
        if strategy_id is None:
            answer_lines.append("No strategy found to backtest.")
        else:
            tf = timeframe.value
            output = _run_tool(
                "backtest_tool",
                {
                    "action": "run",
                    "organization_id": org,
                    "user_id": user,
                    "strategy_id": strategy_id,
                    "assumptions": {
                        "symbol": symbol,
                        "timeframe": tf,
                        "exchange": "mock",
                    },
                },
            )
            if output.success and output.result:
                res = output.result.get("result") or {}
                metrics = res.get("metrics") or {}
                answer_lines.append(
                    _format_tool_answer(
                        "backtest_tool",
                        f"Backtest {output.result.get('status')}: "
                        f"trades={metrics.get('trade_count')}, "
                        f"win_rate={metrics.get('win_rate')}, "
                        f"recommendation={res.get('recommendation')}. "
                        "Historical simulation only — not a profit guarantee.",
                    )
                )
            else:
                answer_lines.append(f"Backtest failed: {output.error}")

    elif intent in {Intent.BACKTEST_RESULTS, Intent.BACKTEST_ELIGIBILITY}:
        list_out = _run_tool(
            "strategy_library_tool",
            {"action": "list", "organization_id": org, "user_id": user},
        )
        strategy_id = None
        if list_out.success and list_out.result:
            items = list_out.result.get("items", [])
            strategy_id = items[0].get("id") if items else None
        if strategy_id is None:
            answer_lines.append("No strategy found.")
        elif intent is Intent.BACKTEST_ELIGIBILITY:
            output = _run_tool(
                "backtest_tool",
                {
                    "action": "eligibility",
                    "organization_id": org,
                    "user_id": user,
                    "strategy_id": strategy_id,
                },
            )
            if output.success and output.result:
                answer_lines.append(
                    _format_tool_answer(
                        "backtest_tool",
                        f"Paper eligible: {output.result.get('paper_eligible')}. "
                        f"Validation: {output.result.get('validation_status')}. "
                        f"Backtest: {output.result.get('backtest_status')}.",
                    )
                )
            else:
                answer_lines.append(f"Eligibility check failed: {output.error}")
        else:
            output = _run_tool(
                "backtest_tool",
                {
                    "action": "latest_result",
                    "organization_id": org,
                    "user_id": user,
                    "strategy_id": strategy_id,
                },
            )
            if output.success and output.result:
                res = output.result.get("result") or {}
                metrics = res.get("metrics") or {}
                limitations = res.get("limitations") or []
                answer_lines.append(
                    _format_tool_answer(
                        "backtest_tool",
                        f"Latest backtest: trades={metrics.get('trade_count')}, "
                        f"PF={metrics.get('profit_factor')}, "
                        f"max_dd={metrics.get('max_drawdown_pct')}%, "
                        f"recommendation={res.get('recommendation')}.",
                    )
                )
                if limitations:
                    answer_lines.append(f"Limitations: {'; '.join(limitations[:3])}")
            else:
                answer_lines.append(f"Backtest results failed: {output.error}")

    final_answer = "\n".join(answer_lines) if answer_lines else "No strategy workflow result."
    final_answer += "\nLLM narrative cannot override deterministic risk, sizing, or approval facts."

    return patch_state(
        state,
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "tool_calls": tool_calls,
            "tool_outputs": tool_outputs,
            "audit_events": audit_events,
            "final_answer": final_answer,
        },
    )


def trading_analytics_retrieval(state: dict, runtime: AgentRuntime) -> dict:
    """Load deterministic analytics via tool boundary (no direct DB in nodes)."""
    agent = parse_state(state)
    if runtime.session is None or agent.organization_id is None or agent.user_id is None:
        return patch_state(state, {})

    output = runtime.tool_registry.execute(
        "analytics_summary_tool",
        {
            "organization_id": str(agent.organization_id),
            "user_id": str(agent.user_id),
        },
    )
    tool_audit = runtime.observability.emit_tool_called(
        agent,
        tool_name="analytics_summary_tool",
        success=output.success,
        latency_ms=output.latency_ms,
    )
    updates: dict = {
        "tool_outputs": [*agent.tool_outputs, dump_partial(output)],
        "audit_events": [*agent.audit_events, tool_audit],
    }
    if output.success and output.result:
        review = output.result.get("trade_review") or {}
        discipline = output.result.get("discipline_summary") or {}
        setups = output.result.get("setup_statistics") or []
        mistakes = output.result.get("repeated_mistakes") or []
        summary_parts = [
            f"Discipline score {discipline.get('score', 'n/a')} ({discipline.get('grade', '?')}).",
            f"Journaled trades: {review.get('total_journaled_trades', 0)}.",
        ]
        if setups:
            top = max(setups, key=lambda s: s.get("paper_trade_count", 0))
            if top:
                summary_parts.append(
                    f"Most active setup: {top.get('setup_type')} "
                    f"({top.get('paper_trade_count', 0)} paper trades)."
                )
        if mistakes:
            summary_parts.append(f"Repeated mistakes: {', '.join(mistakes[:5])}.")
        updates["final_answer"] = " ".join(summary_parts)
    return patch_state(state, updates)


def context_retrieval(state: dict, runtime: AgentRuntime) -> dict:
    """RAG via tool boundary — rules, lessons, and policy context only."""
    agent = parse_state(state)
    from app.schemas.common import DocumentSourceType

    source_types = [
        DocumentSourceType.TRADING_PLAYBOOK,
        DocumentSourceType.RISK_POLICY,
        DocumentSourceType.TRADE_JOURNAL,
        DocumentSourceType.REVIEW_NOTE,
    ]
    lowered = agent.message.lower()
    if any(w in lowered for w in ("mistake", "lesson", "improve", "emotion", "journal")):
        source_types = [
            DocumentSourceType.TRADE_JOURNAL,
            DocumentSourceType.MISTAKES_DATABASE,
            DocumentSourceType.REVIEW_NOTE,
            DocumentSourceType.TRADING_PLAYBOOK,
        ]
    tool_input = ToolInput(
        tool_name="rag_retriever",
        arguments={
            "query": agent.message[:500],
            "organization_id": str(agent.organization_id) if agent.organization_id else None,
            "user_id": str(agent.user_id) if agent.user_id else None,
            "source_types": [st.value for st in source_types],
        },
    )
    output = runtime.tool_registry.execute("rag_retriever", tool_input.arguments)
    tool_audit = runtime.observability.emit_tool_called(
        agent,
        tool_name="rag_retriever",
        success=output.success,
        latency_ms=output.latency_ms,
        used_fallback=output.used_fallback,
    )
    citations: list[dict] = list(agent.citations)
    retrieved: list[dict] = list(agent.retrieved_context)
    if output.success and output.result:
        raw_citations = output.result.get("citations", [])
        for raw in raw_citations:
            citation = Citation.model_validate(raw)
            dumped = dump_partial(citation)
            citations.append(dumped)
            retrieved.append(dumped)
    return patch_state(
        state,
        {
            "tool_calls": [*agent.tool_calls, dump_partial(tool_input)],
            "tool_outputs": [*agent.tool_outputs, dump_partial(output)],
            "retrieved_context": retrieved,
            "citations": citations,
            "audit_events": [*agent.audit_events, tool_audit],
        },
    )


def market_context_retrieval(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    symbol = agent.symbol or _extract_symbol(agent.message) or "BTCUSDT"
    timeframe = agent.timeframe or Timeframe.H4
    output = runtime.tool_registry.execute(
        "market_data",
        {"symbol": symbol, "timeframe": timeframe.value, "exchange": "binance"},
    )
    quality = "missing"
    snapshot = None
    if runtime.market_data_service is not None:
        snap = runtime.market_data_service.get_snapshot(symbol, timeframe, exchange="binance")
        if snap.meta.fallback_used or not snap.meta.is_live:
            quality = "mock"
        elif snap.meta.is_stale:
            quality = "stale"
        else:
            quality = "live"
        latest = snap.latest_bar
        if latest is not None:
            snapshot = MarketSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                open=latest.open,
                high=latest.high,
                low=latest.low,
                close=latest.close,
                volume=latest.volume,
                funding_rate=snap.funding_rate,
                timestamp=latest.timestamp,
            )
    if snapshot is None:
        close = Decimal("60000")
        if output.success and output.result and "close" in output.result:
            close = Decimal(str(output.result["close"]))
        snapshot = MarketSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            open=close * Decimal("0.99"),
            high=close * Decimal("1.01"),
            low=close * Decimal("0.98"),
            close=close,
            volume=Decimal("50000000"),
            funding_rate=Decimal("0.0001"),
            timestamp=datetime.now(UTC),
        )
        quality = "mock"
    return patch_state(
        state,
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "market_context": dump_partial(snapshot),
            "market_data_quality": quality,
            "tool_outputs": [*agent.tool_outputs, dump_partial(output)],
        },
    )


def indicator_calculation(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    symbol = agent.symbol or "BTCUSDT"
    timeframe = agent.timeframe or Timeframe.H4
    output = runtime.tool_registry.execute(
        "indicator",
        {"symbol": symbol, "timeframe": timeframe.value, "exchange": "binance"},
    )
    indicators = None
    if runtime.market_data_service is not None:
        snap = runtime.market_data_service.get_snapshot(symbol, timeframe, exchange="binance")
        ohlcv = runtime.market_data_service.get_ohlcv(symbol, timeframe, exchange="binance")
        funding_rate = snap.funding_rate
        from app.providers.market_data import OHLCVBar

        bars = [
            OHLCVBar(
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                timestamp=b.timestamp,
            )
            for b in ohlcv.bars
        ]
        if bars:
            from app.services.indicator_service import IndicatorService

            indicators = IndicatorService().calculate(
                symbol=symbol,
                timeframe=timeframe,
                bars=bars,
                funding_rate=funding_rate,
            )
    if indicators is None:
        now = datetime.now(UTC)
        close = agent.market_context.close if agent.market_context else Decimal("60000")
        indicators = IndicatorContext(
            symbol=symbol,
            timeframe=timeframe,
            rsi=55.0,
            ema_fast=close * Decimal("0.995"),
            ema_slow=close * Decimal("0.98"),
            funding_rate=Decimal("0.0001"),
            timestamp=now,
        )
    return patch_state(
        state,
        {
            "indicator_context": dump_partial(indicators),
            "tool_outputs": [*agent.tool_outputs, dump_partial(output)],
        },
    )


def strategy_module_execution(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    symbol = agent.symbol or "BTCUSDT"
    timeframe = agent.timeframe or Timeframe.H4
    close = agent.market_context.close if agent.market_context else Decimal("60000")
    ema_fast = agent.indicator_context.ema_fast if agent.indicator_context else None
    ema_slow = agent.indicator_context.ema_slow if agent.indicator_context else None
    data = StrategyEvaluationInput(
        symbol=symbol,
        timeframe=timeframe,
        close=close,
        volume=Decimal("1000000"),
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        htf_trend=TradeDirection.LONG,
        liquidity_sweep_detected="sweep" in agent.message.lower(),
        data_is_live=agent.market_data_quality == "live",
        data_is_stale=agent.market_data_quality == "stale",
        data_fallback_used=agent.market_data_quality in {"mock", "missing", None},
    )
    signals = []
    from app.strategies.confidence import adjust_confidence_for_data_quality

    for strategy_id in (StrategyId.HTF_TREND_PULLBACK, StrategyId.LIQUIDITY_SWEEP_REVERSAL):
        signal = runtime.strategy_service.evaluate(strategy_id, data)
        if signal is not None:
            adjusted = signal.model_copy(
                update={"confidence": adjust_confidence_for_data_quality(signal.confidence, data)}
            )
            evidence = list(adjusted.evidence)
            if agent.market_data_quality != "live":
                evidence.append(f"Market data quality: {agent.market_data_quality or 'unknown'}")
            adjusted = adjusted.model_copy(update={"evidence": evidence})
            signals.append(dump_partial(adjusted))
    tool_out = runtime.tool_registry.execute(
        "strategy_evaluator",
        {
            "strategy_id": StrategyId.HTF_TREND_PULLBACK.value,
            "symbol": symbol,
            "timeframe": timeframe.value,
            "close": str(close),
            "volume": "1000000",
            "htf_trend": "long",
        },
    )
    return patch_state(
        state,
        {
            "strategy_signals": signals,
            "tool_outputs": [*agent.tool_outputs, dump_partial(tool_out)],
        },
    )


def trade_proposal_generation(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    if agent.intent not in {Intent.PLAN_TRADE, Intent.EXECUTE}:
        return patch_state(state, {})
    if agent.user_id is None or agent.organization_id is None:
        return patch_state(state, {})

    symbol = agent.symbol or "BTCUSDT"
    timeframe = agent.timeframe or Timeframe.H4
    close = agent.market_context.close if agent.market_context else Decimal("60000")
    no_stop = "[test_no_stop]" in agent.message.lower()
    stop = None if no_stop else close * Decimal("0.97")
    strategy_id = StrategyId.HTF_TREND_PULLBACK
    if agent.strategy_signals:
        strategy_id = agent.strategy_signals[0].strategy_id

    confidence = 0.45 if "[test_low_confidence]" in agent.message.lower() else 0.72
    if agent.market_data_quality in {"mock", "stale", "missing", None}:
        confidence = max(0.35, confidence - 0.12)
    data_note = ""
    if agent.market_data_quality and agent.market_data_quality != "live":
        data_note = f" Evidence based on {agent.market_data_quality} market data."
    exit = ExitCriteria(
        invalidation="Close below stop or HTF structure breaks.",
        stop_loss=stop if stop is not None else close * Decimal("0.97"),
        take_profits=[TakeProfitLevel(price=close * Decimal("1.02"), size_fraction=0.5)],
    )
    if no_stop:
        exit = ExitCriteria(
            invalidation="N/A",
            stop_loss=close,
            take_profits=[TakeProfitLevel(price=close * Decimal("1.01"), size_fraction=1.0)],
        )
        # Risk engine will block missing stop on check — pass stop_loss anyway for schema;
        # RiskCheckRequest uses separate stop_loss field.

    proposal = TradeProposal(
        organization_id=agent.organization_id,
        user_id=agent.user_id,
        strategy_id=strategy_id,
        symbol=symbol,
        timeframe=timeframe,
        direction=TradeDirection.LONG,
        entry_price=close,
        position_size=Decimal("0.005"),
        leverage=Decimal("50") if "[test_high_risk]" in agent.message.lower() else Decimal("3"),
        exit=exit,
        confidence=confidence,
        risk_level=RiskSeverity.MEDIUM,
        rationale=f"Deterministic scaffold proposal from strategy context.{data_note}",
        status=ProposalStatus.PENDING_APPROVAL,
        created_at=datetime.now(UTC),
    )
    proposal_audit = runtime.observability.emit_trade_proposal_created(agent, symbol=symbol)
    return patch_state(
        state,
        {
            "trade_proposal": dump_partial(proposal),
            "confidence": confidence,
            "risk_level": RiskSeverity.MEDIUM,
            "audit_events": [*agent.audit_events, proposal_audit],
        },
    )


def deterministic_risk_gate(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    if agent.trade_proposal is None:
        return patch_state(state, {})

    p = agent.trade_proposal
    no_stop = "[test_no_stop]" in agent.message.lower()
    request = RiskCheckRequest(
        symbol=p.symbol,
        direction=p.direction,
        strategy_id=p.strategy_id,
        entry_price=p.entry_price,
        stop_loss=None if no_stop else p.exit.stop_loss,
        position_size=p.position_size,
        leverage=p.leverage,
        account_equity=Decimal("10000"),
        volume_24h=Decimal("50000000"),
        is_countertrend=False,
    )
    tool_out = runtime.tool_registry.execute(
        "risk_checker", {"request": request.model_dump(mode="json")}
    )
    result = runtime.risk_service.check(
        request,
        context=RiskEvaluationContext(is_weekend=False, kill_switch_active=False),
    )
    severity = result.severity
    risk_audit = runtime.observability.emit_risk_checked(
        agent,
        action=result.action,
        rules=len(result.triggered_rules),
    )
    return patch_state(
        state,
        {
            "risk_result": dump_partial(result),
            "risk_level": severity,
            "tool_outputs": [*agent.tool_outputs, dump_partial(tool_out)],
            "audit_events": [*agent.audit_events, risk_audit],
        },
    )


def approval_decision(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    if agent.risk_result and agent.risk_result.action is RiskAction.BLOCK:
        return patch_state(
            state,
            {
                "approval_required": False,
                "approval_reason": "Blocked by risk engine; approval not applicable.",
            },
        )

    needs_approval = False
    reason = None
    if agent.intent is Intent.EXECUTE:
        needs_approval = True
        reason = "Execution intent requires explicit human approval."
    if agent.trade_proposal is not None:
        if agent.confidence is not None and agent.confidence < 0.55:
            needs_approval = True
            reason = "Low confidence high-impact trade proposal."
        if agent.risk_result and agent.risk_result.approval_required:
            needs_approval = True
            reason = reason or "Risk engine requires human approval."
    if agent.risk_result and agent.risk_result.action is RiskAction.WARN:
        needs_approval = True
        reason = reason or "Risk warnings present."

    updates: dict = {"approval_required": needs_approval, "approval_reason": reason}
    if needs_approval:
        updates["audit_events"] = [
            *agent.audit_events,
            runtime.observability.emit_approval_required(agent, reason=reason),
        ]
    return patch_state(state, updates)


def tool_execution_if_allowed(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    bypass = runtime.guardrails.check_tool_bypass_attempt(GuardrailInput.from_agent_state(agent))
    if bypass.blocked:
        return patch_state(
            state,
            build_guardrail_updates(agent, bypass, runtime, audit_reason="tool_bypass"),
        )

    if runtime.real_trading_allowed:
        return patch_state(
            state,
            {
                "final_answer": "Real exchange execution is disabled.",
                "safety_verdict": SafetyVerdict.BLOCK,
            },
        )

    if agent.risk_result and agent.risk_result.action is RiskAction.BLOCK:
        return patch_state(state, {})

    if agent.intent is not Intent.EXECUTE:
        return patch_state(state, {})

    if agent.approval_required:
        paper_audit = runtime.observability.emit_paper_execution_attempted(
            agent,
            success=False,
            error="Approval required before paper execution.",
        )
        return patch_state(
            state,
            {
                "tool_outputs": [
                    *agent.tool_outputs,
                    dump_partial(
                        ToolOutput(
                            tool_name="paper_execution",
                            success=False,
                            error="Approval required before paper execution.",
                        )
                    ),
                ],
                "audit_events": [*agent.audit_events, paper_audit],
            },
        )

    # Paper-only path via tool registry (never real exchange).
    paper_args = {
        "mode": "paper",
        "symbol": agent.symbol or "BTCUSDT",
        "note": "Scaffold paper execution stub",
    }
    output = runtime.tool_registry.execute("paper_execution", paper_args)
    paper_audit = runtime.observability.emit_paper_execution_attempted(
        agent,
        success=output.success,
        error=output.error,
    )
    return patch_state(
        state,
        {
            "tool_outputs": [*agent.tool_outputs, dump_partial(output)],
            "audit_events": [*agent.audit_events, paper_audit],
        },
    )


def memory_update(state: dict, runtime: AgentRuntime) -> dict:
    """In-memory conversation note only (no DB writes in Slice 9)."""
    agent = parse_state(state)
    summary = f"intent={agent.intent.value}; class={agent.message_class.value}"
    citation = dump_partial(
        Citation(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            source_type=DocumentSourceType.TRADING_PLAYBOOK,
            snippet=f"Session memory: {summary}",
        )
    )
    return patch_state(state, {"citations": [*agent.citations, citation]})


def usage_tracking(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    llm = runtime.llm_provider
    provider_name = llm.name if llm is not None else "mock-llm"
    llm_result = None
    if llm is not None:
        llm_result = llm.complete(
            LLMCompletionRequest(
                messages=[LLMMessage(role="user", content=agent.message[:500])],
                model=runtime.settings.llm_model,
                temperature=0.0,
                max_tokens=64,
            )
        )
    input_tokens = llm_result.input_tokens if llm_result else max(len(agent.message) // 4, 1)
    output_tokens = llm_result.output_tokens if llm_result else 64
    fallback_used = (llm_result.fallback_used if llm_result else True) or any(
        o.used_fallback for o in agent.tool_outputs
    )

    runtime.observability.persist_usage(
        agent,
        model=runtime.settings.llm_model,
        provider=provider_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        fallback_used=fallback_used,
        latency_ms=llm_result.latency_ms if llm_result else None,
    )
    usage = UsageEvent(
        organization_id=agent.organization_id,
        user_id=agent.user_id,
        request_id=agent.request_id,
        feature="agent_chat",
        model=llm_result.model if llm_result else runtime.settings.llm_model,
        provider=provider_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        tool_calls=len(agent.tool_calls),
        fallback_used=fallback_used,
        latency_ms=(
            llm_result.latency_ms
            if llm_result
            else (sum(o.latency_ms or 0 for o in agent.tool_outputs) or None)
        ),
        timestamp=datetime.now(UTC),
        cost_source=CostSource.STATIC_ESTIMATED,
        cost_is_placeholder=True,
    )
    return patch_state(state, {"usage_metadata": dump_partial(usage)})


def final_response(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    if agent.final_answer and agent.analysis_detail is not None:
        return patch_state(state, {})

    if agent.final_answer and agent.analysis_detail is None:
        # Preserve guardrail-set answers without overwriting structured detail.
        detail = build_trading_analysis(agent, runtime)
        return patch_state(
            state,
            {
                "analysis_detail": dump_partial(detail),
            },
        )

    detail = build_trading_analysis(agent, runtime)
    answer = format_reply_from_analysis(detail)
    if agent.citations:
        answer += f"\nCitations: {len(agent.citations)} reference(s) attached."
    if FORCE_INVALID_OUTPUT in agent.message.lower():
        answer = "Incomplete trading reply."
    return patch_state(
        state,
        {
            "analysis_detail": dump_partial(detail),
            "final_answer": answer,
        },
    )


def narrative_enhancement(state: dict, runtime: AgentRuntime) -> dict:
    """Optional LLM narrative polish — deterministic analysis remains authoritative."""
    agent = parse_state(state)
    if FORCE_INVALID_OUTPUT in agent.message.lower():
        return patch_state(state, {})
    if agent.analysis_detail is None or runtime.narrative_service is None:
        return patch_state(state, {})

    analysis = agent.analysis_detail

    def _persist(agent_state: AgentState, *, llm_result: object, feature: str) -> None:
        from app.providers.llm import LLMCompletionResult

        if not isinstance(llm_result, LLMCompletionResult):
            return
        runtime.observability.persist_usage(
            agent_state,
            model=llm_result.model,
            provider=llm_result.provider,
            input_tokens=llm_result.input_tokens,
            output_tokens=llm_result.output_tokens,
            fallback_used=llm_result.fallback_used,
            latency_ms=llm_result.latency_ms,
            feature=feature,
        )

    result = runtime.narrative_service.enhance(
        agent,
        analysis,
        persist_usage=_persist,
    )
    answer = format_reply_with_narrative(analysis, result.narrative, result.metadata)

    updates: dict = {
        "narrative_detail": dump_partial(result.narrative),
        "narrative_metadata": dump_partial(result.metadata),
        "final_answer": answer,
    }
    if result.used_llm and not result.metadata.validation_passed:
        fallback_audit = runtime.observability.emit_narrative_fallback(
            agent,
            provider=result.metadata.provider,
            rules=["narrative_validation_failed"],
        )
        updates["audit_events"] = [*agent.audit_events, fallback_audit]

    if result.usage is not None and agent.usage_metadata is None:
        updates["usage_metadata"] = dump_partial(result.usage)
    return patch_state(state, updates)


def output_validation(state: dict, runtime: AgentRuntime) -> dict:
    agent = parse_state(state)
    if agent.safety_verdict is SafetyVerdict.BLOCK and agent.final_answer:
        return patch_state(state, {})

    result = runtime.guardrails.validate_output(GuardrailInput.from_agent_state(agent))
    if result.allowed:
        return patch_state(state, {})

    updates: dict = {"final_answer": result.safe_message}
    if result.audit_required:
        updates = build_guardrail_updates(
            agent,
            result,
            runtime,
            audit_reason="output_validation",
            set_final_answer_on_block=True,
        )
    return patch_state(state, updates)


def _extract_symbol(message: str) -> str | None:
    match = re.search(r"\b(BTC|ETH|SOL)[A-Z]*\b", message.upper())
    if match:
        token = match.group(1)
        return f"{token}USDT"
    return None
