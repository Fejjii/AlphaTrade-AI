"""Paper-signal orchestration schemas (AT-038 — paper-only)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import (
    PaperSignalOrchestrationMode,
    PaperSignalOrchestrationStatus,
)

APPROVE_PAPER_SIGNAL_PROPOSAL_CONFIRM = "APPROVE_PAPER_SIGNAL_PROPOSAL"


class EligibilityCheck(BaseModel):
    code: str
    passed: bool
    detail: str


class PaperSignalOrchestrationLinks(BaseModel):
    tradingview_signal_id: uuid.UUID
    setup_definition_id: uuid.UUID | None = None
    strategy_id: uuid.UUID | None = None
    strategy_version_id: uuid.UUID | None = None
    journal_trade_id: uuid.UUID | None = None
    backtest_run_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None
    run_plan_id: uuid.UUID | None = None
    proposal_id: uuid.UUID | None = None
    signal_path: str | None = None
    candidate_path: str | None = None
    run_plan_path: str | None = None
    proposal_path: str | None = None
    journal_path: str | None = None


class PaperSignalOrchestrationTransition(BaseModel):
    at: datetime
    from_status: str | None
    to_status: str
    reason: str
    actor_user_id: uuid.UUID | None = None


class PaperSignalOrchestrationDecisionItem(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    tradingview_signal_id: uuid.UUID
    idempotency_key: str
    status: PaperSignalOrchestrationStatus
    mode: PaperSignalOrchestrationMode
    symbol: str
    timeframe: str
    direction: str
    reason_codes: list[str] | None = None
    reason_summary: str | None = None
    eligibility_checks: list[EligibilityCheck]
    risk_checks: list[EligibilityCheck]
    transitions: list[PaperSignalOrchestrationTransition]
    links: PaperSignalOrchestrationLinks
    decided_by: uuid.UUID | None = None
    approved_by: uuid.UUID | None = None
    decided_at: datetime
    expired_at: datetime | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    note: str = (
        "Paper-signal orchestration only. Never creates live orders or bypasses "
        "risk / kill-switch / approval controls."
    )


class PaperSignalOrchestrationListResponse(BaseModel):
    items: list[PaperSignalOrchestrationDecisionItem]
    total: int
    limit: int
    offset: int
    mode: PaperSignalOrchestrationMode
    enabled: bool


class PaperSignalOrchestrationEvaluateResult(BaseModel):
    decision: PaperSignalOrchestrationDecisionItem
    already_exists: bool = False
    note: str = "Evaluation only. Side effects depend on configured orchestration mode."


class PaperSignalOrchestrationApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: str = Field(min_length=1, max_length=80)


class PaperSignalOrchestrationApproveResult(BaseModel):
    decision: PaperSignalOrchestrationDecisionItem
    proposal_id: uuid.UUID
    already_exists: bool = False
    note: str = (
        "Paper proposal created via approval-gated pathway. Does not place live or "
        "paper orders automatically."
    )
