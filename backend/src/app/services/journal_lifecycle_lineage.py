"""Sticky Candidate/plan lineage on journal lifecycle payloads.

Record-only. Does not create JournalTrade, Candidates, or TradePlans. Nested
``payload.lineage`` is the Phase 7 contract so Agent 1 can later persist columns
without a competing identity system.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from app.core.errors import JournalProjectionConflictError, ValidationAppError
from app.schemas.journal_lifecycle import (
    LINEAGE_PAYLOAD_KEY,
    LINEAGE_STICKY_KEYS,
    JournalLifecycleEventInput,
    JournalLineagePayload,
)

_SCOPE_KEYS = frozenset({"organization_id", "account_id", "execution_lifecycle_id"})


def extract_lineage_map(payload: Mapping[str, object]) -> dict[str, str]:
    """Return canonical string values from nested ``payload.lineage``."""
    raw = payload.get(LINEAGE_PAYLOAD_KEY)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValidationAppError(
            "Journal lineage payload must be an object.",
            details={"reason": "invalid_lineage_payload"},
        )
    parsed = JournalLineagePayload.model_validate(raw)
    dumped = parsed.model_dump(mode="json", exclude_none=True)
    extracted: dict[str, str] = {}
    for key in LINEAGE_STICKY_KEYS:
        value = dumped.get(key)
        if value is None:
            continue
        extracted[key] = str(value)
    return extracted


def assert_lineage_matches_event_scope(
    event: JournalLifecycleEventInput,
    *,
    organization_id: UUID,
) -> None:
    """Fail closed when nested lineage disagrees with the projector scope."""
    incoming = extract_lineage_map(event.payload)
    if not incoming:
        return
    org = incoming.get("organization_id")
    if org is not None and org != str(organization_id):
        raise JournalProjectionConflictError(
            "Journal lineage belongs to a different organization.",
            details={
                "reason": "cross_tenant_lineage",
                "organization_id": str(organization_id),
            },
        )
    account = incoming.get("account_id")
    if account is not None and account != str(event.account_id):
        raise JournalProjectionConflictError(
            "Journal lineage belongs to a different account.",
            details={
                "reason": "lineage_account_mismatch",
                "account_id": str(event.account_id),
            },
        )
    lifecycle = incoming.get("execution_lifecycle_id")
    event_lifecycle = (
        str(event.execution_lifecycle_id) if event.execution_lifecycle_id is not None else None
    )
    if lifecycle is not None and event_lifecycle is not None and lifecycle != event_lifecycle:
        raise JournalProjectionConflictError(
            "Journal lineage execution lifecycle does not match the event.",
            details={
                "reason": "lineage_lifecycle_mismatch",
                "execution_lifecycle_id": event_lifecycle,
            },
        )


def assert_sticky_lineage(
    stored: Mapping[str, str],
    incoming: Mapping[str, str],
    event: JournalLifecycleEventInput,
) -> None:
    """First-seen lineage values are immutable for the execution lifecycle."""
    if not incoming or not stored:
        return
    conflicts = {
        key: {"stored": stored[key], "incoming": incoming[key]}
        for key in LINEAGE_STICKY_KEYS
        if key in stored and key in incoming and stored[key] != incoming[key]
    }
    if not conflicts:
        return
    raise JournalProjectionConflictError(
        "Journal lifecycle lineage conflict.",
        details={
            "reason": "conflicting_lineage_identity",
            "source_system": event.source_system,
            "source_aggregate": event.source_aggregate,
            "source_event_id": event.source_event_id,
            "conflicts": conflicts,
        },
    )


def merge_lineage_maps(*maps: Mapping[str, str]) -> dict[str, str]:
    """Combine lineage maps; identical values converge, conflicts fail closed."""
    merged: dict[str, str] = {}
    for item in maps:
        for key, value in item.items():
            existing = merged.get(key)
            if existing is not None and existing != value:
                raise JournalProjectionConflictError(
                    "Journal lifecycle lineage conflict.",
                    details={
                        "reason": "conflicting_lineage_identity",
                        "key": key,
                        "stored": existing,
                        "incoming": value,
                    },
                )
            merged[key] = value
    return merged


def scope_lineage_values(values: Mapping[str, str]) -> dict[str, str]:
    """Return only tenant/account/lifecycle identity keys."""
    return {key: value for key, value in values.items() if key in _SCOPE_KEYS}
