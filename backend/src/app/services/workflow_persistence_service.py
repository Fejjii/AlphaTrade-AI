"""Persist agent trading outcomes through service boundaries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.schemas.agent import AgentState
from app.schemas.common import RiskAction, SafetyVerdict
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.proposal_service import ProposalService


@dataclass(frozen=True)
class PersistedWorkflow:
    proposal_id: uuid.UUID | None = None
    approval_id: uuid.UUID | None = None


class WorkflowPersistenceService:
    """Coordinate proposal and approval persistence after agent runs."""

    def __init__(self, session: Session, audit_service: AuditService) -> None:
        self._proposals = ProposalService(session, audit_service)
        self._approvals = ApprovalService(session, audit_service)

    def persist_agent_outcome(self, agent: AgentState) -> PersistedWorkflow:
        if agent.trade_proposal is None:
            return PersistedWorkflow()
        if agent.safety_verdict is SafetyVerdict.BLOCK:
            return PersistedWorkflow()
        if agent.risk_result and agent.risk_result.action is RiskAction.BLOCK:
            return PersistedWorkflow()

        proposal = self._proposals.create_from_agent(agent)
        if proposal is None or proposal.id is None:
            return PersistedWorkflow()

        approval_id: uuid.UUID | None = None
        if agent.approval_required:
            approval = self._approvals.create_for_proposal(
                proposal_id=proposal.id,
                organization_id=proposal.organization_id,
                user_id=proposal.user_id,
                risk_level=proposal.risk_level,
                confidence=float(proposal.confidence),
                approval_reason=agent.approval_reason,
            )
            approval_id = approval.id

        return PersistedWorkflow(proposal_id=proposal.id, approval_id=approval_id)
