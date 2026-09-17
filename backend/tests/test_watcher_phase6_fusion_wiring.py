"""Watcher orchestration wiring to Phase 6 evidence, evaluator, and candidates.

Proves first-slice Bearish Liquidity Sweep evaluation through the Watcher
boundary without a second evidence hash, alternative candidate identity,
action eligibility, TradePlan, Telegram, or execution.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.market_contracts.cursor import TradeStreamSnapshot
from app.signal_fusion.adapters import AssessmentCommand, evidence_window_from_assessment_command
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.enums import CandidateState, EvidenceAdapterKind, SetupAssessmentState
from app.signal_fusion.evaluator import evaluate_setup
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle
from app.signal_fusion.lifecycle import (
    CandidateLifecycleService,
    deterministic_candidate_id,
    uniqueness_from_confirmed,
)
from app.signal_fusion.memory import InMemoryCandidateRepository
from app.signal_fusion.policy import build_fusion_policy
from app.watcher.composition import build_orchestrator
from app.watcher.contracts import (
    EvaluationCommand,
    EvaluationMode,
    EvaluationOutcome,
    EvaluationStatus,
    ScanAttemptStatus,
    ScanRequest,
    ScanTrigger,
    WatcherPolicyIdentity,
    WatcherPolicyVersion,
)
from app.watcher.errors import SimulatedWorkerCrashError
from app.watcher.fusion_evaluation import (
    BoundEvaluationClock,
    InMemoryWatcherScanEvidence,
    WatcherCanonicalScanEvidence,
    WatcherFusionEvaluationService,
    build_fusion_evaluation_service,
)
from app.watcher.hashing import evaluation_input_hash, policy_content_hash, scan_request_hash
from app.watcher.memory import FakeClock, InMemoryWatcherStore, SideEffectProbe
from app.watcher.orchestrator import WatcherOrchestrator
from app.watcher.ports import NamedCrashBarrier
from app.watcher.settings import runtime_config_from_settings
from tests.support.phase5_market import spot_identity
from tests.support.phase6_evaluator import EvaluatorWorld, make_world, subsequent_bars
from tests.support.phase6_fusion import ORG_ID, blofin_evidence_identity, eth_evidence_identity

WATCHER_SRC = Path(__file__).resolve().parents[1] / "src" / "app" / "watcher"
FUSION_EVAL_SRC = WATCHER_SRC / "fusion_evaluation.py"
SHARED_SCOPE = "first-slice-btcusdt-15m"


def snapshot_from_world(
    world: EvaluatorWorld,
    *,
    assessment_command: AssessmentCommand | None = None,
    bundle: FirstSliceEvidenceBundle | None = None,
    evaluated_at: datetime | None = None,
) -> WatcherCanonicalScanEvidence:
    command = world.command if assessment_command is None else assessment_command
    payload = world.evidence if bundle is None else bundle
    moment = world.evaluated_at if evaluated_at is None else evaluated_at
    return WatcherCanonicalScanEvidence(
        organization_id=command.organization_id,
        policy=world.policy,
        assessment_command=command,
        evidence=payload,
        evaluated_at=moment,
    )


def rebind_world_organization(world: EvaluatorWorld, organization_id: UUID) -> EvaluatorWorld:
    src = world.policy
    policy = build_fusion_policy(
        policy_version=src.policy_version,
        organization_id=organization_id,
        strategy_version_id=src.strategy_version_id,
        executable_setup=src.executable_setup,
        required_roles=src.required_roles,
        thresholds=src.thresholds,
        freshness_policy_version=src.freshness_policy_version,
        finality_policy_version=src.finality_policy_version,
        optional_roles=src.optional_roles,
        disqualifying_roles=src.disqualifying_roles,
        correction_selection_policy=src.correction_selection_policy,
        role_timeframes=src.role_timeframes,
        required_assertion_roles=src.required_assertion_roles,
        identity_assertion_roles=src.identity_assertion_roles,
    )
    command = world.command.model_copy(update={"organization_id": organization_id})
    return EvaluatorWorld(
        policy=policy,
        command=command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
        bars_15m=world.bars_15m,
        bars_4h=world.bars_4h,
        snapshot=world.snapshot,
        trigger=world.trigger,
    )


def _policy(clock: FakeClock, *, organization_id: UUID = ORG_ID) -> WatcherPolicyVersion:
    identity = WatcherPolicyIdentity(
        policy_id=uuid4(),
        organization_id=organization_id,
        user_id=uuid4(),
        watchlist_item_id=uuid4(),
    )
    draft = WatcherPolicyVersion(
        identity=identity,
        version=1,
        timeframe="15m",
        fusion_policy_version="first-slice-fusion/v1",
        enabled=True,
        created_by=identity.user_id,
        created_at=clock.now(),
        content_hash="0" * 64,
    )
    return draft.model_copy(update={"content_hash": policy_content_hash(draft)})


def _request(
    policy: WatcherPolicyVersion,
    *,
    key: str,
    principal_id: UUID | None = None,
    scan_scope: str = SHARED_SCOPE,
    organization_id: UUID | None = None,
) -> ScanRequest:
    return ScanRequest(
        organization_id=organization_id or policy.identity.organization_id,
        principal_id=principal_id,
        scan_scope=scan_scope,
        policy_id=policy.identity.policy_id,
        policy_version=policy.version,
        policy_content_hash=policy.content_hash,
        watchlist_item_ids=(policy.identity.watchlist_item_id,),
        timeframe="15m",
        idempotency_key=key,
    )


def _direct_assessment(world: EvaluatorWorld) -> SetupAssessment:
    return evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
        account_context={"balance": 1_000_000, "leverage": 25, "kill_switch": True},
    )


def _wired(
    world: EvaluatorWorld,
    *,
    organization_id: UUID | None = None,
    scan_scope: str = SHARED_SCOPE,
) -> tuple[
    WatcherOrchestrator,
    FakeClock,
    InMemoryWatcherStore,
    WatcherFusionEvaluationService,
    SideEffectProbe,
    InMemoryWatcherScanEvidence,
    WatcherPolicyVersion,
]:
    org = organization_id or world.command.organization_id
    probe = SideEffectProbe()
    clock = FakeClock()
    store = InMemoryWatcherStore()
    evidence = InMemoryWatcherScanEvidence()
    evidence.bind(snapshot_from_world(world), scan_scope=scan_scope)
    service = build_fusion_evaluation_service(evidence=evidence)
    orch = build_orchestrator(
        enabled=True,
        clock=clock,
        store=store,
        evaluator=service,
        side_effects=probe,
    )
    policy = _policy(clock, organization_id=org)
    store.put_policy_version(policy)
    return orch, clock, store, service, probe, evidence, policy


def _assert_no_side_effects(probe: SideEffectProbe) -> None:
    assert probe.execution == []
    assert probe.journal == []
    assert probe.telegram == []
    assert probe.unused is True


def test_watcher_and_market_watcher_remain_disabled_by_default() -> None:
    settings = Settings()
    assert settings.watcher_orchestration_enabled is False
    assert settings.market_watcher_enabled is False
    assert settings.enable_real_trading is False
    assert settings.execution_mode.value == "paper"
    assert runtime_config_from_settings(settings).enabled is False


def test_manual_and_worker_evaluation_parity() -> None:
    world = make_world()
    manual_truth = _direct_assessment(world)
    orch, _clock, _store, service, probe, _evidence, policy = _wired(world)
    user = policy.identity.user_id
    manual_request = _request(policy, key="manual-preview", principal_id=user)
    worker_request = _request(policy, key="worker-persist")
    preview = orch.evaluate_manual(manual_request, mode=EvaluationMode.PREVIEW)
    worker = orch.run_worker(worker_request, worker_id="worker-1")
    assert preview.outcome.status is EvaluationStatus.SUCCEEDED
    assert worker.outcome is not None
    assert worker.outcome.status is EvaluationStatus.SUCCEEDED
    assert preview.outcome.reason_code == SetupAssessmentState.CONFIRMED_SETUP.value
    assert worker.outcome.reason_code == SetupAssessmentState.CONFIRMED_SETUP.value
    assert preview.outcome.evidence_validity_token == manual_truth.evidence_window_hash
    assert worker.outcome.evidence_validity_token == manual_truth.evidence_window_hash
    assert evaluation_input_hash(manual_request) == evaluation_input_hash(worker_request)
    window = evidence_window_from_assessment_command(
        world.command.model_copy(update={"adapter_kind": EvidenceAdapterKind.DETECTOR})
    )
    assert window.content_hash == manual_truth.evidence_window_hash
    assert preview.outcome.candidate_ids == ()
    assert worker.outcome.candidate_ids == (service.published_candidate_ids[0],)
    _assert_no_side_effects(probe)


def test_confirmed_setup_creates_exactly_one_candidate() -> None:
    world = make_world()
    assessment = _direct_assessment(world)
    assert assessment.state is SetupAssessmentState.CONFIRMED_SETUP
    orch, _clock, _store, service, probe, _evidence, policy = _wired(world)
    first = orch.run_worker(_request(policy, key="scan-a"), worker_id="worker-1")
    second = orch.run_worker(_request(policy, key="scan-b"), worker_id="worker-1")
    assert first.outcome is not None
    assert second.outcome is not None
    assert first.outcome.candidate_ids == second.outcome.candidate_ids
    assert len(first.outcome.candidate_ids) == 1
    candidate_id = first.outcome.candidate_ids[0]
    window = evidence_window_from_assessment_command(world.command)
    expected = deterministic_candidate_id(
        uniqueness_from_confirmed(assessment, window, world.command.executable_setup)
    )
    assert candidate_id == expected
    stored = service.lifecycle.get_by_candidate_id(ORG_ID, candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE
    assert stored.evidence_window_hash == window.content_hash
    assert stored.candidate_id == service.published_candidate_ids[0]
    assert set(service.published_candidate_ids) == {candidate_id}
    _assert_no_side_effects(probe)


def test_duplicate_semantic_scan_converges() -> None:
    watcher_world = make_world(adapter_kind=EvidenceAdapterKind.WATCHER)
    detector_world = make_world(adapter_kind=EvidenceAdapterKind.DETECTOR)
    orch, clock, store, service, probe, evidence, policy = _wired(watcher_world)
    evidence.bind(snapshot_from_world(detector_world), scan_scope="detector-scope")
    detector_policy = _policy(clock, organization_id=ORG_ID)
    store.put_policy_version(detector_policy)
    left = orch.run_worker(_request(policy, key="watcher-scan"), worker_id="worker-1")
    right = orch.run_worker(
        _request(detector_policy, key="detector-scan", scan_scope="detector-scope"),
        worker_id="worker-2",
    )
    assert left.outcome is not None
    assert right.outcome is not None
    assert left.outcome.candidate_ids == right.outcome.candidate_ids
    assert left.outcome.evidence_validity_token == right.outcome.evidence_validity_token
    assert len(set(service.published_candidate_ids)) == 1
    _assert_no_side_effects(probe)


@pytest.mark.parametrize(
    ("label", "factory"),
    [
        (
            SetupAssessmentState.NO_SETUP,
            lambda: make_world(bar_15m_count=10, pattern_bars=True, include_snapshot=False),
        ),
        (SetupAssessmentState.WATCH, lambda: make_world(pattern_bars=False)),
        (
            SetupAssessmentState.PARTIAL_MATCH,
            lambda: make_world(trigger_volume=Decimal("20")),
        ),
    ],
)
def test_non_confirmed_states_do_not_create_candidate(
    label: SetupAssessmentState, factory: Callable[[], EvaluatorWorld]
) -> None:
    world = factory()
    assessment = _direct_assessment(world)
    assert assessment.state is label
    orch, _clock, _store, service, probe, _evidence, policy = _wired(world)
    result = orch.run_worker(_request(policy, key=label.value), worker_id="worker-1")
    assert result.outcome is not None
    assert result.outcome.status is EvaluationStatus.SUCCEEDED
    assert result.outcome.reason_code == label.value
    assert result.outcome.candidate_ids == ()
    assert service.published_candidate_ids == ()
    _assert_no_side_effects(probe)


def test_invalidated_does_not_create_active_candidate() -> None:
    base = make_world()
    later = subsequent_bars(base.trigger, count=1, high=Decimal("100500"))
    world = make_world(subsequent=tuple(later))
    assessment = _direct_assessment(world)
    assert assessment.state is SetupAssessmentState.INVALIDATED
    orch, _clock, _store, service, probe, _evidence, policy = _wired(world)
    result = orch.run_worker(_request(policy, key="invalidated"), worker_id="worker-1")
    assert result.outcome is not None
    assert result.outcome.reason_code == SetupAssessmentState.INVALIDATED.value
    assert result.outcome.candidate_ids == ()
    assert service.published_candidate_ids == ()
    _assert_no_side_effects(probe)


def test_expired_does_not_create_active_candidate() -> None:
    base = make_world()
    later = subsequent_bars(base.trigger, count=2, high=Decimal("100010"))
    world = make_world(subsequent=tuple(later))
    assessment = _direct_assessment(world)
    assert assessment.state is SetupAssessmentState.EXPIRED
    orch, _clock, _store, service, probe, _evidence, policy = _wired(world)
    result = orch.run_worker(_request(policy, key="expired"), worker_id="worker-1")
    assert result.outcome is not None
    assert result.outcome.reason_code == SetupAssessmentState.EXPIRED.value
    assert result.outcome.candidate_ids == ()
    assert service.published_candidate_ids == ()
    _assert_no_side_effects(probe)


def test_wrong_market_fails_closed() -> None:
    world = make_world()
    mutated = world.command.model_copy(update={"evidence_identity": spot_identity()})
    bound = EvaluatorWorld(
        policy=world.policy,
        command=mutated,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
        bars_15m=world.bars_15m,
        bars_4h=world.bars_4h,
        snapshot=world.snapshot,
        trigger=world.trigger,
    )
    assessment = _direct_assessment(bound)
    assert assessment.state is SetupAssessmentState.NO_SETUP
    orch, _clock, _store, service, probe, _evidence, policy = _wired(bound)
    result = orch.run_worker(_request(policy, key="wrong-market"), worker_id="worker-1")
    assert result.outcome is not None
    assert result.outcome.reason_code == SetupAssessmentState.NO_SETUP.value
    assert result.outcome.candidate_ids == ()
    assert service.published_candidate_ids == ()
    _assert_no_side_effects(probe)


def test_wrong_venue_fails_closed() -> None:
    world = make_world()
    mutated = world.command.model_copy(update={"evidence_identity": blofin_evidence_identity()})
    bound = EvaluatorWorld(
        policy=world.policy,
        command=mutated,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
        bars_15m=world.bars_15m,
        bars_4h=world.bars_4h,
        snapshot=world.snapshot,
        trigger=world.trigger,
    )
    assessment = _direct_assessment(bound)
    assert assessment.state is SetupAssessmentState.NO_SETUP
    orch, _clock, _store, service, probe, _evidence, policy = _wired(bound)
    result = orch.run_worker(_request(policy, key="wrong-venue"), worker_id="worker-1")
    assert result.outcome is not None
    assert result.outcome.reason_code == SetupAssessmentState.NO_SETUP.value
    assert result.outcome.candidate_ids == ()
    assert service.published_candidate_ids == ()
    _assert_no_side_effects(probe)


def test_wrong_instrument_fails_closed() -> None:
    world = make_world()
    mutated = world.command.model_copy(update={"evidence_identity": eth_evidence_identity()})
    bound = EvaluatorWorld(
        policy=world.policy,
        command=mutated,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
        bars_15m=world.bars_15m,
        bars_4h=world.bars_4h,
        snapshot=world.snapshot,
        trigger=world.trigger,
    )
    assessment = _direct_assessment(bound)
    assert assessment.state is SetupAssessmentState.NO_SETUP
    orch, _clock, _store, service, probe, _evidence, policy = _wired(bound)
    result = orch.run_worker(_request(policy, key="wrong-instrument"), worker_id="worker-1")
    assert result.outcome is not None
    assert result.outcome.reason_code == SetupAssessmentState.NO_SETUP.value
    assert result.outcome.candidate_ids == ()
    assert service.published_candidate_ids == ()
    _assert_no_side_effects(probe)


def test_stale_evidence_fails_closed() -> None:
    world = make_world(stale_command=True)
    evaluated_at = world.evaluated_at + timedelta(seconds=30)
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.NO_SETUP
    snap = snapshot_from_world(world, evaluated_at=evaluated_at)
    probe = SideEffectProbe()
    clock = FakeClock()
    store = InMemoryWatcherStore()
    evidence = InMemoryWatcherScanEvidence()
    evidence.bind(snap, scan_scope=SHARED_SCOPE)
    service = build_fusion_evaluation_service(evidence=evidence)
    orch = build_orchestrator(
        enabled=True, clock=clock, store=store, evaluator=service, side_effects=probe
    )
    policy = _policy(clock)
    store.put_policy_version(policy)
    result = orch.run_worker(_request(policy, key="stale"), worker_id="worker-1")
    assert result.outcome is not None
    assert result.outcome.reason_code == SetupAssessmentState.NO_SETUP.value
    assert result.outcome.candidate_ids == ()
    assert service.published_candidate_ids == ()
    _assert_no_side_effects(probe)


def test_gap_evidence_fails_closed() -> None:
    world = make_world()
    assert world.snapshot is not None
    missing = world.snapshot.trades[:10] + world.snapshot.trades[11:]
    forged = TradeStreamSnapshot.model_construct(
        cursor=world.snapshot.cursor,
        trades=missing,
        coverage=world.snapshot.coverage,
        usable=True,
    )
    bound = EvaluatorWorld(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence.model_copy(update={"snapshot": forged}),
        evaluated_at=world.evaluated_at,
        bars_15m=world.bars_15m,
        bars_4h=world.bars_4h,
        snapshot=forged,
        trigger=world.trigger,
    )
    assessment = _direct_assessment(bound)
    assert assessment.state is SetupAssessmentState.NO_SETUP
    orch, _clock, _store, service, probe, _evidence, policy = _wired(bound)
    result = orch.run_worker(_request(policy, key="gap"), worker_id="worker-1")
    assert result.outcome is not None
    assert result.outcome.reason_code == SetupAssessmentState.NO_SETUP.value
    assert result.outcome.candidate_ids == ()
    assert service.published_candidate_ids == ()
    _assert_no_side_effects(probe)


def test_stale_worker_fencing_cannot_publish() -> None:
    world = make_world()
    clock = FakeClock()
    store = InMemoryWatcherStore()
    evidence = InMemoryWatcherScanEvidence()
    evidence.bind(snapshot_from_world(world), scan_scope=SHARED_SCOPE)
    inner = build_fusion_evaluation_service(evidence=evidence)
    policy = _policy(clock)
    store.put_policy_version(policy)
    request = _request(policy, key="fenced")

    class _StealOnEvaluate:
        def evaluate(self, command: EvaluationCommand) -> EvaluationOutcome:
            clock.advance(31)
            store.claim_lease(
                scan_scope=request.scan_scope,
                organization_id=request.organization_id,
                owner_id="worker-b",
                ttl_seconds=30,
                now=clock.now(),
            )
            return inner.evaluate(command)

    stolen = build_orchestrator(
        enabled=True,
        lease_ttl_seconds=30,
        store=store,
        clock=clock,
        evaluator=_StealOnEvaluate(),  # type: ignore[arg-type]
        side_effects=SideEffectProbe(),
    ).run_worker(request, worker_id="worker-a")
    assert stolen.published is False
    assert stolen.status.value == "rejected_stale_fence"
    assert stolen.attempt_id is not None
    attempt = store.get_attempt(stolen.attempt_id)
    assert attempt is not None
    assert attempt.status is ScanAttemptStatus.REJECTED_STALE_FENCE
    assert stolen.lineage_id is not None
    lineage = store.get_lineage(stolen.lineage_id, request.organization_id)
    assert lineage is not None
    assert lineage.terminal_status is not ScanAttemptStatus.SUCCEEDED

    winner = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=inner,
        side_effects=SideEffectProbe(),
    ).run_worker(request, worker_id="worker-b")
    assert winner.published is True
    assert winner.outcome is not None
    assert winner.outcome.status is EvaluationStatus.SUCCEEDED
    assert winner.outcome.reason_code == SetupAssessmentState.CONFIRMED_SETUP.value
    assert len(set(inner.published_candidate_ids)) == 1
    refreshed = store.get_lineage(winner.lineage_id, request.organization_id)
    assert refreshed is not None
    assert refreshed.terminal_status is ScanAttemptStatus.SUCCEEDED


def test_organization_isolation() -> None:
    org_a = uuid4()
    org_b = uuid4()
    world_a = rebind_world_organization(make_world(), org_a)
    world_b = rebind_world_organization(make_world(), org_b)
    clock = FakeClock()
    store = InMemoryWatcherStore()
    repo = InMemoryCandidateRepository()
    eval_clock = BoundEvaluationClock()
    lifecycle = CandidateLifecycleService(repository=repo, clock=eval_clock)
    evidence = InMemoryWatcherScanEvidence()
    evidence.bind(snapshot_from_world(world_a), scan_scope=SHARED_SCOPE)
    evidence.bind(snapshot_from_world(world_b), scan_scope=SHARED_SCOPE)
    service = WatcherFusionEvaluationService(
        evidence=evidence, lifecycle=lifecycle, clock=eval_clock
    )
    orch = build_orchestrator(
        enabled=True,
        clock=clock,
        store=store,
        evaluator=service,
        side_effects=SideEffectProbe(),
    )
    policy_a = _policy(clock, organization_id=org_a)
    policy_b = _policy(clock, organization_id=org_b)
    store.put_policy_version(policy_a)
    store.put_policy_version(policy_b)
    left = orch.run_worker(_request(policy_a, key="org-a"), worker_id="worker-a")
    right = orch.run_worker(_request(policy_b, key="org-b"), worker_id="worker-b")
    assert left.outcome is not None
    assert right.outcome is not None
    assert left.outcome.candidate_ids != right.outcome.candidate_ids
    left_id = left.outcome.candidate_ids[0]
    right_id = right.outcome.candidate_ids[0]
    assert service.lifecycle.get_by_candidate_id(org_a, left_id) is not None
    assert service.lifecycle.get_by_candidate_id(org_b, left_id) is None
    assert service.lifecycle.get_by_candidate_id(org_b, right_id) is not None
    assert service.lifecycle.get_by_candidate_id(org_a, right_id) is None
    assert left.outcome.evidence_validity_token != right.outcome.evidence_validity_token


def test_worker_crash_and_retry_preserves_semantic_convergence() -> None:
    world = make_world()
    clock = FakeClock()
    store = InMemoryWatcherStore()
    evidence = InMemoryWatcherScanEvidence()
    evidence.bind(snapshot_from_world(world), scan_scope=SHARED_SCOPE)
    service = build_fusion_evaluation_service(evidence=evidence)
    policy = _policy(clock)
    store.put_policy_version(policy)
    request = _request(policy, key="crash-retry")
    crashing = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=service,
        crash=NamedCrashBarrier("after_evaluation"),
        side_effects=SideEffectProbe(),
    )
    with pytest.raises(SimulatedWorkerCrashError):
        crashing.run_worker(request, worker_id="worker-1")
    recovered = build_orchestrator(
        enabled=True,
        store=store,
        clock=clock,
        evaluator=service,
        side_effects=SideEffectProbe(),
    )
    result = recovered.run_worker(request, worker_id="worker-1")
    assert result.status.value == "succeeded"
    assert result.published is True
    assert result.outcome is not None
    assert result.outcome.reason_code == SetupAssessmentState.CONFIRMED_SETUP.value
    assert len(set(service.published_candidate_ids)) == 1
    assert result.outcome.candidate_ids == (service.published_candidate_ids[0],)
    scheduled = store.get_schedule(policy.identity.organization_id, None, "crash-retry")
    assert scheduled is not None
    attempts = store.list_attempts(scheduled.lineage_id)
    assert attempts[-1].status is ScanAttemptStatus.SUCCEEDED


def test_missing_evidence_is_failed_scan_not_setup_truth() -> None:
    world = make_world()
    _orch, _clock, store, service, probe, _evidence, policy = _wired(world)
    empty = InMemoryWatcherScanEvidence()
    bare = WatcherFusionEvaluationService(
        evidence=empty,
        lifecycle=service.lifecycle,
        clock=BoundEvaluationClock(),
    )
    failed = build_orchestrator(
        enabled=True,
        store=store,
        clock=FakeClock(),
        evaluator=bare,
        side_effects=probe,
    ).run_worker(_request(policy, key="missing"), worker_id="worker-1")
    assert failed.outcome is not None
    assert failed.outcome.status is EvaluationStatus.FAILED
    assert failed.outcome.reason_code == "missing_canonical_evidence"
    assert failed.outcome.candidate_ids == ()
    assert failed.outcome.reason_code != SetupAssessmentState.CONFIRMED_SETUP.value
    _assert_no_side_effects(probe)


def test_preview_does_not_persist_candidate() -> None:
    world = make_world()
    orch, _clock, _store, service, probe, _evidence, policy = _wired(world)
    preview = orch.evaluate_manual(
        _request(policy, key="preview", principal_id=policy.identity.user_id),
        mode=EvaluationMode.PREVIEW,
    )
    persist = orch.evaluate_manual(
        _request(policy, key="persist", principal_id=policy.identity.user_id),
        mode=EvaluationMode.PERSIST_EVIDENCE,
    )
    assert preview.outcome.candidate_ids == ()
    assert persist.outcome.candidate_ids == (service.published_candidate_ids[0],)
    assert persist.outcome.evidence_validity_token == preview.outcome.evidence_validity_token
    _assert_no_side_effects(probe)


def test_manual_persist_and_worker_converge_on_one_candidate() -> None:
    world = make_world()
    orch, _clock, _store, service, probe, _evidence, policy = _wired(world)
    manual = orch.evaluate_manual(
        _request(policy, key="manual-persist", principal_id=policy.identity.user_id),
        mode=EvaluationMode.PERSIST_EVIDENCE,
    )
    worker = orch.run_worker(_request(policy, key="worker-persist"), worker_id="worker-1")
    assert worker.outcome is not None
    assert manual.outcome.candidate_ids == worker.outcome.candidate_ids
    assert len(set(service.published_candidate_ids)) == 1
    assert scan_request_hash(_request(policy, key="x", principal_id=policy.identity.user_id)) != (
        scan_request_hash(_request(policy, key="y"))
    )
    _assert_no_side_effects(probe)


def test_fusion_wiring_does_not_hash_or_mint_identity() -> None:
    text = FUSION_EVAL_SRC.read_text(encoding="utf-8")
    assert "hash_canonical_evidence_window" not in text
    assert "canonical_sha256" not in text
    assert "uuid4" not in text
    assert "uuid5" not in text
    assert "account_context=None" in text
    assert "ActionEligibility" not in text
    assert "TradePlan" not in text
    assert "evaluate_setup" in text
    assert "evidence_window_from_assessment_command" in text
    assert "create_from_confirmed_setup" in text


def test_direct_manual_and_worker_commands_share_window() -> None:
    world = make_world()
    evidence = InMemoryWatcherScanEvidence()
    evidence.bind(snapshot_from_world(world), scan_scope=SHARED_SCOPE)
    service = build_fusion_evaluation_service(evidence=evidence)
    policy = _policy(FakeClock())
    manual_request = _request(policy, key="m", principal_id=policy.identity.user_id)
    worker_request = _request(policy, key="w")
    manual = service.evaluate(
        EvaluationCommand(
            command_id=uuid4(),
            request=manual_request,
            request_hash=scan_request_hash(manual_request),
            evaluation_input_hash=evaluation_input_hash(manual_request),
            mode=EvaluationMode.PREVIEW,
            trigger=ScanTrigger.MANUAL,
            correlation_id=uuid4(),
        )
    )
    worker = service.evaluate(
        EvaluationCommand(
            command_id=uuid4(),
            request=worker_request,
            request_hash=scan_request_hash(worker_request),
            evaluation_input_hash=evaluation_input_hash(worker_request),
            mode=EvaluationMode.PERSIST_EVIDENCE,
            trigger=ScanTrigger.WORKER,
            correlation_id=uuid4(),
        )
    )
    assert manual.evidence_validity_token == worker.evidence_validity_token
    assert manual.reason_code == worker.reason_code == SetupAssessmentState.CONFIRMED_SETUP.value
    assert manual.candidate_ids == ()
    assert len(worker.candidate_ids) == 1
    assert evaluation_input_hash(manual_request) == evaluation_input_hash(worker_request)
