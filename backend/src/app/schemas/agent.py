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
    STRATEGY_CARD = "strategy_card"
    PRE_TRADE = "pre_trade"
    POSITION_SIZE = "position_size"
    INVALIDATION_QUERY = "invalidation_query"
    LOSS_ACCEPTANCE = "loss_acceptance"
    HUMAN_VS_SYSTEM = "human_vs_system"
    MANUAL_LEVELS = "manual_levels"
    STRATEGY_STATUS = "strategy_status"
    BACKTEST_QUEUE = "backtest_queue"
    BACKTEST_RUN = "backtest_run"
    BACKTEST_RESULTS = "backtest_results"
    BACKTEST_ELIGIBILITY = "backtest_eligibility"
    EARLY_EXIT_QUERY = "early_exit_query"
    STOP_DISCIPLINE_QUERY = "stop_discipline_query"
    STRATEGY_TESTABILITY = "strategy_testability"
    STRUCTURE_STRATEGY = "structure_strategy"
    LESSON_PENDING_QUERY = "lesson_pending_query"
    LESSON_ACCEPTED_QUERY = "lesson_accepted_query"
    LESSON_ACCEPT = "lesson_accept"
    LESSON_REJECT = "lesson_reject"
    LESSON_RULE_SUGGEST = "lesson_rule_suggest"
    ADD_RUNNER_RULE = "add_runner_rule"
    PAPER_ELIGIBILITY_BLOCKERS = "paper_eligibility_blockers"
    LESSON_STRATEGY_UPDATE = "lesson_strategy_update"
    LESSON_CREATE_VERSION = "lesson_create_version"
    LESSON_STRATEGY_LINKED = "lesson_strategy_linked"
    LESSON_UNRESOLVED_BLOCKERS = "lesson_unresolved_blockers"
    BACKTEST_PREP = "backtest_prep"
    PAPER_VALIDATION_START = "paper_validation_start"
    PAPER_VALIDATION_SCAN = "paper_validation_scan"
    PAPER_VALIDATION_QUERY = "paper_validation_query"
    PAPER_VALIDATION_RECOMMEND = "paper_validation_recommend"
    PAPER_SCHEDULER_QUERY = "paper_scheduler_query"
    PAPER_ALERTS_QUERY = "paper_alerts_query"
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
