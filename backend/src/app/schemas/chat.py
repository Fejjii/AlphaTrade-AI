"""Chat API schemas for the agent workspace."""

from __future__ import annotations

from pydantic import Field

from app.schemas.analysis import TradingAnalysisDetail
from app.schemas.common import ORMModel, RiskSeverity, StrictModel
from app.schemas.narrative import NarrativeMetadata, TradingNarrativeDetail
from app.schemas.rag import Citation
from app.schemas.risk import RiskCheckResult
from app.schemas.tools import ToolOutput
from app.schemas.usage import UsageEvent


class ChatMessageRequest(StrictModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = None
    symbol: str | None = None
    timeframe: str | None = None


class AgentMessageResponse(StrictModel):
    """Structured agent response (Slice 9)."""

    conversation_id: str
    request_id: str
    reply: str
    risk_level: RiskSeverity | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    approval_required: bool = False
    approval_status: str = Field(
        description="pending | not_required | blocked",
    )
    approval_reason: str | None = None
    proposal_id: str | None = None
    approval_id: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    tool_outputs: list[ToolOutput] = Field(default_factory=list)
    risk_result: RiskCheckResult | None = None
    limitations: list[str] = Field(default_factory=list)
    usage: UsageEvent | None = None
    analysis: TradingAnalysisDetail | None = None
    narrative: TradingNarrativeDetail | None = None
    narrative_meta: NarrativeMetadata | None = None


class ChatMessageResponse(ORMModel):
    """Alias response for backward-compatible route name."""

    conversation_id: str
    reply: str
    approval_required: bool = False
