"""Operator-facing Watcher PAPER MONITORING contracts.

Read-only projections of existing runtime evidence. These schemas do not enable
Watcher, mint SetupAssessments, evaluate strategies, or place trades.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel
from app.signal_fusion.enums import SetupAssessmentState


class WatcherMonitoringRuntimeState(StrEnum):
    """Operator runtime state. RUNNING requires live lease/heartbeat evidence."""

    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    BLOCKED = "BLOCKED"


class WatcherConfigFlags(StrictModel):
    """Explicit configuration flags. Never treat these as RUNNING by themselves."""

    market_watcher_enabled: bool = False
    watcher_orchestration_enabled: bool = False
    worker_enabled: bool = False
    market_watcher_bridge_enabled: bool = False
    market_watcher_bridge_auto_tick: bool = False
    telegram_alerts_enabled: bool = False
    telegram_interaction_enabled: bool = False
    automatic_telegram_delivery_enabled: bool = False


class PaperMonitoringPosture(StrictModel):
    """Safety posture that must remain visible on every monitoring surface."""

    paper_only: Literal[True] = True
    execution_mode: str
    real_trading_enabled: bool = False
    kill_switch_blocked: bool = False
    kill_switch_reason_code: str | None = None
    telegram_enabled: bool = False
    watcher_config_enabled: bool = False
    runtime_evidence: bool = False


class WatcherApprovedStrategy(StrictModel):
    strategy_id: UUID
    strategy_version_id: UUID
    name: str
    lifecycle_state: str
    compiled: bool = True


class WatcherSetupAssessmentSummary(StrictModel):
    """Lineage projection from persisted Candidates. Not a second evaluator."""

    assessment_id: UUID
    candidate_id: UUID
    state: SetupAssessmentState
    strategy_version_id: UUID
    instrument: str
    timeframe: str
    valid_until: datetime
    live_executable: Literal[False] = False


class WatcherDetectedCandidateSummary(StrictModel):
    """Scanner detections from the last persisted scan. Empty when none exist."""

    count: int = 0
    conditions: list[str] = Field(default_factory=list)
    last_scan_at: datetime | None = None
    source: Literal["market_watcher_scan"] = "market_watcher_scan"


class WatcherCanonicalCandidateSummary(StrictModel):
    candidate_id: UUID
    assessment_id: UUID
    state: str
    instrument: str
    timeframe: str
    strategy_version_id: UUID
    created_at: datetime


class WatcherMarketFreshness(StrictModel):
    status: Literal["fresh", "stale", "unavailable", "unknown"] = "unknown"
    observed_at: datetime | None = None
    symbol: str | None = None
    data_freshness: str | None = None
    stale_after_minutes: int


class WatcherProviderHealthItem(StrictModel):
    name: str
    kind: str
    health: str
    using_fallback: bool = False
    is_mock: bool = False
    detail: str | None = None
    error_message: str | None = None


class WatcherLeaseHealth(StrictModel):
    scan_scope: str
    owner_id: str | None = None
    lease_epoch: int = 0
    fencing_token: int = 0
    expires_at: datetime | None = None
    last_beat_at: datetime | None = None
    seconds_since_beat: float | None = None
    fenced: bool = False
    heartbeat_fresh: bool = False
    orchestration_state: str | None = None
    reason_code: str | None = None


class WatcherWorkerHealth(StrictModel):
    name: str
    worker_enabled: bool = False
    heartbeat_live: bool = False
    last_beat_at: datetime | None = None
    status: str | None = None
    paused: bool | None = None
    detail: str | None = None


class WatcherRecentError(StrictModel):
    source: str
    message: str
    at: datetime | None = None
    reason_code: str | None = None


class WatcherMonitoringSnapshot(StrictModel):
    """Aggregated paper-monitoring snapshot. No fabricated activity or prices."""

    watcher_status: WatcherMonitoringRuntimeState
    paper_monitoring_status: WatcherMonitoringRuntimeState
    reason_code: str
    block_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    paper_posture: PaperMonitoringPosture
    config_flags: WatcherConfigFlags
    symbols_monitored: list[str] = Field(default_factory=list)
    approved_strategies: list[WatcherApprovedStrategy] = Field(default_factory=list)
    last_scan_at: datetime | None = None
    last_scan_status: str | None = None
    next_scan_at: datetime | None = None
    next_scan_basis: Literal["worker_interval", "lease_ttl", "bridge_interval"] | None = None
    market_freshness: WatcherMarketFreshness
    provider_health: list[WatcherProviderHealthItem] = Field(default_factory=list)
    setup_assessments: list[WatcherSetupAssessmentSummary] = Field(default_factory=list)
    scanner_candidates: WatcherDetectedCandidateSummary
    canonical_candidates: list[WatcherCanonicalCandidateSummary] = Field(default_factory=list)
    leases: list[WatcherLeaseHealth] = Field(default_factory=list)
    worker: WatcherWorkerHealth
    recent_errors: list[WatcherRecentError] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: datetime
    paper_only: Literal[True] = True
