"""Worker lease exclusivity. Same owner id is not a shared mutex bypass."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from multiprocessing import get_context
from uuid import uuid4

import pytest

from app.persistence.composition import build_postgres_watcher_store
from app.watcher.errors import StaleFenceError
from app.watcher.memory import FakeClock, InMemoryWatcherStore
from tests.support.postgres_persistence import (
    POSTGRES_URL,
    persistence_session_factory,
    requires_postgres,
)


def _instance_id(prefix: str) -> str:
    from app.workers.watcher_paper import new_worker_instance_id

    return new_worker_instance_id(prefix)


def test_configured_worker_id_is_not_the_process_identity() -> None:
    left = _instance_id("watcher-paper-1")
    right = _instance_id("watcher-paper-1")
    assert left != right
    assert left != "watcher-paper-1"
    assert right != "watcher-paper-1"
    assert left.startswith("watcher-paper-1:")
    assert right.startswith("watcher-paper-1:")


def test_same_owner_without_token_cannot_renew() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    org = uuid4()
    scope = "same-owner"
    acquired, lease, reason = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id="watcher-paper-1",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert acquired is True
    assert reason == "claimed"
    again, held, held_reason = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id="watcher-paper-1",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert again is False
    assert held_reason == "lease_held"
    assert held.fencing_token == lease.fencing_token
    renewed, current, renew_reason = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id="watcher-paper-1",
        ttl_seconds=30,
        now=clock.now(),
        fencing_token=lease.fencing_token,
    )
    assert renewed is True
    assert renew_reason == "renewed"
    assert current.fencing_token == lease.fencing_token


def test_takeover_after_expiry_rejects_stale_fence() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    org = uuid4()
    scope = "restart"
    _acquired, first, _reason = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id="watcher-paper-1:aaaaaaaaaaaaaaaa",
        ttl_seconds=30,
        now=clock.now(),
    )
    clock.advance(31)
    restarted_id = _instance_id("watcher-paper-1")
    taken, second, reason = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id=restarted_id,
        ttl_seconds=30,
        now=clock.now(),
    )
    assert taken is True
    assert reason == "claimed"
    assert second.lease_epoch == first.lease_epoch + 1
    assert (
        store.fence_is_active(
            organization_id=org,
            scan_scope=scope,
            owner_id=first.owner_id or "",
            fencing_token=first.fencing_token,
            now=clock.now(),
        )
        is False
    )


def test_two_instance_workers_contend_for_one_lease() -> None:
    store = InMemoryWatcherStore()
    now = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)
    org = uuid4()
    scope = "two-workers"
    left_id = _instance_id("watcher-paper-1")
    right_id = _instance_id("watcher-paper-1")
    left_ok, left, _left_reason = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id=left_id,
        ttl_seconds=30,
        now=now,
    )
    right_ok, _right, right_reason = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id=right_id,
        ttl_seconds=30,
        now=now,
    )
    assert left_ok is True
    assert right_ok is False
    assert right_reason == "lease_held"
    later = now + timedelta(seconds=31)
    taken, winner, reason = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id=right_id,
        ttl_seconds=30,
        now=later,
    )
    assert taken is True
    assert reason == "claimed"
    assert winner.owner_id == right_id
    assert winner.fencing_token != left.fencing_token


def _process_claim(payload: dict[str, str]) -> tuple[bool, str, int]:
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool

    from app.persistence.watcher_postgres import PostgresWatcherStore

    engine = create_engine(payload["url"], poolclass=NullPool, future=True)
    store = PostgresWatcherStore(sessionmaker(bind=engine, expire_on_commit=False))
    acquired, lease, reason = store.claim_lease(
        organization_id=UUID(payload["org"]),
        scan_scope=payload["scope"],
        owner_id=payload["owner"],
        ttl_seconds=30,
        now=datetime.fromisoformat(payload["now"]),
    )
    engine.dispose()
    return acquired, reason, lease.fencing_token


@requires_postgres
def test_two_processes_with_one_owner_cannot_both_hold_the_lease() -> None:
    persistence_session_factory()
    org = uuid4()
    now = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)
    payload = {
        "url": POSTGRES_URL,
        "org": str(org),
        "scope": "process-contention",
        "owner": "watcher-paper-1",
        "now": now.isoformat(),
    }
    context = get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=context) as pool:
        results = list(pool.map(_process_claim, [payload, payload]))
    acquired = [item for item in results if item[0]]
    rejected = [item for item in results if not item[0]]
    assert len(acquired) == 1
    assert acquired[0][1] == "claimed"
    assert len(rejected) == 1
    assert rejected[0][1] == "lease_held"

    store = build_postgres_watcher_store(persistence_session_factory())
    # Schema was recreated above; re-seed the contention on a fresh database
    # and prove expiry takeover plus stale-token rejection in-process.
    fresh_org = uuid4()
    scope = "process-restart"
    first_ok, first, first_reason = store.claim_lease(
        organization_id=fresh_org,
        scan_scope=scope,
        owner_id="watcher-paper-1:process-a",
        ttl_seconds=30,
        now=now,
    )
    assert first_ok is True
    assert first_reason == "claimed"
    blocked, _blocked_lease, blocked_reason = store.claim_lease(
        organization_id=fresh_org,
        scan_scope=scope,
        owner_id="watcher-paper-1:process-a",
        ttl_seconds=30,
        now=now,
    )
    assert blocked is False
    assert blocked_reason == "lease_held"
    taken, second, taken_reason = store.claim_lease(
        organization_id=fresh_org,
        scan_scope=scope,
        owner_id="watcher-paper-1:process-b",
        ttl_seconds=30,
        now=now + timedelta(seconds=31),
    )
    assert taken is True
    assert taken_reason == "claimed"
    assert second.fencing_token == first.fencing_token + 1
    with pytest.raises(StaleFenceError):
        store.record_heartbeat(
            organization_id=fresh_org,
            scan_scope=scope,
            owner_id="watcher-paper-1:process-a",
            lease_epoch=first.lease_epoch,
            fencing_token=first.fencing_token,
            now=now + timedelta(seconds=31),
        )
