"""Account lifecycle schemas: verification, password reset, invitations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import MembershipRole, ORMModel, StrictModel


class MessageResponse(ORMModel):
    message: str


class VerifyEmailRequest(StrictModel):
    """Optional email for unauthenticated resend; authenticated users use profile email."""

    email: EmailStr | None = None


class VerifyEmailConfirmRequest(StrictModel):
    token: str = Field(min_length=20, max_length=512)


class PasswordResetRequest(StrictModel):
    email: EmailStr


class PasswordResetConfirmRequest(StrictModel):
    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=12, max_length=128)


class CreateInvitationRequest(StrictModel):
    email: EmailStr
    role: MembershipRole = MembershipRole.TRADER


class AcceptInvitationRequest(StrictModel):
    token: str = Field(min_length=20, max_length=512)


class OrganizationInvitationView(ORMModel):
    id: UUID
    organization_id: UUID
    email: EmailStr
    role: MembershipRole
    invited_by_user_id: UUID
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    is_pending: bool = False


class InvitationListResponse(ORMModel):
    invitations: list[OrganizationInvitationView] = Field(default_factory=list)
