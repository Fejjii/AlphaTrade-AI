"""Pure Watcher PAPER MONITORING state projection.

RUNNING is never inferred from configuration flags. Live lease fencing or a
fresh watcher-related heartbeat is required. This module has no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.schemas.watcher_monitoring import WatcherMonitoringRuntimeState

_HEALTHY = "healthy"
_DEGRADED = "degraded"
_BLOCKED = "blocked"
_STALE = "stale"


@dataclass(frozen=True)
class WatcherMonitoringEvidence:
    """Facts collected from runtime stores. Callers must not invent values."""

    execution_mode: str
    real_trading_enabled: bool
    kill_switch_blocked: bool
    kill_switch_reason: str | None
    market_watcher_enabled: bool
    watcher_orchestration_enabled: bool
    worker_enabled: bool
    worker_heartbeat_live: bool
    orchestration_health_state: str | None
    orchestration_reason_code: str | None
    orchestration_lease_fenced: bool
    orchestration_heartbeat_fresh: bool
    last_scan_status: str | None
    last_observation_status: str | None
    market_data_health: str | None
    generated_at: datetime


@dataclass(frozen=True)
class WatcherMonitoringDecision:
    state: WatcherMonitoringRuntimeState
    reason_code: str
    block_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    runtime_evidence: bool
    watcher_intended: bool


def project_watcher_monitoring_state(
    evidence: WatcherMonitoringEvidence,
) -> WatcherMonitoringDecision:
    """Map observed evidence onto RUNNING/STOPPED/DEGRADED/STALE/BLOCKED."""

    warnings: list[str] = []
    block_reasons: list[str] = []
    runtime_evidence = _runtime_evidence(evidence)
    watcher_intended = _watcher_intended(evidence)

    if evidence.real_trading_enabled:
        block_reasons.append("real_trading_enabled")
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.BLOCKED,
            reason_code="real_trading_enabled",
            block_reasons=tuple(block_reasons),
            warnings=(),
            runtime_evidence=runtime_evidence,
            watcher_intended=watcher_intended,
        )
    if evidence.execution_mode != "paper":
        block_reasons.append("execution_mode_not_paper")
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.BLOCKED,
            reason_code="execution_mode_not_paper",
            block_reasons=tuple(block_reasons),
            warnings=(),
            runtime_evidence=runtime_evidence,
            watcher_intended=watcher_intended,
        )
    if evidence.kill_switch_blocked:
        reason = evidence.kill_switch_reason or "kill_switch_active"
        block_reasons.append(reason)
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.BLOCKED,
            reason_code=reason,
            block_reasons=tuple(block_reasons),
            warnings=(),
            runtime_evidence=runtime_evidence,
            watcher_intended=watcher_intended,
        )

    if evidence.worker_heartbeat_live and not watcher_intended:
        warnings.append("unexpected_worker_heartbeat")

    if evidence.market_data_health == "unavailable":
        warnings.append("provider_unavailable")
    elif evidence.market_data_health == "degraded":
        warnings.append("provider_degraded")

    if not watcher_intended:
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.STOPPED,
            reason_code="watcher_disabled",
            block_reasons=(),
            warnings=tuple(warnings),
            runtime_evidence=runtime_evidence,
            watcher_intended=False,
        )

    if not runtime_evidence:
        reason = _missing_runtime_reason(evidence)
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.STALE,
            reason_code=reason,
            block_reasons=(),
            warnings=tuple(warnings),
            runtime_evidence=False,
            watcher_intended=True,
        )

    orchestration_state = evidence.orchestration_health_state
    if evidence.watcher_orchestration_enabled and orchestration_state == _BLOCKED:
        reason = evidence.orchestration_reason_code or "blocked"
        if reason != "watcher_disabled":
            block_reasons.append(reason)
            return WatcherMonitoringDecision(
                state=WatcherMonitoringRuntimeState.BLOCKED,
                reason_code=reason,
                block_reasons=tuple(block_reasons),
                warnings=tuple(warnings),
                runtime_evidence=True,
                watcher_intended=True,
            )

    if evidence.last_scan_status == "blocked":
        block_reasons.append("last_scan_blocked")
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.BLOCKED,
            reason_code="last_scan_blocked",
            block_reasons=tuple(block_reasons),
            warnings=tuple(warnings),
            runtime_evidence=True,
            watcher_intended=True,
        )

    if evidence.watcher_orchestration_enabled and orchestration_state == _STALE:
        reason = evidence.orchestration_reason_code or "heartbeat_stale"
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.STALE,
            reason_code=reason,
            block_reasons=(),
            warnings=tuple(warnings),
            runtime_evidence=runtime_evidence,
            watcher_intended=True,
        )

    if evidence.last_observation_status == "stale":
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.STALE,
            reason_code="market_data_stale",
            block_reasons=(),
            warnings=tuple(warnings),
            runtime_evidence=True,
            watcher_intended=True,
        )

    if evidence.watcher_orchestration_enabled and orchestration_state == _DEGRADED:
        reason = evidence.orchestration_reason_code or "degraded"
        warnings.append(reason)
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.DEGRADED,
            reason_code=reason,
            block_reasons=(),
            warnings=tuple(dict.fromkeys(warnings)),
            runtime_evidence=True,
            watcher_intended=True,
        )

    if evidence.market_data_health == "unavailable":
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.DEGRADED,
            reason_code="provider_unavailable",
            block_reasons=(),
            warnings=tuple(warnings),
            runtime_evidence=True,
            watcher_intended=True,
        )
    if evidence.market_data_health == "degraded":
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.DEGRADED,
            reason_code="provider_degraded",
            block_reasons=(),
            warnings=tuple(warnings),
            runtime_evidence=True,
            watcher_intended=True,
        )
    if evidence.last_scan_status == "degraded":
        warnings.append("last_scan_degraded")
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.DEGRADED,
            reason_code="last_scan_degraded",
            block_reasons=(),
            warnings=tuple(dict.fromkeys(warnings)),
            runtime_evidence=True,
            watcher_intended=True,
        )
    if evidence.last_observation_status == "unavailable":
        return WatcherMonitoringDecision(
            state=WatcherMonitoringRuntimeState.DEGRADED,
            reason_code="market_data_unavailable",
            block_reasons=(),
            warnings=tuple(warnings),
            runtime_evidence=True,
            watcher_intended=True,
        )

    return WatcherMonitoringDecision(
        state=WatcherMonitoringRuntimeState.RUNNING,
        reason_code="healthy",
        block_reasons=(),
        warnings=tuple(warnings),
        runtime_evidence=True,
        watcher_intended=True,
    )


def _watcher_intended(evidence: WatcherMonitoringEvidence) -> bool:
    if evidence.watcher_orchestration_enabled:
        return True
    return evidence.market_watcher_enabled and evidence.worker_enabled


def _runtime_evidence(evidence: WatcherMonitoringEvidence) -> bool:
    orchestration_live = (
        evidence.watcher_orchestration_enabled
        and evidence.orchestration_lease_fenced
        and evidence.orchestration_heartbeat_fresh
    )
    watcher_worker_live = (
        evidence.worker_heartbeat_live
        and evidence.market_watcher_enabled
        and evidence.worker_enabled
    )
    return orchestration_live or watcher_worker_live


def _missing_runtime_reason(evidence: WatcherMonitoringEvidence) -> str:
    if evidence.watcher_orchestration_enabled:
        if evidence.orchestration_reason_code:
            return evidence.orchestration_reason_code
        if not evidence.orchestration_heartbeat_fresh:
            return "heartbeat_missing"
        if not evidence.orchestration_lease_fenced:
            return "lease_expired"
    return "heartbeat_missing"
