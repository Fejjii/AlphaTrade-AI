"""Human approval workflow."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import ApprovalRequest as ApprovalModel
from app.repositories.approvals import ApprovalRepository
from app.repositories.proposals import ProposalRepository
from app.schemas.approval import ApprovalDecisionRequest, ApprovalRequest
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    ApprovalAction,
    ApprovalStatus,
    AuditEventType,
    ProposalStatus,
    RiskSeverity,
)
from app.services.audit_service import AuditService


class ApprovalService:
    def __init__(self, session: Session, audit_service: AuditService) -> None:
        self._session = session
        self._repo = ApprovalRepository(session)
        self._proposals = ProposalRepository(session)
        self._audit = audit_service

    def create_for_proposal(
        self,
        *,
        proposal_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        risk_level: RiskSeverity,
        confidence: float,
        approval_reason: str | None = None,
    ) -> ApprovalRequest:
        existing = self._repo.get_by_proposal(proposal_id)
        if existing is not None:
            return _to_schema(existing)
        row = ApprovalModel(
            proposal_id=proposal_id,
            organization_id=organization_id,
            user_id=user_id,
            risk_level=risk_level,
            confidence=confidence,
            approval_reason=approval_reason,
        )
        self._repo.add(row)
        proposal = self._proposals.get(proposal_id)
        if proposal is not None:
            proposal.status = ProposalStatus.PENDING_APPROVAL
            self._proposals.add(proposal)
        self._record_audit(
            AuditEventType.APPROVAL_REQUIRED,
            organization_id=organization_id,
            user_id=user_id,
            resource_id=str(row.id),
            metadata={"proposal_id": str(proposal_id), "reason": approval_reason},
        )
        return _to_schema(row)

    def get(self, approval_id: uuid.UUID) -> ApprovalRequest:
        row = self._repo.get(approval_id)
        if row is None:
            raise NotFoundError("Approval not found")
        return _to_schema(row)

    def get_by_proposal(self, proposal_id: uuid.UUID) -> ApprovalRequest | None:
        row = self._repo.get_by_proposal(proposal_id)
        if row is None:
            return None
        return _to_schema(row)

    def list_approvals(
        self,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        status: ApprovalStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApprovalRequest], int]:
        rows, total = self._repo.list_approvals(
            organization_id=organization_id,
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [_to_schema(row) for row in rows], total

    def decide(self, approval_id: uuid.UUID, decision: ApprovalDecisionRequest) -> ApprovalRequest:
        row = self._repo.get(approval_id)
        if row is None:
            raise NotFoundError("Approval not found")
        if row.status is not ApprovalStatus.PENDING:
            raise ValidationAppError(
                "Approval is not pending",
                details={"current_status": row.status.value},
            )
        row.status = _action_to_status(decision.action)
        row.proposed_action = decision.action
        row.modified_fields = decision.modified_fields
        row.approval_reason = decision.reason
        row.decided_at = datetime.now(UTC)
        self._repo.add(row)

        proposal = self._proposals.get(row.proposal_id)
        if proposal is not None:
            proposal.status = _proposal_status_for_action(decision.action)
            self._proposals.add(proposal)

        audit_record = self._record_audit(
            AuditEventType.APPROVAL_DECISION,
            organization_id=row.organization_id,
            user_id=row.user_id,
            resource_id=str(row.id),
            metadata={
                "action": decision.action.value,
                "proposal_id": str(row.proposal_id),
                "modified_fields": decision.modified_fields or {},
            },
        )
        if audit_record is not None:
            row.audit_event_id = audit_record.event_id
            self._repo.add(row)
        return _to_schema(row)

    def _record_audit(self, event_type: AuditEventType, **fields: object):
        return self._audit.record(
            AuditRecordCreate(
                request_id="approval-api",
                trace_id="approval-api",
                event_type=event_type,
                resource_type="approval",
                resource_id=str(fields["resource_id"]),
                organization_id=fields["organization_id"],  # type: ignore[arg-type]
                user_id=fields["user_id"],  # type: ignore[arg-type]
                actor_type=ActorType.USER,
                metadata=fields.get("metadata", {}),  # type: ignore[arg-type]
            )
        )


def _action_to_status(action: ApprovalAction) -> ApprovalStatus:
    mapping = {
        ApprovalAction.APPROVE: ApprovalStatus.APPROVED,
        ApprovalAction.REJECT: ApprovalStatus.REJECTED,
        ApprovalAction.MODIFY: ApprovalStatus.MODIFIED,
        ApprovalAction.PAUSE: ApprovalStatus.PAUSED,
        ApprovalAction.CANCEL: ApprovalStatus.CANCELLED,
        ApprovalAction.CLOSE: ApprovalStatus.CLOSED,
        ApprovalAction.NEEDS_MORE_ANALYSIS: ApprovalStatus.NEEDS_MORE_ANALYSIS,
    }
    return mapping[action]


def _proposal_status_for_action(action: ApprovalAction) -> ProposalStatus:
    if action is ApprovalAction.APPROVE:
        return ProposalStatus.APPROVED
    if action is ApprovalAction.REJECT:
        return ProposalStatus.REJECTED
    if action is ApprovalAction.MODIFY:
        return ProposalStatus.PENDING_APPROVAL
    return ProposalStatus.PENDING_APPROVAL


def _to_schema(row: ApprovalModel) -> ApprovalRequest:
    return ApprovalRequest(
        id=row.id,
        proposal_id=row.proposal_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        status=row.status,
        proposed_action=row.proposed_action,
        modified_fields=row.modified_fields,
        risk_level=row.risk_level,
        confidence=row.confidence,
        approval_reason=row.approval_reason,
        audit_event_id=row.audit_event_id,
        created_at=row.created_at,
        decided_at=row.decided_at,
    )
