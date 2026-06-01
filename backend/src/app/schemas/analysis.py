"""Structured trading analysis response fields for agent output."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import RiskSeverity, StrictModel


class TradingAnalysisDetail(StrictModel):
    """Structured trading response — built deterministically, never raw LLM-only."""

    summary: str
    setup_type: str | None = None
    evidence: list[str] = Field(default_factory=list)
    risk_level: RiskSeverity | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    invalidation: str | None = None
    stop_loss_or_no_trade_reason: str
    approval_status: str = Field(description="pending | not_required | blocked")
    next_decision_point: str | None = None
    paper_mode_disclaimer: str | None = None
    market_data_quality: str = Field(
        default="mock",
        description="mock | stale | missing | live — transparency for market data source",
    )
