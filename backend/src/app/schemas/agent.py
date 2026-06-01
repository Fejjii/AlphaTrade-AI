"""Typed LangGraph agent state (master prompt §10).

This is the single mutable object threaded through the agent workflow. Keeping
it strongly typed avoids untyped-dict drift between nodes and makes the graph
testable. Fields are optional and filled progressively as nodes execute.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import TradingAnalysisDetail
from app.schemas.audit import AuditEvent
from app.schemas.common import Confidence, RiskSeverity, SafetyVerdict, Symbol, Timeframe
from app.schemas.market import IndicatorContext, MarketSnapshot
from app.schemas.narrative import NarrativeMetadata, TradingNarrativeDetail
from app.schemas.proposal import TradeProposal
from app.schemas.rag import Citation
from app.schemas.risk import RiskCheckResult
from app.schemas.strategy import StrategySignal
from app.schemas.tools import ToolInput, ToolOutput
from app.schemas.usage import UsageEvent


class MessageClass(StrEnum):
    QUESTION = "question"
    COMMAND = "command"
    ANALYSIS_REQUEST = "analysis_request"
    APPROVAL_RESPONSE = "approval_response"
    JOURNAL_ENTRY = "journal_entry"
    SMALLTALK = "smalltalk"
    UNKNOWN = "unknown"


class Intent(StrEnum):
    MONITOR = "monitor"
    PLAN_TRADE = "plan_trade"
    EXECUTE = "execute"
    REVIEW = "review"
    UPDATE_RULE = "update_rule"
    EXPLAIN = "explain"
    UNKNOWN = "unknown"


class AgentState(BaseModel):
    """Mutable workflow state passed between graph nodes."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # Identity / correlation
    request_id: str
    user_id: UUID | None = None
    organization_id: UUID | None = None
    conversation_id: UUID | None = None

    # Request context
    symbol: Symbol | None = None
    timeframe: Timeframe | None = None
    message: str = ""

    # Classification
    message_class: MessageClass = MessageClass.UNKNOWN
    intent: Intent = Intent.UNKNOWN
    safety_verdict: SafetyVerdict | None = None

    # Gathered context
    market_context: MarketSnapshot | None = None
    indicator_context: IndicatorContext | None = None
    market_data_quality: str | None = Field(
        default=None, description="live | mock | stale | missing"
    )
    strategy_signals: list[StrategySignal] = Field(default_factory=list)
    retrieved_context: list[Citation] = Field(default_factory=list)

    # Tooling
    tool_calls: list[ToolInput] = Field(default_factory=list)
    tool_outputs: list[ToolOutput] = Field(default_factory=list)

    # Proposal + risk
    trade_proposal: TradeProposal | None = None
    risk_result: RiskCheckResult | None = None
    risk_level: RiskSeverity | None = None
    confidence: Confidence | None = None

    # Approval
    approval_required: bool = False
    approval_reason: str | None = None
    proposal_id: UUID | None = None
    approval_id: UUID | None = None

    # Output
    citations: list[Citation] = Field(default_factory=list)
    final_answer: str | None = None
    analysis_detail: TradingAnalysisDetail | None = None
    narrative_detail: TradingNarrativeDetail | None = None
    narrative_metadata: NarrativeMetadata | None = None

    # Observability
    usage_metadata: UsageEvent | None = None
    audit_events: list[AuditEvent] = Field(default_factory=list)
