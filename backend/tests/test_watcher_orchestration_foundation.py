"""Watcher orchestration foundation: fencing, leases, lineage, and parity.

No market adapters, candidates, Telegram, execution, journal, or ORM models.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.watcher.composition import build_orchestrator
from app.watcher.contracts import (
    EvaluationCommand,
    EvaluationMode,
    EvaluationOutcome,
    EvaluationStatus,
    ScanAttemptStatus,
    ScanRequest,
    ScanTrigger,
    UnitAttempt,
    UnitAttemptKind,
    UnitAttemptStatus,
    WatcherHealthState,
    WatcherPolicyIdentity,
    WatcherPolicyVersion,
)
from app.watcher.errors import (
    SimulatedWorkerCrashError,
    WatcherIdempotencyConflictError,
    WatcherTenantMismatchError,
)
from app.watcher.hashing import derive_scan_scope, evaluation_input_hash, policy_content_hash
from app.watcher.memory import (
    FakeClock,
    InMemoryWatcherStore,
    ScriptedEvaluationBoundary,
    SideEffectProbe,
)
from app.watcher.orchestrator import WatcherOrchestrator
from app.watcher.ports import NamedCrashBarrier
from app.watcher.settings import runtime_config_from_settings

WATCHER_SRC = Path(__file__).resolve().parents[1] / "src" / "app" / "watcher"


def _policy(clock: FakeClock, *, version: int = 1) -> WatcherPolicyVersion:
    identity = WatcherPolicyIdentity(
        policy_id=uuid4(),
        organization_id=uuid4(),
        user_id=uuid4(),
        watchlist_item_id=uuid4(),
    )
    draft = WatcherPolicyVersion(
        identity=identity,
        version=version,
        timeframe="15m",
        enabled=True,
        created_by=identity.user_id,
        created_at=clock.now(),
        content_hash="0" * 64,
    )
    return draft.model_copy(update={"content_hash": policy_content_hash(draft)})


def _request(
    policy: WatcherPolicyVersion,
    *,
    key: str = "scan-1",
    principal_id: UUID | None = None,
    timeframe: str | None = "15m",
    organization_id: UUID | None = None,
    extra_items: tuple[UUID, ...] = (),
    scan_scope: str | None = None,
) -> ScanRequest:
    org = organization_id or policy.identity.organization_id
    items = (policy.identity.watchlist_item_id, *extra_items)
    return ScanRequest(
        organization_id=org,
        principal_id=principal_id,
        scan_scope=scan_scope
        or derive_scan_scope(
            policy_id=policy.identity.policy_id,
            timeframe=timeframe,
        ),
        policy_id=policy.identity.policy_id,
        policy_version=policy.version,
        policy_content_hash=policy.content_hash,
        watchlist_item_ids=items,
        timeframe=timeframe,
        idempotency_key=key,
    )


def _enabled(
    **kwargs: object,
) -> tuple[
    WatcherOrchestrator,
    FakeClock,
    InMemoryWatcherStore,
    object,
    SideEffectProbe,
]:
    probe = SideEffectProbe()
    clock = kwargs.pop("clock", FakeClock())
    store = kwargs.pop("store", InMemoryWatcherStore())
    evaluator = kwargs.pop("evaluator", ScriptedEvaluationBoundary())
    if not isinstance(clock, FakeClock):
        raise TypeError("clock must be FakeClock")
    if not isinstance(store, InMemoryWatcherStore):
        raise TypeError("store must be InMemoryWatcherStore")
    orch = build_orchestrator(
        enabled=True,
        clock=clock,
        store=store,
        evaluator=evaluator,  # type: ignore[arg-type]
        side_effects=probe,
        **kwargs,  # type: ignore[arg-type]
    )
    return orch, clock, store, evaluator, probe


def _assert_no_side_effects(probe: SideEffectProbe) -> None:
    assert probe.execution == []
    assert probe.journal == []
    assert probe.telegram == []
    assert probe.unused is True


def test_watcher_feature_disabled_by_default() -> None:
    settings = Settings()
    assert settings.market_watcher_enabled is False
    assert settings.market_watcher_bridge_enabled is False
    assert settings.watcher_orchestration_enabled is False
    assert settings.worker_enabled is False
    assert settings.enable_real_trading is False
    assert settings.real_trading_enabled is False
    assert settings.telegram_alerts_enabled is False
    assert settings.automatic_telegram_delivery_enabled is False
    config = runtime_config_from_settings(settings)
    assert config.enabled is False


def test_disabled_orchestrator_blocks_schedule_worker_and_manual() -> None:
    probe = SideEffectProbe()
    evaluator = ScriptedEvaluationBoundary()
    clock = FakeClock()
    policy = _policy(clock)
    request = _request(policy, principal_id=policy.identity.user_id)
    orch = build_orchestrator(
        enabled=False,
        clock=clock,
        evaluator=evaluator,
        side_effects=probe,
    )
    scheduled = orch.schedule(request)
    assert scheduled.status.value == "blocked"
    assert scheduled.lineage_id is None
    manual = orch.evaluate_manual(request)
    assert manual.outcome.status is EvaluationStatus.BLOCKED
    assert manual.persisted is False
    assert evaluator.call_count == 0
    worker = orch.run_worker(request, worker_id="worker-1")
    assert worker.status.value == "blocked"
    assert worker.health.state is WatcherHealthState.BLOCKED
    assert evaluator.call_count == 0
    _assert_no_side_effects(probe)


def test_duplicate_scheduled_scan_is_idempotent() -> None:
    orch, clock, store, _evaluator, probe = _enabled()
    policy = _policy(clock)
    store.put_policy_version(policy)
    request = _request(policy)
    first = orch.schedule(request)
    second = orch.schedule(request)
    assert first.replayed is False
    assert second.replayed is True
    assert second.lineage_id == first.lineage_id
    assert second.scheduled_scan_id == first.scheduled_scan_id
    _assert_no_side_effects(probe)


def test_same_request_replay_does_not_re_evaluate() -> None:
    orch, clock, store, evaluator, probe = _enabled()
    policy = _policy(clock)
    store.put_policy_version(policy)
    request = _request(policy)
    first = orch.run_worker(request, worker_id="worker-1")
    second = orch.run_worker(request, worker_id="worker-1")
    assert first.replayed is False
    assert first.status.value == "succeeded"
    assert second.replayed is True
    assert second.attempt_id == first.attempt_id
    assert evaluator.call_count == 1
    assert first.lineage_id is not None
    lineage = store.get_lineage(first.lineage_id, policy.identity.organization_id)
    assert lineage is not None
    assert len(store.list_attempts(lineage.lineage_id)) == 1
    _assert_no_side_effects(probe)


def test_same_key_different_request_is_isolated_conflict() -> None:
    orch, clock, store, _evaluator, probe = _enabled()
    policy = _policy(clock)
    other = _policy(clock)
    store.put_policy_version(policy)
    request = _request(policy, key="shared-key")
    conflict = _request(other, key="shared-key", organization_id=policy.identity.organization_id)
    first = orch.schedule(request)
    with pytest.raises(WatcherIdempotencyConflictError):
        orch.schedule(conflict)
    stored = store.get_schedule(policy.identity.organization_id, None, "shared-key")
    assert stored is not None
    assert stored.lineage_id == first.lineage_id
    _assert_no_side_effects(probe)


def test_different_request_isolation() -> None:
    orch, clock, store, evaluator, probe = _enabled()
    policy_a = _policy(clock)
    policy_b = _policy(clock)
    req_a = _request(policy_a, key="a")
    req_b = _request(policy_b, key="b")
    result_a = orch.run_worker(req_a, worker_id="worker-a")
    result_b = orch.run_worker(req_b, worker_id="worker-b")
    assert result_a.lineage_id != result_b.lineage_id
    assert result_a.request_hash != result_b.request_hash
    assert evaluator.call_count == 2
    assert result_a.lineage_id is not None
    assert result_b.lineage_id is not None
    assert store.list_attempts(result_a.lineage_id)[0].lineage_id == result_a.lineage_id
    assert store.list_attempts(result_b.lineage_id)[0].lineage_id == result_b.lineage_id
    _assert_no_side_effects(probe)


def test_different_organization_same_key_is_isolated() -> None:
    orch, clock, store, _evaluator, probe = _enabled()
    policy_a = _policy(clock)
    policy_b = _policy(clock)
    result_a = orch.schedule(_request(policy_a, key="same"))
    result_b = orch.schedule(_request(policy_b, key="same"))
    assert result_a.lineage_id != result_b.lineage_id
    assert store.get_schedule(policy_a.identity.organization_id, None, "same") is not None
    assert store.get_schedule(policy_b.identity.organization_id, None, "same") is not None
    _assert_no_side_effects(probe)


def test_concurrent_worker_claim_single_owner() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    org = uuid4()
    scope = "policy-15m"
    barrier = threading.Barrier(2)
    results: list[tuple[bool, int, str]] = []

    def _claim(owner: str) -> None:
        barrier.wait()
        acquired, lease, reason = store.claim_lease(
            scan_scope=scope,
            organization_id=org,
            owner_id=owner,
            ttl_seconds=30,
            now=clock.now(),
        )
        results.append((acquired, lease.fencing_token, reason))

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(_claim, "worker-a")
        pool.submit(_claim, "worker-b")
        pool.shutdown(wait=True)

    acquired = [item for item in results if item[0]]
    rejected = [item for item in results if not item[0]]
    assert len(acquired) == 1
    assert len(rejected) == 1
    assert rejected[0][2] == "lease_held"
    lease = store.get_lease(org, scope)
    assert lease is not None
    assert lease.fencing_token == acquired[0][1]


def test_concurrent_orchestrator_claim_one_publisher() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    policy = _policy(clock)
    request = _request(policy)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def _run(worker_id: str) -> None:
        orch = build_orchestrator(
            enabled=True,
            store=store,
            clock=clock,
            evaluator=ScriptedEvaluationBoundary(),
            side_effects=SideEffectProbe(),
        )
        barrier.wait()
        result = orch.run_worker(request, worker_id=worker_id)
        outcomes.append(result.status.value)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(_run, "worker-a")
        pool.submit(_run, "worker-b")
        pool.shutdown(wait=True)

    assert sorted(outcomes) == ["skipped", "succeeded"]
    scheduled = store.get_schedule(policy.identity.organization_id, None, "scan-1")
    assert scheduled is not None
    attempts = store.list_attempts(scheduled.lineage_id)
    succeeded = [item for item in attempts if item.status is ScanAttemptStatus.SUCCEEDED]
    assert len(succeeded) == 1


def test_expired_lease_allows_new_owner_and_invalidates_old_fence() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    org = uuid4()
    scope = "scope-expired"
    acquired_a, lease_a, _reason_a = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id="worker-a",
        ttl_seconds=10,
        now=clock.now(),
    )
    assert acquired_a is True
    clock.advance(11)
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
    acquired_b, lease_b, _reason_b = store.claim_lease(
        organization_id=org,
        scan_scope=scope,
        owner_id="worker-b",
        ttl_seconds=10,
        now=clock.now(),
    )
    assert acquired_b is True
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
    assert (
        store.fence_is_active(
            organization_id=org,
            scan_scope=scope,
            owner_id="worker-b",
            fencing_token=lease_b.fencing_token,
            now=clock.now(),
        )
        is True
    )


def test_stale_fence_cannot_publish_valid_results() -> None:
    clock = FakeClock()
    store = InMemoryWatcherStore()
    policy = _policy(clock)
    request = _request(policy)

    class _StealOnEvaluate(ScriptedEvaluationBoundary):
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

    orch_a = build_orchestrator(
        enabled=True,
        lease_ttl_seconds=30,
        store=store,
        clock=clock,
        evaluator=_StealOnEvaluate(),
        side_effects=SideEffectProbe(),
    )
    stolen = orch_a.run_worker(request, worker_id="worker-a")
    assert stolen.status.value == "rejected_stale_fence"
    assert stolen.published is False
    assert stolen.attempt_id is not None
    attempt = store.get_attempt(stolen.attempt_id)
    assert attempt is not None
    assert attempt.status is ScanAttemptStatus.REJECTED_STALE_FENCE
    assert stolen.lineage_id is not None
    lineage = store.get_lineage(stolen.lineage_id, request.organization_id)
    assert lineage is not None
    assert lineage.terminal_status is not ScanAttemptStatus.SUCCEEDED

    orch_b = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=ScriptedEvaluationBoundary(),
        side_effects=SideEffectProbe(),
    )
    winner = orch_b.run_worker(request, worker_id="worker-b")
    assert winner.status.value == "succeeded"
    assert winner.published is True
    assert winner.fencing_token != stolen.fencing_token
    assert winner.lineage_id is not None
    refreshed = store.get_lineage(winner.lineage_id, request.organization_id)
    assert refreshed is not None
    assert refreshed.terminal_attempt_id == winner.attempt_id
    assert refreshed.terminal_status is ScanAttemptStatus.SUCCEEDED


def test_worker_crash_leaves_started_attempt() -> None:
    clock = FakeClock()
    store = InMemoryWatcherStore()
    policy = _policy(clock)
    request = _request(policy)
    orch = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        crash=NamedCrashBarrier("after_scan_attempt"),
        side_effects=SideEffectProbe(),
    )
    with pytest.raises(SimulatedWorkerCrashError):
        orch.run_worker(request, worker_id="worker-1")
    scheduled = store.get_schedule(policy.identity.organization_id, None, "scan-1")
    assert scheduled is not None
    attempts = store.list_attempts(scheduled.lineage_id)
    assert len(attempts) == 1
    assert attempts[0].status is ScanAttemptStatus.STARTED
    assert attempts[0].finished_at is None


def test_retry_after_crash_completes_same_lineage() -> None:
    clock = FakeClock()
    store = InMemoryWatcherStore()
    evaluator = ScriptedEvaluationBoundary()
    policy = _policy(clock)
    request = _request(policy)
    crashing = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=evaluator,
        crash=NamedCrashBarrier("after_scan_attempt"),
        side_effects=SideEffectProbe(),
    )
    with pytest.raises(SimulatedWorkerCrashError):
        crashing.run_worker(request, worker_id="worker-1")
    recovered = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=evaluator,
        side_effects=SideEffectProbe(),
    )
    result = recovered.run_worker(request, worker_id="worker-1")
    assert result.status.value == "succeeded"
    scheduled = store.get_schedule(policy.identity.organization_id, None, "scan-1")
    assert scheduled is not None
    attempts = store.list_attempts(scheduled.lineage_id)
    assert attempts[0].status is ScanAttemptStatus.SUCCEEDED
    assert evaluator.call_count == 1
    assert result.lineage_id == scheduled.lineage_id


def test_retry_after_failure_opens_new_attempt() -> None:
    evaluator = ScriptedEvaluationBoundary(
        outcomes=[EvaluationStatus.FAILED, EvaluationStatus.SUCCEEDED]
    )
    orch, clock, store, _scripted, probe = _enabled(evaluator=evaluator)
    policy = _policy(clock)
    request = _request(policy)
    first = orch.run_worker(request, worker_id="worker-1")
    assert first.status.value == "failed"
    assert first.published is True
    assert first.outcome is not None
    assert first.outcome.status is EvaluationStatus.FAILED
    second = orch.run_worker(request, worker_id="worker-1")
    assert second.status.value == "succeeded"
    assert first.lineage_id is not None
    attempts = store.list_attempts(first.lineage_id)
    assert [item.attempt_number for item in attempts] == [1, 2]
    assert attempts[1].recovered_from_attempt_id == attempts[0].attempt_id
    assert evaluator.call_count == 2
    _assert_no_side_effects(probe)


def test_manual_and_worker_boundary_equivalence() -> None:
    evaluator = ScriptedEvaluationBoundary()
    clock = FakeClock()
    store = InMemoryWatcherStore()
    probe = SideEffectProbe()
    orch = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=evaluator,
        side_effects=probe,
    )
    policy = _policy(clock)
    request = _request(policy, principal_id=policy.identity.user_id)
    manual = orch.evaluate_manual(request, mode=EvaluationMode.PREVIEW)
    worker = orch.run_worker(
        request.model_copy(update={"principal_id": None, "idempotency_key": "worker-scan"}),
        worker_id="worker-1",
    )
    assert manual.outcome.status is EvaluationStatus.SUCCEEDED
    assert worker.outcome is not None
    assert worker.outcome.status is EvaluationStatus.SUCCEEDED
    assert manual.evaluation_input_hash == worker.outcome.evaluation_input_hash
    assert manual.persisted is False
    assert worker.published is True
    assert evaluator.commands[0].trigger is ScanTrigger.MANUAL
    assert evaluator.commands[1].trigger is ScanTrigger.WORKER
    assert (
        evaluator.commands[0].evaluation_input_hash == evaluator.commands[1].evaluation_input_hash
    )
    semantic_manual = request.model_copy(update={"principal_id": None, "idempotency_key": "x"})
    semantic_worker = request.model_copy(update={"principal_id": None, "idempotency_key": "y"})
    assert evaluation_input_hash(semantic_manual) == evaluation_input_hash(semantic_worker)
    _assert_no_side_effects(probe)


def test_failure_propagation_does_not_become_success() -> None:
    class _LyingEvaluator(ScriptedEvaluationBoundary):
        def evaluate(self, command: EvaluationCommand) -> EvaluationOutcome:
            self.commands.append(command)
            item = command.request.watchlist_item_ids[0]
            return EvaluationOutcome(
                command_id=command.command_id,
                request_hash=command.request_hash,
                evaluation_input_hash=command.evaluation_input_hash,
                status=EvaluationStatus.SUCCEEDED,
                reason_code="pretend_ok",
                evaluated_units=1,
                failed_units=1,
                unit_attempts=(
                    UnitAttempt(
                        kind=UnitAttemptKind.SUBSCRIPTION_EVALUATION,
                        subject_id=item,
                        status=UnitAttemptStatus.FAILED,
                        reason_code="unit_failed",
                    ),
                ),
                error="unit exploded",
                candidate_ids=(),
            )

    orch, clock, store, _evaluator, probe = _enabled(evaluator=_LyingEvaluator())
    policy = _policy(clock)
    result = orch.run_worker(_request(policy), worker_id="worker-1")
    assert result.status.value == "failed"
    assert result.outcome is not None
    assert result.outcome.status is EvaluationStatus.FAILED
    assert result.outcome.reason_code == "failure_not_propagated"
    assert result.lineage_id is not None
    lineage = store.get_lineage(result.lineage_id, policy.identity.organization_id)
    assert lineage is not None
    assert lineage.terminal_status is ScanAttemptStatus.FAILED
    _assert_no_side_effects(probe)


def test_evaluator_exception_is_failed_scan() -> None:
    evaluator = ScriptedEvaluationBoundary(
        raise_on=1, raise_exc=RuntimeError("api_key=supersecret boom")
    )
    orch, clock, store, _scripted, probe = _enabled(evaluator=evaluator)
    policy = _policy(clock)
    result = orch.run_worker(_request(policy), worker_id="worker-1")
    assert result.status.value == "failed"
    assert result.outcome is not None
    assert result.outcome.status is EvaluationStatus.FAILED
    assert result.attempt_id is not None
    attempt = store.get_attempt(result.attempt_id)
    assert attempt is not None
    assert attempt.status is ScanAttemptStatus.FAILED
    assert "supersecret" not in (attempt.sanitized_error or "")
    _assert_no_side_effects(probe)


def test_health_degradation_and_stale() -> None:
    evaluator = ScriptedEvaluationBoundary(default=EvaluationStatus.DEGRADED)
    orch, clock, _store, _scripted, probe = _enabled(
        evaluator=evaluator,
        heartbeat_stale_after_seconds=90,
        lease_ttl_seconds=30,
    )
    policy = _policy(clock)
    request = _request(policy)
    result = orch.run_worker(request, worker_id="worker-1")
    assert result.health.state is WatcherHealthState.DEGRADED
    clock.advance(91)
    stale = orch.health(request.organization_id, request.scan_scope)
    assert stale.state is WatcherHealthState.STALE
    _assert_no_side_effects(probe)


def test_health_healthy_after_success() -> None:
    orch, clock, _store, _evaluator, probe = _enabled()
    policy = _policy(clock)
    result = orch.run_worker(_request(policy), worker_id="worker-1")
    assert result.health.state is WatcherHealthState.HEALTHY
    _assert_no_side_effects(probe)


def test_persist_and_notify_is_blocked_without_telegram() -> None:
    orch, clock, _store, evaluator, probe = _enabled()
    policy = _policy(clock)
    request = _request(policy, principal_id=policy.identity.user_id)
    result = orch.evaluate_manual(request, mode=EvaluationMode.PERSIST_AND_NOTIFY)
    assert result.outcome.status is EvaluationStatus.BLOCKED
    assert result.reason_code == "notify_disabled"
    assert evaluator.call_count == 0
    _assert_no_side_effects(probe)


def test_scan_lineage_is_immutable_across_retry() -> None:
    evaluator = ScriptedEvaluationBoundary(
        outcomes=[EvaluationStatus.FAILED, EvaluationStatus.SUCCEEDED]
    )
    orch, clock, store, _scripted, probe = _enabled(evaluator=evaluator)
    policy = _policy(clock)
    request = _request(policy)
    first = orch.run_worker(request, worker_id="worker-1")
    second = orch.run_worker(request, worker_id="worker-1")
    assert first.lineage_id == second.lineage_id
    assert first.lineage_id is not None
    lineage = store.get_lineage(first.lineage_id, policy.identity.organization_id)
    assert lineage is not None
    assert lineage.request_hash == first.request_hash
    attempts = store.list_attempts(lineage.lineage_id)
    assert attempts[0].lineage_id == lineage.lineage_id
    assert attempts[1].lineage_id == lineage.lineage_id
    assert store.list_subscription_evals(attempts[1].attempt_id)
    _assert_no_side_effects(probe)


def test_candidate_ids_from_evaluator_are_rejected() -> None:
    class _CandidateEvaluator(ScriptedEvaluationBoundary):
        def evaluate(self, command: EvaluationCommand) -> EvaluationOutcome:
            outcome = super().evaluate(command)
            return outcome.model_copy(update={"candidate_ids": (uuid4(),)})

    orch, clock, _store, _evaluator, probe = _enabled(evaluator=_CandidateEvaluator())
    policy = _policy(clock)
    result = orch.run_worker(_request(policy), worker_id="worker-1")
    assert result.outcome is not None
    assert result.outcome.candidate_ids == ()
    assert result.outcome.status is EvaluationStatus.FAILED
    assert result.outcome.reason_code == "candidate_creation_forbidden"
    _assert_no_side_effects(probe)


def test_no_execution_journal_or_telegram_side_effects_on_success_paths() -> None:
    orch, clock, store, evaluator, probe = _enabled()
    policy = _policy(clock)
    request = _request(policy, principal_id=policy.identity.user_id)
    orch.evaluate_manual(request, mode=EvaluationMode.PREVIEW)
    orch.evaluate_manual(
        request.model_copy(update={"idempotency_key": "persist"}),
        mode=EvaluationMode.PERSIST_EVIDENCE,
    )
    orch.run_worker(
        request.model_copy(update={"principal_id": None, "idempotency_key": "w"}),
        worker_id="worker-1",
    )
    assert evaluator.call_count == 3
    names = {event.name for event in store.events()}
    assert "watcher_scan_scheduled" in names
    _assert_no_side_effects(probe)


def test_source_fetch_tokens_are_stored_not_interpreted() -> None:
    class _DeferredSource(ScriptedEvaluationBoundary):
        def evaluate(self, command: EvaluationCommand) -> EvaluationOutcome:
            base = super().evaluate(command)
            extra = UnitAttempt(
                kind=UnitAttemptKind.SOURCE_FETCH,
                subject_id=command.request.watchlist_item_ids[0],
                status=UnitAttemptStatus.SUCCEEDED,
                reason_code="deferred_to_agent_1",
                source_freshness_token="opaque-freshness-token",
            )
            return base.model_copy(
                update={
                    "unit_attempts": (*base.unit_attempts, extra),
                    "evaluated_units": 2,
                }
            )

    orch, clock, store, _evaluator, probe = _enabled(evaluator=_DeferredSource())
    policy = _policy(clock)
    result = orch.run_worker(_request(policy), worker_id="worker-1")
    assert result.status.value == "succeeded"
    assert result.attempt_id is not None
    fetches = store.list_source_fetches(result.attempt_id)
    assert len(fetches) == 1
    assert fetches[0].source_freshness_token == "opaque-freshness-token"
    _assert_no_side_effects(probe)


def test_watcher_sources_do_not_import_forbidden_modules() -> None:
    forbidden = (
        "from app.services.execution",
        "import app.services.execution",
        "from app.services.journal",
        "from app.db.models",
        "from app.providers.alert_delivery",
        "from app.services.telegram",
        "from app.services.blofin",
        "alembic",
    )
    for path in WATCHER_SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for snippet in forbidden:
            assert snippet not in text, f"{path.name} contains {snippet}"


def test_settings_fixture_keeps_watcher_disabled(settings: Settings) -> None:
    assert settings.watcher_orchestration_enabled is False
    assert settings.market_watcher_enabled is False
    assert runtime_config_from_settings(settings).enabled is False


SHARED_TENANT_SCOPE = "identical-scan-scope"


def test_derive_scan_scope_does_not_embed_organization_id() -> None:
    org = uuid4()
    policy_id = uuid4()
    scope = derive_scan_scope(policy_id=policy_id, timeframe="15m")
    assert str(org) not in scope
    assert str(policy_id) in scope
    assert ":" in scope


def test_two_organizations_same_scan_scope_concurrent_lease_acquisition() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    org_a = uuid4()
    org_b = uuid4()
    barrier = threading.Barrier(2)
    results: dict[str, tuple[bool, int, str]] = {}
    lock = threading.Lock()

    def _claim(label: str, org: UUID) -> None:
        barrier.wait()
        acquired, lease, reason = store.claim_lease(
            organization_id=org,
            scan_scope=SHARED_TENANT_SCOPE,
            owner_id=f"worker-{label}",
            ttl_seconds=30,
            now=clock.now(),
        )
        with lock:
            results[label] = (acquired, lease.fencing_token, reason)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(_claim, "a", org_a)
        pool.submit(_claim, "b", org_b)
        pool.shutdown(wait=True)

    assert results["a"][0] is True
    assert results["b"][0] is True
    lease_a = store.get_lease(org_a, SHARED_TENANT_SCOPE)
    lease_b = store.get_lease(org_b, SHARED_TENANT_SCOPE)
    assert lease_a is not None
    assert lease_b is not None
    assert lease_a.organization_id == org_a
    assert lease_b.organization_id == org_b
    assert lease_a.owner_id == "worker-a"
    assert lease_b.owner_id == "worker-b"
    assert lease_a.fencing_token == 1
    assert lease_b.fencing_token == 1
    assert store.get_lease(org_a, SHARED_TENANT_SCOPE) is not store.get_lease(
        org_b, SHARED_TENANT_SCOPE
    )


def test_tenant_cannot_invalidate_other_tenant_fence() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    org_a = uuid4()
    org_b = uuid4()
    acquired_a, lease_a, _reason_a = store.claim_lease(
        organization_id=org_a,
        scan_scope=SHARED_TENANT_SCOPE,
        owner_id="worker-a",
        ttl_seconds=30,
        now=clock.now(),
    )
    acquired_b, lease_b, _reason_b = store.claim_lease(
        organization_id=org_b,
        scan_scope=SHARED_TENANT_SCOPE,
        owner_id="worker-b",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert acquired_a is True
    assert acquired_b is True
    stolen, _lease_stolen, stolen_reason = store.claim_lease(
        organization_id=org_b,
        scan_scope=SHARED_TENANT_SCOPE,
        owner_id="worker-b2",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert stolen is False
    assert stolen_reason == "lease_held"
    assert (
        store.fence_is_active(
            organization_id=org_a,
            scan_scope=SHARED_TENANT_SCOPE,
            owner_id="worker-a",
            fencing_token=lease_a.fencing_token,
            now=clock.now(),
        )
        is True
    )
    assert (
        store.fence_is_active(
            organization_id=org_b,
            scan_scope=SHARED_TENANT_SCOPE,
            owner_id="worker-a",
            fencing_token=lease_a.fencing_token,
            now=clock.now(),
        )
        is False
    )
    refreshed_a = store.get_lease(org_a, SHARED_TENANT_SCOPE)
    assert refreshed_a is not None
    assert refreshed_a.fencing_token == lease_a.fencing_token
    assert refreshed_a.owner_id == "worker-a"
    refreshed_b = store.get_lease(org_b, SHARED_TENANT_SCOPE)
    assert refreshed_b is not None
    assert refreshed_b.fencing_token == lease_b.fencing_token
    assert refreshed_b.owner_id == "worker-b"


def test_tenant_heartbeat_health_lineage_and_latest_attempt_isolation() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    policy_a = _policy(clock)
    policy_b = _policy(clock)
    request_a = _request(policy_a, key="tenant-a", scan_scope=SHARED_TENANT_SCOPE)
    request_b = _request(policy_b, key="tenant-b", scan_scope=SHARED_TENANT_SCOPE)
    assert request_a.scan_scope == request_b.scan_scope == SHARED_TENANT_SCOPE
    assert request_a.organization_id != request_b.organization_id
    assert str(request_a.organization_id) not in request_a.scan_scope
    assert str(request_b.organization_id) not in request_b.scan_scope
    orch_a = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=ScriptedEvaluationBoundary(),
        side_effects=SideEffectProbe(),
    )
    orch_b = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=ScriptedEvaluationBoundary(default=EvaluationStatus.FAILED),
        side_effects=SideEffectProbe(),
    )
    result_a = orch_a.run_worker(request_a, worker_id="worker-a")
    result_b = orch_b.run_worker(request_b, worker_id="worker-b")
    assert result_a.status.value == "succeeded"
    assert result_b.status.value == "failed"
    assert result_a.published is True
    assert result_b.published is True
    assert result_a.lineage_id != result_b.lineage_id

    beat_a = store.get_heartbeat(request_a.organization_id, SHARED_TENANT_SCOPE)
    beat_b = store.get_heartbeat(request_b.organization_id, SHARED_TENANT_SCOPE)
    assert beat_a is not None
    assert beat_b is not None
    assert beat_a.owner_id == "worker-a"
    assert beat_b.owner_id == "worker-b"
    assert beat_a.organization_id == request_a.organization_id
    assert beat_b.organization_id == request_b.organization_id
    assert beat_a.detail != beat_b.detail

    health_a = orch_a.health(request_a.organization_id, SHARED_TENANT_SCOPE)
    health_b = orch_b.health(request_b.organization_id, SHARED_TENANT_SCOPE)
    assert health_a.state is WatcherHealthState.HEALTHY
    assert health_b.state is WatcherHealthState.DEGRADED
    assert health_a.organization_id == request_a.organization_id
    assert health_b.organization_id == request_b.organization_id
    assert health_a.last_lineage_id == result_a.lineage_id
    assert health_b.last_lineage_id == result_b.lineage_id
    stored_health_a = store.latest_health(request_a.organization_id, SHARED_TENANT_SCOPE)
    stored_health_b = store.latest_health(request_b.organization_id, SHARED_TENANT_SCOPE)
    assert stored_health_a is not None
    assert stored_health_b is not None
    assert stored_health_a.state is WatcherHealthState.HEALTHY
    assert stored_health_b.state is WatcherHealthState.DEGRADED

    latest_a = store.latest_attempt_for_scope(request_a.organization_id, SHARED_TENANT_SCOPE)
    latest_b = store.latest_attempt_for_scope(request_b.organization_id, SHARED_TENANT_SCOPE)
    assert latest_a is not None
    assert latest_b is not None
    assert latest_a.lineage_id == result_a.lineage_id
    assert latest_b.lineage_id == result_b.lineage_id
    assert latest_a.status is ScanAttemptStatus.SUCCEEDED
    assert latest_b.status is ScanAttemptStatus.FAILED

    assert result_a.lineage_id is not None
    lineage_a = store.get_lineage(result_a.lineage_id, request_a.organization_id)
    assert lineage_a is not None
    assert lineage_a.organization_id == request_a.organization_id
    with pytest.raises(WatcherTenantMismatchError):
        store.get_lineage(result_a.lineage_id, request_b.organization_id)


def test_organization_mismatch_is_rejected_on_lineage_and_cas() -> None:
    store = InMemoryWatcherStore()
    clock = FakeClock()
    policy = _policy(clock)
    orch = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=ScriptedEvaluationBoundary(),
        side_effects=SideEffectProbe(),
    )
    result = orch.run_worker(_request(policy, scan_scope=SHARED_TENANT_SCOPE), worker_id="worker-1")
    assert result.lineage_id is not None
    other_org = uuid4()
    with pytest.raises(WatcherTenantMismatchError) as mismatch:
        store.get_lineage(result.lineage_id, other_org)
    assert mismatch.value.code == "watcher_tenant_mismatch"
    with pytest.raises(WatcherTenantMismatchError):
        store.cas_lineage_terminal(
            result.lineage_id,
            result.attempt_id or uuid4(),
            ScanAttemptStatus.SUCCEEDED.value,
            other_org,
        )
    assert store.get_lease(other_org, SHARED_TENANT_SCOPE) is None
    assert store.get_heartbeat(other_org, SHARED_TENANT_SCOPE) is None
    assert store.latest_health(other_org, SHARED_TENANT_SCOPE) is None
    assert store.latest_attempt_for_scope(other_org, SHARED_TENANT_SCOPE) is None
    own_lease = store.get_lease(policy.identity.organization_id, SHARED_TENANT_SCOPE)
    assert own_lease is not None
    assert own_lease.organization_id == policy.identity.organization_id
