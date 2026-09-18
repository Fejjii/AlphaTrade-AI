"""PostgreSQL WatcherStore adapter: fencing, tenant isolation, crash recovery."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.persistence.composition import (
    build_postgres_watcher_orchestrator,
    build_postgres_watcher_store,
)
from app.watcher.composition import build_orchestrator
from app.watcher.contracts import (
    EvaluationCommand,
    EvaluationMode,
    EvaluationOutcome,
    EvaluationStatus,
    ScanAttempt,
    ScanAttemptStatus,
    ScanLineage,
    ScanTrigger,
    ScheduledScan,
    SourceFetchAttempt,
    SubscriptionEvaluationAttempt,
    UnitAttemptStatus,
    WatcherHealthSnapshot,
    WatcherHealthState,
)
from app.watcher.errors import (
    SimulatedWorkerCrashError,
    StaleFenceError,
    WatcherIdempotencyConflictError,
    WatcherTenantMismatchError,
)
from app.watcher.memory import FakeClock, ScriptedEvaluationBoundary, SideEffectProbe
from app.watcher.orchestrator import WatcherOrchestrator
from app.watcher.ports import NamedCrashBarrier, WatcherStore
from tests.support.postgres_persistence import persistence_session_factory, requires_postgres
from tests.test_watcher_orchestration_foundation import SHARED_TENANT_SCOPE, _policy, _request


def _worker_health(
    *,
    organization_id: UUID,
    scan_scope: str,
    owner_id: str,
    lease_epoch: int,
    fencing_token: int,
    now: datetime,
) -> WatcherHealthSnapshot:
    return WatcherHealthSnapshot(
        state=WatcherHealthState.HEALTHY,
        organization_id=organization_id,
        scan_scope=scan_scope,
        enabled=True,
        lease_owner=owner_id,
        lease_epoch=lease_epoch,
        fencing_token=fencing_token,
        lease_expires_at=now,
        last_beat_at=now,
        seconds_since_beat=0.0,
        last_attempt_status=None,
        last_lineage_id=None,
        reason_code="worker",
        generated_at=now,
    )


def _observer_health(
    *,
    organization_id: UUID,
    scan_scope: str,
    now: datetime,
) -> WatcherHealthSnapshot:
    return WatcherHealthSnapshot(
        state=WatcherHealthState.STALE,
        organization_id=organization_id,
        scan_scope=scan_scope,
        enabled=True,
        lease_owner=None,
        lease_epoch=0,
        fencing_token=0,
        lease_expires_at=None,
        last_beat_at=None,
        seconds_since_beat=None,
        last_attempt_status=None,
        last_lineage_id=None,
        reason_code="observer",
        generated_at=now,
    )


def _lineage_row(store: WatcherStore, org: UUID, scope: str, clock: FakeClock) -> ScanLineage:
    return store.insert_lineage(
        ScanLineage(
            lineage_id=uuid4(),
            organization_id=org,
            principal_id=None,
            scan_scope=scope,
            request_hash="c" * 64,
            policy_id=uuid4(),
            policy_version=1,
            policy_content_hash="d" * 64,
            trigger_created_by=ScanTrigger.WORKER,
            created_at=clock.now(),
        )
    )


def _scan_attempt(
    lineage: ScanLineage,
    *,
    worker_id: str | None,
    lease_epoch: int | None,
    fencing_token: int | None,
    clock: FakeClock,
    status: ScanAttemptStatus = ScanAttemptStatus.STARTED,
    attempt_id: UUID | None = None,
    attempt_number: int = 1,
) -> ScanAttempt:
    now = clock.now()
    return ScanAttempt(
        attempt_id=attempt_id or uuid4(),
        lineage_id=lineage.lineage_id,
        attempt_number=attempt_number,
        worker_id=worker_id,
        lease_epoch=lease_epoch,
        fencing_token=fencing_token,
        trigger=ScanTrigger.MANUAL if worker_id is None else ScanTrigger.WORKER,
        mode=EvaluationMode.PERSIST_EVIDENCE,
        status=status,
        started_at=now,
        heartbeat_at=now,
        finished_at=None if status is ScanAttemptStatus.STARTED else now,
    )


def _orch(store: WatcherStore, clock: FakeClock, **kwargs: object) -> WatcherOrchestrator:
    crash = kwargs.get("crash")
    return build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=kwargs.get("evaluator", ScriptedEvaluationBoundary()),  # type: ignore[arg-type]
        side_effects=kwargs.get("side_effects", SideEffectProbe()),  # type: ignore[arg-type]
        crash=crash if isinstance(crash, NamedCrashBarrier) else None,
        lease_ttl_seconds=int(kwargs.get("lease_ttl_seconds", 30)),  # type: ignore[arg-type]
    )


@requires_postgres
def test_postgres_store_not_auto_enabled() -> None:
    settings = Settings()
    assert settings.watcher_orchestration_enabled is False
    assert settings.market_watcher_enabled is False
    store = build_postgres_watcher_store(persistence_session_factory())
    blocked = build_orchestrator(enabled=False, store=store, clock=FakeClock()).schedule(
        _request(_policy(FakeClock()))
    )
    assert blocked.status.value == "blocked"
    disabled = build_postgres_watcher_orchestrator(persistence_session_factory(), enabled=False)
    assert disabled.schedule(_request(_policy(FakeClock()))).status.value == "blocked"


@requires_postgres
def test_postgres_adapter_does_not_use_process_local_lock() -> None:
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "src/app/persistence/watcher_postgres.py"
    text = source.read_text(encoding="utf-8")
    assert "threading.Lock" not in text
    assert "RLock" not in text
    assert "FOR UPDATE" in text


@requires_postgres
def test_postgres_duplicate_scheduled_scan_converges() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    policy = _policy(clock)
    request = _request(policy, key="dup-key")
    first = store.insert_lineage(
        ScanLineage(
            lineage_id=uuid4(),
            organization_id=request.organization_id,
            principal_id=request.principal_id,
            scan_scope=request.scan_scope,
            request_hash="a" * 64,
            policy_id=request.policy_id,
            policy_version=request.policy_version,
            policy_content_hash=request.policy_content_hash,
            trigger_created_by=ScanTrigger.WORKER,
            created_at=clock.now(),
        )
    )
    row = ScheduledScan(
        scheduled_scan_id=uuid4(),
        organization_id=request.organization_id,
        principal_id=request.principal_id,
        idempotency_key=request.idempotency_key,
        request_hash="a" * 64,
        scan_scope=request.scan_scope,
        lineage_id=first.lineage_id,
        created_at=clock.now(),
    )
    stored = store.insert_schedule(row)
    replay = store.insert_schedule(row.model_copy(update={"scheduled_scan_id": uuid4()}))
    assert replay.scheduled_scan_id == stored.scheduled_scan_id
    with pytest.raises(WatcherIdempotencyConflictError):
        store.insert_schedule(
            row.model_copy(update={"scheduled_scan_id": uuid4(), "request_hash": "b" * 64})
        )


@requires_postgres
def test_postgres_duplicate_request_identity_different_payload_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    policy = _policy(clock)
    orch = _orch(store, clock)
    first = orch.schedule(_request(policy, key="same-key"))
    assert first.status.value == "accepted"
    other_policy = _policy(clock)
    other = _request(other_policy, key="same-key", organization_id=policy.identity.organization_id)
    with pytest.raises(WatcherIdempotencyConflictError):
        orch.schedule(other)


@requires_postgres
def test_postgres_concurrent_lease_claim_single_owner() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "concurrent-scope"
    barrier = threading.Barrier(2)
    results: list[tuple[bool, str, int]] = []
    lock = threading.Lock()

    def worker(owner: str) -> None:
        barrier.wait(timeout=20)
        acquired, lease, reason = store.claim_lease(
            organization_id=org,
            scan_scope=scope,
            owner_id=owner,
            ttl_seconds=30,
            now=clock.now(),
        )
        with lock:
            results.append((acquired, reason, lease.fencing_token))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, "worker-a"), pool.submit(worker, "worker-b")]
        for future in futures:
            future.result(timeout=30)
    acquired = [item for item in results if item[0]]
    held = [item for item in results if not item[0]]
    assert len(acquired) == 1
    assert len(held) == 1
    assert held[0][1] == "lease_held"
    current = store.get_lease(org, scope)
    assert current is not None
    assert current.owner_id in {"worker-a", "worker-b"}
    assert current.fencing_token == 1


@requires_postgres
def test_postgres_two_organizations_same_scan_scope_isolated() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org_a = uuid4()
    org_b = uuid4()
    barrier = threading.Barrier(2)
    results: dict[str, tuple[bool, int]] = {}
    lock = threading.Lock()

    def claim(label: str, org: UUID) -> None:
        barrier.wait(timeout=20)
        acquired, lease, _reason = store.claim_lease(
            organization_id=org,
            scan_scope=SHARED_TENANT_SCOPE,
            owner_id=f"worker-{label}",
            ttl_seconds=30,
            now=clock.now(),
        )
        with lock:
            results[label] = (acquired, lease.fencing_token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim, "a", org_a), pool.submit(claim, "b", org_b)]
        for future in futures:
            future.result(timeout=30)
    assert results["a"][0] is True
    assert results["b"][0] is True
    assert results["a"][1] == 1
    assert results["b"][1] == 1
    lease_a = store.get_lease(org_a, SHARED_TENANT_SCOPE)
    lease_b = store.get_lease(org_b, SHARED_TENANT_SCOPE)
    assert lease_a is not None and lease_b is not None
    assert lease_a.organization_id == org_a
    assert lease_b.organization_id == org_b
    assert str(org_a) not in SHARED_TENANT_SCOPE
    assert str(org_b) not in SHARED_TENANT_SCOPE


@requires_postgres
def test_postgres_expired_lease_takeover_increments_fence() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "takeover-scope"
    acquired_a, lease_a, _ = store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    assert acquired_a is True
    clock.advance(31)
    acquired_b, lease_b, reason = store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    assert acquired_b is True
    assert reason == "claimed"
    assert lease_b.fencing_token == lease_a.fencing_token + 1
    assert (
        store.fence_is_active(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-a",
            fencing_token=lease_a.fencing_token,
            now=clock.now(),
        )
        is False
    )


@requires_postgres
def test_postgres_stale_fence_writer_rejected() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "stale-write"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    assert (
        store.renew_lease(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-a",
            fencing_token=1,
            ttl_seconds=30,
            now=clock.now(),
        )
        is False
    )


@requires_postgres
def test_postgres_stale_lease_holder_cannot_update_heartbeat() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "heartbeat-stale"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    store.record_heartbeat(
        organization_id=org,
        scan_scope=scope,
        owner_id="worker-a",
        lease_epoch=1,
        fencing_token=1,
        now=clock.now(),
        detail="owner-a",
    )
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    store.record_heartbeat(
        organization_id=org,
        scan_scope=scope,
        owner_id="worker-b",
        lease_epoch=2,
        fencing_token=2,
        now=clock.now(),
        detail="owner-b",
    )
    with pytest.raises(StaleFenceError):
        store.record_heartbeat(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-a",
            lease_epoch=1,
            fencing_token=1,
            now=clock.now(),
            detail="stale-a",
        )
    beat = store.get_heartbeat(org, scope)
    assert beat is not None
    assert beat.owner_id == "worker-b"
    assert beat.detail == "owner-b"
    assert beat.fencing_token == 2


@requires_postgres
def test_postgres_stale_first_heartbeat_without_prior_row_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "heartbeat-stale-first"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    with pytest.raises(StaleFenceError):
        store.record_heartbeat(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-a",
            lease_epoch=1,
            fencing_token=1,
            now=clock.now(),
            detail="stale-first",
        )
    assert store.get_heartbeat(org, scope) is None


@requires_postgres
def test_postgres_heartbeat_wrong_owner_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "heartbeat-wrong-owner"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    store.record_heartbeat(
        organization_id=org,
        scan_scope=scope,
        owner_id="worker-a",
        lease_epoch=1,
        fencing_token=1,
        now=clock.now(),
        detail="owner-a",
    )
    with pytest.raises(StaleFenceError):
        store.record_heartbeat(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-b",
            lease_epoch=1,
            fencing_token=1,
            now=clock.now(),
            detail="intruder",
        )
    beat = store.get_heartbeat(org, scope)
    assert beat is not None
    assert beat.owner_id == "worker-a"
    assert beat.detail == "owner-a"


@requires_postgres
def test_postgres_heartbeat_wrong_fence_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "heartbeat-wrong-fence"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    with pytest.raises(StaleFenceError):
        store.record_heartbeat(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-a",
            lease_epoch=1,
            fencing_token=99,
            now=clock.now(),
            detail="wrong-fence",
        )
    assert store.get_heartbeat(org, scope) is None


@requires_postgres
def test_postgres_heartbeat_expired_lease_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "heartbeat-expired"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    clock.advance(31)
    with pytest.raises(StaleFenceError):
        store.record_heartbeat(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-a",
            lease_epoch=1,
            fencing_token=1,
            now=clock.now(),
            detail="expired",
        )
    assert store.get_heartbeat(org, scope) is None


@requires_postgres
def test_postgres_heartbeat_missing_lease_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "heartbeat-missing-lease"
    with pytest.raises(StaleFenceError):
        store.record_heartbeat(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-a",
            lease_epoch=1,
            fencing_token=1,
            now=clock.now(),
            detail="no-lease",
        )
    assert store.get_heartbeat(org, scope) is None


@requires_postgres
def test_postgres_stale_lease_holder_cannot_publish_health() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "health-stale"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    stale = WatcherHealthSnapshot(
        state=WatcherHealthState.HEALTHY,
        organization_id=org,
        scan_scope=scope,
        enabled=True,
        lease_owner="worker-a",
        lease_epoch=1,
        fencing_token=1,
        lease_expires_at=clock.now(),
        last_beat_at=clock.now(),
        seconds_since_beat=0.0,
        last_attempt_status=None,
        last_lineage_id=None,
        reason_code="stale",
        generated_at=clock.now(),
    )
    with pytest.raises(StaleFenceError):
        store.remember_health(stale)
    assert store.latest_health(org, scope) is None


@requires_postgres
def test_postgres_worker_health_missing_lease_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "health-missing-lease"
    with pytest.raises(StaleFenceError):
        store.remember_health(
            _worker_health(
                organization_id=org,
                scan_scope=scope,
                owner_id="worker-a",
                lease_epoch=1,
                fencing_token=1,
                now=clock.now(),
            )
        )
    assert store.latest_health(org, scope) is None


@requires_postgres
def test_postgres_worker_health_expired_lease_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "health-expired"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    clock.advance(31)
    with pytest.raises(StaleFenceError):
        store.remember_health(
            _worker_health(
                organization_id=org,
                scan_scope=scope,
                owner_id="worker-a",
                lease_epoch=1,
                fencing_token=1,
                now=clock.now(),
            )
        )
    assert store.latest_health(org, scope) is None


@requires_postgres
def test_postgres_worker_health_wrong_owner_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "health-wrong-owner"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    with pytest.raises(StaleFenceError):
        store.remember_health(
            _worker_health(
                organization_id=org,
                scan_scope=scope,
                owner_id="worker-b",
                lease_epoch=1,
                fencing_token=1,
                now=clock.now(),
            )
        )
    assert store.latest_health(org, scope) is None


@requires_postgres
def test_postgres_worker_health_stale_fence_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "health-stale-fence"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    with pytest.raises(StaleFenceError):
        store.remember_health(
            _worker_health(
                organization_id=org,
                scan_scope=scope,
                owner_id="worker-a",
                lease_epoch=1,
                fencing_token=99,
                now=clock.now(),
            )
        )
    assert store.latest_health(org, scope) is None


@requires_postgres
def test_postgres_observer_health_without_lease_is_allowed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "health-observer"
    snapshot = _observer_health(organization_id=org, scan_scope=scope, now=clock.now())
    store.remember_health(snapshot)
    stored = store.latest_health(org, scope)
    assert stored is not None
    assert stored.lease_owner is None
    assert stored.lease_epoch == 0
    assert stored.fencing_token == 0
    assert stored.reason_code == "observer"


@requires_postgres
def test_postgres_observer_health_cannot_overwrite_active_lease() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "health-observer-vs-active"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    store.remember_health(
        _worker_health(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-a",
            lease_epoch=1,
            fencing_token=1,
            now=clock.now(),
        )
    )
    with pytest.raises(StaleFenceError):
        store.remember_health(
            _observer_health(organization_id=org, scan_scope=scope, now=clock.now())
        )
    stored = store.latest_health(org, scope)
    assert stored is not None
    assert stored.lease_owner == "worker-a"
    assert stored.fencing_token == 1


@requires_postgres
def test_postgres_stale_holder_cannot_publish_successful_scan_state() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "success-stale"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    lineage = store.insert_lineage(
        ScanLineage(
            lineage_id=uuid4(),
            organization_id=org,
            principal_id=None,
            scan_scope=scope,
            request_hash="c" * 64,
            policy_id=uuid4(),
            policy_version=1,
            policy_content_hash="d" * 64,
            trigger_created_by=ScanTrigger.WORKER,
            created_at=clock.now(),
        )
    )
    attempt = store.insert_attempt(
        ScanAttempt(
            attempt_id=uuid4(),
            lineage_id=lineage.lineage_id,
            attempt_number=1,
            worker_id="worker-a",
            lease_epoch=1,
            fencing_token=1,
            trigger=ScanTrigger.WORKER,
            mode=EvaluationMode.PERSIST_EVIDENCE,
            status=ScanAttemptStatus.STARTED,
            started_at=clock.now(),
            heartbeat_at=clock.now(),
        )
    )
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    with pytest.raises(StaleFenceError):
        store.update_attempt(
            attempt.model_copy(
                update={
                    "status": ScanAttemptStatus.SUCCEEDED,
                    "finished_at": clock.now(),
                    "heartbeat_at": clock.now(),
                }
            )
        )


@requires_postgres
def test_postgres_latest_attempt_and_lineage_are_tenant_scoped() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    policy_a = _policy(clock)
    policy_b = _policy(clock)
    orch_a = _orch(store, clock)
    orch_b = _orch(
        store, clock, evaluator=ScriptedEvaluationBoundary(default=EvaluationStatus.FAILED)
    )
    request_a = _request(policy_a, key="tenant-a", scan_scope=SHARED_TENANT_SCOPE)
    request_b = _request(policy_b, key="tenant-b", scan_scope=SHARED_TENANT_SCOPE)
    result_a = orch_a.run_worker(request_a, worker_id="worker-a")
    result_b = orch_b.run_worker(request_b, worker_id="worker-b")
    assert result_a.published is True
    assert result_b.published is True
    latest_a = store.latest_attempt_for_scope(request_a.organization_id, SHARED_TENANT_SCOPE)
    latest_b = store.latest_attempt_for_scope(request_b.organization_id, SHARED_TENANT_SCOPE)
    assert latest_a is not None and latest_b is not None
    assert latest_a.lineage_id == result_a.lineage_id
    assert latest_b.lineage_id == result_b.lineage_id
    assert result_a.lineage_id is not None
    with pytest.raises(WatcherTenantMismatchError):
        store.get_lineage(result_a.lineage_id, request_b.organization_id)
    assert store.latest_attempt_for_scope(uuid4(), SHARED_TENANT_SCOPE) is None


@requires_postgres
def test_postgres_worker_crash_then_lease_expiry_recovery() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    evaluator = ScriptedEvaluationBoundary()
    policy = _policy(clock)
    request = _request(policy)
    crashing = _orch(
        store, clock, evaluator=evaluator, crash=NamedCrashBarrier("after_scan_attempt")
    )
    with pytest.raises(SimulatedWorkerCrashError):
        crashing.run_worker(request, worker_id="worker-a")
    scheduled = store.get_schedule(request.organization_id, None, "scan-1")
    assert scheduled is not None
    attempts = store.list_attempts(scheduled.lineage_id)
    assert attempts[0].status is ScanAttemptStatus.STARTED
    clock.advance(31)
    recovered = _orch(store, clock, evaluator=evaluator)
    result = recovered.run_worker(request, worker_id="worker-b")
    assert result.status.value == "succeeded"
    assert result.published is True
    scheduled = store.get_schedule(request.organization_id, None, "scan-1")
    assert scheduled is not None
    retries = store.list_attempts(scheduled.lineage_id)
    assert len(retries) == 2
    assert retries[1].fencing_token == 2
    assert retries[1].status is ScanAttemptStatus.SUCCEEDED
    assert retries[1].recovered_from_attempt_id == retries[0].attempt_id


@requires_postgres
def test_postgres_policy_version_immutable() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    policy = _policy(clock)
    stored = store.put_policy_version(policy)
    assert stored.content_hash == policy.content_hash
    again = store.put_policy_version(policy)
    assert again.content_hash == policy.content_hash
    mutated = policy.model_copy(update={"content_hash": "f" * 64})
    with pytest.raises(WatcherIdempotencyConflictError):
        store.put_policy_version(mutated)


@requires_postgres
def test_postgres_orchestrator_stale_fence_cannot_publish() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    policy = _policy(clock)
    request = _request(policy)

    class StealOnEvaluate(ScriptedEvaluationBoundary):
        def evaluate(self, command: EvaluationCommand) -> EvaluationOutcome:
            clock.advance(31)
            store.claim_lease(
                scan_scope=request.scan_scope,
                organization_id=request.organization_id,
                owner_id="worker-b",
                ttl_seconds=30,
                now=clock.now(),
            )
            return super().evaluate(command)

    stolen = _orch(store, clock, evaluator=StealOnEvaluate(), lease_ttl_seconds=30).run_worker(
        request, worker_id="worker-a"
    )
    assert stolen.published is False
    assert stolen.status.value == "rejected_stale_fence"
    scheduled = store.get_schedule(request.organization_id, None, "scan-1")
    assert scheduled is not None
    stale_attempts = store.list_attempts(scheduled.lineage_id)
    assert stale_attempts[0].status is ScanAttemptStatus.REJECTED_STALE_FENCE
    winner = _orch(store, clock).run_worker(request, worker_id="worker-b")
    assert winner.status.value == "succeeded"
    assert winner.published is True
    assert winner.fencing_token == 2


def _takeover_pair(store: WatcherStore, org: UUID, scope: str, clock: FakeClock) -> ScanLineage:
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    lineage = _lineage_row(store, org, scope, clock)
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    return lineage


@requires_postgres
def test_postgres_stale_holder_cannot_insert_attempt_after_takeover() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "insert-attempt-stale"
    lineage = _takeover_pair(store, org, scope, clock)
    with pytest.raises(StaleFenceError) as exc:
        store.insert_attempt(
            _scan_attempt(
                lineage, worker_id="worker-a", lease_epoch=1, fencing_token=1, clock=clock
            )
        )
    assert exc.value.details["cause"] == "mismatched_authority"
    assert store.list_attempts(lineage.lineage_id) == ()


@requires_postgres
def test_postgres_incomplete_worker_authority_cannot_insert_attempt() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "insert-attempt-incomplete"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    lineage = _lineage_row(store, org, scope, clock)
    with pytest.raises(StaleFenceError) as exc:
        store.insert_attempt(
            _scan_attempt(
                lineage, worker_id="worker-a", lease_epoch=None, fencing_token=None, clock=clock
            )
        )
    assert exc.value.details["cause"] == "incomplete_authority"
    assert store.list_attempts(lineage.lineage_id) == ()


@requires_postgres
def test_postgres_manual_attempt_without_worker_authority_is_allowed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "manual-attempt"
    lineage = _lineage_row(store, org, scope, clock)
    inserted = store.insert_attempt(
        _scan_attempt(lineage, worker_id=None, lease_epoch=None, fencing_token=None, clock=clock)
    )
    updated = store.update_attempt(
        inserted.model_copy(update={"status": ScanAttemptStatus.FAILED, "finished_at": clock.now()})
    )
    assert updated.status is ScanAttemptStatus.FAILED
    terminal = store.cas_lineage_terminal(
        lineage.lineage_id, updated.attempt_id, ScanAttemptStatus.FAILED.value, org
    )
    assert terminal.terminal_status is ScanAttemptStatus.FAILED


@requires_postgres
def test_postgres_stale_holder_cannot_update_failed_attempt_after_takeover() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "failed-attempt-stale"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    lineage = _lineage_row(store, org, scope, clock)
    attempt = store.insert_attempt(
        _scan_attempt(lineage, worker_id="worker-a", lease_epoch=1, fencing_token=1, clock=clock)
    )
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    with pytest.raises(StaleFenceError):
        store.update_attempt(
            attempt.model_copy(
                update={"status": ScanAttemptStatus.FAILED, "finished_at": clock.now()}
            )
        )
    stored = store.get_attempt(attempt.attempt_id)
    assert stored is not None
    assert stored.status is ScanAttemptStatus.STARTED


@requires_postgres
def test_postgres_current_owner_can_publish_failed_attempt() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "failed-attempt-current"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    lineage = _lineage_row(store, org, scope, clock)
    attempt = store.insert_attempt(
        _scan_attempt(lineage, worker_id="worker-a", lease_epoch=1, fencing_token=1, clock=clock)
    )
    updated = store.update_attempt(
        attempt.model_copy(update={"status": ScanAttemptStatus.FAILED, "finished_at": clock.now()})
    )
    assert updated.status is ScanAttemptStatus.FAILED
    terminal = store.cas_lineage_terminal(
        lineage.lineage_id, updated.attempt_id, ScanAttemptStatus.FAILED.value, org
    )
    assert terminal.terminal_status is ScanAttemptStatus.FAILED


@requires_postgres
def test_postgres_stale_holder_cannot_insert_source_fetch_after_takeover() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "source-fetch-stale"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    lineage = _lineage_row(store, org, scope, clock)
    attempt = store.insert_attempt(
        _scan_attempt(lineage, worker_id="worker-a", lease_epoch=1, fencing_token=1, clock=clock)
    )
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    with pytest.raises(StaleFenceError):
        store.insert_source_fetch(
            SourceFetchAttempt(
                fetch_attempt_id=uuid4(),
                scan_attempt_id=attempt.attempt_id,
                lineage_id=lineage.lineage_id,
                lease_epoch=1,
                fencing_token=1,
                subject_id=uuid4(),
                status=UnitAttemptStatus.FAILED,
                reason_code="stale",
                created_at=clock.now(),
                finished_at=clock.now(),
            )
        )
    assert store.list_source_fetches(attempt.attempt_id) == ()


@requires_postgres
def test_postgres_stale_holder_cannot_insert_subscription_eval_after_takeover() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "sub-eval-stale"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    lineage = _lineage_row(store, org, scope, clock)
    attempt = store.insert_attempt(
        _scan_attempt(lineage, worker_id="worker-a", lease_epoch=1, fencing_token=1, clock=clock)
    )
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    with pytest.raises(StaleFenceError):
        store.insert_subscription_eval(
            SubscriptionEvaluationAttempt(
                subscription_attempt_id=uuid4(),
                scan_attempt_id=attempt.attempt_id,
                lineage_id=lineage.lineage_id,
                lease_epoch=1,
                fencing_token=1,
                subject_id=uuid4(),
                status=UnitAttemptStatus.FAILED,
                reason_code="stale",
                created_at=clock.now(),
                finished_at=clock.now(),
            )
        )
    assert store.list_subscription_evals(attempt.attempt_id) == ()


@requires_postgres
def test_postgres_stale_holder_cannot_publish_failed_lineage_after_takeover() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "lineage-failed-stale"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    lineage = _lineage_row(store, org, scope, clock)
    attempt = store.insert_attempt(
        _scan_attempt(lineage, worker_id="worker-a", lease_epoch=1, fencing_token=1, clock=clock)
    )
    clock.advance(31)
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-b", ttl_seconds=30, now=clock.now()
    )
    with pytest.raises(StaleFenceError):
        store.cas_lineage_terminal(
            lineage.lineage_id, attempt.attempt_id, ScanAttemptStatus.FAILED.value, org
        )
    stored = store.get_lineage(lineage.lineage_id, org)
    assert stored is not None
    assert stored.terminal_status is None
    assert stored.terminal_attempt_id is None


@requires_postgres
def test_postgres_takeover_race_stale_failed_write_fails_closed() -> None:
    store = build_postgres_watcher_store(persistence_session_factory())
    clock = FakeClock()
    org = uuid4()
    scope = "takeover-race-failed"
    store.claim_lease(
        organization_id=org, scan_scope=scope, owner_id="worker-a", ttl_seconds=30, now=clock.now()
    )
    lineage = _lineage_row(store, org, scope, clock)
    attempt = store.insert_attempt(
        _scan_attempt(lineage, worker_id="worker-a", lease_epoch=1, fencing_token=1, clock=clock)
    )
    clock.advance(31)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []
    lock = threading.Lock()

    def claim_b() -> None:
        barrier.wait(timeout=20)
        store.claim_lease(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-b",
            ttl_seconds=30,
            now=clock.now(),
        )

    def stale_fail() -> None:
        barrier.wait(timeout=20)
        try:
            store.update_attempt(
                attempt.model_copy(
                    update={"status": ScanAttemptStatus.FAILED, "finished_at": clock.now()}
                )
            )
        except BaseException as exc:
            with lock:
                errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim_b), pool.submit(stale_fail)]
        for future in futures:
            future.result(timeout=30)
    stored = store.get_attempt(attempt.attempt_id)
    assert stored is not None
    assert stored.status is ScanAttemptStatus.STARTED
    assert any(isinstance(item, StaleFenceError) for item in errors)
    lease = store.get_lease(org, scope)
    assert lease is not None
    assert lease.owner_id == "worker-b"
    assert lease.fencing_token == 2
