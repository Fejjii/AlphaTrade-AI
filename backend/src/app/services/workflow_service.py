"""Workflow views linking proposals, approvals, and paper execution eligibility."""

from __future__ import annotations

import uuid

from app.core.errors import NotFoundError
from app.schemas.workflow import ApprovalWorkflowView, ProposalWorkflowView
from app.services.approval_service import ApprovalService
from app.services.execution_eligibility import paper_execution_eligibility
from app.services.proposal_service import ProposalService


class WorkflowService:
    def __init__(
        self,
        proposal_service: ProposalService,
        approval_service: ApprovalService,
    ) -> None:
        self._proposals = proposal_service
        self._approvals = approval_service

    def get_proposal_workflow(self, proposal_id: uuid.UUID) -> ProposalWorkflowView:
        proposal = self._proposals.get(proposal_id)
        approval = self._approvals.get_by_proposal(proposal_id)
        can_execute, block_reason = paper_execution_eligibility(proposal, approval)
        return ProposalWorkflowView(
            proposal=proposal,
            approval=approval,
            can_execute_paper=can_execute,
            block_reason=block_reason,
        )

    def get_approval_workflow(self, approval_id: uuid.UUID) -> ApprovalWorkflowView:
        approval = self._approvals.get(approval_id)
        try:
            proposal = self._proposals.get(approval.proposal_id)
        except NotFoundError:
            proposal = None
        can_execute, block_reason = (
            paper_execution_eligibility(proposal, approval)
            if proposal is not None
            else (False, "Linked proposal not found.")
        )
        return ApprovalWorkflowView(
            approval=approval,
            proposal=proposal,
            can_execute_paper=can_execute,
            block_reason=block_reason,
        )
