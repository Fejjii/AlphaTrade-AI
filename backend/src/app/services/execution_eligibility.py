"""Paper execution eligibility — shared policy for API and services."""

from __future__ import annotations

from app.schemas.approval import ApprovalRequest
from app.schemas.common import ApprovalStatus, ProposalStatus, RiskAction
from app.schemas.proposal import TradeProposal
from app.schemas.risk import RiskCheckResult


def paper_execution_eligibility(
    proposal: TradeProposal,
    approval: ApprovalRequest | None,
) -> tuple[bool, str | None]:
    """Return whether a paper order may be placed and an optional block reason."""
    if proposal.risk_result is not None:
        risk = RiskCheckResult.model_validate(proposal.risk_result)
        if risk.action is RiskAction.BLOCK:
            return False, "Blocked by risk engine."

    if approval is None:
        if proposal.approval_required:
            return False, "Approval record required before paper execution."
        return True, None

    if approval.proposal_id != proposal.id:
        return False, "Approval does not match proposal."

    if approval.status is not ApprovalStatus.APPROVED:
        return False, (
            f"Approval status is {approval.status.value}; paper execution requires approved."
        )

    if proposal.status is ProposalStatus.REJECTED:
        return False, "Proposal was rejected."

    return True, None
