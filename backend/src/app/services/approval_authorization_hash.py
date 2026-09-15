"""Immutable issuance hashing for approval authorizations."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime

from app.schemas.approval import ApprovalAuthorization, ApprovalAuthorizationIssuance
from app.services.canonical_serialization import canonical_sha256


def authorization_issuance(
    authorization: ApprovalAuthorization,
) -> ApprovalAuthorizationIssuance:
    """Project an authorization onto immutable issuance fields only."""
    values = {
        name: getattr(authorization, name) for name in ApprovalAuthorizationIssuance.model_fields
    }
    values["created_at"] = _aware(authorization.created_at)
    values["expires_at"] = _aware(authorization.expires_at)
    return ApprovalAuthorizationIssuance.model_validate(values)


def verify_authorization_issuance_hash(authorization: ApprovalAuthorization) -> bool:
    """Verify the issuance hash independently of mutable lifecycle state."""
    return hmac.compare_digest(
        canonical_sha256(authorization_issuance(authorization)),
        authorization.authorization_content_hash,
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
