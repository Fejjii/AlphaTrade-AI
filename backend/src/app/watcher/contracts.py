"""Scan, policy, lease, lineage, health, and evaluation contracts.

This package does not model market freshness, CVD, pattern evaluation, or
candidate lifecycle. Those belong to later agents. Opaque tokens are stored
only so Agent 1 can bind source freshness / evidence validity later.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common import StrictModel

WATCHER_SCAN_REQUEST_SCHEMA: Literal["WatcherScanRequestV1"] = "WatcherScanRequestV1"
WATCHER_POLICY_VERSION_SCHEMA: Literal["WatcherPolicyVersionV1"] = "WatcherPolicyVersionV1"
WATCHER_EVALUATION_INPUT_SCHEMA: Literal["WatcherEvaluationInputV1"] = "WatcherEvaluationInputV1"


class FrozenModel(StrictModel):
    """Immutable contract object."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EvaluationMode(StrEnum):
    PREVIEW = "preview"
    PERSIST_EVIDENCE = "persist_evidence"
    PERSIST_AND_NOTIFY = "persist_and_notify"


class ScanTrigger(StrEnum):
    MANUAL = "manual"
    WORKER = "worker"


class ScanAttemptStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    REJECTED_STALE_FENCE = "rejected_stale_fence"
    CONVERGED_REPLAY = "converged_replay"


class EvaluationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class UnitAttemptKind(StrEnum):
    SOURCE_FETCH = "source_fetch"
    SUBSCRIPTION_EVALUATION = "subscription_evaluation"


class UnitAttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"
    SKIPPED = "skipped"


class WatcherHealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    STALE = "stale"


class ScheduleStatus(StrEnum):
    ACCEPTED = "accepted"
    REPLAYED = "replayed"
    BLOCKED = "blocked"


class WorkerCycleStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    REJECTED_STALE_FENCE = "rejected_stale_fence"


class RecoveryDisposition(StrEnum):
    NONE = "none"
    RETRY = "retry"
    REPLAY = "replay"
    ABANDON_STALE_FENCE = "abandon_stale_fence"


class WatcherPolicyIdentity(FrozenModel):
    """Stable policy identity associated with an existing WatchlistItem id."""

    policy_id: UUID
    organization_id: UUID
    user_id: UUID
    watchlist_item_id: UUID


class WatcherPolicyVersion(FrozenModel):
    """Immutable watchlist policy version. No market-symbol validation here."""

    schema_version: Literal["WatcherPolicyVersionV1"] = WATCHER_POLICY_VERSION_SCHEMA
    identity: WatcherPolicyIdentity
    version: int = Field(ge=1)
    timeframe: str
    strategy_version_id: UUID | None = None
    setup_definition_id: UUID | None = None
    fusion_policy_version: str | None = None
    alert_threshold: str | None = None
    delivery_policy_id: UUID | None = None
    enabled: bool
    created_by: UUID
    confirmed_by: UUID | None = None
    created_at: datetime
    content_hash: str = Field(min_length=64, max_length=64)


class ScanRequest(FrozenModel):
    """Semantic scan request. Opaque idempotency key is not part of the hash."""

    schema_version: Literal["WatcherScanRequestV1"] = WATCHER_SCAN_REQUEST_SCHEMA
    organization_id: UUID
    principal_id: UUID | None = None
    scan_scope: str = Field(min_length=1, max_length=200)
    policy_id: UUID
    policy_version: int = Field(ge=1)
    policy_content_hash: str = Field(min_length=64, max_length=64)
    watchlist_item_ids: tuple[UUID, ...]
    timeframe: str | None = None
    source_context_id: UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("watchlist_item_ids", mode="before")
    @classmethod
    def _tuple_ids(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value


class EvaluationCommand(FrozenModel):
    """Shared manual/worker evaluation command. Scheduling metadata is explicit."""

    command_id: UUID
    request: ScanRequest
    request_hash: str
    evaluation_input_hash: str
    mode: EvaluationMode
    trigger: ScanTrigger
    lineage_id: UUID | None = None
    attempt_id: UUID | None = None
    lease_epoch: int | None = None
    fencing_token: int | None = None
    worker_id: str | None = None
    correlation_id: UUID


class UnitAttempt(FrozenModel):
    """Child attempt emitted by the evaluation boundary; not interpreted here."""

    kind: UnitAttemptKind
    subject_id: UUID
    status: UnitAttemptStatus
    reason_code: str | None = None
    source_freshness_token: str | None = None
    evidence_validity_token: str | None = None
    error: str | None = None


class EvaluationOutcome(FrozenModel):
    command_id: UUID
    request_hash: str
    evaluation_input_hash: str
    status: EvaluationStatus
    reason_code: str
    evaluated_units: int = Field(ge=0, default=0)
    failed_units: int = Field(ge=0, default=0)
    unit_attempts: tuple[UnitAttempt, ...] = ()
    source_freshness_token: str | None = None
    evidence_validity_token: str | None = None
    error: str | None = None
    candidate_ids: tuple[UUID, ...] = ()


class ScanLineage(FrozenModel):
    """Immutable scan lineage root. Attempts append; identity never changes."""

    lineage_id: UUID
    organization_id: UUID
    principal_id: UUID | None
    scan_scope: str
    request_hash: str
    policy_id: UUID
    policy_version: int
    policy_content_hash: str
    trigger_created_by: ScanTrigger
    created_at: datetime
    terminal_attempt_id: UUID | None = None
    terminal_status: ScanAttemptStatus | None = None


class ScanAttempt(FrozenModel):
    attempt_id: UUID
    lineage_id: UUID
    attempt_number: int = Field(ge=1)
    worker_id: str | None
    lease_epoch: int | None
    fencing_token: int | None
    trigger: ScanTrigger
    mode: EvaluationMode
    status: ScanAttemptStatus
    started_at: datetime
    heartbeat_at: datetime
    finished_at: datetime | None = None
    sanitized_error: str | None = None
    recovery_disposition: RecoveryDisposition = RecoveryDisposition.NONE
    recovered_from_attempt_id: UUID | None = None
    outcome_reason_code: str | None = None
    evaluation_input_hash: str | None = None


class SourceFetchAttempt(FrozenModel):
    fetch_attempt_id: UUID
    scan_attempt_id: UUID
    lineage_id: UUID
    lease_epoch: int | None
    fencing_token: int | None
    subject_id: UUID
    status: UnitAttemptStatus
    reason_code: str | None = None
    source_freshness_token: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    sanitized_error: str | None = None


class SubscriptionEvaluationAttempt(FrozenModel):
    subscription_attempt_id: UUID
    scan_attempt_id: UUID
    lineage_id: UUID
    lease_epoch: int | None
    fencing_token: int | None
    subject_id: UUID
    status: UnitAttemptStatus
    reason_code: str | None = None
    evidence_validity_token: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    sanitized_error: str | None = None


class ScheduledScan(FrozenModel):
    scheduled_scan_id: UUID
    organization_id: UUID
    principal_id: UUID | None
    idempotency_key: str
    request_hash: str
    scan_scope: str
    lineage_id: UUID
    created_at: datetime


class WorkerLease(FrozenModel):
    scan_scope: str
    organization_id: UUID
    owner_id: str | None
    lease_epoch: int = Field(ge=0)
    fencing_token: int = Field(ge=0)
    acquired_at: datetime | None = None
    renewed_at: datetime | None = None
    expires_at: datetime | None = None


class LeaseClaimResult(FrozenModel):
    acquired: bool
    lease: WorkerLease
    reason_code: str


class WatcherHeartbeat(FrozenModel):
    organization_id: UUID
    scan_scope: str
    owner_id: str | None
    lease_epoch: int
    fencing_token: int
    last_beat_at: datetime
    detail: str | None = None


class WatcherHealthSnapshot(FrozenModel):
    state: WatcherHealthState
    organization_id: UUID
    scan_scope: str
    enabled: bool
    lease_owner: str | None
    lease_epoch: int
    fencing_token: int
    lease_expires_at: datetime | None
    last_beat_at: datetime | None
    seconds_since_beat: float | None
    last_attempt_status: ScanAttemptStatus | None
    last_lineage_id: UUID | None
    reason_code: str
    generated_at: datetime


class WatcherObservabilityEvent(FrozenModel):
    name: str
    at: datetime
    lineage_id: UUID | None = None
    attempt_id: UUID | None = None
    organization_id: UUID | None = None
    scan_scope: str | None = None
    fencing_token: int | None = None
    fields: dict[str, str | int | bool | None] = Field(default_factory=dict)


class WatcherRuntimeConfig(FrozenModel):
    enabled: bool = False
    lease_ttl_seconds: int = Field(default=30, ge=1, le=3600)
    heartbeat_stale_after_seconds: int = Field(default=90, ge=5, le=3600)


class ScheduleResult(FrozenModel):
    status: ScheduleStatus
    replayed: bool
    scheduled_scan_id: UUID | None
    lineage_id: UUID | None
    request_hash: str | None
    reason_code: str


class EvaluationResult(FrozenModel):
    outcome: EvaluationOutcome
    persisted: bool
    replayed: bool
    lineage_id: UUID | None
    attempt_id: UUID | None
    evaluation_input_hash: str
    reason_code: str


class WorkerCycleResult(FrozenModel):
    status: WorkerCycleStatus
    replayed: bool
    lineage_id: UUID | None
    attempt_id: UUID | None
    request_hash: str | None
    fencing_token: int | None
    lease_epoch: int | None
    outcome: EvaluationOutcome | None
    health: WatcherHealthSnapshot
    reason_code: str
    published: bool
