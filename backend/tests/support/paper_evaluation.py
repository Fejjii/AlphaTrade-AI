"""Builders for continuous paper-evaluation measurement tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.learning_attribution.contracts import (
    AttributionFacts,
    AttributionRecord,
    DecisionActor,
    ExecutionQuality,
    ExecutionQualityFacts,
    HumanVsSystemAttributionFacts,
    LearningVenueMode,
    PlannedSetupQuality,
    PlannedSetupQualityFacts,
    RiskAdherence,
    RiskAdherenceFacts,
    StrategyPatternStatFacts,
    TradeOutcomeFacts,
    TraderBehavior,
    TraderBehaviorFacts,
)
from app.paper_evaluation.contracts import (
    DataQualityClass,
    PaperEvaluationObservation,
    PaperEvaluationStage,
)
from app.paper_evaluation.hashing import hashed_observation
from app.paper_evaluation.identity import observation_id_for
from app.paper_evaluation.ports import JournalTradeMeasurement
from app.schemas.common import JournalLifecycleEventType, JournalTradeStatus, TradeResult
from app.signal_fusion.action_eligibility import ActionEligibilityEvaluation
from app.signal_fusion.enums import (
    ActionEligibilityState,
    CandidateState,
    EligibilityReasonCode,
    SetupAssessmentState,
)
from app.signal_fusion.types import hashed_model
from app.watcher.contracts import (
    EvaluationCommand,
    EvaluationMode,
    EvaluationOutcome,
    EvaluationStatus,
    ScanRequest,
    ScanTrigger,
)
from tests.support.phase6_fusion import (
    ACCOUNT_ID,
    COMPILED_SETUP_ID,
    ORG_ID,
    STRATEGY_VERSION_ID,
    USER_ID,
)

HASH = "ab" * 32
GENERATED_AT = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
OTHER_STRATEGY_VERSION_ID = UUID("dddddddd-dddd-dddd-dddd-ddddddddddd1")


def make_observation(**overrides: object) -> PaperEvaluationObservation:
    source_system = str(overrides.get("source_system", "watcher_fusion"))
    source_event_id = str(overrides.get("source_event_id", str(uuid4())))
    source_event_version = int(overrides.get("source_event_version", 1))
    organization_id = overrides.get("organization_id", ORG_ID)
    assert isinstance(organization_id, UUID)
    payload: dict[str, object] = {
        "observation_id": observation_id_for(
            organization_id=organization_id,
            source_system=source_system,
            source_event_id=source_event_id,
            source_event_version=source_event_version,
        ),
        "organization_id": organization_id,
        "stage": PaperEvaluationStage.WATCHER_SCAN,
        "source_system": source_system,
        "source_event_id": source_event_id,
        "source_event_version": source_event_version,
        "occurred_at": GENERATED_AT,
        "data_quality": DataQualityClass.FRESH,
        "learning_venue_mode": LearningVenueMode.PAPER_INTERNAL,
        "live_executable": False,
        "content_hash": "0" * 64,
    }
    payload.update(overrides)
    return hashed_observation(PaperEvaluationObservation.model_validate(payload))


def make_scan(
    *,
    status: str = "succeeded",
    reason_code: str | None = None,
    data_quality: DataQualityClass = DataQualityClass.FRESH,
    replayed: bool = False,
    organization_id: UUID = ORG_ID,
    source_event_id: str | None = None,
    assessment_state: SetupAssessmentState | None = None,
) -> PaperEvaluationObservation:
    return make_observation(
        organization_id=organization_id,
        stage=PaperEvaluationStage.WATCHER_SCAN,
        source_system="watcher_fusion",
        source_event_id=source_event_id or str(uuid4()),
        scan_status=status,
        reason_code=reason_code,
        data_quality=data_quality,
        replayed=replayed,
        assessment_state=assessment_state,
    )


def make_assessment_observation(
    *,
    state: SetupAssessmentState,
    organization_id: UUID = ORG_ID,
    assessment_id: UUID | None = None,
) -> PaperEvaluationObservation:
    return make_observation(
        organization_id=organization_id,
        stage=PaperEvaluationStage.SETUP_ASSESSMENT,
        source_system="watcher_setup_assessment",
        source_event_id=str(uuid4()),
        assessment_id=assessment_id or uuid4(),
        assessment_state=state,
        reason_code=state.value,
        setup_quality=(
            PlannedSetupQuality.CONFIRMED
            if state is SetupAssessmentState.CONFIRMED_SETUP
            else PlannedSetupQuality.INVALIDATED
            if state is SetupAssessmentState.INVALIDATED
            else PlannedSetupQuality.NOT_CONFIRMED
        ),
    )


def make_eval_command(*, organization_id: UUID = ORG_ID) -> EvaluationCommand:
    request = ScanRequest(
        organization_id=organization_id,
        scan_scope="BTCUSDT:15m",
        policy_id=uuid4(),
        policy_version=1,
        policy_content_hash=HASH,
        watchlist_item_ids=(uuid4(),),
        idempotency_key=f"eval-{uuid4()}",
    )
    return EvaluationCommand(
        command_id=uuid4(),
        request=request,
        request_hash=HASH,
        evaluation_input_hash=HASH,
        mode=EvaluationMode.PREVIEW,
        trigger=ScanTrigger.MANUAL,
        correlation_id=uuid4(),
    )


def make_eval_outcome(
    command: EvaluationCommand,
    *,
    status: EvaluationStatus = EvaluationStatus.SUCCEEDED,
    reason_code: str = SetupAssessmentState.CONFIRMED_SETUP.value,
    candidate_ids: tuple[UUID, ...] = (),
) -> EvaluationOutcome:
    return EvaluationOutcome(
        command_id=command.command_id,
        request_hash=command.request_hash,
        evaluation_input_hash=command.evaluation_input_hash,
        status=status,
        reason_code=reason_code,
        evaluated_units=1,
        candidate_ids=candidate_ids,
    )


def journal_measurement(
    journal_trade_id: UUID,
    *,
    net_pnl: str | None = "10",
    mfe: str | None = "20",
    mae: str | None = "5",
    capture: str | None = "60",
    closed_at: datetime | None = GENERATED_AT,
) -> JournalTradeMeasurement:
    return JournalTradeMeasurement(
        journal_trade_id=journal_trade_id,
        mfe_amount=None if mfe is None else Decimal(mfe),
        mae_amount=None if mae is None else Decimal(mae),
        capture_pct=None if capture is None else Decimal(capture),
        net_pnl=None if net_pnl is None else Decimal(net_pnl),
        result=TradeResult.WIN
        if net_pnl is not None and Decimal(net_pnl) > 0
        else TradeResult.LOSS,
        closed_at=closed_at,
    )


def make_attribution_record(
    *,
    organization_id: UUID = ORG_ID,
    candidate_id: UUID | None = None,
    strategy_version_id: UUID = STRATEGY_VERSION_ID,
    setup_definition_id: UUID = COMPILED_SETUP_ID,
    confirmed: bool = True,
    rejected: bool = False,
    skipped: bool = False,
    plan_approved: bool = False,
    filled: bool = False,
    closed: bool = False,
    win: bool = False,
    loss: bool = False,
    breakeven: bool = False,
    executed: bool = False,
    net_pnl: str | None = None,
    result: TradeResult | None = None,
    journal_trade_id: UUID | None = None,
    risk_adherence: RiskAdherence = RiskAdherence.NOT_APPLICABLE,
    assessment_id: UUID | None = None,
    narrative: str | None = None,
) -> AttributionRecord:
    resolved_candidate = candidate_id or uuid4()
    resolved_assessment = assessment_id or uuid4()
    attribution_id = uuid4()
    outcome_eligible = executed
    setup_axis = PlannedSetupQuality.CONFIRMED if confirmed else PlannedSetupQuality.NOT_CONFIRMED
    if rejected:
        behavior_axis = TraderBehavior.REJECTED
        actor = DecisionActor.HUMAN_DECISION
        event_type = JournalLifecycleEventType.REJECT
        candidate_state = CandidateState.REJECTED
    elif skipped:
        behavior_axis = TraderBehavior.SKIPPED
        actor = DecisionActor.HUMAN_DECISION
        event_type = JournalLifecycleEventType.SKIP
        candidate_state = CandidateState.SKIPPED
    elif closed or executed:
        behavior_axis = TraderBehavior.EXECUTED
        actor = DecisionActor.PAPER_SYSTEM_EXECUTION
        event_type = JournalLifecycleEventType.CLOSE
        candidate_state = CandidateState.ACTIVE
    elif filled:
        behavior_axis = TraderBehavior.EXECUTED
        actor = DecisionActor.PAPER_SYSTEM_EXECUTION
        event_type = JournalLifecycleEventType.FILL
        candidate_state = CandidateState.ACTIVE
    elif plan_approved:
        behavior_axis = TraderBehavior.APPROVED_PLAN
        actor = DecisionActor.HUMAN_APPROVAL
        event_type = JournalLifecycleEventType.APPROVED_PLAN
        candidate_state = CandidateState.ACTIVE
    else:
        behavior_axis = TraderBehavior.AWAITING_DECISION
        actor = DecisionActor.SYSTEM_SETUP
        event_type = JournalLifecycleEventType.CANDIDATE_CONFIRMED
        candidate_state = CandidateState.ACTIVE
    setup = PlannedSetupQualityFacts(
        axis=setup_axis,
        assessment_id=resolved_assessment,
        assessment_state=(
            SetupAssessmentState.CONFIRMED_SETUP if confirmed else SetupAssessmentState.NO_SETUP
        ),
        assessment_content_hash=HASH,
        evidence_window_hash=HASH,
        reason_codes=("confirmed_setup",) if confirmed else ("no_setup",),
        confirmed=confirmed,
    )
    execution = ExecutionQualityFacts(axis=ExecutionQuality.NOT_APPLICABLE)
    risk = RiskAdherenceFacts(axis=risk_adherence)
    behavior = TraderBehaviorFacts(
        axis=behavior_axis,
        actor=actor,
        event_type=event_type,
        candidate_state=candidate_state,
        executed_trade_outcome=outcome_eligible,
    )
    outcome = TradeOutcomeFacts(
        eligible=outcome_eligible,
        journal_trade_id=journal_trade_id,
        status=JournalTradeStatus.CLOSED if closed else None,
        result=result,
        net_pnl=None if net_pnl is None else Decimal(net_pnl),
    )
    pattern = StrategyPatternStatFacts(
        strategy_version_id=strategy_version_id,
        setup_definition_id=setup_definition_id,
        fusion_policy_version="fusion/v1",
        uniqueness_tuple_hash=HASH,
        candidate_confirmed=confirmed,
        rejected=rejected,
        skipped=skipped,
        plan_approved=plan_approved,
        filled=filled,
        closed=closed,
        executed_outcome=outcome_eligible,
        win=win,
        loss=loss,
        breakeven=breakeven,
    )
    human = HumanVsSystemAttributionFacts(
        decision_actor=actor,
        setup_quality_axis=setup_axis,
        execution_quality_axis=execution.axis,
        risk_adherence_axis=risk_adherence,
        trader_behavior_axis=behavior_axis,
        net_pnl=outcome.net_pnl,
        result=result,
        executed_trade_outcome=outcome_eligible,
        journal_trade_id=journal_trade_id,
        candidate_id=resolved_candidate,
        strategy_version_id=strategy_version_id,
        setup_definition_id=setup_definition_id,
    )
    draft = AttributionFacts(
        attribution_id=attribution_id,
        organization_id=organization_id,
        account_id=ACCOUNT_ID,
        user_id=USER_ID,
        candidate_id=resolved_candidate,
        candidate_content_hash=HASH,
        uniqueness_tuple_hash=HASH,
        execution_lifecycle_id=None,
        journal_trade_id=journal_trade_id,
        assessment_id=resolved_assessment,
        evidence_window_hash=HASH,
        trade_plan_revision_id=None,
        setup_quality=setup,
        execution_quality=execution,
        risk_adherence=risk,
        trader_behavior=behavior,
        outcome=outcome,
        human_vs_system=human,
        strategy_pattern=pattern,
        projection_replayed=False,
        content_hash="0" * 64,
    )
    facts = hashed_model(draft)
    return AttributionRecord(
        attribution_id=facts.attribution_id,
        organization_id=organization_id,
        candidate_id=resolved_candidate,
        execution_lifecycle_id=None,
        journal_trade_id=journal_trade_id,
        facts=facts,
        events=(),
        narrative_explanation=narrative,
    )


def closed_win(
    *,
    pnl: str = "10",
    candidate_id: UUID | None = None,
    strategy_version_id: UUID = STRATEGY_VERSION_ID,
    journal_trade_id: UUID | None = None,
) -> AttributionRecord:
    trade_id = journal_trade_id or uuid4()
    return make_attribution_record(
        candidate_id=candidate_id,
        strategy_version_id=strategy_version_id,
        confirmed=True,
        plan_approved=True,
        filled=True,
        closed=True,
        win=True,
        executed=True,
        net_pnl=pnl,
        result=TradeResult.WIN,
        journal_trade_id=trade_id,
        risk_adherence=RiskAdherence.ADHERED,
    )


def closed_loss(
    *,
    pnl: str = "-8",
    candidate_id: UUID | None = None,
    strategy_version_id: UUID = STRATEGY_VERSION_ID,
    journal_trade_id: UUID | None = None,
    risk_adherence: RiskAdherence = RiskAdherence.ADHERED,
) -> AttributionRecord:
    trade_id = journal_trade_id or uuid4()
    return make_attribution_record(
        candidate_id=candidate_id,
        strategy_version_id=strategy_version_id,
        confirmed=True,
        plan_approved=True,
        filled=True,
        closed=True,
        loss=True,
        executed=True,
        net_pnl=pnl,
        result=TradeResult.LOSS,
        journal_trade_id=trade_id,
        risk_adherence=risk_adherence,
    )


def blocked_evaluation(
    evaluation: ActionEligibilityEvaluation,
    *,
    reason: EligibilityReasonCode = EligibilityReasonCode.BLOCKED_KILL_SWITCH,
    candidate_id: UUID | None = None,
) -> ActionEligibilityEvaluation:
    eligibility = hashed_model(
        evaluation.eligibility.model_copy(
            update={
                "state": ActionEligibilityState.BLOCKED,
                "reason_codes": (reason,),
                "candidate_id": candidate_id or evaluation.eligibility.candidate_id,
                "content_hash": "0" * 64,
                "valid_until": evaluation.eligibility.checked_at + timedelta(minutes=5),
            }
        )
    )
    return evaluation.model_copy(
        update={
            "eligibility": eligibility,
            "paper_actionable": False,
            "evaluation_revision": evaluation.evaluation_revision + 1,
        }
    )
