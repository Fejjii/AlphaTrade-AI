"""Existing worker wiring, isolation and cooperative shutdown without exchange IO."""

from threading import Event
from uuid import uuid4

from app.services.blofin_activity_config import BloFinActivitySettings
from app.services.blofin_activity_service import ActivitySyncResult
from app.workers.blofin_activity import BloFinActivityCycle
from app.workers.paper_worker import (
    CycleOutcome,
    PaperWorkerSupervisor,
    build_paper_worker_supervisor,
)
from tests.test_blofin_activity_provider import readonly_settings


def supervisor():
    return PaperWorkerSupervisor(
        watcher_cycle=lambda: CycleOutcome("running"),
        telegram_cycle=lambda: CycleOutcome("disarmed"),
        poll_seconds=0.01,
    )


def config():
    return BloFinActivitySettings(
        _env_file=None, enabled=True, organization_id=uuid4(), expected_uid="fixture-uid"
    )


def test_disabled_defaults_build_no_activity_client_or_database(monkeypatch):
    monkeypatch.setenv("BLOFIN_ACTIVITY_ENABLED", "false")
    monkeypatch.setattr("app.workers.paper_worker._build_armed_supervisor", lambda *_: supervisor())

    def forbidden():
        raise AssertionError("disabled activity opened database")

    monkeypatch.setattr("app.workers.blofin_activity.get_engine", forbidden)
    assert BloFinActivitySettings(_env_file=None).enabled is False
    worker = build_paper_worker_supervisor(readonly_settings())
    assert worker.run_round().activity is None
    worker.close()


def test_explicit_configuration_wires_bounded_tick_and_safe_shutdown(monkeypatch):
    activity_config = config()
    monkeypatch.setattr(
        "app.services.blofin_activity_config.get_activity_settings", lambda: activity_config
    )
    monkeypatch.setattr("app.workers.paper_worker._build_armed_supervisor", lambda *_: supervisor())
    marker = object()
    monkeypatch.setattr("app.workers.blofin_activity.get_engine", lambda: marker)
    calls = []

    def tick(engine, settings, configured, *, shutdown):
        assert engine is marker and configured.max_pages == 4 and configured.budget_seconds == 30
        assert configured.poll_seconds == 60 and not shutdown()
        assert settings.enable_real_trading is False
        calls.append(shutdown)
        return ActivitySyncResult("failed", error_code="rate_limited")

    monkeypatch.setattr("app.workers.blofin_activity.run_activity_sync", tick)
    worker = build_paper_worker_supervisor(readonly_settings())
    health = worker.run_round()
    assert health.activity.status == "degraded" and health.activity.last_error == "rate_limited"
    assert health.watcher.status == "running" and health.watcher.restart_count == 0
    worker.request_stop()
    assert calls[0]()
    worker.close()
    worker.run_round()
    assert len(calls) == 1


def test_blocked_activity_does_not_delay_watcher_and_starts_only_one_thread():
    entered, stopping, watcher_progress = Event(), Event(), Event()
    scans = []

    def watch():
        scans.append(1)
        if entered.is_set() and len(scans) > 2:
            watcher_progress.set()
        return CycleOutcome("running")

    def activity():
        entered.set()
        assert stopping.wait(2)
        return CycleOutcome("interrupted")

    worker = PaperWorkerSupervisor(
        watcher_cycle=watch, telegram_cycle=lambda: CycleOutcome("disarmed"), poll_seconds=0.01
    )
    worker.attach_activity(activity, poll_seconds=60, request_stop=stopping.set)
    try:
        worker.start()
        first_thread = worker._activity.thread
        worker.start()
        assert worker._activity.thread is first_thread
        assert entered.wait(1) and watcher_progress.wait(1)
    finally:
        worker.request_stop()
        worker.join()
        worker.close()
    health = worker.snapshot()
    assert health.activity.status == "stopped" and health.activity.cycles_completed == 1
    assert not first_thread.is_alive()


def test_activity_exception_stays_local_and_stopped_cycle_opens_no_dependencies(monkeypatch):
    worker = supervisor()

    def failing():
        raise RuntimeError("fixture failure")

    worker.attach_activity(failing, poll_seconds=60, request_stop=lambda: None)
    for _ in range(2):
        health = worker.run_round()
        assert health.watcher.status == "running" and health.watcher.restart_count == 0
    assert health.activity.restart_count == 2
    worker.close()
    cycle = BloFinActivityCycle(readonly_settings(), config())
    cycle.request_stop()

    def forbidden():
        raise AssertionError("stopped cycle opened database")

    monkeypatch.setattr("app.workers.blofin_activity.get_engine", forbidden)
    assert cycle().status == "stopped"


def test_activity_provider_retains_retry_and_request_timeout_caps(monkeypatch):
    from app.services.blofin_activity_service import activity_provider

    captured = []
    monkeypatch.setattr(
        "app.services.blofin_activity_service.get_readonly_client",
        lambda settings, **_: captured.append(settings) or object(),
    )
    monkeypatch.setattr(
        "app.services.blofin_activity_service.BloFinActivityProvider", lambda client: client
    )
    settings = readonly_settings().model_copy(
        update={"blofin_max_retries": 9, "blofin_request_timeout_seconds": 99}
    )
    activity_provider(settings)
    assert captured[0].blofin_max_retries == 2
    assert captured[0].blofin_request_timeout_seconds == 10
    assert captured[0].blofin_rate_limit_requests_per_second == 1
    assert settings.blofin_max_retries == 9 and settings.blofin_request_timeout_seconds == 99


def test_missing_activity_pins_fail_only_the_activity_component(monkeypatch):
    activity_config = BloFinActivitySettings(_env_file=None, enabled=True)
    monkeypatch.setattr(
        "app.services.blofin_activity_config.get_activity_settings", lambda: activity_config
    )
    monkeypatch.setattr("app.workers.paper_worker._build_armed_supervisor", lambda *_: supervisor())

    def forbidden():
        raise AssertionError("unverified activity configuration opened database")

    monkeypatch.setattr("app.workers.blofin_activity.get_engine", forbidden)
    worker = build_paper_worker_supervisor(readonly_settings())
    health = worker.run_round()
    assert health.activity.status == "failed"
    assert health.watcher.status == "running" and health.watcher.restart_count == 0
    worker.close()
