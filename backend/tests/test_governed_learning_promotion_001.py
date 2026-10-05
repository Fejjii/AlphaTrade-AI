"""Exact-version learning gates, human paper promotion and preserved rollback history."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.db.models import (
    BacktestDataset,
    BacktestRun,
    Document,
    JournalTrade,
    JournalTradeObservation,
    Membership,
    PaperTrade,
    PaperValidationRun,
    StrategyConversationProposal,
    StrategyLifecycleEvent,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.strategy_immutability import StrategyVersionImmutabilityError
from app.interactive_agent.contracts import AgentTurnRequest, TurnOperation
from app.interactive_agent.service import InteractiveAgentService
from app.schemas.backtest import BacktestAssumptions
from app.schemas.common import (
    ConversationMessageRole,
    DocumentSourceType,
    JournalTradeSource,
    JournalTradeStatus,
    MembershipRole,
    PaperTradeStatus,
    PaperValidationRuntimeMode,
    PaperValidationStatus,
    StrategyId,
)
from app.schemas.governed_learning import (
    GovernedProposalCreate,
    LearningEvidenceRef,
    LearningPromotionApproval,
    LearningRollbackApproval,
    LearningValidationEvidence,
)
from app.schemas.nested_continuation import NestedContinuationSpec
from app.schemas.paper_validation import PaperValidationConfig, PaperValidationRunStart
from app.schemas.strategy_library import StrategyCard, UserStrategyCreate
from app.schemas.strategy_replay import ReplayWindows, StrategyReplayCreate
from app.services.backtest_hashing import dataset_content_hash
from app.services.backtest_service import BacktestService
from app.services.canonical_strategy_evaluation import resolve_executable_strategy_policy
from app.services.compiled_setup_service import CompiledSetupService
from app.services.conversation_service import ConversationService
from app.services.paper_validation_runtime_service import PaperValidationRuntimeService
from app.services.strategy_library_service import StrategyLibraryService
from app.services.strategy_promotion import StrategyPromotionService
from app.services.strategy_proposal_service import StrategyProposalService
from app.services.strategy_replay_service import StrategyReplayService
from app.signal_fusion.errors import StrategyEvaluationPolicyError
from tests.test_interactive_agent_foundation import ORG_A, ORG_B, USER_A, USER_A2, USER_B
from tests.test_interactive_agent_foundation import agent_db as agent_db
from tests.test_strategy_brain_nested import PRICES, START
from tests.test_strategy_replay_001 import STEP, candle_rows


@pytest.fixture
def lifecycle(agent_db, request):
    factory, settings = agent_db
    with factory() as session:
        card = StrategyCard(
            strategy_name="Governed Nested",
            entry_conditions=["Closed break"],
            invalidation=["Structure lost"],
            stop_loss=["Beyond retracement"],
            promotion_requirements=getattr(request, "param", None),
        )
        spec = NestedContinuationSpec(symbol="BTCUSDT").model_dump(mode="json")
        strategy = StrategyLibraryService(session).create(
            UserStrategyCreate(
                organization_id=ORG_A,
                user_id=USER_A,
                name="Governed Nested",
                setup_type=StrategyId.NESTED_CONTINUATION,
                card=card,
                pattern_spec=spec,
            )
        )
        parent = session.scalar(
            select(UserStrategyVersion).where(UserStrategyVersion.strategy_id == strategy.id)
        )
        compiled = CompiledSetupService(session)
        compiled.compile_version(parent.id, organization_id=ORG_A, user_id=USER_A)
        compiled.approve_version(
            parent.id, organization_id=ORG_A, user_id=USER_A, confirm_message="I confirm"
        )
        conversations = ConversationService(session)
        conversation = conversations.get_or_create(
            organization_id=ORG_A, user_id=USER_A, strategy_id=strategy.id, conversation_id=None
        )
        message = conversations.append_message(
            conversation=conversation,
            role=ConversationMessageRole.USER,
            content="Observed several retracement failures.",
        )
        spec = deepcopy(spec)
        spec["parameters"]["minimum_impulse"] = "0.004"
        payload = GovernedProposalCreate(
            conversation_id=conversation.id,
            base_version_id=parent.id,
            source_observations=[LearningEvidenceRef(kind="conversation_message", id=message.id)],
            hypothesis="A smaller impulse may preserve valid continuation setups.",
            reason="Review the recorded retracement failures.",
            validation_plan="Exact replay then separate paper sample.",
            card=card,
            pattern_spec=spec,
        )
        proposal = StrategyProposalService(session).create_governed(
            strategy.id, payload, organization_id=ORG_A, user_id=USER_A
        )
        session.commit()
        promotion = StrategyPromotionService(session, settings)
        yield session, settings, strategy, parent, proposal, payload, promotion


def candidate(lifecycle):
    session, _, _, _, proposal, _, _ = lifecycle
    result = StrategyProposalService(session).request_governed_validation(
        proposal.id,
        expected_content_hash=proposal.content_hash,
        organization_id=ORG_A,
        user_id=USER_A,
    )
    session.commit()
    return result.resulting_version_id


def replays(lifecycle, version_id, cycles=10, evaluation_bars=None):
    session, settings, _, parent, proposal, _, promotion = lifecycle
    rows = candle_rows(PRICES * cycles)
    session.add_all(rows)
    session.flush()
    session.expire_all()
    dataset = BacktestDataset(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="15m",
        start_date=START.date(),
        end_date=rows[-1].open_time.date(),
        candle_count=len(rows),
        first_open_time=rows[0].open_time,
        last_open_time=rows[-1].open_time,
        gap_count=0,
        stale_count=0,
        source_counts={"binance": len(rows)},
        dataset_hash=dataset_content_hash(rows),
    )
    session.add(dataset)
    session.commit()
    backtests = BacktestService(session, settings)
    replay = StrategyReplayService(session, backtests)
    ids = []
    for identity in (parent.id, version_id):
        request = StrategyReplayCreate(
            strategy_version_id=identity,
            dataset_id=dataset.id,
            windows=ReplayWindows(
                training_start=START,
                training_end=START + STEP * len(PRICES) * 4,
                evaluation_start=START + STEP * len(PRICES) * 4,
                evaluation_end=START
                + STEP
                * (len(PRICES) * 4 + evaluation_bars if evaluation_bars is not None else len(rows)),
                as_of=START + STEP * len(rows),
            ),
            minimum_sample=2,
            assumptions=BacktestAssumptions(timeframe="15m", risk_per_trade_pct=Decimal("0.1")),
            idempotency_key=str(uuid4()),
        )
        run = replay.create(request, organization_id=ORG_A, user_id=USER_A)
        session.commit()
        completed = backtests.execute_run(run.id, organization_id=ORG_A)
        session.commit()
        assert completed.result is not None
        ids.append(run.id)
    evidence = LearningValidationEvidence(
        expected_content_hash=proposal.content_hash, baseline_run_id=ids[0], proposed_run_id=ids[1]
    )
    status = promotion.record_validation(
        proposal.id, evidence, organization_id=ORG_A, user_id=USER_A
    )
    session.commit()
    assert status.replayed
    return evidence


def paper(lifecycle, version_id, count=3):
    session, settings, strategy, _, _, _, _ = lifecycle
    runtime = PaperValidationRuntimeService(session, settings)
    run = runtime.start(
        strategy.id,
        PaperValidationRunStart(
            strategy_version_id=version_id,
            runtime_mode=PaperValidationRuntimeMode.AUTO_PAPER,
            config=PaperValidationConfig(exchange="binance"),
        ),
        organization_id=ORG_A,
        user_id=USER_A,
    )
    session.commit()
    policy = resolve_executable_strategy_policy(
        session,
        organization_id=ORG_A,
        user_id=USER_A,
        strategy_version_id=version_id,
        paper_validation_run_id=run.id,
    )
    assert policy.execution_scope == "paper_validation"
    with pytest.raises(StrategyEvaluationPolicyError):
        resolve_executable_strategy_policy(
            session, organization_id=ORG_A, user_id=USER_A, strategy_version_id=version_id
        )
    for n in range(count):
        session.add(
            PaperTrade(
                paper_validation_run_id=run.id,
                strategy_id=strategy.id,
                strategy_version_id=version_id,
                organization_id=ORG_A,
                user_id=USER_A,
                symbol="BTCUSDT",
                exchange="binance",
                timeframe="15m",
                direction="long",
                status=PaperTradeStatus.CLOSED,
                entry_time=datetime.now(UTC) - timedelta(hours=2),
                exit_time=datetime.now(UTC),
                gross_pnl=Decimal(5 + n),
                net_pnl=Decimal(5 + n),
                fees=Decimal(0),
                slippage=Decimal(0),
            )
        )
    session.flush()
    row = session.get(PaperValidationRun, run.id)
    row.metrics = runtime._aggregate_metrics(
        run.id, organization_id=ORG_A, config=PaperValidationConfig(exchange="binance")
    ).model_dump(mode="json")
    row.status = PaperValidationStatus.PASSED
    row.ended_at = datetime.now(UTC)
    row.blockers = []
    session.commit()
    return run.id


def ready(lifecycle, count=3):
    version_id = candidate(lifecycle)
    evidence = replays(lifecycle, version_id)
    run_id = paper(lifecycle, version_id, count)
    session, _, _, _, proposal, _, promotion = lifecycle
    evidence = evidence.model_copy(update={"paper_validation_run_id": run_id})
    status = promotion.record_validation(
        proposal.id, evidence, organization_id=ORG_A, user_id=USER_A
    )
    session.commit()
    approval = LearningPromotionApproval(
        confirm="APPROVE_PAPER_PROMOTION",
        expected_content_hash=proposal.content_hash,
        expected_version_id=version_id,
        expected_comparison_hash=status.comparison_hash,
        expected_paper_validation_run_id=run_id,
        evidence_review="Reviewed limited samples and unchanged PnL; approve paper research only.",
    )
    return approval, status


def test_proposal_and_validation_do_not_select_active_rules(lifecycle):
    session, _, strategy, parent, proposal, _, promotion = lifecycle
    assert session.get(UserStrategy, strategy.id).current_version == parent.version
    assert session.scalar(select(func.count()).select_from(UserStrategyVersion)) == 1
    version_id = candidate(lifecycle)
    assert session.get(UserStrategy, strategy.id).current_version == parent.version
    version = session.get(UserStrategyVersion, version_id)
    assert version.parent_version_id == parent.id
    assert version.content_hash != parent.content_hash
    repeated = candidate(lifecycle)
    assert repeated == version_id
    status = promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A)
    assert status.paper_active_version_id == parent.id
    assert not status.replayed and status.blockers
    with pytest.raises(ValidationAppError, match="evidence-bound"):
        CompiledSetupService(session).approve_version(
            version_id, organization_id=ORG_A, user_id=USER_A, confirm_message="I confirm"
        )


def test_missing_replay_blocks_promotion(lifecycle):
    _, _, _, _, proposal, _, promotion = lifecycle
    version_id = candidate(lifecycle)
    approval = LearningPromotionApproval(
        confirm="APPROVE_PAPER_PROMOTION",
        expected_content_hash=proposal.content_hash,
        expected_version_id=version_id,
        expected_comparison_hash="0" * 64,
        expected_paper_validation_run_id=uuid4(),
    )
    with pytest.raises(ValidationAppError) as error:
        promotion.promote(proposal.id, approval, organization_id=ORG_A, user_id=USER_A)
    assert "replay" in str(error.value.details)


def test_missing_paper_and_baseline_mismatch(lifecycle):
    _, _, _, _, proposal, _, promotion = lifecycle
    evidence = replays(lifecycle, candidate(lifecycle))
    status = promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A)
    assert not status.paper_validation_completed
    assert any("paper validation" in blocker for blocker in status.blockers)
    with pytest.raises(ValidationAppError, match="Baseline/candidate mismatch"):
        promotion.record_validation(
            proposal.id,
            evidence.model_copy(update={"baseline_run_id": evidence.proposed_run_id}),
            organization_id=ORG_A,
            user_id=USER_A,
        )


def test_insufficient_evidence_needs_human_review(lifecycle):
    approval, status = ready(lifecycle)
    assert status.insufficient_evidence and not status.blockers
    _, _, _, _, proposal, _, promotion = lifecycle
    with pytest.raises(ValidationAppError, match="explicit human evidence review"):
        promotion.promote(
            proposal.id,
            approval.model_copy(update={"evidence_review": None}),
            organization_id=ORG_A,
            user_id=USER_A,
        )


def test_explicit_approval_immutable_activation_rollback_and_duplicate(lifecycle):
    approval, _ = ready(lifecycle)
    session, _, strategy, parent, proposal, _, promotion = lifecycle
    before = deepcopy(parent.card), parent.content_hash
    event = promotion.promote(proposal.id, approval, organization_id=ORG_A, user_id=USER_A)
    session.commit()
    assert event.evidence_snapshot["rollback_version_id"] == str(parent.id)
    assert event.evidence_snapshot["explicit_human_approval"]
    assert session.get(UserStrategy, strategy.id).current_version == 2
    assert (parent.card, parent.content_hash) == before
    assert session.scalar(select(func.count()).select_from(UserStrategyVersion)) == 2
    repeated = promotion.promote(proposal.id, approval, organization_id=ORG_A, user_id=USER_A)
    assert event.id == repeated.id
    status = promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A)
    assert status.can_roll_back and not status.live_execution_permitted
    promotion.rollback(
        strategy.id,
        LearningRollbackApproval(
            confirm="ROLLBACK_PAPER_STRATEGY",
            expected_active_version_id=approval.expected_version_id,
            target_version_id=parent.id,
            reason="Return to reviewed baseline",
        ),
        organization_id=ORG_A,
        user_id=USER_A,
    )
    session.commit()
    assert session.get(UserStrategy, strategy.id).current_version == parent.version
    assert (
        promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A).approval_state
        == "rolled_back"
    )
    # A duplicate approval after rollback returns its receipt without activating again.
    assert (
        promotion.promote(proposal.id, approval, organization_id=ORG_A, user_id=USER_A).id
        == event.id
    )
    assert session.get(UserStrategy, strategy.id).current_version == parent.version
    version = session.get(UserStrategyVersion, approval.expected_version_id)
    version.pattern_spec = {**version.pattern_spec, "symbol": "ETHUSDT"}
    with pytest.raises(StrategyVersionImmutabilityError):
        session.flush()
    session.rollback()


def test_single_winning_paper_trade_is_not_validation(lifecycle):
    approval, status = ready(lifecycle, count=1)
    assert any("One paper trade" in blocker for blocker in status.blockers)
    _, _, _, _, proposal, _, promotion = lifecycle
    with pytest.raises(ValidationAppError):
        promotion.promote(proposal.id, approval, organization_id=ORG_A, user_id=USER_A)


def test_unauthorized_and_tenant_isolation(lifecycle):
    session, _, _, _, proposal, _, promotion = lifecycle
    approval, _ = ready(lifecycle)
    membership = session.scalar(select(Membership).where(Membership.user_id == USER_A))
    membership.role = MembershipRole.VIEWER
    session.commit()
    with pytest.raises(ForbiddenError):
        promotion.promote(proposal.id, approval, organization_id=ORG_A, user_id=USER_A)
    for org, user in ((ORG_B, USER_B), (ORG_A, USER_A2)):
        with pytest.raises(NotFoundError):
            promotion.status(proposal.id, organization_id=org, user_id=user)
        assert not promotion.list_status(organization_id=org, user_id=user).items


def test_agent_reads_are_bounded_and_prose_cannot_approve(lifecycle):
    session, settings, strategy, _, proposal, _, promotion = lifecycle
    counts = session.scalar(select(func.count()).select_from(StrategyLifecycleEvent))
    for question in (
        "What strategy changes are proposed?",
        "Why was this change proposed?",
        "Has it been replayed?",
        "Did it outperform the baseline?",
        "Has it completed paper validation?",
        "Which version is paper active?",
        "Can we roll back?",
        "I approve this promotion",
    ):
        result = InteractiveAgentService(session, settings=settings).handle_turn(
            AgentTurnRequest(message=question, strategy_id=strategy.id),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        assert result.operation is TurnOperation.READ
        assert result.governed_learning[0].proposal_id == proposal.id
        assert not result.authority_mutated and not result.proposals
    assert session.scalar(select(func.count()).select_from(StrategyLifecycleEvent)) == counts
    with pytest.raises(ValidationAppError):
        promotion.list_status(organization_id=ORG_A, user_id=USER_A, limit=21)


def test_live_enablement_refused(lifecycle):
    session, settings, strategy, _, _, _, _ = lifecycle
    with pytest.raises(ValidationError):
        LearningPromotionApproval(
            confirm="APPROVE_PAPER_PROMOTION",
            expected_content_hash="0" * 64,
            expected_version_id=uuid4(),
            expected_comparison_hash="0" * 64,
            expected_paper_validation_run_id=uuid4(),
            execution_mode="live",
        )
    result = InteractiveAgentService(session, settings=settings).handle_turn(
        AgentTurnRequest(
            message="Enable live trading and promote strategy", strategy_id=strategy.id
        ),
        organization_id=ORG_A,
        user_id=USER_A,
    )
    assert result.operation is TurnOperation.REFUSE


def test_changed_proposal_identity_and_source_scope_rejected(lifecycle):
    session, _, strategy, _, proposal, payload, promotion = lifecycle
    with pytest.raises(NotFoundError):
        StrategyProposalService(session).create_governed(
            strategy.id,
            payload.model_copy(
                update={
                    "source_observations": [
                        LearningEvidenceRef(kind="conversation_message", id=uuid4())
                    ]
                }
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
    row = session.get(StrategyConversationProposal, proposal.id)
    row.proposed_pattern_spec = {**row.proposed_pattern_spec, "symbol": "ETHUSDT"}
    session.flush()
    with pytest.raises(ConflictError):
        promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A)


@pytest.mark.parametrize(
    "lifecycle",
    [
        {"minimum_replay_trades": 100, "minimum_paper_trades": 2},
        {"minimum_replay_trades": 2, "minimum_paper_trades": 4},
    ],
    indirect=True,
)
def test_strategy_defined_sample_requirements_cannot_be_overridden(lifecycle):
    approval, status = ready(lifecycle)
    assert any("base strategy's requirements" in blocker for blocker in status.blockers)
    _, _, _, _, proposal, _, promotion = lifecycle
    with pytest.raises(ValidationAppError):
        promotion.promote(proposal.id, approval, organization_id=ORG_A, user_id=USER_A)


def test_comparison_requires_identical_data_windows(lifecycle):
    session, _, _, _, proposal, _, promotion = lifecycle
    evidence = replays(lifecycle, candidate(lifecycle))
    row = session.get(BacktestRun, evidence.proposed_run_id)
    snapshot = deepcopy(row.config_snapshot)
    snapshot["replay_request"]["windows"]["evaluation_end"] = START.isoformat()
    row.config_snapshot = snapshot
    session.commit()
    status = promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A)
    assert not status.replayed and any(
        "identical windows" in blocker for blocker in status.blockers
    )


def test_wrong_paper_version_is_rejected(lifecycle):
    session, _, _, parent, proposal, _, promotion = lifecycle
    version_id = candidate(lifecycle)
    evidence = replays(lifecycle, version_id)
    run_id = paper(lifecycle, version_id)
    session.get(PaperValidationRun, run_id).strategy_version_id = parent.id
    session.commit()
    with pytest.raises(ValidationAppError, match="exact candidate"):
        promotion.record_validation(
            proposal.id,
            evidence.model_copy(update={"paper_validation_run_id": run_id}),
            organization_id=ORG_A,
            user_id=USER_A,
        )


def test_paper_aggregate_tampering_cannot_pass(lifecycle):
    approval, _ = ready(lifecycle)
    session, _, _, _, proposal, _, promotion = lifecycle
    run = session.get(PaperValidationRun, approval.expected_paper_validation_run_id)
    run.metrics = {**run.metrics, "net_pnl": "1000000"}
    session.commit()
    status = promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A)
    assert not status.paper_validation_completed
    with pytest.raises(ValidationAppError):
        promotion.promote(proposal.id, approval, organization_id=ORG_A, user_id=USER_A)


def test_approval_identity_does_not_accept_other_evidence(lifecycle):
    approval, _ = ready(lifecycle)
    _, _, _, _, proposal, _, promotion = lifecycle
    with pytest.raises(ConflictError, match="reviewed validation"):
        promotion.promote(
            proposal.id,
            approval.model_copy(update={"expected_comparison_hash": "f" * 64}),
            organization_id=ORG_A,
            user_id=USER_A,
        )
    event = promotion.promote(proposal.id, approval, organization_id=ORG_A, user_id=USER_A)
    with pytest.raises(ConflictError, match="Duplicate approval"):
        promotion.promote(
            proposal.id,
            approval.model_copy(update={"expected_comparison_hash": "f" * 64}),
            organization_id=ORG_A,
            user_id=USER_A,
        )
    assert event.id


def test_unsupported_candidate_leaves_no_partial_version(lifecycle):
    session, _, strategy, parent, _, payload, _ = lifecycle
    payload = payload.model_copy(update={"pattern_spec": {"kind": "unsupported"}})
    service = StrategyProposalService(session)
    proposal = service.create_governed(strategy.id, payload, organization_id=ORG_A, user_id=USER_A)
    session.commit()
    with pytest.raises(ValidationAppError, match="supported executable"):
        service.request_governed_validation(
            proposal.id,
            expected_content_hash=proposal.content_hash,
            organization_id=ORG_A,
            user_id=USER_A,
        )
    assert session.scalar(select(func.count()).select_from(UserStrategyVersion)) == 1
    assert session.get(UserStrategy, strategy.id).current_version == parent.version


def test_http_governed_endpoints_and_rbac(lifecycle):
    from fastapi.testclient import TestClient

    from app.core.auth import get_current_tenant
    from app.db.session import get_session
    from app.main import create_app
    from app.security.tenant import TenantContext

    session, settings, strategy, parent, proposal, payload, _ = lifecycle
    app = create_app(settings=settings)
    actor = {"user": USER_A, "org": ORG_A, "role": MembershipRole.OWNER}
    app.dependency_overrides[get_current_tenant] = lambda: TenantContext(
        user_id=actor["user"],
        organization_id=actor["org"],
        email="test@example.org",
        membership_role=actor["role"],
    )
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        response = client.get(f"/governed-learning/proposals/{proposal.id}")
        assert response.status_code == 200
        assert response.json()["paper_active_version_id"] == str(parent.id)
        assert client.get("/governed-learning/proposals?limit=21").status_code == 422
        created = client.post(
            f"/governed-learning/strategies/{strategy.id}/proposals",
            json=payload.model_dump(mode="json"),
        )
        assert created.status_code == 200, created.text
        requested = client.post(
            f"/governed-learning/proposals/{proposal.id}/validation-request",
            json={"expected_content_hash": proposal.content_hash},
        )
        assert requested.status_code == 200, requested.text
        candidate_id = requested.json()["resulting_version_id"]
        assert (
            client.post(
                f"/strategies/{strategy.id}/versions/{candidate_id}/approve",
                json={"confirm": "I confirm"},
            ).status_code
            == 422
        )
        promotion = {
            "confirm": "APPROVE_PAPER_PROMOTION",
            "expected_content_hash": proposal.content_hash,
            "expected_version_id": candidate_id,
            "expected_comparison_hash": "f" * 64,
            "expected_paper_validation_run_id": str(uuid4()),
        }
        assert (
            client.post(
                f"/governed-learning/proposals/{proposal.id}/approve-paper-promotion",
                json=promotion,
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/governed-learning/proposals/{proposal.id}/approve-paper-promotion",
                json={**promotion, "execution_mode": "live"},
            ).status_code
            == 422
        )
        actor["role"] = MembershipRole.VIEWER
        assert (
            client.post(
                f"/governed-learning/proposals/{proposal.id}/approve-paper-promotion",
                json=promotion,
            ).status_code
            == 403
        )
        actor.update(user=USER_B, org=ORG_B, role=MembershipRole.OWNER)
        assert client.get(f"/governed-learning/proposals/{proposal.id}").status_code == 404
        assert client.get("/governed-learning/proposals").json()["items"] == []


def test_one_winning_replay_trade_cannot_promote(lifecycle):
    _, _, _, _, proposal, _, promotion = lifecycle
    replays(lifecycle, candidate(lifecycle), evaluation_bars=15)
    status = promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A)
    assert any("One winning trade" in blocker for blocker in status.blockers)


def test_status_reads_never_flush_pending_strategy_mutations(lifecycle):
    session, _, strategy, parent, proposal, _, promotion = lifecycle
    parent.card = {**parent.card, "strategy_name": "Unflushed mutation"}
    # A flush would raise immutability; bounded reads must not perform that write.
    assert (
        promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A).proposal_id
        == proposal.id
    )
    assert promotion.list_status(
        organization_id=ORG_A, user_id=USER_A, strategy_id=strategy.id
    ).items
    session.rollback()


def test_recorded_journal_knowledge_analytics_and_daily_review_are_hashable(lifecycle):
    session, _, strategy, parent, _, payload, promotion = lifecycle
    journal = JournalTrade(
        organization_id=ORG_A,
        user_id=USER_A,
        source=JournalTradeSource.MANUAL,
        status=JournalTradeStatus.CLOSED,
        symbol="BTCUSDT",
        timeframe="15m",
        direction="long",
        user_strategy_id=strategy.id,
        strategy_version_id=parent.id,
        net_pnl=Decimal("10"),
        gross_pnl=Decimal("11"),
        fees=Decimal("1"),
        funding=Decimal(0),
        slippage=Decimal(0),
        entry_time=START,
        exit_time=START + timedelta(hours=1),
    )
    document = Document(
        organization_id=ORG_A,
        user_id=USER_A,
        source_type=DocumentSourceType.REVIEW_NOTE,
        title="Continuation research",
    )
    session.add_all([journal, document])
    session.flush()
    observation = JournalTradeObservation(
        organization_id=ORG_A,
        journal_trade_id=journal.id,
        category="process",
        observation="Review retracement quality",
        recorded_by=USER_A,
    )
    session.add(observation)
    session.commit()
    payload = payload.model_copy(
        update={
            "source_observations": [
                LearningEvidenceRef(kind="journal_observation", id=observation.id)
            ],
            "evidence_ids": [
                LearningEvidenceRef(kind="journal_trade", id=journal.id),
                LearningEvidenceRef(kind="document", id=document.id),
            ],
            "review_day": START.date(),
        }
    )
    proposal = StrategyProposalService(session).create_governed(
        strategy.id, payload, organization_id=ORG_A, user_id=USER_A
    )
    session.commit()
    metadata = proposal.context_refs["governed_learning_001"]
    assert metadata["analytics"]["overall"]["trade_count"] == 1
    assert metadata["daily_review"]["review_id"]
    assert promotion.status(proposal.id, organization_id=ORG_A, user_id=USER_A).evidence_ids


def test_legacy_conversation_confirmation_preserves_paper_active_selection(lifecycle):
    session, _, strategy, parent, _, payload, _ = lifecycle
    service = StrategyProposalService(session)
    conversation = ConversationService(session).require(
        payload.conversation_id, organization_id=ORG_A, user_id=USER_A
    )
    proposal = service.create_draft_from_text(
        conversation,
        text="HTF pullback long, 2% fixed stop, take profit 1R, skip high funding",
        strategy_id=strategy.id,
    )
    assert proposal.proposed_structured_rules is not None
    confirmed = service.confirm(
        proposal.id,
        organization_id=ORG_A,
        user_id=USER_A,
        confirm_message="I confirm",
        expected_content_hash=proposal.content_hash,
        expected_parent_version_id=parent.id,
        expected_target_strategy_id=strategy.id,
        expected_organization_id=ORG_A,
        expected_user_id=USER_A,
        expected_conversation_id=conversation.id,
    )
    session.commit()
    assert confirmed.resulting_version_id != parent.id
    assert session.get(UserStrategy, strategy.id).current_version == parent.version
    resolve_executable_strategy_policy(
        session, organization_id=ORG_A, user_id=USER_A, strategy_version_id=parent.id
    )
    with pytest.raises(StrategyEvaluationPolicyError):
        resolve_executable_strategy_policy(
            session,
            organization_id=ORG_A,
            user_id=USER_A,
            strategy_version_id=confirmed.resulting_version_id,
        )
