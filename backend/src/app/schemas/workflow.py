"""End-to-end workflow view schemas (Slice 20)."""

from __future__ import annotations

from app.schemas.approval import ApprovalRequest
from app.schemas.common import StrictModel
from app.schemas.proposal import TradeProposal


class ProposalWorkflowView(StrictModel):
    proposal: TradeProposal
    approval: ApprovalRequest | None = None
    can_execute_paper: bool = False
    block_reason: str | None = None


class ApprovalWorkflowView(StrictModel):
    approval: ApprovalRequest
    proposal: TradeProposal | None = None
    can_execute_paper: bool = False
    block_reason: str | None = None
