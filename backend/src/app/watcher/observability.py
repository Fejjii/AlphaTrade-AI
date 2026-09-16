"""Structured watcher orchestration observability. No secrets."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog

from app.watcher.contracts import WatcherObservabilityEvent
from app.watcher.ports import WatcherStore

logger = structlog.get_logger("watcher.orchestration")


def emit(
    store: WatcherStore,
    *,
    name: str,
    at: datetime,
    lineage_id: UUID | None = None,
    attempt_id: UUID | None = None,
    organization_id: UUID | None = None,
    scan_scope: str | None = None,
    fencing_token: int | None = None,
    **fields: str | int | bool | None,
) -> None:
    event = WatcherObservabilityEvent(
        name=name,
        at=at,
        lineage_id=lineage_id,
        attempt_id=attempt_id,
        organization_id=organization_id,
        scan_scope=scan_scope,
        fencing_token=fencing_token,
        fields=dict(fields),
    )
    store.append_event(event)
    logger.info(
        name,
        lineage_id=None if lineage_id is None else str(lineage_id),
        attempt_id=None if attempt_id is None else str(attempt_id),
        organization_id=None if organization_id is None else str(organization_id),
        scan_scope=scan_scope,
        fencing_token=fencing_token,
        **fields,
    )
