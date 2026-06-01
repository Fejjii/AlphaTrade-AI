"""Deterministic structured trading response builder."""

from __future__ import annotations

from app.agents.runtime import AgentRuntime
from app.schemas.agent import AgentState, Intent
from app.schemas.analysis import TradingAnalysisDetail
from app.schemas.common import RiskAction, SafetyVerdict


def _market_data_quality(runtime: AgentRuntime, agent: AgentState) -> str:
    if agent.market_data_quality:
        return agent.market_data_quality
    market_tool = next(
        (o for o in agent.tool_outputs if o.tool_name == "market_data"),
        None,
    )
    if market_tool is None or not market_tool.success:
        return "missing"
    result = market_tool.result or {}
    if market_tool.used_fallback or result.get("fallback_used") or result.get("source") == "mock":
        return "mock"
    if result.get("is_stale"):
        return "stale"
    if result.get("is_live"):
        return "live"
    return "mock"


def _approval_status(agent: AgentState) -> str:
    if agent.safety_verdict is SafetyVerdict.BLOCK:
        return "blocked"
    if agent.risk_result and agent.risk_result.action is RiskAction.BLOCK:
        return "blocked"
    if agent.approval_required:
        return "pending"
    return "not_required"


def _setup_type(agent: AgentState) -> str | None:
    if agent.trade_proposal is not None:
        return agent.trade_proposal.strategy_id.value
    if agent.intent is Intent.MONITOR:
        return "monitor"
    if agent.intent is Intent.EXPLAIN:
        return "explain"
    if agent.intent is Intent.REVIEW:
        return "review"
    return None


def _evidence(agent: AgentState) -> list[str]:
    evidence: list[str] = []
    if agent.strategy_signals:
        for signal in agent.strategy_signals[:3]:
            evidence.append(
                f"{signal.strategy_id.value}: {signal.direction.value} "
                f"(confidence {signal.confidence:.2f})"
            )
    if agent.indicator_context:
        evidence.append(
            f"RSI {agent.indicator_context.rsi:.1f} on "
            f"{agent.indicator_context.symbol} {agent.indicator_context.timeframe.value}"
        )
    if agent.market_context:
        quality = agent.market_data_quality or "unknown"
        evidence.append(
            f"Close {agent.market_context.close} ({agent.market_context.symbol}, "
            f"{quality} market data)"
        )
    if agent.retrieved_context:
        evidence.append(f"{len(agent.retrieved_context)} RAG citation(s) retrieved.")
    if not evidence:
        evidence.append("No strategy signals or market context available for this intent.")
    return evidence


def build_trading_analysis(agent: AgentState, runtime: AgentRuntime) -> TradingAnalysisDetail:
    """Build validated structured response fields from deterministic agent state."""
    approval_status = _approval_status(agent)
    market_quality = _market_data_quality(runtime, agent)
    paper_disclaimer = (
        "Paper mode only — no real exchange execution. Approval required before any paper order."
        if agent.intent is Intent.EXECUTE or agent.trade_proposal is not None
        else "Paper mode only — analysis and education; no live orders."
    )

    if agent.safety_verdict is SafetyVerdict.BLOCK:
        return TradingAnalysisDetail(
            summary=agent.final_answer or "Request blocked by safety policy.",
            setup_type=_setup_type(agent),
            evidence=_evidence(agent),
            risk_level=agent.risk_level,
            confidence=agent.confidence,
            invalidation=None,
            stop_loss_or_no_trade_reason="No trade — blocked by safety guardrails.",
            approval_status=approval_status,
            next_decision_point="Resolve safety block before retrying.",
            paper_mode_disclaimer=paper_disclaimer,
            market_data_quality=market_quality,
        )

    if agent.risk_result and agent.risk_result.action is RiskAction.BLOCK:
        return TradingAnalysisDetail(
            summary=f"Trade blocked by risk engine: {agent.risk_result.explanation}",
            setup_type=_setup_type(agent),
            evidence=_evidence(agent),
            risk_level=agent.risk_level,
            confidence=agent.confidence,
            invalidation=agent.trade_proposal.exit.invalidation if agent.trade_proposal else None,
            stop_loss_or_no_trade_reason="Stop loss missing or invalid — do not trade.",
            approval_status=approval_status,
            next_decision_point="Revise proposal with valid stop loss and re-run risk check.",
            paper_mode_disclaimer=paper_disclaimer,
            market_data_quality=market_quality,
        )

    if agent.trade_proposal:
        proposal = agent.trade_proposal
        next_step = (
            "Submit for human approval before paper execution."
            if agent.approval_required
            else "Review proposal; no execution without explicit approval."
        )
        return TradingAnalysisDetail(
            summary=(
                f"Trade proposal for {proposal.symbol} ({proposal.direction.value}) "
                f"via {proposal.strategy_id.value}."
            ),
            setup_type=proposal.strategy_id.value,
            evidence=_evidence(agent),
            risk_level=agent.risk_level or proposal.risk_level,
            confidence=agent.confidence or proposal.confidence,
            invalidation=proposal.exit.invalidation,
            stop_loss_or_no_trade_reason=f"Stop loss at {proposal.exit.stop_loss}.",
            approval_status=approval_status,
            next_decision_point=next_step,
            paper_mode_disclaimer=paper_disclaimer,
            market_data_quality=market_quality,
        )

    return TradingAnalysisDetail(
        summary="Completed analysis workflow without an executable trade proposal.",
        setup_type=_setup_type(agent),
        evidence=_evidence(agent),
        risk_level=agent.risk_level,
        confidence=agent.confidence,
        invalidation=None,
        stop_loss_or_no_trade_reason="No trade — no valid setup met strategy and risk criteria.",
        approval_status=approval_status,
        next_decision_point="Provide symbol/timeframe or request a specific setup review.",
        paper_mode_disclaimer=paper_disclaimer,
        market_data_quality=market_quality,
    )


def format_reply_from_analysis(detail: TradingAnalysisDetail) -> str:
    """Human-readable reply assembled from structured fields (not raw LLM)."""
    confidence_line = (
        f"Confidence: {detail.confidence:.2f}"
        if detail.confidence is not None
        else "Confidence: n/a"
    )
    lines = [
        f"Summary: {detail.summary}",
        f"Setup type: {detail.setup_type or 'none'}",
        f"Evidence: {'; '.join(detail.evidence)}",
        f"Risk level: {detail.risk_level.value if detail.risk_level else 'unknown'}",
        confidence_line,
    ]
    if detail.invalidation:
        lines.append(f"Invalidation: {detail.invalidation}")
    lines.extend(
        [
            f"Stop loss / no-trade: {detail.stop_loss_or_no_trade_reason}",
            f"Approval status: {detail.approval_status}",
            f"Next decision point: {detail.next_decision_point or 'n/a'}",
            f"Market data: {detail.market_data_quality} (do not treat mock data as live prices).",
            "Limitations: Analysis only — not financial advice; mock market data; "
            "real exchange execution disabled; deterministic risk engine is final authority.",
            f"Paper mode: {detail.paper_mode_disclaimer}",
        ]
    )
    return "\n".join(lines)
