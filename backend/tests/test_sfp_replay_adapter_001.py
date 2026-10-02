"""Canonical SFP research through PR173 jobs: causality, identity, and no trades."""

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, Inexact, localcontext
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.db.models import (
    BacktestDataset,
    BacktestRun,
    BacktestTrade,
    HistoricalCandle,
    JournalTrade,
    Organization,
    PaperValidationCandidate,
    User,
    UserStrategy,
    UserStrategyVersion,
)
from app.market_contracts.derivatives import DerivativeMetric, derivative_observation
from app.market_contracts.enums import FreshnessState
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.order_flow import order_flow_identity, order_flow_observation
from app.market_contracts.trade_reduction import build_released_trade_snapshot
from app.market_contracts.trades import build_trade_event
from app.schemas.backtest import BacktestAssumptions
from app.schemas.common import (
    BacktestRunStatus,
    BacktestSplitLabel,
    StrategyChangeSource,
    Timeframe,
)
from app.schemas.strategy_replay import (
    ReplayCandleEvidence,
    ReplayComparisonRequest,
    ReplayReport,
    ReplayWindows,
    SfpReplayEvidence,
    StrategyReplayCreate,
)
from app.services.backtest_hashing import dataset_content_hash
from app.services.backtest_service import BacktestService
from app.services.risk.engine import RiskEngine
from app.services.sfp_replay_adapter import SfpReplayAdapter
from app.services.strategy_replay_engine import StrategyReplayEngine
from app.services.strategy_replay_service import StrategyReplayService
from app.services.strategy_versioning import StrategyVersioningService
from app.strategy_brain.service import create_template
from app.strategy_brain.sfp.detector import detect_sfp
from app.strategy_brain.sfp.levels import derive_levels
from tests.test_sfp_detector import BEAR, BULL, START, evidence, spec
from tests.test_watcher_paper_runtime import _sqlite_factory

STEP = timedelta(minutes=15)


def inputs(prices=BULL):
    bars, observations = evidence([*prices, *prices])
    proofs = SfpReplayEvidence(
        candles=[
            ReplayCandleEvidence(bar=b, observation=o)
            for b, o in zip(bars, observations, strict=True)
        ]
    )
    rows = [
        HistoricalCandle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="15m",
            open_time=b.interval_start,
            close_time=b.interval_end - timedelta(seconds=1),
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.base_volume,
            source="synthetic",
            is_stale=False,
        )
        for b in bars
    ]
    return rows, proofs


@pytest.fixture
def sfp_store(settings, request):
    bearish = getattr(request, "param", False)
    factory = _sqlite_factory()
    org, user = uuid4(), uuid4()
    with factory() as session:
        session.add_all(
            [
                Organization(id=org, name="SFP research"),
                User(id=user, email="sfp-replay@test.example", hashed_password="unused"),
            ]
        )
        session.flush()
        template = create_template(
            session, organization_id=org, user_id=user, spec=spec(bearish=bearish)
        )
        rows, proofs = inputs(BEAR if bearish else BULL)
        session.add_all(rows)
        session.flush()
        session.expire_all()
        dataset = BacktestDataset(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="15m",
            start_date=START.date(),
            end_date=START.date(),
            candle_count=len(rows),
            first_open_time=rows[0].open_time,
            last_open_time=rows[-1].open_time,
            gap_count=0,
            stale_count=0,
            source_counts={"synthetic": len(rows)},
            dataset_hash=dataset_content_hash(rows),
        )
        session.add(dataset)
        session.commit()
        replay = StrategyReplayCreate(
            strategy_version_id=template["version_id"],
            dataset_id=dataset.id,
            windows=ReplayWindows(
                training_start=START,
                training_end=START + STEP * 6,
                evaluation_start=START + STEP * 6,
                evaluation_end=START + STEP * 12,
                as_of=START + STEP * 12,
            ),
            assumptions=BacktestAssumptions(timeframe="15m"),
            idempotency_key="sfp-baseline",
            sfp_evidence=proofs,
        )
        backtests = BacktestService(session, settings)
        service = StrategyReplayService(session, backtests)
        yield session, org, user, replay, backtests, service
    factory.kw["bind"].dispose()


def complete(store, request=None):
    session, org, user, original, backtests, service = store
    queued = service.create(request or original, organization_id=org, user_id=user)
    session.commit()
    run = backtests.execute_run(queued.id, organization_id=org)
    session.commit()
    assert run.status is BacktestRunStatus.COMPLETED, run.error_message
    return run


def test_governed_learning_keeps_sfp_research_out_of_trade_promotion(sfp_store, settings):
    from app.db.models import Membership
    from app.schemas.common import ConversationMessageRole, MembershipRole
    from app.schemas.governed_learning import (
        GovernedProposalCreate,
        LearningEvidenceRef,
        LearningPromotionApproval,
        LearningValidationEvidence,
    )
    from app.schemas.strategy_library import StrategyCard
    from app.services.compiled_setup_service import CompiledSetupService
    from app.services.conversation_service import ConversationService
    from app.services.strategy_promotion import StrategyPromotionService
    from app.services.strategy_proposal_service import StrategyProposalService

    session, org, user, request, _, _ = sfp_store
    parent = session.get(UserStrategyVersion, request.strategy_version_id)
    session.add(Membership(organization_id=org, user_id=user, role=MembershipRole.OWNER))
    compiled = CompiledSetupService(session)
    compiled.compile_version(parent.id, organization_id=org, user_id=user)
    compiled.approve_version(
        parent.id, organization_id=org, user_id=user, confirm_message="I confirm"
    )
    conversations = ConversationService(session)
    conversation = conversations.get_or_create(
        organization_id=org, user_id=user, strategy_id=parent.strategy_id, conversation_id=None
    )
    message = conversations.append_message(
        conversation=conversation,
        role=ConversationMessageRole.USER,
        content="Review SFP sweep-depth sensitivity using structural replay.",
    )
    proposals = StrategyProposalService(session)
    proposal = proposals.create_governed(
        parent.strategy_id,
        GovernedProposalCreate(
            conversation_id=conversation.id,
            base_version_id=parent.id,
            source_observations=[LearningEvidenceRef(kind="conversation_message", id=message.id)],
            hypothesis="Compare larger SFP sweep depth.",
            reason="Recorded structural review only.",
            validation_plan="Structural replay cannot substitute for trade-return evidence.",
            card=StrategyCard.model_validate(parent.card),
            pattern_spec=spec(minimum_sweep_depth="0.03").model_dump(mode="json"),
        ),
        organization_id=org,
        user_id=user,
    )
    candidate = proposals.request_governed_validation(
        proposal.id,
        expected_content_hash=proposal.content_hash,
        organization_id=org,
        user_id=user,
    )
    session.commit()
    baseline = complete(sfp_store)
    proposed = complete(
        sfp_store,
        request.model_copy(
            update={
                "strategy_version_id": candidate.resulting_version_id,
                "idempotency_key": "candidate",
            }
        ),
    )
    promotion = StrategyPromotionService(session, settings)
    status = promotion.record_validation(
        proposal.id,
        LearningValidationEvidence(
            expected_content_hash=proposal.content_hash,
            baseline_run_id=baseline.id,
            proposed_run_id=proposed.id,
        ),
        organization_id=org,
        user_id=user,
    )
    assert status.replayed
    assert status.observed_net_pnl_delta is None and status.outperformed_baseline is None
    assert not status.improvement_claim and status.insufficient_evidence
    assert "Replay lacks authorized trade-return evidence for promotion." in status.blockers
    with pytest.raises(ValidationAppError, match="Promotion blocked"):
        promotion.promote(
            proposal.id,
            LearningPromotionApproval(
                confirm="APPROVE_PAPER_PROMOTION",
                expected_content_hash=proposal.content_hash,
                expected_version_id=candidate.resulting_version_id,
                expected_comparison_hash=status.comparison_hash,
                expected_paper_validation_run_id=uuid4(),
                evidence_review="Structural observations cannot supply execution returns.",
            ),
            organization_id=org,
            user_id=user,
        )
    assert session.get(UserStrategy, parent.strategy_id).current_version == parent.version
    assert session.scalar(select(func.count()).select_from(BacktestTrade)) == 0
    assert session.scalar(select(func.count()).select_from(JournalTrade)) == 0


@pytest.mark.parametrize("sfp_store", [False, True], indirect=True)
def test_both_directions_real_detector_restart_and_no_execution(sfp_store, monkeypatch):
    session, org, user, request, backtests, service = sfp_store
    monkeypatch.setattr(
        backtests._engine,
        "_build_trade_record",
        lambda *a, **kw: pytest.fail("SFP must never fill"),
    )
    monkeypatch.setattr(
        RiskEngine, "evaluate", lambda *a, **kw: pytest.fail("No SFP plan for risk")
    )
    run = complete(sfp_store)
    report = ReplayReport.model_validate(run.result.replay)
    assert run.result.metrics is None and run.result.trades == []
    assert report.mode == "sfp_research" and report.improvement_claim is False
    assert report.structural_levels and report.research_buckets
    assert all(sample.net_pnl is None and sample.mean_r is None for sample in report.samples)
    assert all(sample.candidate_count == 1 and sample.setup_count == 1 for sample in report.samples)
    assert all(sample.status == "insufficient_sample" for sample in report.samples)
    first = request.sfp_evidence.candles[:6]
    canonical = detect_sfp(
        tuple(item.bar for item in first),
        tuple(item.observation for item in first),
        spec(bearish=request.sfp_evidence.candles[4].bar.high == Decimal(102)),
        evaluated_at=first[-1].bar.interval_end,
    )
    assert [
        c.sfp_detection for c in report.candidates if c.split_label is BacktestSplitLabel.IN_SAMPLE
    ] == list(canonical.events)
    assert all(
        c.entry is None
        and c.stop is None
        and not c.targets
        and c.risk_decision is None
        and c.trade_sequence is None
        for c in report.candidates
    )
    assert all(
        c.risk_applicability == "not_evaluated_no_authorized_execution_plan"
        for c in report.candidates
    )
    for model in (PaperValidationCandidate, BacktestTrade, JournalTrade):
        assert session.scalar(select(func.count()).select_from(model)) == 0
    session.expire_all()
    assert backtests.verify(run.id, organization_id=org, user_id=user).match
    with Session(session.get_bind()) as restarted:
        assert (
            BacktestService(restarted, backtests._settings)
            .verify(run.id, organization_id=org, user_id=user)
            .match
        )
    repeated = complete(sfp_store, request.model_copy(update={"idempotency_key": "repeat"}))
    assert repeated.result_hash == run.result_hash
    with localcontext() as context:
        context.prec = 8
        context.traps[Inexact] = True
        assert (
            service.replay(session.get(BacktestRun, run.id), persist=False).result_hash
            == run.result_hash
        )


@pytest.mark.parametrize("bearish", [False, True])
def test_prefixes_levels_and_future_pivots(bearish):
    _rows, proofs = inputs(BEAR if bearish else BULL)
    bars = tuple(item.bar for item in proofs.candles[:6])
    authored = spec(bearish=bearish).model_dump(mode="json")
    adapter = SfpReplayAdapter(proofs)
    full = list(adapter.events(bars, authored, BacktestSplitLabel.IN_SAMPLE))
    for count in range(1, len(bars) + 1):
        partial = SfpReplayAdapter(proofs)
        events = list(partial.events(bars[:count], authored, BacktestSplitLabel.IN_SAMPLE))
        assert events == [(i, c) for i, c in full if i < count]
        assert partial.levels == [
            level for level in adapter.levels if level.considered_at <= bars[count - 1].interval_end
        ]
        assert all(
            level.level.known_at
            <= bars[int((level.considered_at - START) / STEP) - 1].interval_start
            for level in partial.levels
        )
    future_pivot = spec(bearish=bearish, pivot_width=2)
    bars, observations = evidence(
        [
            (102, 104, 101, 103),
            (101, 103, 100, 101),
            (102, 104, 101, 103),
            (103, 104, 98, 101),
            (101, 106, 100, 105),
        ]
    )
    proof = SfpReplayEvidence(
        candles=[
            ReplayCandleEvidence(bar=b, observation=o)
            for b, o in zip(bars, observations, strict=True)
        ]
    )
    result = list(
        SfpReplayAdapter(proof).events(
            bars, future_pivot.model_dump(mode="json"), BacktestSplitLabel.IN_SAMPLE
        )
    )
    assert not any(c.sfp_detection.sweep.reference_level.price == 100 for _, c in result)


@pytest.mark.parametrize(
    "damage",
    [
        "absent",
        "missing_confirmation",
        "stale_confirmation",
        "late_confirmation",
        "forming_confirmation",
    ],
)
def test_missing_required_proof_never_fabricates_confirmation(sfp_store, damage):
    request = sfp_store[3].model_copy(deep=True)
    proof = request.sfp_evidence
    if damage == "absent":
        request.sfp_evidence = None
    elif damage == "missing_confirmation":
        proof.candles.pop(5)
    else:
        item = proof.candles[5]
        if damage == "stale_confirmation":
            item.observation = with_content_hash(
                item.observation.model_copy(update={"freshness_state": FreshnessState.STALE})
            )
        elif damage == "late_confirmation":
            item.observation = item.observation.model_copy(
                update={"receive_time": item.bar.interval_end + timedelta(days=1)}
            )
        else:
            bars, obs = evidence(forming=True)
            proof.candles[5] = ReplayCandleEvidence(bar=bars[-1], observation=obs[-1])
    run = complete(sfp_store, request)
    report = run.result.replay
    assert report["samples"][0]["status"] == "missing_data"
    assert report["samples"][0]["candidate_count"] == 0
    assert report["evidence_gaps"] and report["missing_evidence"]
    assert run.result.metrics is None
    if damage == "stale_confirmation":
        assert report["stale_evidence"]
    if damage != "absent":
        assert any(
            c["state"] == "FORMING" for c in report["candidates"] if c["split_label"] == "in_sample"
        )


def test_receipt_delay_is_preserved(sfp_store):
    request = sfp_store[3].model_copy(deep=True)
    item = request.sfp_evidence.candles[4]
    delayed = item.bar.interval_end + timedelta(seconds=5)
    item.observation = item.observation.model_copy(
        update={"observed_at": delayed, "receive_time": delayed}
    )
    run = complete(sfp_store, request)
    candidate = run.result.replay["candidates"][0]
    assert candidate["detected_at"] == delayed.isoformat().replace("+00:00", "Z")
    assert candidate["sfp_detection"]["event_time"] != candidate["detected_at"]


@pytest.mark.parametrize(
    "tail,expected",
    [
        ([(101, 102, 99, 100)], "failed_reclaims"),
        ([(101, 102, 97, 99)], "invalidations"),
        ([(104, 106, 102, 105)] * 7, "expiries"),
    ],
)
def test_canonical_failures_invalidation_and_expiry(tail, expected):
    bars, obs = evidence([*BULL, *tail])
    proof = SfpReplayEvidence(
        candles=[ReplayCandleEvidence(bar=b, observation=o) for b, o in zip(bars, obs, strict=True)]
    )
    events = [
        candidate
        for _, candidate in SfpReplayAdapter(proof).events(
            bars, spec().model_dump(mode="json"), BacktestSplitLabel.IN_SAMPLE
        )
    ]
    counts = StrategyReplayEngine._sfp_counts(events)
    assert counts[expected] >= 1 and counts["confirmed_setups"] == 1


def native_evidence(proof, clock):
    ident = proof.candles[0].observation.identity
    derivatives = [
        derivative_observation(
            identity=ident,
            metric=metric,
            observed_at=clock,
            row={
                "value": "123" if metric is DerivativeMetric.OPEN_INTEREST else "-0.0001",
                "time": int(clock.timestamp() * 1000),
            },
            value_key="value",
            time_key="time",
        )
        for metric in DerivativeMetric
    ]
    flow_ident = order_flow_identity(ident)
    lineage = uuid4()
    trades = [
        build_trade_event(
            instrument=ident.instrument,
            venue_trade_id=str(i),
            sequence=i,
            price=Decimal(100),
            quantity=Decimal(i + 1),
            buyer_is_maker=False,
            event_timestamp=at,
            receive_timestamp=clock,
            source_connection_id=lineage,
            adapter_version=ident.source.adapter_version,
        )
        for i, at in enumerate((clock - timedelta(minutes=9), clock - timedelta(minutes=1)))
    ]
    tape = build_released_trade_snapshot(
        trades,
        identity=flow_ident,
        lineage_id=lineage,
        window_start=clock - timedelta(minutes=10),
        window_end=clock,
        observed_at=clock,
    )
    flow = order_flow_observation(identity=ident, observed_at=clock, snapshot=tape)
    return flow, derivatives


def test_native_flow_cvd_oi_funding_and_staleness(sfp_store):
    request = sfp_store[3].model_copy(deep=True)
    flow, derivatives = native_evidence(request.sfp_evidence, START + STEP * 6)
    request.sfp_evidence.order_flow = [flow]
    request.sfp_evidence.derivatives = derivatives
    run = complete(sfp_store, request)
    candidates = run.result.replay["candidates"]
    available = next(
        c for c in candidates if c["split_label"] == "in_sample" and c["state"] == "CONFIRMED"
    )
    assert all(
        available["evidence"][key] == "AVAILABLE"
        for key in ("cvd", "order_flow", "open_interest", "funding")
    )
    assert available["research_evidence"]["funding"]["observation"]["value"] == "-0.0001"
    stale = next(
        c for c in candidates if c["split_label"] == "out_of_sample" and c["state"] == "CONFIRMED"
    )
    assert {"cvd", "order_flow", "open_interest"}.issubset(stale["stale_evidence"])
    assert stale["research_evidence"]["cvd"]["observation"] is None
    assert stale["evidence"]["funding"] == "AVAILABLE"
    assert run.result.metrics is None


@pytest.mark.parametrize("future", [False, True])
def test_htf_known_at_and_target_space(sfp_store, future):
    request = sfp_store[3].model_copy(deep=True)
    bars, obs = evidence(
        BULL[:3], start=START - timedelta(hours=8 if future else 12), timeframe=Timeframe.H4
    )
    request.sfp_evidence.context_levels = list(
        derive_levels(
            bars, obs, spec().parameters, evaluated_at=bars[-1].interval_end, higher_timeframe=True
        )
    )
    run = complete(sfp_store, request)
    first = run.result.replay["candidates"][0]["sfp_detection"]["quality"]
    assert first["higher_timeframe_alignment"]["availability"] == (
        "MISSING" if future else "AVAILABLE"
    )
    assert first["available_target_space"]["availability"] == "MISSING"
    assert first["available_target_space"]["value"] is None
    assert run.result.replay["candidates"][0]["targets"] == []


def test_version_comparison_same_evidence_no_improvement(sfp_store):
    session, org, user, request, _, service = sfp_store
    baseline = complete(sfp_store)
    parent = session.get(UserStrategyVersion, request.strategy_version_id)
    proposed = StrategyVersioningService(session).fork_semantic_update(
        session.get(UserStrategy, parent.strategy_id),
        parent=parent,
        card=parent.card,
        structured_rules=parent.structured_rules,
        lesson_source_metadata=parent.lesson_source_metadata,
        actor_user_id=user,
        source=StrategyChangeSource.PATTERN_SPEC,
        reason="SFP parameter research",
        pattern_spec=spec(minimum_sweep_depth="0.03").model_dump(mode="json"),
    )
    session.commit()
    changed = complete(
        sfp_store,
        request.model_copy(
            update={"strategy_version_id": proposed.id, "idempotency_key": "proposed"}
        ),
    )
    comparison_request = ReplayComparisonRequest(
        baseline_run_id=baseline.id, proposed_run_id=changed.id
    )
    comparison = service.compare(comparison_request, organization_id=org)
    assert comparison.baseline_version_id != comparison.proposed_version_id
    assert comparison.improvement_claim is False and comparison.evaluation_net_pnl_delta is None
    assert comparison.baseline_samples[1].candidate_count == 1
    assert comparison.proposed_samples[1].candidate_count == 0
    assert comparison.baseline_research_buckets
    assert (
        comparison.comparison_hash
        == service.compare(comparison_request, organization_id=org).comparison_hash
    )
    with pytest.raises(NotFoundError):
        service.compare(comparison_request, organization_id=uuid4())
    alternate = request.model_copy(deep=True)
    alternate.idempotency_key = "different-proof"
    alternate.sfp_evidence.candles[0].observation = alternate.sfp_evidence.candles[
        0
    ].observation.model_copy(update={"recorded_at": START + timedelta(days=1)})
    different = complete(sfp_store, alternate)
    with pytest.raises(ValidationAppError, match=r"identical.*evidence"):
        service.compare(
            ReplayComparisonRequest(baseline_run_id=baseline.id, proposed_run_id=different.id),
            organization_id=org,
        )


@pytest.mark.parametrize(
    "damage", ["receipt", "quality", "trade_metrics", "dataset", "assumptions", "version"]
)
def test_tamper_detection(sfp_store, damage):
    session, org, user, _, backtests, service = sfp_store
    run = complete(sfp_store)
    row = session.get(BacktestRun, run.id)
    if damage == "receipt":
        config = deepcopy(row.config_snapshot)
        config["replay_request"]["sfp_evidence"]["candles"][0]["observation"]["receive_time"] = (
            "2026-10-02T12:00:00Z"
        )
        row.config_snapshot = config
    elif damage == "quality":
        result = deepcopy(row.result)
        result["replay"]["candidates"][0]["sfp_detection"]["quality"]["volume"]["value"] = "99"
        row.result = result
    elif damage == "trade_metrics":
        result = deepcopy(row.result)
        result["metrics"] = {}
        row.result = result
    elif damage == "dataset":
        session.scalar(select(HistoricalCandle)).is_stale = True
    elif damage == "assumptions":
        row.assumptions = {**row.assumptions, "fees_bps": "99"}
    else:
        version = session.get(UserStrategyVersion, row.strategy_version_id)
        # Simulate corruption without a semantic edit through the versioning API.
        set_committed_value(version, "content_hash", "0" * 64)
    session.flush()
    assert backtests.verify(run.id, organization_id=org, user_id=user).match is False
    if damage in {"quality", "trade_metrics", "assumptions"}:
        with pytest.raises(ValidationAppError):
            service.compare(
                ReplayComparisonRequest(baseline_run_id=run.id, proposed_run_id=run.id),
                organization_id=org,
            )


def test_training_isolation_cancel_and_idempotency(sfp_store):
    session, org, user, request, backtests, service = sfp_store
    queued = service.create(request, organization_id=org, user_id=user)
    session.commit()
    row = session.get(BacktestRun, queued.id)
    rows = backtests._load_dataset_candles(session.get(BacktestDataset, row.dataset_id))
    first = StrategyReplayEngine(backtests._engine).run(rows=rows, snapshot=row.config_snapshot)
    changed = deepcopy(row.config_snapshot)
    changed["replay_request"]["sfp_evidence"]["candles"] = changed["replay_request"][
        "sfp_evidence"
    ]["candles"][:6]
    second = StrategyReplayEngine(backtests._engine).run(rows=rows, snapshot=changed)
    assert first.replay["samples"][0] == second.replay["samples"][0]
    assert [c for c in first.replay["candidates"] if c["split_label"] == "in_sample"] == [
        c for c in second.replay["candidates"] if c["split_label"] == "in_sample"
    ]
    cancelled = StrategyReplayEngine(backtests._engine).run(
        rows=rows, snapshot=row.config_snapshot, should_cancel=lambda: True
    )
    assert cancelled.cancelled and cancelled.processed_bars == 0 and cancelled.metrics is None
    assert all(s["status"] == "cancelled" for s in cancelled.replay["samples"])
    with pytest.raises(ConflictError):
        service.create(
            request.model_copy(update={"minimum_sample": 1}), organization_id=org, user_id=user
        )


def test_bad_native_hash_and_mismatched_candle_refused(sfp_store):
    _session, org, user, original, _, service = sfp_store
    request = original.model_copy(deep=True)
    flow, _ = native_evidence(request.sfp_evidence, START + STEP * 6)
    request.sfp_evidence.order_flow = [flow.model_copy(update={"content_hash": "0" * 64})]
    with pytest.raises(ValidationAppError, match="hash"):
        service.create(request, organization_id=org, user_id=user)
    request = original.model_copy(deep=True)
    request.sfp_evidence.candles[0].bar = request.sfp_evidence.candles[0].bar.model_copy(
        update={"content_hash": "0" * 64}
    )
    with pytest.raises(ValidationAppError, match="hash"):
        service.create(request, organization_id=org, user_id=user)


def test_future_optional_evidence_cannot_change_past_decisions(sfp_store):
    request = sfp_store[3].model_copy(deep=True)
    flow, derivatives = native_evidence(request.sfp_evidence, START + STEP * 12)
    request.sfp_evidence.order_flow = [flow]
    request.sfp_evidence.derivatives = derivatives
    run = complete(sfp_store, request)
    for candidate in run.result.replay["candidates"]:
        if candidate["split_label"] == "in_sample":
            assert all(
                candidate["evidence"][key] == "MISSING"
                for key in ("cvd", "order_flow", "open_interest", "funding")
            )
    assert len(run.result.replay["evidence_frames"]) == 12
    assert all(
        frame["evidence"]["cvd"]["availability"] == "MISSING"
        for frame in run.result.replay["evidence_frames"]
        if frame["split_label"] == "in_sample"
    )


def test_sfp_existing_replay_api_read_verify_compare_and_tenant_fences():
    from tests.test_at034_integration import ORG_A, USER_A, _auth, _build_client

    def seed(session):
        rows, _ = inputs()
        session.add_all(rows)
        session.flush()
        session.expire_all()
        session.add(
            BacktestDataset(
                symbol="BTCUSDT",
                exchange="binance",
                timeframe="15m",
                start_date=START.date(),
                end_date=START.date(),
                candle_count=len(rows),
                first_open_time=rows[0].open_time,
                last_open_time=rows[-1].open_time,
                gap_count=0,
                stale_count=0,
                source_counts={"synthetic": len(rows)},
                dataset_hash=dataset_content_hash(rows),
            )
        )

    with _build_client(candle_seed=seed) as (client, factory, _settings):
        with factory() as session:
            template = create_template(session, organization_id=ORG_A, user_id=USER_A, spec=spec())
            dataset = session.scalar(select(BacktestDataset))
            _, proofs = inputs()
            request = StrategyReplayCreate(
                strategy_version_id=template["version_id"],
                dataset_id=dataset.id,
                windows=ReplayWindows(
                    training_start=START,
                    training_end=START + STEP * 6,
                    evaluation_start=START + STEP * 6,
                    evaluation_end=START + STEP * 12,
                    as_of=START + STEP * 12,
                ),
                assumptions=BacktestAssumptions(timeframe="15m"),
                sfp_evidence=proofs,
                idempotency_key="sfp-api",
            )
            session.commit()
        auth = _auth(client, "at034-int-a@test.example")
        created = client.post(
            "/backtests/replays", json=request.model_dump(mode="json"), headers=auth
        )
        assert created.status_code == 201, created.text
        identity = created.json()["id"]
        run = client.get(f"/backtests/{identity}", headers=auth).json()
        assert run["status"] == "completed", run
        assert run["result"]["metrics"] is None and run["result"]["trades"] == []
        assert run["result"]["replay"]["mode"] == "sfp_research"
        assert client.post(f"/backtests/{identity}/verify", headers=auth).json()["match"]
        comparison = client.post(
            "/backtests/replays/compare",
            json={"baseline_run_id": identity, "proposed_run_id": identity},
            headers=auth,
        )
        assert comparison.status_code == 200, comparison.text
        assert comparison.json()["evaluation_net_pnl_delta"] is None
        assert comparison.json()["improvement_claim"] is False
        assert client.get(f"/backtests/{identity}/trades", headers=auth).json()["total"] == 0
        other = _auth(client, "at034-int-b@test.example")
        assert client.get(f"/backtests/{identity}", headers=other).status_code == 404
        assert (
            client.post(
                "/backtests/replays", json=request.model_dump(mode="json"), headers=other
            ).status_code
            == 404
        )
        viewer = _auth(client, "at034-int-viewer@test.example")
        assert (
            client.post(
                "/backtests/replays", json=request.model_dump(mode="json"), headers=viewer
            ).status_code
            == 403
        )
