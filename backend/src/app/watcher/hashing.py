"""Canonical hashes for scan requests, policies, and evaluation inputs."""

from __future__ import annotations

from typing import Any

from app.services.canonical_serialization import canonical_sha256
from app.watcher.contracts import (
    WATCHER_EVALUATION_INPUT_SCHEMA,
    WATCHER_POLICY_VERSION_SCHEMA,
    WATCHER_SCAN_REQUEST_SCHEMA,
    ScanRequest,
    WatcherPolicyVersion,
)


def policy_content_hash(version: WatcherPolicyVersion) -> str:
    """Hash immutable policy semantics; exclude created_at and confirmation actor."""

    payload: dict[str, Any] = {
        "schema_version": WATCHER_POLICY_VERSION_SCHEMA,
        "policy_id": str(version.identity.policy_id),
        "organization_id": str(version.identity.organization_id),
        "user_id": str(version.identity.user_id),
        "watchlist_item_id": str(version.identity.watchlist_item_id),
        "timeframe": version.timeframe,
        "strategy_version_id": _opt_uuid(version.strategy_version_id),
        "setup_definition_id": _opt_uuid(version.setup_definition_id),
        "fusion_policy_version": version.fusion_policy_version,
        "alert_threshold": version.alert_threshold,
        "delivery_policy_id": _opt_uuid(version.delivery_policy_id),
        "enabled": version.enabled,
    }
    return canonical_sha256(payload)


def scan_request_hash(request: ScanRequest) -> str:
    """Semantic request hash. Excludes the opaque idempotency key."""

    payload: dict[str, Any] = {
        "schema_version": WATCHER_SCAN_REQUEST_SCHEMA,
        "organization_id": str(request.organization_id),
        "principal_id": _opt_uuid(request.principal_id),
        "scan_scope": request.scan_scope,
        "policy_id": str(request.policy_id),
        "policy_version": request.policy_version,
        "policy_content_hash": request.policy_content_hash,
        "watchlist_item_ids": sorted(str(item) for item in request.watchlist_item_ids),
        "timeframe": request.timeframe,
        "source_context_id": _opt_uuid(request.source_context_id),
    }
    return canonical_sha256(payload)


def evaluation_input_hash(request: ScanRequest) -> str:
    """Hash shared by manual and worker evaluation.

    Excludes trigger, mode, lease, principal, and the opaque idempotency key so
    both callers can present the same semantic evaluation input.
    """

    payload: dict[str, Any] = {
        "schema_version": WATCHER_EVALUATION_INPUT_SCHEMA,
        "organization_id": str(request.organization_id),
        "scan_scope": request.scan_scope,
        "policy_id": str(request.policy_id),
        "policy_version": request.policy_version,
        "policy_content_hash": request.policy_content_hash,
        "watchlist_item_ids": sorted(str(item) for item in request.watchlist_item_ids),
        "timeframe": request.timeframe,
        "source_context_id": _opt_uuid(request.source_context_id),
    }
    return canonical_sha256(payload)


def derive_scan_scope(*, organization_id: object, policy_id: object, timeframe: str | None) -> str:
    tf = timeframe if timeframe else "*"
    return f"{organization_id}:{policy_id}:{tf}"


def _opt_uuid(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)
