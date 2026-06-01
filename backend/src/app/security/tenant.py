"""Tenant context resolved from authenticated requests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.errors import ForbiddenError
from app.schemas.common import MembershipRole


@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    membership_role: MembershipRole


def ensure_same_organization(resource_org_id: uuid.UUID, tenant: TenantContext) -> None:
    if resource_org_id != tenant.organization_id:
        raise ForbiddenError("Resource not found.")
