"""Tests for the background worker: locking, heartbeats, dead-letters, control."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.workers.lock import InMemoryWorkerLock
from app.workers.repository import MarketScanRunRepository, WorkerHeartbeatRepository
from app.workers.runner import WorkerLoopDriver
from app.workers.service import WorkerService

WORKER = "test-worker"


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def _service(factory: sessionmaker[Session], scanner=None) -> WorkerService:
    return WorkerService(
        factory,
        InMemoryWorkerLock("k", ttl_seconds=60),
        worker_name=WORKER,
        scanner=scanner,
    )


# --- lock ------------------------------------------------------------------


def test_in_memory_lock_is_single_runner() -> None:
    lock = InMemoryWorkerLock("k", ttl_seconds=60)
    token = lock.try_acquire()
    assert token is not None
    assert lock.try_acquire() is None  # already held
    lock.release(token)
    assert lock.try_acquire() is not None


def test_lock_release_requires_matching_token() -> None:
    lock = InMemoryWorkerLock("k", ttl_seconds=60)
    token = lock.try_acquire()
    lock.release("wrong-token")
    assert lock.try_acquire() is None  # still held by original token
    lock.release(token)
    assert lock.try_acquire() is not None


def test_lock_expires_after_ttl() -> None:
    fake = {"t": 0.0}
    lock = InMemoryWorkerLock("k", ttl_seconds=10, clock=lambda: fake["t"])
    assert lock.try_acquire() is not None
    assert lock.try_acquire() is None
    fake["t"] = 11.0  # past TTL
    assert lock.try_acquire() is not None


# --- service ---------------------------------------------------------------


def test_run_cycle_success_records_run_and_heartbeat(factory: sessionmaker[Session]) -> None:
    service = _service(factory, scanner=lambda _s: (3, 2))
    result = service.run_cycle()

    assert result.status == "success"
    assert result.symbols_scanned == 3
    assert result.setups_detected == 2

    with factory() as session:
        heartbeat = WorkerHeartbeatRepository(session).get_by_name(WORKER)
        assert heartbeat is not None
        assert heartbeat.status == "running"
        assert heartbeat.cycle_count == 1
        runs = MarketScanRunRepository(session).list_recent()
        assert len(runs) == 1
        assert runs[0].status == "success"


def test_failed_cycle_is_dead_lettered(factory: sessionmaker[Session]) -> None:
    def boom(_s: Session) -> tuple[int, int]:
        raise RuntimeError("scanner exploded")

    service = _service(factory, scanner=boom)
    result = service.run_cycle()

    assert result.status == "failed"
    with factory() as session:
        dead = MarketScanRunRepository(session).list_dead_letters()
        assert len(dead) == 1
        assert dead[0].status == "failed"
        assert "scanner exploded" in (dead[0].error or "")
        heartbeat = WorkerHeartbeatRepository(session).get_by_name(WORKER)
        assert heartbeat is not None
        assert heartbeat.status == "error"


def test_error_messages_are_redacted(factory: sessionmaker[Session]) -> None:
    def boom(_s: Session) -> tuple[int, int]:
        raise RuntimeError("api_key=supersecret failed")

    _service(factory, scanner=boom).run_cycle()
    with factory() as session:
        dead = MarketScanRunRepository(session).list_dead_letters()
        assert "supersecret" not in (dead[0].error or "")


def test_paused_worker_skips_cycle(factory: sessionmaker[Session]) -> None:
    service = _service(factory, scanner=lambda _s: (1, 1))
    service.set_paused(True)
    result = service.run_cycle()

    assert result.status == "skipped"
    assert result.reason == "paused"
    with factory() as session:
        assert MarketScanRunRepository(session).list_recent() == []


def test_resume_clears_pause(factory: sessionmaker[Session]) -> None:
    service = _service(factory, scanner=lambda _s: (1, 1))
    service.set_paused(True)
    assert service.is_paused() is True
    service.set_paused(False)
    assert service.is_paused() is False
    assert service.run_cycle().status == "success"


def test_lock_held_elsewhere_skips_cycle(factory: sessionmaker[Session]) -> None:
    lock = InMemoryWorkerLock("k", ttl_seconds=60)
    service = WorkerService(factory, lock, worker_name=WORKER, scanner=lambda _s: (1, 1))
    held = lock.try_acquire()  # simulate another runner holding the lock
    assert held is not None

    result = service.run_cycle()
    assert result.status == "skipped"
    assert result.reason == "lock_not_acquired"


# --- loop driver -----------------------------------------------------------


def test_loop_driver_runs_max_cycles(factory: sessionmaker[Session]) -> None:
    service = _service(factory, scanner=lambda _s: (1, 0))
    driver = WorkerLoopDriver(service, interval_seconds=0, sleeper=lambda _x: None)
    cycles = driver.run(max_cycles=3)

    assert cycles == 3
    with factory() as session:
        heartbeat = WorkerHeartbeatRepository(session).get_by_name(WORKER)
        assert heartbeat is not None
        assert heartbeat.cycle_count == 3


def test_loop_driver_stops_on_should_continue(factory: sessionmaker[Session]) -> None:
    service = _service(factory, scanner=lambda _s: (1, 0))
    driver = WorkerLoopDriver(service, interval_seconds=0, sleeper=lambda _x: None)
    cycles = driver.run(max_cycles=10, should_continue=lambda: False)
    assert cycles == 0


# --- HTTP endpoints --------------------------------------------------------


def test_worker_health_and_control_endpoints(client_with_workflow_db: TestClient) -> None:
    # No heartbeat yet -> unknown but 200.
    initial = client_with_workflow_db.get("/worker/health")
    assert initial.status_code == 200
    assert initial.json()["status"] == "unknown"
    assert initial.json()["running"] is False

    paused = client_with_workflow_db.post("/worker/pause")
    assert paused.status_code == 200
    assert paused.json()["paused"] is True

    after = client_with_workflow_db.get("/worker/health")
    assert after.json()["paused"] is True

    resumed = client_with_workflow_db.post("/worker/resume")
    assert resumed.status_code == 200
    assert resumed.json()["paused"] is False
