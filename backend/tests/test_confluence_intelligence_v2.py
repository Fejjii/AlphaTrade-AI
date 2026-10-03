"""Deterministic advisory assessments over real canonical contracts and fixture prints."""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.confluence import assess_confluence, get_policy
from app.confluence.comparisons import (
    ResearchCase,
    compare_with_cvd_filter,
    compare_with_oi_filter,
    compare_with_order_flow_filter,
)
from app.confluence.contracts import AnalysisState, ComponentName, ConfluenceAssessment
from app.market_contracts.derivatives import DerivativeMetric, derivative_observation
from app.market_contracts.enums import FreshnessState, VenueId
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.observation import (
    observation_from_derivative,
    observation_from_ohlcv,
    observation_from_order_flow,
)
from app.market_contracts.ohlcv import ClosedOhlcvSeries
from app.schemas.common import (
    JournalTradeSource,
    JournalTradeStatus,
    MarketRegime,
    Timeframe,
    TradeDirection,
)
from app.schemas.journal_trades import JournalTradeRead
from app.schemas.nested_continuation import EvidenceAvailability as Availability
from app.schemas.nested_continuation import NestedContinuationSpec
from app.schemas.risk import DailyRiskState
from app.schemas.strategy_analytics import (
    StrategyAnalyticsFilters,
    StrategyAnalyticsMetrics,
    StrategyAnalyticsReport,
)
from app.services.canonical_serialization import canonical_sha256
from app.signal_fusion.action_eligibility import PortfolioState
from app.signal_fusion.adapters import AssessmentCommand
from app.signal_fusion.eligibility import build_action_eligibility
from app.signal_fusion.enums import (
    ActionEligibilityState,
    EligibilityReasonCode,
    EvidenceAdapterKind,
    EvidenceRole,
)
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle
from app.signal_fusion.policy import FusionThresholds, build_fusion_policy
from app.signal_fusion.strategy_evaluation_policy import (
    evaluate_canonical_strategy,
    executable_policy_from_fusion_policy,
)
from app.signal_fusion.types import HalfOpenInterval, TriggerIdentity
from tests.support.phase6_fusion import (
    ACCOUNT_ID,
    ORG_ID,
    STRATEGY_ID,
    STRATEGY_VERSION_ID,
    USER_ID,
    executable_setup,
)
from tests.test_market_intelligence_cvd_orderflow import END, NOW, read
from tests.test_market_intelligence_oi_funding import identity
from tests.test_sfp_detector import BEAR, BULL
from tests.test_sfp_detector import evidence as sfp_evidence
from tests.test_sfp_detector import spec as sfp_spec
from tests.test_strategy_brain_nested import PRICES


def world(*, family="nested", bearish=False, required=(), flow=False):
    ident = identity(VenueId.BINANCE)
    if family == "nested":
        prices = [300 - p if bearish else p for p in PRICES]
        rows = [(p, p + 1, p - 1, p) for p in prices]
        spec = NestedContinuationSpec(
            symbol="BTCUSDT", direction=TradeDirection.SHORT if bearish else TradeDirection.LONG
        )
    else:
        rows, spec = (BEAR if bearish else BULL), sfp_spec(bearish=bearish)
    bars, _ = sfp_evidence(rows, start=END - timedelta(minutes=15 * len(rows)))
    observations = tuple(
        observation_from_ohlcv(
            b,
            identity=ident,
            observed_at=b.interval_end,
            receive_time=b.interval_end,
            freshness_state=FreshnessState.FRESH,
        ).model_copy(update={"recorded_at": b.interval_end})
        for b in bars
    )
    # Use the same canonical command representation as each existing family.
    if family == "nested":
        history_hash = canonical_sha256([b.content_hash for b in bars])
        history = with_content_hash(
            observations[-1].model_copy(
                update={
                    "observation_id": UUID(int=70),
                    "source_event_id": f"history:{history_hash}",
                    "interval_start": bars[0].interval_start,
                    "payload_content_hash": history_hash,
                }
            )
        )
        public, roles = (
            (observations[-1], history),
            (EvidenceRole.TRIGGER_OHLCV, EvidenceRole.STRUCTURE),
        )
    else:
        public = (observations[-1], *observations)
        roles = (EvidenceRole.TRIGGER_OHLCV, *(EvidenceRole.STRUCTURE for _ in observations))
    flow_item = read() if flow else None
    for role in required:
        if role in {EvidenceRole.CVD_5M, EvidenceRole.ORDER_FLOW_5M} and flow_item:
            public += (observation_from_order_flow(flow_item, cvd=role is EvidenceRole.CVD_5M),)
        elif role in {EvidenceRole.OPEN_INTEREST, EvidenceRole.FUNDING}:
            placeholder = derivative(ident, DerivativeMetric(role.value))
            public += (observation_from_derivative(placeholder),)
        else:
            # Canonical window can reference a role, but an envelope is no payload substitute.
            public += (observations[-1],)
        roles += (role,)
    fusion = build_fusion_policy(
        policy_version=f"{family}-fixture/v1",
        organization_id=ORG_ID,
        strategy_version_id=STRATEGY_VERSION_ID,
        executable_setup=executable_setup(),
        required_roles=(EvidenceRole.TRIGGER_OHLCV, EvidenceRole.STRUCTURE, *required),
        role_timeframes=(),
        thresholds=FusionThresholds(confirmation_score=Decimal(1)),
        freshness_policy_version="fixture-freshness/v1",
        finality_policy_version="final-bar/v1",
    )
    executable = executable_policy_from_fusion_policy(
        fusion,
        strategy_id=STRATEGY_ID,
        strategy_version_content_hash="a" * 64,
        authored_spec=spec,
    )
    command = AssessmentCommand(
        organization_id=ORG_ID,
        strategy_version_id=STRATEGY_VERSION_ID,
        executable_setup=fusion.executable_setup,
        fusion_policy_version=fusion.policy_version,
        finality_policy_version=fusion.finality_policy_version,
        freshness_policy_version=fusion.freshness_policy_version,
        evidence_identity=ident,
        direction=spec.direction,
        interval=HalfOpenInterval(start=bars[0].interval_start, end=END),
        trigger=TriggerIdentity(natural_event_id=bars[-1].source_event_id, revision=1),
        mandatory_evidence_roles=fusion.required_roles,
        public_observations=public,
        selected_roles=roles,
        role_timeframes=(),
        source_set=(),
        adapter_kind=EvidenceAdapterKind.WATCHER,
    )
    evidence = FirstSliceEvidenceBundle(bars_15m=bars, order_flow=flow_item)
    setup = evaluate_canonical_strategy(
        executable_policy=executable, command=command, evidence=evidence, evaluated_at=NOW
    )
    return {
        "executable": executable,
        "command": command,
        "evidence": evidence,
        "setup": setup,
        "user_id": USER_ID,
        "account_id": ACCOUNT_ID,
        "assessed_at": NOW,
    }


def derivative(ident, metric=DerivativeMetric.OPEN_INTEREST, value="100", at=NOW):
    return derivative_observation(
        identity=ident,
        metric=metric,
        observed_at=at,
        row={"value": value, "time": int(at.timestamp() * 1000)},
        value_key="value",
        time_key="time",
    )


def item(result, name):
    return next(
        c for c in (*result.quality_components, *result.context_components) if c.key == name
    )


def rehash(result):
    return result.model_copy(
        update={"content_hash": canonical_sha256(result.model_dump(exclude={"content_hash"}))}
    )


@pytest.mark.parametrize("family", ["nested", "sfp"])
@pytest.mark.parametrize("bearish", [False, True])
def test_reuses_exact_setup_and_detector_identity_without_mutation(family, bearish):
    data = world(family=family, bearish=bearish)
    before = {k: v.model_dump() for k, v in data.items() if hasattr(v, "model_dump")}
    result = assess_confluence(**data)
    assert result.state is AnalysisState.READY
    assert result.setup == data["setup"]
    assert result.detector_kind == data["executable"].adapter_id
    assert before == {k: v.model_dump() for k, v in data.items() if hasattr(v, "model_dump")}
    assert result == assess_confluence(**data)
    assert ConfluenceAssessment.model_validate_json(result.model_dump_json()) == result


def test_missing_optional_reduces_coverage_without_blocking():
    data = world()
    baseline = assess_confluence(**data)
    data["evidence"] = data["evidence"].model_copy(update={"order_flow": read()})
    enriched = assess_confluence(**data)
    assert baseline.state is enriched.state is AnalysisState.READY
    assert enriched.setup == baseline.setup
    assert baseline.coverage.scored_weight_fraction == Decimal("0.4")
    assert enriched.coverage.scored_weight_fraction == Decimal("0.8")
    assert baseline.data_quality.insufficient_score_coverage
    assert not enriched.data_quality.insufficient_score_coverage
    assert item(baseline, ComponentName.CVD).availability is Availability.MISSING


@pytest.mark.parametrize("family", ["nested", "sfp"])
@pytest.mark.parametrize(
    "role",
    [
        EvidenceRole.CVD_5M,
        EvidenceRole.ORDER_FLOW_5M,
        EvidenceRole.OPEN_INTEREST,
        EvidenceRole.FUNDING,
        EvidenceRole.ORDER_BOOK,
        EvidenceRole.CONTEXT_OHLCV,
    ],
)
def test_missing_required_data_blocks_analysis(family, role):
    result = assess_confluence(**world(family=family, required=(role,)))
    assert result.state is AnalysisState.REQUIRED_DATA_UNAVAILABLE
    assert result.quality_score is None
    assert f"required_role:{role.value}" in result.coverage.required.missing_keys


def test_hard_failure_cannot_be_compensated_by_optional_evidence():
    data = world(flow=True)
    rules = data["setup"].rule_results
    data["setup"] = with_content_hash(
        data["setup"].model_copy(
            update={"rule_results": (rules[0].model_copy(update={"passed": False}), *rules[1:])}
        )
    )
    result = assess_confluence(**data)
    assert result.coverage.scored_weight_fraction == Decimal("0.8")
    assert result.state is AnalysisState.HARD_REQUIREMENTS_FAILED
    assert result.quality_score is None
    assert all(c.weight == 0 for c in result.hard_requirements)


@pytest.mark.parametrize(
    "change", ["missing", "hash", "wrong_instrument", "future", "gap", "forming"]
)
def test_unusable_candles_block_required_analysis(change):
    data = world()
    bars = data["evidence"].bars_15m
    if change == "missing":
        bars = ()
    elif change == "gap":
        bars = (*bars[:-2], bars[-1])
    elif change == "hash":
        bars = (*bars[:-1], bars[-1].model_copy(update={"close": Decimal(131)}))
    elif change == "future":
        bars = (
            *bars[:-1],
            with_content_hash(
                bars[-1].model_copy(update={"source_time": NOW + timedelta(seconds=1)})
            ),
        )
    elif change == "forming":
        from app.market_contracts.enums import Finality

        bars = (
            *bars[:-1],
            with_content_hash(bars[-1].model_copy(update={"finality": Finality.FORMING})),
        )
    else:
        from app.market_contracts.identity import binance_usdm_perpetual

        bars = (
            *bars[:-1],
            with_content_hash(
                bars[-1].model_copy(update={"instrument": binance_usdm_perpetual("ETHUSDT")})
            ),
        )
    data["evidence"] = data["evidence"].model_copy(update={"bars_15m": bars})
    result = assess_confluence(**data)
    assert result.state is AnalysisState.REQUIRED_DATA_UNAVAILABLE
    assert result.quality_score is None


def test_stale_or_future_assessment_blocks_analysis():
    data = world()
    data["assessed_at"] = data["setup"].valid_until
    assert assess_confluence(**data).state is AnalysisState.REQUIRED_DATA_UNAVAILABLE
    data["assessed_at"] = data["setup"].assessed_at - timedelta(seconds=1)
    assert assess_confluence(**data).state is AnalysisState.REQUIRED_DATA_UNAVAILABLE


def test_score_is_quality_only_and_context_has_no_weight():
    data = world(flow=True)
    data["evidence"] = data["evidence"].model_copy(
        update={
            "market_intelligence": (
                derivative(data["command"].evidence_identity),
                derivative(data["command"].evidence_identity, DerivativeMetric.FUNDING, "-0.003"),
            )
        }
    )
    result = assess_confluence(**data)
    assert result.score_semantics == "quality_points_not_win_probability"
    assert result.analysis_only
    assert item(result, ComponentName.OI).value == 100
    assert item(result, ComponentName.FUNDING).value == Decimal("-0.003")
    for c in result.context_components:
        assert c.weight == 0 and c.normalized_contribution is None
    for c in result.quality_components:
        assert (c.reason and c.source) or c.availability is not Availability.AVAILABLE


@pytest.mark.parametrize(
    "field", ["organization_id", "strategy_version_id", "evidence_window_hash", "content_hash"]
)
def test_mismatched_or_corrupt_setup_rejected(field):
    data = world()
    value = "f" * 64 if field.endswith("hash") else UUID(int=999)
    data["setup"] = data["setup"].model_copy(update={field: value})
    with pytest.raises(ValueError, match="lineage"):
        assess_confluence(**data)


def test_version_registry_is_frozen_and_unknown_versions_fail():
    policy = get_policy()
    with pytest.raises(ValidationError):
        policy.quality_reference_points = Decimal(50)
    with pytest.raises(ValueError, match="Unknown"):
        assess_confluence(**world(), policy_version="unregistered/v99")
    assert policy.content_hash == get_policy().content_hash


def risk_records(data, *, locked=True):
    setup = data["setup"]
    eligibility = build_action_eligibility(
        eligibility_id=UUID(int=80),
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        candidate_id=UUID(int=81),
        candidate_revision=1,
        assessment_id=setup.assessment_id,
        risk_snapshot_id=UUID(int=82),
        venue_state_id=UUID(int=83),
        state=ActionEligibilityState.BLOCKED if locked else ActionEligibilityState.ELIGIBLE,
        reason_codes=(
            EligibilityReasonCode.BLOCKED_DAILY_LOSS if locked else EligibilityReasonCode.ELIGIBLE,
        ),
        checked_at=NOW,
        valid_until=NOW + timedelta(seconds=60),
        correlation_id=UUID(int=84),
    )
    daily = DailyRiskState(
        organization_id=ORG_ID, user_id=USER_ID, day=NOW.date(), locked=locked, updated_at=NOW
    )
    portfolio = PortfolioState(
        organization_id=ORG_ID,
        account_id=ACCOUNT_ID,
        account_equity=Decimal(10000),
        open_exposure_notional=Decimal(1000),
    )
    return {
        "eligibility": eligibility,
        "daily_risk": daily,
        "portfolio": portfolio,
        "portfolio_observed_at": NOW,
    }


def test_risk_context_is_separate_and_never_recomputed():
    data = world(flow=True)
    baseline = assess_confluence(**data)
    context = risk_records(data)
    result = assess_confluence(**data, **context)
    assert result.quality_score == baseline.quality_score
    assert result.state is baseline.state
    assert result.risk_eligibility.canonical_record == context["eligibility"]
    assert result.risk_eligibility.canonical_record.state is ActionEligibilityState.BLOCKED
    assert item(result, ComponentName.DAILY_RISK).value is True
    assert item(result, ComponentName.EXPOSURE).value == 1000


@pytest.mark.parametrize(
    "kind,field",
    [("portfolio", "account_id"), ("daily_risk", "user_id"), ("eligibility", "organization_id")],
)
def test_cross_scope_context_rejected(kind, field):
    data = world()
    context = risk_records(data)
    context[kind] = context[kind].model_copy(update={field: UUID(int=555)})
    with pytest.raises(ValueError, match="Cross-"):
        assess_confluence(**data, **context)


def test_untimestamped_and_stale_account_context_never_gets_fresh_clock():
    data = world()
    context = risk_records(data)
    context["portfolio_observed_at"] = None
    context["daily_risk"] = context["daily_risk"].model_copy(
        update={"updated_at": NOW - timedelta(minutes=2)}
    )
    result = assess_confluence(**data, **context)
    assert item(result, ComponentName.EXPOSURE).availability is Availability.INCOMPLETE
    assert item(result, ComponentName.EXPOSURE).timestamp is None
    assert item(result, ComponentName.DAILY_RISK).availability is Availability.STALE


def analytics(*, version=STRATEGY_VERSION_ID, pnl=Decimal(12), count=3, truncated=True):
    return StrategyAnalyticsReport(
        organization_id=ORG_ID,
        user_id=USER_ID,
        filters=StrategyAnalyticsFilters(strategy_version_id=version),
        group_by=(),
        overall=StrategyAnalyticsMetrics(expectancy=pnl, pnl_sample_count=count),
        buckets=[],
        total_buckets=0,
        limit=50,
        offset=0,
        scanned_trade_count=count,
        truncated=truncated,
        max_rows=1000,
        min_sample_size=20,
        generated_at=NOW,
    )


def test_measured_expectancy_keeps_sample_and_truncation_outside_score():
    data = world()
    baseline = assess_confluence(**data)
    result = assess_confluence(**data, analytics=analytics())
    history = result.historical_expectancy
    assert history.component.value == 12
    assert history.sample_count == 3 and history.insufficient_history and history.truncated
    assert history.component.weight == 0
    assert result.quality_score == baseline.quality_score
    with pytest.raises(ValueError, match="cohort"):
        assess_confluence(**data, analytics=analytics(version=UUID(int=500)))


def test_btc_context_requires_measured_closed_evidence():
    data = world()
    bars = data["evidence"].bars_15m[-2:]
    series = with_content_hash(
        ClosedOhlcvSeries(
            identity=data["command"].evidence_identity,
            timeframe=Timeframe.M15,
            bars=list(bars),
            evaluated_at=NOW,
            content_hash="0" * 64,
        )
    )
    baseline = assess_confluence(**data)
    result = assess_confluence(**data, btc_context=series)
    assert item(baseline, ComponentName.BTC).availability is Availability.MISSING
    assert item(result, ComponentName.BTC).availability is Availability.AVAILABLE
    assert result.quality_score == baseline.quality_score


def research_case(result, *, pnl="10", identifier=100, **changes):
    trade = JournalTradeRead(
        id=UUID(int=identifier),
        organization_id=ORG_ID,
        user_id=USER_ID,
        source=JournalTradeSource.PAPER_VALIDATION,
        status=JournalTradeStatus.CLOSED,
        symbol="BTCUSDT",
        timeframe="15m",
        market_regime=MarketRegime.UNKNOWN,
        user_strategy_id=STRATEGY_ID,
        strategy_version_id=STRATEGY_VERSION_ID,
        direction=result.direction,
        net_pnl=Decimal(pnl),
        entry_time=NOW + timedelta(seconds=1),
        exit_time=NOW + timedelta(minutes=1),
        created_at=NOW,
        updated_at=NOW + timedelta(minutes=1),
    ).model_copy(update=changes)
    return ResearchCase(assessment=result, outcome=trade)


def test_filter_comparisons_keep_baseline_and_missing_sample_counts():
    with_flow = assess_confluence(**world(flow=True))
    without_flow = assess_confluence(**world())
    cases = [
        research_case(with_flow, pnl="20", identifier=100),
        research_case(without_flow, pnl="-10", identifier=101),
    ]
    for compare in (compare_with_cvd_filter, compare_with_order_flow_filter):
        result = compare(cases)
        assert result.baseline.trade_count == 2 and result.baseline.expectancy == 5
        assert result.with_filter.trade_count == 1 and result.with_filter.expectancy == 20
        assert result.missing_filter_count == 1 and result.filter_measured_count == 1
        assert result.expectancy_difference == 15
        assert not result.causal_claim and result.descriptive_only
        assert result.with_filter.insufficient_history
        assert result == compare(cases)


def test_oi_comparison_uses_explicit_versioned_raw_units_not_quality():
    data = world()
    data["evidence"] = data["evidence"].model_copy(
        update={"market_intelligence": (derivative(data["command"].evidence_identity),)}
    )
    cases = [research_case(assess_confluence(**data))]
    comparison = compare_with_oi_filter(
        cases,
        minimum_open_interest=Decimal(90),
        units="BTC",
        filter_version="oi-research-threshold-90/v1",
    )
    assert comparison.with_filter.trade_count == 1
    with pytest.raises(ValueError, match="units"):
        compare_with_oi_filter(
            cases, minimum_open_interest=Decimal(90), units="USDT", filter_version="test/v1"
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"status": JournalTradeStatus.OPEN},
        {"net_pnl": None},
        {"exit_time": None},
        {"entry_time": NOW - timedelta(seconds=1)},
    ],
)
def test_comparisons_exclude_unmeasured_or_noncausal_outcomes(changes):
    result = compare_with_order_flow_filter(
        [research_case(assess_confluence(**world(flow=True)), **changes)]
    )
    assert result.baseline.trade_count == 0
    assert result.baseline.expectancy is None and result.expectancy_difference is None
    assert result.excluded_outcome_count == 1


def test_comparison_rejects_duplicates_mixed_versions_and_bad_lineage():
    result = assess_confluence(**world(flow=True))
    case = research_case(result)
    with pytest.raises(ValueError, match="Duplicate"):
        compare_with_cvd_filter([case, case])
    mixed = rehash(result.model_copy(update={"policy_content_hash": "f" * 64}))
    with pytest.raises(ValueError, match="cohort"):
        compare_with_cvd_filter([case, research_case(mixed, identifier=101)])
    with pytest.raises(ValueError, match="cohort"):
        compare_with_cvd_filter([research_case(result, strategy_version_id=UUID(int=700))])
    assert compare_with_cvd_filter([]).baseline.expectancy is None


def test_no_io_or_detector_call_during_assessment(monkeypatch):
    data = world()

    def forbidden(*args, **kwargs):
        pytest.fail("Analysis reached an IO, detector or trading authority")

    import httpx

    from app.signal_fusion.action_eligibility import ActionEligibilityService
    from app.strategy_brain import detector

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(detector, "detect_nested", forbidden)
    monkeypatch.setattr(ActionEligibilityService, "evaluate", forbidden)
    result = assess_confluence(**data)
    assert result.analysis_only


def test_eighty_is_explainable_quality_points_only():
    data = world(flow=True)
    htf, _ = sfp_evidence(
        [(100, 101, 99, 100), (100, 101, 99, 100)],
        start=END.replace(minute=0) - timedelta(hours=8),
        timeframe=Timeframe.H4,
    )
    data["evidence"] = data["evidence"].model_copy(update={"bars_4h": htf})
    result = assess_confluence(**data)
    assert result.quality_score == Decimal("80.00")
    assert result.coverage.scored_weight_fraction == 1
    assert result.score_semantics == "quality_points_not_win_probability"
    assert result.quality_band == "at_or_above_reference"
    assert item(result, ComponentName.HTF).normalized_contribution == Decimal("0.5")
    assert result.historical_expectancy.component.value is None
    assert result.risk_eligibility.canonical_record is None


def test_arithmetic_is_independent_of_callers_decimal_context():
    from decimal import localcontext

    data = world(flow=True)
    expected = assess_confluence(**data)
    with localcontext() as ctx:
        ctx.prec = 6
        actual = assess_confluence(**data)
        assert ctx.prec == 6
    assert actual == expected
    cases = [research_case(expected, pnl="123.456789")]
    comparison = compare_with_cvd_filter(cases)
    with localcontext() as ctx:
        ctx.prec = 5
        assert compare_with_cvd_filter(cases) == comparison


def test_optional_stale_flow_reduces_coverage_without_changing_setup():
    data = world(flow=True)
    data["assessed_at"] = NOW + timedelta(seconds=601)
    result = assess_confluence(**data)
    assert result.state is AnalysisState.READY
    assert result.setup == data["setup"]
    assert item(result, ComponentName.ORDER_FLOW).availability is Availability.STALE
    assert item(result, ComponentName.CVD).normalized_contribution is None
    assert result.coverage.scored_weight_fraction == Decimal("0.4")


@pytest.mark.parametrize("role", [EvidenceRole.CVD_5M, EvidenceRole.ORDER_FLOW_5M])
def test_available_required_flow_uses_existing_sfp_gate(role):
    result = assess_confluence(**world(family="sfp", required=(role,), flow=True))
    assert result.state is AnalysisState.READY
    requirement = next(
        c for c in result.hard_requirements if c.key == f"required_role:{role.value}"
    )
    assert requirement.passed and requirement.weight == 0


@pytest.mark.parametrize("metric", [DerivativeMetric.OPEN_INTEREST, DerivativeMetric.FUNDING])
def test_required_derivative_requires_selected_payload_and_rechecks_age(metric):
    role = EvidenceRole(metric.value)
    data = world(family="sfp", required=(role,))
    observation = derivative(data["command"].evidence_identity, metric)
    data["evidence"] = data["evidence"].model_copy(update={"market_intelligence": (observation,)})
    assert assess_confluence(**data).state is AnalysisState.READY
    changed = derivative(data["command"].evidence_identity, metric, "101")
    data["evidence"] = data["evidence"].model_copy(update={"market_intelligence": (changed,)})
    assert assess_confluence(**data).state is AnalysisState.REQUIRED_DATA_UNAVAILABLE


def test_oi_consumer_age_is_rechecked_and_duplicates_are_incomplete():
    data = world()
    observation = derivative(data["command"].evidence_identity)
    data["evidence"] = data["evidence"].model_copy(update={"market_intelligence": (observation,)})
    data["assessed_at"] = NOW + timedelta(seconds=61)
    assert item(assess_confluence(**data), ComponentName.OI).availability is Availability.STALE
    data["evidence"] = data["evidence"].model_copy(
        update={"market_intelligence": (observation, observation)}
    )
    assert item(assess_confluence(**data), ComponentName.OI).availability is Availability.INCOMPLETE


def test_expired_canonical_eligibility_is_context_not_quality_gate():
    data = world()
    context = risk_records(data)
    data["assessed_at"] = NOW + timedelta(seconds=61)
    result = assess_confluence(**data, **context)
    assert result.risk_eligibility.availability is Availability.STALE
    assert result.state is AnalysisState.READY
    assert result.quality_score == assess_confluence(**data).quality_score


def test_optional_flow_hash_corruption_never_contributes():
    data = world(flow=True)
    flow = data["evidence"].order_flow.model_copy(update={"content_hash": "f" * 64})
    data["evidence"] = data["evidence"].model_copy(update={"order_flow": flow})
    result = assess_confluence(**data)
    assert result.state is AnalysisState.READY
    assert item(result, ComponentName.CVD).availability is Availability.INCOMPLETE
    assert item(result, ComponentName.CVD).normalized_contribution is None


def test_naive_clock_and_nonfinite_comparison_threshold_rejected():
    data = world()
    data["assessed_at"] = NOW.replace(tzinfo=None)
    with pytest.raises(ValueError, match="aware"):
        assess_confluence(**data)
    with pytest.raises(ValueError, match="Finite"):
        compare_with_oi_filter(
            [], minimum_open_interest=Decimal("Infinity"), units="BTC", filter_version="test/v1"
        )
