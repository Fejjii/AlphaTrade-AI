"""Audit event schemas for observability and compliance-style review."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    ORMModel,
    StrictModel,
)


class AuditRecordCreate(StrictModel):
    """Input for recording an auditable event."""

    request_id: str
    trace_id: str
    event_type: AuditEventType
    resource_type: str
    actor_type: ActorType = ActorType.SYSTEM
    action: str | None = Field(
        default=None,
        description="Optional action label; defaults to event_type value.",
    )
    result: AuditResult = AuditResult.SUCCESS
    severity: AuditSeverity = AuditSeverity.INFO
    user_id: UUID | None = None
    organization_id: UUID | None = None
    resource_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None


class AuditRecord(ORMModel):
    """Persisted audit record returned by APIs and services."""

    event_id: UUID
    request_id: str
    trace_id: str
    user_id: UUID | None = None
    organization_id: UUID | None = None
    event_type: AuditEventType
    resource_type: str
    resource_id: str | None = None
    actor_type: ActorType
    action: str
    result: AuditResult
    severity: AuditSeverity
    payload_hash: str
    redacted_metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class AuditEvent(ORMModel):
    """Legacy in-graph audit event (mapped to :class:`AuditRecord` on persist)."""

    id: UUID | None = None
    organization_id: UUID | None = None
    user_id: UUID | None = None
    actor: str = Field(description="Who/what initiated the action (user id or 'system').")
    action: AuditEventType
    resource_type: str
    resource_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    request_id: str | None = None
    trace_id: str | None = None
    timestamp: datetime


class PaginatedAuditRecords(StrictModel):
    items: list[AuditRecord]
    total: int
    limit: int
    offset: int
