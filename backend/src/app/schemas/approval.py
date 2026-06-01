"""Human-in-the-loop approval schemas.

Every sensitive action routes through an approval record. Low-confidence,
high-impact recommendations always require approval (master prompt §16).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    ApprovalAction,
    ApprovalStatus,
    Confidence,
    ORMModel,
    RiskSeverity,
    StrictModel,
)


class ApprovalDecisionRequest(StrictModel):
    """A human decision on a pending proposal."""

    action: ApprovalAction
    reason: str | None = Field(default=None, max_length=2000)
    modified_fields: dict[str, str] | None = Field(
        default=None, description="Field overrides when action is 'modify'."
    )


class ApprovalActionRequest(StrictModel):
    """Simplified body for dedicated approval action routes."""

    reason: str | None = Field(default=None, max_length=2000)
    modified_fields: dict[str, str] | None = None


class ApprovalRequest(ORMModel):
    """Persisted approval record tied to a proposal."""

    id: UUID
    proposal_id: UUID
    organization_id: UUID
    user_id: UUID
    status: ApprovalStatus = ApprovalStatus.PENDING
    proposed_action: ApprovalAction | None = None
    modified_fields: dict[str, str] | None = None
    risk_level: RiskSeverity
    confidence: Confidence
    approval_reason: str | None = None
    audit_event_id: UUID | None = None
    created_at: datetime
    decided_at: datetime | None = None


class PaginatedApprovalRequests(StrictModel):
    items: list[ApprovalRequest]
    total: int
    limit: int
    offset: int
