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
from app.schemas.trade_plan import (
    AccountMode,
    AuthorizationChannel,
    AuthorizationState,
    CanonicalModel,
    ExecutionMode,
    PlanOperation,
)


class ApprovalAuthorizationAssertion(StrictModel):
    """Optional redundant caller assertions; none can override persisted plan semantics."""

    organization_id: UUID
    user_id: UUID
    account_id: UUID
    exchange_account_id: UUID | None
    operation: PlanOperation
    plan_id: UUID
    revision_id: UUID
    plan_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ApprovalAuthorizationContent(CanonicalModel):
    """Immutable issuance content; lifecycle updates never rewrite this hash preimage."""

    authorization_id: UUID
    approval_request_id: UUID
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    exchange_account_id: UUID | None
    operation: PlanOperation
    execution_mode: ExecutionMode
    plan_id: UUID
    revision_id: UUID
    plan_content_hash: str
    execution_venue: str
    execution_instrument: str
    verified_account_mode: AccountMode
    permission_attestation_id: UUID
    permission_attestation_version: str
    expires_at: datetime
    state: AuthorizationState
    channel: AuthorizationChannel
    actor_type: str
    actor_id: UUID
    created_at: datetime


class ApprovalAuthorization(ApprovalAuthorizationContent):
    """One exact paper authorization issued for an immutable plan revision."""

    consumed_at: datetime | None
    consumed_by_execution_command_id: UUID | None
    authorization_content_hash: str


class ApprovalDecisionRequest(StrictModel):
    """A human decision on a pending proposal."""

    action: ApprovalAction
    reason: str | None = Field(default=None, max_length=2000)
    modified_fields: dict[str, str] | None = Field(
        default=None, description="Field overrides when action is 'modify'."
    )
    authorization_assertion: ApprovalAuthorizationAssertion | None = None


class ApprovalActionRequest(StrictModel):
    """Simplified body for dedicated approval action routes."""

    reason: str | None = Field(default=None, max_length=2000)
    modified_fields: dict[str, str] | None = None
    authorization_assertion: ApprovalAuthorizationAssertion | None = None


class PlanApprovalRequestCreate(StrictModel):
    """Create a pending human decision for one exact executable revision."""

    authorization_expires_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=2000)


class ApprovalRequest(ORMModel):
    """Persisted approval record tied to a proposal."""

    id: UUID
    proposal_id: UUID
    plan_revision_id: UUID | None = None
    organization_id: UUID
    user_id: UUID
    status: ApprovalStatus = ApprovalStatus.PENDING
    proposed_action: ApprovalAction | None = None
    modified_fields: dict[str, str] | None = None
    risk_level: RiskSeverity
    confidence: Confidence
    approval_reason: str | None = None
    audit_event_id: UUID | None = None
    authorization_expires_at: datetime | None = None
    authorization: ApprovalAuthorization | None = None
    created_at: datetime
    decided_at: datetime | None = None


class PaginatedApprovalRequests(StrictModel):
    items: list[ApprovalRequest]
    total: int
    limit: int
    offset: int
