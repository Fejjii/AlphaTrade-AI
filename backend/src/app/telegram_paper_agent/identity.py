"""Deterministic paper-notification identity. Duplicate events converge."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid5

from app.services.canonical_serialization import canonical_sha256
from app.telegram_paper_agent.contracts import (
    PAPER_NOTIFICATION_SCHEMA,
    PaperNotificationKind,
)

PAPER_NOTIFY_IDENTITY_NAMESPACE = UUID("9e8d7c6b-5a4f-4011-8011-abcdef000001")
PAPER_NOTIFY_REVISION_NAMESPACE = UUID("9e8d7c6b-5a4f-4011-8011-abcdef000002")
PAPER_THREAD_NAMESPACE = UUID("9e8d7c6b-5a4f-4011-8011-abcdef000003")
PAPER_CONFIRM_NAMESPACE = UUID("9e8d7c6b-5a4f-4011-8011-abcdef000004")


def paper_notification_preimage(
    *,
    organization_id: UUID,
    user_id: UUID,
    account_id: UUID,
    kind: PaperNotificationKind,
    resource_type: str,
    resource_id: UUID,
    content_hash: str,
) -> dict[str, Any]:
    return {
        "account_id": str(account_id),
        "content_hash": content_hash,
        "kind": kind.value,
        "organization_id": str(organization_id),
        "resource_id": str(resource_id),
        "resource_type": resource_type,
        "schema": PAPER_NOTIFICATION_SCHEMA,
        "user_id": str(user_id),
    }


def build_paper_notification_identity(
    *,
    organization_id: UUID,
    user_id: UUID,
    account_id: UUID,
    kind: PaperNotificationKind,
    resource_type: str,
    resource_id: UUID,
    content_hash: str,
) -> tuple[UUID, str]:
    digest = canonical_sha256(
        paper_notification_preimage(
            organization_id=organization_id,
            user_id=user_id,
            account_id=account_id,
            kind=kind,
            resource_type=resource_type,
            resource_id=resource_id,
            content_hash=content_hash,
        )
    )
    return uuid5(PAPER_NOTIFY_IDENTITY_NAMESPACE, digest), digest


def paper_telegram_revision_id(*, resource_id: UUID, content_hash: str) -> UUID:
    return uuid5(PAPER_NOTIFY_REVISION_NAMESPACE, f"{resource_id}:{content_hash}")


def paper_thread_id(
    *,
    organization_id: UUID,
    binding_id: UUID,
    resource_type: str,
    resource_id: UUID | None,
) -> UUID:
    suffix = "none" if resource_id is None else str(resource_id)
    return uuid5(
        PAPER_THREAD_NAMESPACE,
        f"{organization_id}:{binding_id}:{resource_type}:{suffix}",
    )


def paper_confirmation_id(*, thread_id: UUID, action: str, payload_hash: str) -> UUID:
    return uuid5(PAPER_CONFIRM_NAMESPACE, f"{thread_id}:{action}:{payload_hash}")
