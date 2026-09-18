"""PostgreSQL CandidateRepository: uniqueness, idempotency, fencing, tenant isolation."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.deployment_safety import deployment_posture
from app.db.canonical_candidates import (
    CanonicalCandidateHistoryImmutabilityError,
    CanonicalCandidateTransitionRow,
)
from app.persistence.candidate_postgres import (
    PostgresCandidateRepository,
    WorkerCandidateWriteFence,
)
from app.persistence.composition import (
    build_postgres_candidate_repository,
    build_postgres_watcher_store,
)
from app.signal_fusion.adapters import evidence_window_from_assessment_command
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.enums import CandidateReasonCode, CandidateState
from app.signal_fusion.errors import (
    CandidateNotFoundError,
    ConflictingCandidateIdempotencyError,
    ConflictingCandidateTransitionError,
    IllegalCandidateTransitionError,
)
from app.signal_fusion.lifecycle import (
    CandidateLifecycleService,
    in_memory_candidate_lifecycle,
    uniqueness_from_confirmed,
)
from app.signal_fusion.memory import FrozenClock
from app.watcher.composition import build_orchestrator
from app.watcher.contracts import EvaluationCommand, EvaluationOutcome, ScanAttemptStatus
from app.watcher.errors import StaleFenceError
from app.watcher.fusion_evaluation import (
    BoundEvaluationClock,
    InMemoryWatcherScanEvidence,
    WatcherFusionEvaluationService,
)
from app.watcher.memory import FakeClock, SideEffectProbe
from tests.support.phase5_market import EVALUATED_AT, TRIGGER_OPEN
from tests.support.phase6_evaluator import make_world
from tests.support.phase6_fusion import (
    CORRELATION_B,
    ORG_ID,
    interval,
    make_assessment,
    make_creation_command,
    make_evidence_window,
)
from tests.support.postgres_persistence import persistence_session_factory, requires_postgres
from tests.test_phase6_candidate_lifecycle import ORG_B, _transition
from tests.test_watcher_phase6_fusion_wiring import (
    SHARED_SCOPE,
    _direct_assessment,
    _policy,
    _request,
    snapshot_from_world,
)

SCAN_SCOPE = SHARED_SCOPE


def _service(
    factory: sessionmaker[Session] | None = None,
    *,
    clock: FrozenClock | FakeClock | None = None,
) -> tuple[CandidateLifecycleService, PostgresCandidateRepository]:
    session_factory = factory if factory is not None else persistence_session_factory()
    resolved_clock: FrozenClock | FakeClock
    resolved_clock = clock if clock is not None else FrozenClock(EVALUATED_AT)
    repository = PostgresCandidateRepository(session_factory, clock=resolved_clock)
    lifecycle = CandidateLifecycleService(repository=repository, clock=FrozenClock(EVALUATED_AT))
    return lifecycle, repository


def _create(
    factory: sessionmaker[Session] | None = None,
) -> tuple[CandidateLifecycleService, PostgresCandidateRepository, Candidate]:
    lifecycle, repository = _service(factory)
    candidate = lifecycle.create_from_confirmed_setup(make_creation_command())
    return lifecycle, repository, candidate


@requires_postgres
def test_postgres_defaults_remain_paper_only() -> None:
    settings = Settings()
    assert settings.watcher_orchestration_enabled is False
    assert settings.market_watcher_enabled is False
    assert settings.telegram_interaction_enabled is False
    assert settings.real_trading_enabled is False
    posture = deployment_posture(settings)
    assert posture["real_trading_enabled"] is False
    assert posture["telegram_interaction_enabled"] is False


@requires_postgres
def test_concurrent_candidate_creation_converges() -> None:
    factory = persistence_session_factory()
    lifecycle, repository = _service(factory)
    command = make_creation_command()
    start = threading.Barrier(8)

    def worker(_index: int) -> object:
        start.wait()
        return lifecycle.create_from_confirmed_setup(command)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, range(8)))

    identities = {item.candidate_id for item in results}
    hashes = {item.content_hash for item in results}
    assert len(identities) == 1
    assert len(hashes) == 1
    stored = repository.get_by_id(ORG_ID, results[0].candidate_id)
    assert stored is not None
    assert stored.candidate_id == results[0].candidate_id


@requires_postgres
def test_uniqueness_survives_repository_restart() -> None:
    factory = persistence_session_factory()
    lifecycle, _repository = _service(factory)
    first = lifecycle.create_from_confirmed_setup(make_creation_command())
    restarted = PostgresCandidateRepository(factory)
    revived = CandidateLifecycleService(repository=restarted, clock=FrozenClock(EVALUATED_AT))
    keyed = revived.get_by_uniqueness(first.uniqueness_tuple())
    assert keyed is not None
    assert keyed.candidate_id == first.candidate_id
    assert keyed.content_hash == first.content_hash
    replay = revived.create_from_confirmed_setup(make_creation_command())
    assert replay.candidate_id == first.candidate_id
    assert replay.content_hash == first.content_hash


@requires_postgres
def test_transition_history_is_append_only() -> None:
    lifecycle, repository, candidate = _create()
    _transition(lifecycle, candidate.candidate_id, CandidateState.PLAN_CREATED)
    first_history = lifecycle.transition_history(ORG_ID, candidate.candidate_id)
    first_hash = first_history[0].content_hash
    _transition(
        lifecycle,
        candidate.candidate_id,
        CandidateState.EXPIRED,
        idempotency_key="expire-after-plan",
    )
    history = lifecycle.transition_history(ORG_ID, candidate.candidate_id)
    assert [item.transition_version for item in history] == [2, 3]
    assert history[0].content_hash == first_hash
    assert history[0] == first_history[0]
    replay = _transition(
        lifecycle,
        candidate.candidate_id,
        CandidateState.EXPIRED,
        idempotency_key="expire-after-plan-replay",
    )
    assert replay.state is CandidateState.EXPIRED
    assert replay.transition_version == 3
    replayed = lifecycle.transition_history(ORG_ID, candidate.candidate_id)
    assert len(replayed) == 2
    assert replayed[1].content_hash == history[1].content_hash
    session = repository._session_factory()
    try:
        row = session.scalars(select(CanonicalCandidateTransitionRow)).first()
        assert row is not None
        row.new_state = CandidateState.SKIPPED.value
        with pytest.raises(CanonicalCandidateHistoryImmutabilityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


@requires_postgres
def test_cross_tenant_access_fails_closed() -> None:
    lifecycle, _repository, candidate = _create()
    assert lifecycle.get_by_candidate_id(ORG_B, candidate.candidate_id) is None
    assert lifecycle.latest_projection(ORG_B, candidate.candidate_id) is None
    assert lifecycle.transition_history(ORG_B, candidate.candidate_id) == ()
    with pytest.raises(CandidateNotFoundError):
        _transition(
            lifecycle, candidate.candidate_id, CandidateState.REJECTED, organization_id=ORG_B
        )
    window_b = make_evidence_window(organization_id=ORG_B)
    other = lifecycle.create_from_confirmed_setup(
        make_creation_command(
            window=window_b,
            assessment=make_assessment(window_b, organization_id=ORG_B),
        )
    )
    assert other.candidate_id != candidate.candidate_id
    assert lifecycle.get_by_candidate_id(ORG_ID, other.candidate_id) is None
    assert lifecycle.get_by_candidate_id(ORG_B, candidate.candidate_id) is None


@requires_postgres
def test_conflicting_idempotency_fails_closed() -> None:
    lifecycle, _repository, first = _create()
    adjacent = make_evidence_window(
        interval=interval(
            start=TRIGGER_OPEN + timedelta(minutes=15),
            end=TRIGGER_OPEN + timedelta(minutes=30),
        )
    )
    with pytest.raises(ConflictingCandidateIdempotencyError, match="already bound"):
        lifecycle.create_from_confirmed_setup(
            make_creation_command(window=adjacent, idempotency_key="candidate-create-1")
        )
    stored = lifecycle.get_by_candidate_id(ORG_ID, first.candidate_id)
    assert stored is not None
    assert stored.content_hash == first.content_hash
    _transition(lifecycle, first.candidate_id, CandidateState.REJECTED)
    with pytest.raises(ConflictingCandidateIdempotencyError, match="semantic transition"):
        lifecycle.transition(
            organization_id=ORG_ID,
            candidate_id=first.candidate_id,
            new_state=CandidateState.REJECTED,
            reason_codes=(CandidateReasonCode.REJECTED,),
            idempotency_key="candidate-transition-1",
            correlation_id=uuid4(),
        )
    history = lifecycle.transition_history(ORG_ID, first.candidate_id)
    assert len(history) == 1


@requires_postgres
def test_terminal_candidates_cannot_resurrect() -> None:
    lifecycle, _repository, candidate = _create()
    rejected = _transition(lifecycle, candidate.candidate_id, CandidateState.REJECTED)
    assert rejected.state is CandidateState.REJECTED
    with pytest.raises(IllegalCandidateTransitionError, match="resurrected"):
        lifecycle.transition(
            organization_id=ORG_ID,
            candidate_id=candidate.candidate_id,
            new_state=CandidateState.ACTIVE,
            reason_codes=(CandidateReasonCode.CONFIRMED_SETUP,),
            idempotency_key="resurrect-active",
            correlation_id=CORRELATION_B,
        )
    with pytest.raises(IllegalCandidateTransitionError, match="resurrected"):
        _transition(
            lifecycle,
            candidate.candidate_id,
            CandidateState.PLAN_CREATED,
            idempotency_key="resurrect-plan",
        )
    latest = lifecycle.latest_projection(ORG_ID, candidate.candidate_id)
    assert latest is not None
    assert latest.state is CandidateState.REJECTED
    with pytest.raises(ConflictingCandidateTransitionError, match="Conflicting terminal"):
        _transition(
            lifecycle,
            candidate.candidate_id,
            CandidateState.SKIPPED,
            idempotency_key="conflict-skip",
        )


@requires_postgres
def test_stale_watcher_worker_cannot_persist() -> None:
    factory = persistence_session_factory()
    clock = FakeClock()
    store = build_postgres_watcher_store(factory)
    lifecycle, repository = _service(factory, clock=clock)
    claimed, lease, reason = store.claim_lease(
        organization_id=ORG_ID,
        scan_scope=SCAN_SCOPE,
        owner_id="worker-a",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert claimed is True
    assert reason == "claimed"
    clock.advance(31)
    taken, winner, _taken_reason = store.claim_lease(
        organization_id=ORG_ID,
        scan_scope=SCAN_SCOPE,
        owner_id="worker-b",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert taken is True
    assert winner.fencing_token == lease.fencing_token + 1
    with (
        repository.bind_worker_fence(
            WorkerCandidateWriteFence(
                organization_id=ORG_ID,
                scan_scope=SCAN_SCOPE,
                owner_id="worker-a",
                lease_epoch=lease.lease_epoch,
                fencing_token=lease.fencing_token,
            )
        ),
        pytest.raises(StaleFenceError, match="Candidate authority"),
    ):
        lifecycle.create_from_confirmed_setup(make_creation_command())
    command = make_creation_command()
    assert (
        lifecycle.get_by_uniqueness(
            uniqueness_from_confirmed(
                command.assessment, command.evidence_window, command.executable_setup
            )
        )
        is None
    )


@requires_postgres
def test_expired_lease_without_takeover_cannot_persist() -> None:
    factory = persistence_session_factory()
    clock = FakeClock()
    store = build_postgres_watcher_store(factory)
    lifecycle, repository = _service(factory, clock=clock)
    claimed, lease, _reason = store.claim_lease(
        organization_id=ORG_ID,
        scan_scope=SCAN_SCOPE,
        owner_id="worker-a",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert claimed is True
    clock.advance(31)
    with (
        repository.bind_worker_fence(
            WorkerCandidateWriteFence(
                organization_id=ORG_ID,
                scan_scope=SCAN_SCOPE,
                owner_id="worker-a",
                lease_epoch=lease.lease_epoch,
                fencing_token=lease.fencing_token,
            )
        ),
        pytest.raises(StaleFenceError, match="Candidate authority"),
    ):
        lifecycle.create_from_confirmed_setup(make_creation_command())
    command = make_creation_command()
    assert (
        lifecycle.get_by_uniqueness(
            uniqueness_from_confirmed(
                command.assessment, command.evidence_window, command.executable_setup
            )
        )
        is None
    )


@requires_postgres
def test_lease_takeover_race_linearizes_candidate_persist() -> None:
    factory = persistence_session_factory()
    clock = FakeClock()
    store = build_postgres_watcher_store(factory)
    lifecycle, repository = _service(factory, clock=clock)
    claimed, lease, _reason = store.claim_lease(
        organization_id=ORG_ID,
        scan_scope=SCAN_SCOPE,
        owner_id="worker-a",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert claimed is True
    clock.advance(31)
    start = threading.Barrier(2)
    persist_error: list[str] = []
    persist_ok: list[UUID] = []

    def persist_stale() -> None:
        start.wait()
        try:
            with repository.bind_worker_fence(
                WorkerCandidateWriteFence(
                    organization_id=ORG_ID,
                    scan_scope=SCAN_SCOPE,
                    owner_id="worker-a",
                    lease_epoch=lease.lease_epoch,
                    fencing_token=lease.fencing_token,
                )
            ):
                created = lifecycle.create_from_confirmed_setup(make_creation_command())
        except StaleFenceError:
            persist_error.append("stale")
            return
        persist_ok.append(created.candidate_id)

    def takeover() -> None:
        start.wait()
        store.claim_lease(
            organization_id=ORG_ID,
            scan_scope=SCAN_SCOPE,
            owner_id="worker-b",
            ttl_seconds=30,
            now=clock.now(),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda fn: fn(), (persist_stale, takeover)))

    command = make_creation_command()
    stored = lifecycle.get_by_uniqueness(
        uniqueness_from_confirmed(
            command.assessment, command.evidence_window, command.executable_setup
        )
    )
    current = store.get_lease(ORG_ID, SCAN_SCOPE)
    assert current is not None
    if persist_ok:
        assert stored is not None
        assert stored.candidate_id == persist_ok[0]
        assert current.fencing_token >= lease.fencing_token
    else:
        assert persist_error == ["stale"]
        assert stored is None
        assert current.owner_id == "worker-b"
        assert current.fencing_token == lease.fencing_token + 1


@requires_postgres
def test_current_fence_holder_can_persist() -> None:
    factory = persistence_session_factory()
    clock = FakeClock()
    store = build_postgres_watcher_store(factory)
    lifecycle, repository = _service(factory, clock=clock)
    claimed, lease, _reason = store.claim_lease(
        organization_id=ORG_ID,
        scan_scope=SCAN_SCOPE,
        owner_id="worker-a",
        ttl_seconds=30,
        now=clock.now(),
    )
    assert claimed is True
    with repository.bind_worker_fence(
        WorkerCandidateWriteFence(
            organization_id=ORG_ID,
            scan_scope=SCAN_SCOPE,
            owner_id="worker-a",
            lease_epoch=lease.lease_epoch,
            fencing_token=lease.fencing_token,
        )
    ):
        created = lifecycle.create_from_confirmed_setup(make_creation_command())
    assert created.state is CandidateState.ACTIVE
    assert lifecycle.get_by_candidate_id(ORG_ID, created.candidate_id) == created


@requires_postgres
def test_incomplete_worker_authority_cannot_persist() -> None:
    factory = persistence_session_factory()
    lifecycle, repository = _service(factory)
    with (
        repository.bind_worker_fence(
            WorkerCandidateWriteFence(
                organization_id=ORG_ID,
                scan_scope=SCAN_SCOPE,
                owner_id="worker-a",
                lease_epoch=None,
                fencing_token=1,
            )
        ),
        pytest.raises(StaleFenceError, match="Candidate authority"),
    ):
        lifecycle.create_from_confirmed_setup(make_creation_command())


@requires_postgres
def test_stale_worker_steal_during_persist_cannot_mint_candidate() -> None:
    world = make_world()
    factory = persistence_session_factory()
    clock = FakeClock()
    store = build_postgres_watcher_store(factory)
    eval_clock = BoundEvaluationClock()
    repository = build_postgres_candidate_repository(factory, clock=clock)
    lifecycle = CandidateLifecycleService(repository=repository, clock=eval_clock)
    evidence = InMemoryWatcherScanEvidence()
    evidence.bind(snapshot_from_world(world), scan_scope=SHARED_SCOPE)
    inner = WatcherFusionEvaluationService(
        evidence=evidence,
        lifecycle=lifecycle,
        clock=eval_clock,
        persistence_fence=repository,
    )
    policy = _policy(clock)
    store.put_policy_version(policy)
    request = _request(policy, key="fenced-persist")

    class _StealOnPersist:
        def evaluate(self, command: EvaluationCommand) -> EvaluationOutcome:
            return inner.evaluate(command)

        def persist_confirmed_setup(
            self, command: EvaluationCommand, outcome: EvaluationOutcome
        ) -> EvaluationOutcome:
            clock.advance(31)
            store.claim_lease(
                scan_scope=request.scan_scope,
                organization_id=request.organization_id,
                owner_id="worker-b",
                ttl_seconds=30,
                now=clock.now(),
            )
            return inner.persist_confirmed_setup(command, outcome)

    stolen = build_orchestrator(
        enabled=True,
        lease_ttl_seconds=30,
        store=store,
        clock=clock,
        evaluator=_StealOnPersist(),  # type: ignore[arg-type]
        side_effects=SideEffectProbe(),
    ).run_worker(request, worker_id="worker-a")
    assert stolen.published is False
    assert stolen.status.value == "rejected_stale_fence"
    assert stolen.attempt_id is not None
    stale_attempt = store.get_attempt(stolen.attempt_id)
    assert stale_attempt is not None
    assert stale_attempt.status is ScanAttemptStatus.REJECTED_STALE_FENCE
    uniqueness = uniqueness_from_confirmed(
        _direct_assessment(world),
        evidence_window_from_assessment_command(world.command),
        world.command.executable_setup,
    )
    assert inner.lifecycle.get_by_uniqueness(uniqueness) is None
    assert inner.published_candidate_ids == ()

    winner = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=inner,
        side_effects=SideEffectProbe(),
    ).run_worker(request, worker_id="worker-b")
    assert winner.published is True
    assert winner.outcome is not None
    assert len(set(inner.published_candidate_ids)) == 1
    assert inner.lifecycle.get_by_uniqueness(uniqueness) is not None
    refreshed = store.get_lineage(winner.lineage_id, request.organization_id)
    assert refreshed is not None
    assert refreshed.terminal_status is ScanAttemptStatus.SUCCEEDED


@requires_postgres
def test_builder_is_not_wired_into_in_memory_default() -> None:
    service = in_memory_candidate_lifecycle(now=EVALUATED_AT)
    candidate = service.create_from_confirmed_setup(make_creation_command())
    assert candidate.state is CandidateState.ACTIVE
    factory = persistence_session_factory()
    postgres = PostgresCandidateRepository(factory)
    assert postgres.get_by_id(ORG_ID, candidate.candidate_id) is None
