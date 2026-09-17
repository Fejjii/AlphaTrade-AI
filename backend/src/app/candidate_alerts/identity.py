"""Deterministic CandidateAlertIntent identity.

Duplicate semantic Candidate events converge to one identity hash. A changed
lifecycle revision or candidate content hash produces a distinct identity and
must not reuse an older outbox alert.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid5

from app.candidate_alerts.contracts import (
    CANDIDATE_ALERT_SCHEMA,
    CandidateAlertKind,
    DeliveryChannel,
)
from app.services.canonical_serialization import canonical_sha256

# Stable namespaces. Distinct from candidate lifecycle identity (a11fa7de-...).
CANDIDATE_ALERT_IDENTITY_NAMESPACE = UUID("7e1e6a11-a1e7-4000-8000-c4ad1da7e001")
CANDIDATE_ALERT_REVISION_NAMESPACE = UUID("7e1e6a11-a1e7-4000-8000-c4ad1da7e002")
RISK_REDUCTION_INTENT_NAMESPACE = UUID("7e1e6a11-a1e7-4000-8000-c4ad1da7e003")


def candidate_alert_identity_preimage(
    *,
    organization_id: UUID,
    user_id: UUID,
    account_id: UUID | None,
    candidate_id: UUID,
    candidate_content_hash: str,
    strategy_version_id: UUID,
    compiled_setup_definition_id: UUID,
    compiled_setup_content_hash: str,
    fusion_policy_version: str,
    evidence_window_hash: str,
    candidate_lifecycle_revision: int,
    alert_kind: CandidateAlertKind,
    delivery_channel: DeliveryChannel,
) -> dict[str, Any]:
    """Canonical identity preimage. Keys are sorted by canonical JSON encoding."""
    return {
        "account_id": None if account_id is None else str(account_id),
        "alert_kind": alert_kind.value,
        "candidate_content_hash": candidate_content_hash,
        "candidate_id": str(candidate_id),
        "candidate_lifecycle_revision": candidate_lifecycle_revision,
        "compiled_setup_content_hash": compiled_setup_content_hash,
        "compiled_setup_definition_id": str(compiled_setup_definition_id),
        "delivery_channel": delivery_channel.value,
        "evidence_window_hash": evidence_window_hash,
        "fusion_policy_version": fusion_policy_version,
        "organization_id": str(organization_id),
        "schema": CANDIDATE_ALERT_SCHEMA,
        "strategy_version_id": str(strategy_version_id),
        "user_id": str(user_id),
    }


def hash_candidate_alert_identity(preimage: dict[str, Any]) -> str:
    return canonical_sha256(preimage)


def candidate_alert_intent_id(identity_hash: str) -> UUID:
    return uuid5(CANDIDATE_ALERT_IDENTITY_NAMESPACE, identity_hash)


def candidate_telegram_revision_id(*, candidate_id: UUID, lifecycle_revision: int) -> UUID:
    """UUID revision bound to Telegram ActionPayload.revision_id."""
    return uuid5(
        CANDIDATE_ALERT_REVISION_NAMESPACE,
        f"{candidate_id}:{lifecycle_revision}",
    )


def risk_reduction_intent_id(*, alert_intent_id: UUID) -> UUID:
    return uuid5(RISK_REDUCTION_INTENT_NAMESPACE, f"{alert_intent_id}:REDUCE_RISK")


def build_candidate_alert_identity(
    *,
    organization_id: UUID,
    user_id: UUID,
    account_id: UUID | None,
    candidate_id: UUID,
    candidate_content_hash: str,
    strategy_version_id: UUID,
    compiled_setup_definition_id: UUID,
    compiled_setup_content_hash: str,
    fusion_policy_version: str,
    evidence_window_hash: str,
    candidate_lifecycle_revision: int,
    alert_kind: CandidateAlertKind = CandidateAlertKind.CANDIDATE_ACTIVE,
    delivery_channel: DeliveryChannel = DeliveryChannel.TELEGRAM,
) -> tuple[UUID, str]:
    """Return ``(intent_id, identity_hash)`` for one semantic Candidate alert."""
    digest = hash_candidate_alert_identity(
        candidate_alert_identity_preimage(
            organization_id=organization_id,
            user_id=user_id,
            account_id=account_id,
            candidate_id=candidate_id,
            candidate_content_hash=candidate_content_hash,
            strategy_version_id=strategy_version_id,
            compiled_setup_definition_id=compiled_setup_definition_id,
            compiled_setup_content_hash=compiled_setup_content_hash,
            fusion_policy_version=fusion_policy_version,
            evidence_window_hash=evidence_window_hash,
            candidate_lifecycle_revision=candidate_lifecycle_revision,
            alert_kind=alert_kind,
            delivery_channel=delivery_channel,
        )
    )
    return candidate_alert_intent_id(digest), digest
