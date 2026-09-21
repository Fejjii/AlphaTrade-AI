"""Pure Watcher PAPER MONITORING state projection tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.watcher_monitoring import WatcherMonitoringRuntimeState
from app.services.watcher_monitoring_state import (
    WatcherMonitoringEvidence,
    project_watcher_monitoring_state,
)

NOW = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)


def _evidence(**overrides: object) -> WatcherMonitoringEvidence:
    payload: dict[str, object] = {
        "execution_mode": "paper",
        "real_trading_enabled": False,
        "kill_switch_blocked": False,
        "kill_switch_reason": None,
        "market_watcher_enabled": False,
        "watcher_orchestration_enabled": False,
        "worker_enabled": False,
        "worker_heartbeat_live": False,
        "orchestration_health_state": None,
        "orchestration_reason_code": None,
        "orchestration_lease_fenced": False,
        "orchestration_heartbeat_fresh": False,
        "last_scan_status": None,
        "last_observation_status": None,
        "market_data_health": None,
        "generated_at": NOW,
    }
    payload.update(overrides)
    return WatcherMonitoringEvidence(**payload)  # type: ignore[arg-type]


def test_default_disabled_is_stopped() -> None:
    decision = project_watcher_monitoring_state(_evidence())
    assert decision.state is WatcherMonitoringRuntimeState.STOPPED
    assert decision.reason_code == "watcher_disabled"
    assert decision.runtime_evidence is False


def test_config_flag_alone_is_not_running() -> None:
    decision = project_watcher_monitoring_state(_evidence(market_watcher_enabled=True))
    assert decision.state is WatcherMonitoringRuntimeState.STOPPED
    assert decision.runtime_evidence is False


def test_orchestration_without_heartbeat_is_stale() -> None:
    decision = project_watcher_monitoring_state(_evidence(watcher_orchestration_enabled=True))
    assert decision.state is WatcherMonitoringRuntimeState.STALE
    assert decision.reason_code == "heartbeat_missing"
    assert decision.runtime_evidence is False


def test_live_lease_and_heartbeat_is_running() -> None:
    decision = project_watcher_monitoring_state(
        _evidence(
            watcher_orchestration_enabled=True,
            orchestration_lease_fenced=True,
            orchestration_heartbeat_fresh=True,
            orchestration_health_state="healthy",
            orchestration_reason_code="healthy",
        )
    )
    assert decision.state is WatcherMonitoringRuntimeState.RUNNING
    assert decision.reason_code == "healthy"
    assert decision.runtime_evidence is True


def test_worker_and_scanner_live_heartbeat_is_running() -> None:
    decision = project_watcher_monitoring_state(
        _evidence(
            market_watcher_enabled=True,
            worker_enabled=True,
            worker_heartbeat_live=True,
        )
    )
    assert decision.state is WatcherMonitoringRuntimeState.RUNNING
    assert decision.runtime_evidence is True


def test_provider_outage_degrades_running_watcher() -> None:
    decision = project_watcher_monitoring_state(
        _evidence(
            watcher_orchestration_enabled=True,
            orchestration_lease_fenced=True,
            orchestration_heartbeat_fresh=True,
            orchestration_health_state="healthy",
            market_data_health="unavailable",
        )
    )
    assert decision.state is WatcherMonitoringRuntimeState.DEGRADED
    assert decision.reason_code == "provider_unavailable"


def test_stale_market_data_is_stale_when_running() -> None:
    decision = project_watcher_monitoring_state(
        _evidence(
            watcher_orchestration_enabled=True,
            orchestration_lease_fenced=True,
            orchestration_heartbeat_fresh=True,
            orchestration_health_state="healthy",
            last_observation_status="stale",
        )
    )
    assert decision.state is WatcherMonitoringRuntimeState.STALE
    assert decision.reason_code == "market_data_stale"


def test_last_scan_degraded_is_degraded() -> None:
    decision = project_watcher_monitoring_state(
        _evidence(
            market_watcher_enabled=True,
            worker_enabled=True,
            worker_heartbeat_live=True,
            last_scan_status="degraded",
        )
    )
    assert decision.state is WatcherMonitoringRuntimeState.DEGRADED
    assert decision.reason_code == "last_scan_degraded"


def test_kill_switch_blocks() -> None:
    decision = project_watcher_monitoring_state(
        _evidence(
            watcher_orchestration_enabled=True,
            orchestration_lease_fenced=True,
            orchestration_heartbeat_fresh=True,
            kill_switch_blocked=True,
            kill_switch_reason="kill_switch_active",
        )
    )
    assert decision.state is WatcherMonitoringRuntimeState.BLOCKED
    assert decision.reason_code == "kill_switch_active"


def test_real_trading_blocks_even_with_runtime_evidence() -> None:
    decision = project_watcher_monitoring_state(
        _evidence(
            real_trading_enabled=True,
            watcher_orchestration_enabled=True,
            orchestration_lease_fenced=True,
            orchestration_heartbeat_fresh=True,
        )
    )
    assert decision.state is WatcherMonitoringRuntimeState.BLOCKED
    assert "real_trading_enabled" in decision.block_reasons


def test_non_paper_execution_blocks() -> None:
    decision = project_watcher_monitoring_state(_evidence(execution_mode="read_only"))
    assert decision.state is WatcherMonitoringRuntimeState.BLOCKED
    assert decision.reason_code == "execution_mode_not_paper"


def test_last_scan_blocked_is_blocked_when_running() -> None:
    decision = project_watcher_monitoring_state(
        _evidence(
            watcher_orchestration_enabled=True,
            orchestration_lease_fenced=True,
            orchestration_heartbeat_fresh=True,
            last_scan_status="blocked",
        )
    )
    assert decision.state is WatcherMonitoringRuntimeState.BLOCKED
    assert decision.reason_code == "last_scan_blocked"


def test_provider_outage_does_not_fake_running_when_stopped() -> None:
    decision = project_watcher_monitoring_state(_evidence(market_data_health="unavailable"))
    assert decision.state is WatcherMonitoringRuntimeState.STOPPED
    assert "provider_unavailable" in decision.warnings
