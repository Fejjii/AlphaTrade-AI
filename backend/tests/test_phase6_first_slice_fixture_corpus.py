"""Self-validation for the Phase 6 first-slice golden fixture corpus.

Evidence identity is the canonical ``CanonicalEvidenceWindowV1``; states and
reason codes are the frozen ``app.signal_fusion`` enumerations. No production
evaluator or candidate code is exercised or implemented here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from uuid import UUID, uuid5

import pytest
from pydantic import ValidationError

from app.analysis.wilder_atr_v1 import (
    FinalOhlcvBar,
    OhlcvFinality,
    WilderAtrFeatureV1,
    WilderAtrStatus,
    compute_wilder_atr_v1,
)
from app.market_contracts.coverage import build_complete_trade_window_coverage
from app.market_contracts.cursor import (
    TradeStreamAssembler,
    require_contiguous_sequences,
)
from app.market_contracts.cvd import (
    cvd_at_close,
    first_slice_baseline_open,
    first_slice_cvd_window,
    require_contiguous_connection,
)
from app.market_contracts.enums import (
    Finality,
    FreshnessState,
    MarketType,
    PrivacyClass,
    ProductFamily,
    VenueId,
)
from app.market_contracts.errors import (
    FormingCandleError,
    GapDetectedError,
    IncompleteWarmUpError,
    StaleEvidenceError,
    WrongInstrumentError,
    WrongMarketError,
)
from app.market_contracts.first_slice import FIRST_SLICE_PATTERN_NAME, first_slice_identity
from app.market_contracts.flow import (
    bar_signed_quote_flow,
    trigger_bar_aggressive_sell_imbalance,
)
from app.market_contracts.freshness import evaluate_freshness, first_slice_freshness_policy
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import (
    ProviderProvenance,
    binance_usdm_btcusdt,
    require_instrument,
    require_perpetual,
)
from app.market_contracts.ohlcv import OhlcvBar, observation_id_for, require_closed_series
from app.market_contracts.trades import OrderedTradeBatch
from app.schemas.common import SetupCompileStatus, Timeframe, TradeDirection
from app.schemas.strategy_pattern_spec import FIRST_SLICE_NAME, canonical_first_slice_authored_spec
from app.services.canonical_serialization import canonical_sha256
from app.services.manual_level_service import manual_level_revision_content_hash
from app.services.setup_ast_compiler import compile_from_spec
from app.signal_fusion.assessment import (
    ALLOWED_ASSESSMENT_TRANSITIONS,
    build_setup_assessment_transition,
)
from app.signal_fusion.candidate import CandidateUniquenessTuple, build_confirmed_candidate
from app.signal_fusion.enums import (
    AssessmentReasonCode,
    CandidateState,
    EvidenceRole,
    SetupAssessmentState,
    TenantAssertionRole,
)
from app.signal_fusion.errors import (
    EvidenceIdentityMismatchError,
    EvidenceWindowContractError,
    FormingObservationNotExecutableError,
    TenantAssertionNotPublicError,
    TenantAssertionSelectionError,
)
from app.signal_fusion.evidence_window import (
    EVIDENCE_WINDOW_EXCLUDED_INPUTS,
    EVIDENCE_WINDOW_SCHEMA_VERSION,
    CanonicalEvidenceWindowV1,
    evidence_window_preimage,
    hash_canonical_evidence_window,
)
from app.signal_fusion.observation import (
    assert_public_observation_boundary,
    refuse_tenant_assertion_as_public_observation,
    require_distinct_observation_for_finality_change,
)
from app.signal_fusion.policy import DEFAULT_FUSION_POLICY_VERSION
from app.signal_fusion.types import (
    SelectedPublicObservation,
    SelectedTenantAssertion,
    require_observation_matches_evidence,
)
from tests.fixtures.phase6_first_slice.factory import (
    BASE_CONNECTION_ID,
    COMPILED_SETUP_DEFINITION_ID,
    MANDATORY_EVIDENCE_ROLES,
    ORGANIZATION_ID,
    RECONNECT_CONNECTION_ID,
    STRATEGY_VERSION_ID,
    SWING_INDEX,
    SWING_PRICE,
    EvidenceIdentityBehavior,
    Phase6Fixture,
    build_fixture_corpus,
    canonical_evidence_window,
    corpus_bytes,
    executable_setup_ref,
    manifest_rows,
    public_observations,
    trigger_observation,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "phase6_first_slice"
ATR_REVISION_NAMESPACE = UUID("df85c21d-99dc-43cb-8fe9-7a5c48ec0b1f")
EXPECTED_CORPUS_SHA256 = "651d4d62f94040f93a5cf794210c49361685138fb2e5e18128f40b0259ba2e42"
EXPECTED_CONFIRMED_WINDOW_HASH = "abbd30146b1db555ea33dfbae0218241b8dcf12c6fcee5a1789015522327a674"
FIXTURE_COUNT = 25
CANDIDATE_FIXTURE_IDS = frozenset(
    {
        "confirmed-setup",
        "invalidated-by-price",
        "expiry",
        "corrected-candle-revision",
        "presentation-enrichment",
        "mandatory-evidence-change",
        "adjacent-trigger-window",
    }
)
CANONICAL_IDENTITY_15M = first_slice_identity(timeframe=Timeframe.M15, replay=True)


@pytest.fixture(scope="module")
def corpus() -> dict[str, Phase6Fixture]:
    fixtures = build_fixture_corpus()
    return {fixture.fixture_id: fixture for fixture in fixtures}


@pytest.fixture(scope="module")
def windows(corpus: dict[str, Phase6Fixture]) -> dict[str, CanonicalEvidenceWindowV1]:
    """Canonical windows for every fixture that is structurally buildable in isolation."""
    return {
        fixture_id: canonical_evidence_window(fixture)
        for fixture_id, fixture in corpus.items()
        if fixture_id not in UNBUILDABLE_WINDOW_FIXTURES
    }


# FORMING triggers cannot occupy an executable role; spot/delivery have no Phase 5
# perpetual TradeEvent stream, so the mandatory CVD_WINDOW role cannot be filled.
UNBUILDABLE_WINDOW_FIXTURES = frozenset({"forming-candle", "wrong-market", "spot-substitution"})


def _atr_bar(bar: OhlcvBar) -> FinalOhlcvBar:
    return FinalOhlcvBar(
        revision_id=uuid5(
            ATR_REVISION_NAMESPACE,
            f"{bar.source_event_id}:{bar.revision}:{bar.content_hash}",
        ),
        content_hash=bar.content_hash,
        venue=bar.instrument.venue.value,
        market=bar.instrument.market_type.value,
        instrument=bar.instrument.provider_symbol,
        timeframe=bar.timeframe.value,
        open_time=bar.interval_start,
        close_time=bar.interval_end,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.base_volume,
        finality=(OhlcvFinality.FINAL if bar.finality is Finality.FINAL else OhlcvFinality.FORMING),
    )


def _atr(bars: tuple[OhlcvBar, ...]) -> WilderAtrFeatureV1:
    return compute_wilder_atr_v1([_atr_bar(bar) for bar in bars])


def _snapshot(fixture: Phase6Fixture) -> object:
    trigger = fixture.bars_15m[-1]
    window_start = first_slice_baseline_open(trigger)
    coverage = build_complete_trade_window_coverage(
        identity=fixture.identity_15m,
        lineage_id=BASE_CONNECTION_ID,
        requested_start=window_start,
        requested_end=trigger.interval_end,
        trades=list(fixture.trades),
    )
    batch = with_content_hash(
        OrderedTradeBatch(
            identity=fixture.identity_15m,
            trades=list(fixture.trades),
            source_connection_id=BASE_CONNECTION_ID,
            coverage=coverage,
            content_hash="0" * 64,
        )
    )
    assembler = TradeStreamAssembler(
        fixture.identity_15m,
        connected_at=fixture.evaluated_at,
        connection_identity=BASE_CONNECTION_ID,
        expected_contiguous_count=len(fixture.trades),
    )
    return assembler.ingest_batch(batch, observed_at=fixture.evaluated_at)


def _closed_15m(fixture: Phase6Fixture) -> object:
    return require_closed_series(
        list(fixture.bars_15m),
        identity=fixture.identity_15m,
        timeframe=Timeframe.M15,
        evaluated_at=fixture.evaluated_at,
        min_bars=100,
    )


def _assert_ordered_contiguous_bars(bars: tuple[OhlcvBar, ...]) -> None:
    assert list(bars) == sorted(bars, key=lambda bar: bar.interval_start)
    for previous, current in pairwise(bars):
        assert current.interval_start == previous.interval_end


def _active_resistance(fixture: Phase6Fixture) -> Decimal | None:
    if fixture.active_manual_revision_id is None:
        return None
    revisions = {
        revision.id: revision
        for revision in fixture.manual_level_revisions
        if revision.valid and revision.level_type == "resistance"
    }
    return revisions[fixture.active_manual_revision_id].value


def _confirmed_measurements(
    fixture: Phase6Fixture,
) -> tuple[WilderAtrFeatureV1, WilderAtrFeatureV1, Decimal, Decimal]:
    atr_15m = _atr(fixture.bars_15m)
    atr_4h = _atr(fixture.bars_4h)
    series = _closed_15m(fixture)
    snapshot = _snapshot(fixture)
    cvd = first_slice_cvd_window(
        identity=fixture.identity_15m,
        series_15m=series,
        snapshot=snapshot,
        created_at=fixture.evaluated_at,
    )
    swing = fixture.swing
    assert swing is not None
    cvd_at_swing = cvd_at_close(
        list(fixture.trades),
        window_start=cvd.window_start,
        bar_end=fixture.bars_15m[swing.bar_index].interval_end,
        baseline=cvd.baseline,
    )
    return atr_15m, atr_4h, cvd_at_swing, cvd.signed_quote_delta


def test_manifest_is_explicit_complete_and_matches_factories(
    corpus: dict[str, Phase6Fixture],
) -> None:
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "phase6-first-slice-fixture-manifest/v2"
    assert manifest["strategy_name"] == FIRST_SLICE_PATTERN_NAME
    assert manifest["evidence_identity"] == EVIDENCE_WINDOW_SCHEMA_VERSION
    assert manifest["fixtures"] == manifest_rows()
    assert len(corpus) == FIXTURE_COUNT
    assert len(corpus) == len(set(corpus))
    for fixture in corpus.values():
        assert fixture.fixture_id
        assert fixture.purpose
        assert fixture.expected.fixture_detail_code
        assert fixture.expected.freshness_posture
        assert fixture.expected.finality_posture
        assert all(isinstance(code, AssessmentReasonCode) for code in fixture.expected.reason_codes)


def test_canonical_strategy_name_is_used_everywhere(corpus: dict[str, Phase6Fixture]) -> None:
    assert FIRST_SLICE_PATTERN_NAME == FIRST_SLICE_NAME
    assert "exhaustion" not in FIRST_SLICE_PATTERN_NAME.lower()
    for fixture in corpus.values():
        assert fixture.strategy_name == FIRST_SLICE_PATTERN_NAME
        assert fixture.direction is TradeDirection.SHORT
    for path in sorted(FIXTURE_DIR.iterdir()):
        if path.suffix in {".py", ".json"}:
            assert "exhaustion" not in path.read_text(encoding="utf-8").lower(), path.name


def test_current_strategy_and_compiler_contracts_define_exact_thresholds() -> None:
    spec = canonical_first_slice_authored_spec()
    compiled = compile_from_spec(spec)
    assert compiled.status == SetupCompileStatus.EXECUTABLE.value
    assert compiled.document is not None
    assert spec.symbol == "BTCUSDT"
    assert spec.trigger_timeframe == "15m"
    assert spec.context_timeframe == "4h"
    assert spec.resistance_distance_atr_threshold == Decimal("0.50")
    assert spec.sweep_threshold_atr == Decimal("0.25")
    assert spec.volume_lookback_bars == 20
    assert spec.volume_ratio_threshold == Decimal("1.50")
    assert spec.aggressive_sell_imbalance_threshold == Decimal("-0.10")
    assert spec.invalidation.atr_multiple == Decimal("0.10")
    assert spec.invalidation.tick_multiple == Decimal("2")
    assert spec.expiry_final_bars == 2


def test_all_candle_timestamps_are_ordered_and_contiguous(
    corpus: dict[str, Phase6Fixture],
) -> None:
    for fixture in corpus.values():
        _assert_ordered_contiguous_bars(fixture.bars_15m)
        _assert_ordered_contiguous_bars(fixture.bars_4h)
        _assert_ordered_contiguous_bars(fixture.post_trigger_bars)


def test_finality_and_warmup_postures_are_material(
    corpus: dict[str, Phase6Fixture],
) -> None:
    forming = corpus["forming-candle"]
    incomplete = corpus["incomplete-warmup"]
    for fixture_id, fixture in corpus.items():
        assert len(fixture.bars_4h) == 30
        assert all(bar.finality is Finality.FINAL for bar in fixture.bars_4h)
        if fixture_id == "forming-candle":
            assert len(fixture.bars_15m) == 100
            assert fixture.bars_15m[-1].finality is Finality.FORMING
            assert all(bar.finality is Finality.FINAL for bar in fixture.bars_15m[:-1])
        elif fixture_id == "incomplete-warmup":
            assert len(fixture.bars_15m) == 99
            assert all(bar.finality is Finality.FINAL for bar in fixture.bars_15m)
        else:
            assert len(fixture.bars_15m) == 100
            assert all(bar.finality is Finality.FINAL for bar in fixture.bars_15m)
    with pytest.raises(FormingCandleError):
        _closed_15m(forming)
    with pytest.raises(FormingCandleError, match="at least 100"):
        _closed_15m(incomplete)


def test_confirmed_fixture_exact_atr_goldens(corpus: dict[str, Phase6Fixture]) -> None:
    confirmed = corpus["confirmed-setup"]
    atr_15m = _atr(confirmed.bars_15m)
    atr_4h = _atr(confirmed.bars_4h)
    assert atr_15m.status is WilderAtrStatus.VALUE
    assert atr_4h.status is WilderAtrStatus.VALUE
    assert atr_15m.value == Decimal("102.1428571428571429")
    assert atr_4h.value == Decimal("400.0000000000000000")


def test_confirmed_fixture_strict_swing_context_and_trigger(
    corpus: dict[str, Phase6Fixture],
) -> None:
    fixture = corpus["confirmed-setup"]
    spec = canonical_first_slice_authored_spec()
    swing = fixture.swing
    assert swing is not None
    assert swing.strict and swing.left_bars == 2 and swing.right_bars == 2
    highs = [bar.high for bar in fixture.bars_15m]
    assert swing.price == highs[swing.bar_index] == SWING_PRICE
    assert swing.price > max(highs[swing.bar_index - 2 : swing.bar_index])
    assert swing.price > max(highs[swing.bar_index + 1 : swing.bar_index + 3])

    atr_15m, atr_4h, _cvd_swing, _cvd_trigger = _confirmed_measurements(fixture)
    assert atr_15m.value is not None
    assert atr_4h.value is not None
    resistance = _active_resistance(fixture)
    assert resistance == Decimal("100250")
    assert abs(swing.price - resistance) <= spec.resistance_distance_atr_threshold * atr_4h.value

    trigger = fixture.bars_15m[-1]
    assert trigger.high >= swing.price + spec.sweep_threshold_atr * atr_15m.value
    assert trigger.close < swing.price
    assert trigger.close < trigger.open
    prior_mean = sum(
        (bar.base_volume for bar in fixture.bars_15m[-21:-1]),
        start=Decimal("0"),
    ) / Decimal(spec.volume_lookback_bars)
    assert prior_mean == Decimal("10")
    assert trigger.base_volume / prior_mean == spec.volume_ratio_threshold


def test_confirmed_fixture_exact_cvd_and_flow_goldens(
    corpus: dict[str, Phase6Fixture],
) -> None:
    fixture = corpus["confirmed-setup"]
    spec = canonical_first_slice_authored_spec()
    series = _closed_15m(fixture)
    snapshot = _snapshot(fixture)
    cvd = first_slice_cvd_window(
        identity=fixture.identity_15m,
        series_15m=series,
        snapshot=snapshot,
        created_at=fixture.evaluated_at,
    )
    swing = fixture.swing
    assert swing is not None
    cvd_swing = cvd_at_close(
        list(fixture.trades),
        window_start=cvd.window_start,
        bar_end=fixture.bars_15m[swing.bar_index].interval_end,
        baseline=cvd.baseline,
    )
    assert cvd.window_start == fixture.bars_15m[-1].interval_start - timedelta(minutes=32 * 15)
    assert cvd_swing == Decimal("3000.000")
    assert cvd.signed_quote_delta == Decimal("2800.000")
    assert cvd.total_quote_volume == Decimal("4200.000")
    assert cvd.signed_quote_delta < cvd_swing

    flow = bar_signed_quote_flow(
        identity=fixture.identity_15m,
        bar=fixture.bars_15m[-1],
        snapshot=snapshot,
        evaluated_at=fixture.evaluated_at,
    )
    assert flow.signed_quote_delta == Decimal("-400.000")
    assert flow.total_quote_volume == Decimal("1000.000")
    assert flow.buy_quote_volume == Decimal("300.000")
    assert flow.sell_quote_volume == Decimal("700.000")
    assert flow.signed_flow_ratio == Decimal("-0.4")
    assert trigger_bar_aggressive_sell_imbalance(
        flow,
        threshold=spec.aggressive_sell_imbalance_threshold,
    )


def test_trade_sequence_and_freshness_boundaries_are_exact(
    corpus: dict[str, Phase6Fixture],
) -> None:
    confirmed = corpus["confirmed-setup"]
    sequences = [trade.sequence for trade in confirmed.trades]
    require_contiguous_sequences(sequences)
    freshness = evaluate_freshness(
        source_time=confirmed.trades[-1].event_timestamp,
        evaluated_at=confirmed.evaluated_at,
        policy=first_slice_freshness_policy(),
        require_fresh=True,
    )
    assert freshness.age_seconds == Decimal("10")
    assert freshness.state is FreshnessState.AGING
    assert freshness.valid_until == confirmed.evaluated_at

    stale = corpus["stale-source"]
    stale_check = evaluate_freshness(
        source_time=stale.trades[-1].event_timestamp,
        evaluated_at=stale.evaluated_at,
        policy=first_slice_freshness_policy(),
        require_fresh=False,
    )
    assert stale_check.age_seconds == Decimal("11")
    assert stale_check.state is FreshnessState.STALE
    with pytest.raises(StaleEvidenceError):
        evaluate_freshness(
            source_time=stale.trades[-1].event_timestamp,
            evaluated_at=stale.evaluated_at,
            policy=first_slice_freshness_policy(),
            require_fresh=True,
        )


def test_gap_and_reconnect_fixtures_are_material(
    corpus: dict[str, Phase6Fixture],
) -> None:
    gap = corpus["sequence-gap"]
    gap_sequences = [trade.sequence for trade in gap.trades]
    missing = set(range(gap_sequences[0], gap_sequences[-1] + 1)) - set(gap_sequences)
    assert missing == {FIRST_MISSING_SEQUENCE}
    with pytest.raises(GapDetectedError, match="sequence gap"):
        require_contiguous_sequences(gap_sequences)

    reconnect = corpus["reconnect-discontinuity"]
    require_contiguous_sequences([trade.sequence for trade in reconnect.trades])
    assert {trade.source_connection_id for trade in reconnect.trades} == {
        BASE_CONNECTION_ID,
        RECONNECT_CONNECTION_ID,
    }
    with pytest.raises(IncompleteWarmUpError, match="Cross-connection"):
        require_contiguous_connection(list(reconnect.trades), BASE_CONNECTION_ID)


FIRST_MISSING_SEQUENCE = 9_000_010


def test_wrong_identity_market_and_fallback_fixtures_are_true(
    corpus: dict[str, Phase6Fixture],
) -> None:
    wrong_venue = corpus["wrong-venue"]
    assert wrong_venue.identity_15m.venue is VenueId.BLOFIN
    assert wrong_venue.identity_15m.instrument.venue is VenueId.BLOFIN
    assert wrong_venue.identity_15m.market_type is MarketType.PERPETUAL
    with pytest.raises(WrongInstrumentError):
        require_instrument(wrong_venue.identity_15m, binance_usdm_btcusdt())

    wrong_instrument = corpus["wrong-instrument"]
    assert wrong_instrument.identity_15m.instrument.provider_symbol == "ETHUSDT"
    with pytest.raises(WrongInstrumentError):
        require_instrument(wrong_instrument.identity_15m, binance_usdm_btcusdt())

    wrong_market = corpus["wrong-market"]
    assert wrong_market.identity_15m.market_type is MarketType.DELIVERY
    with pytest.raises(WrongMarketError):
        require_perpetual(wrong_market.identity_15m)

    spot = corpus["spot-substitution"]
    assert spot.identity_15m.market_type is MarketType.SPOT
    assert spot.identity_15m.instrument.product_family is ProductFamily.SPOT
    with pytest.raises(WrongMarketError):
        require_perpetual(spot.identity_15m)

    fallback = corpus["fallback-source"]
    assert fallback.identity_15m.provenance.fallback_used is True
    with pytest.raises(ValidationError, match="fallback"):
        ProviderProvenance.model_validate(
            fallback.identity_15m.provenance.model_dump(mode="python")
        )


def test_manual_level_revision_chain_is_content_bound_and_unchanged(
    corpus: dict[str, Phase6Fixture],
) -> None:
    fixture = corpus["confirmed-setup"]
    first, second = fixture.manual_level_revisions
    assert first.value == Decimal("100300")
    assert second.value == Decimal("100250")
    assert second.supersedes_revision_id == first.id
    for revision in fixture.manual_level_revisions:
        expected_hash = manual_level_revision_content_hash(
            level_id=revision.level_id,
            revision_id=revision.id,
            revision_number=revision.revision_number,
            organization_id=revision.organization_id,
            actor_user_id=revision.actor_user_id,
            instrument=revision.instrument,
            exchange=revision.exchange,
            venue=revision.venue,
            market_type=revision.market_type,
            price_unit=revision.price_unit,
            timeframe=revision.timeframe,
            level_type=revision.level_type,
            value=revision.value,
            price_low=revision.price_low,
            price_high=revision.price_high,
            valid=revision.valid,
            effective_at=revision.effective_at,
            created_at=revision.created_at,
            supersedes_revision_id=revision.supersedes_revision_id,
        )
        assert revision.content_hash == expected_hash
    assert fixture.manual_level_revisions == build_fixture_corpus()[0].manual_level_revisions


def test_negative_matrix_mutations_fail_the_intended_predicate(
    corpus: dict[str, Phase6Fixture],
) -> None:
    spec = canonical_first_slice_authored_spec()
    confirmed_atr_15m = _atr(corpus["confirmed-setup"].bars_15m).value
    assert confirmed_atr_15m is not None

    no_setup = corpus["no-setup"]
    index = SWING_INDEX
    highs = [bar.high for bar in no_setup.bars_15m]
    assert highs[index] <= max(highs[index - 2 : index] + highs[index + 1 : index + 3])

    watch = corpus["watch"]
    assert watch.bars_15m[-1].high < SWING_PRICE + (
        spec.sweep_threshold_atr * _atr(watch.bars_15m).value
    )

    partial = corpus["partial-match"]
    assert partial.bars_15m[-1].close >= partial.bars_15m[-1].open

    missing = corpus["missing-manual-resistance"]
    assert _active_resistance(missing) is None

    outside = corpus["resistance-outside-tolerance"]
    outside_atr = _atr(outside.bars_4h).value
    outside_resistance = _active_resistance(outside)
    assert outside_atr is not None and outside_resistance is not None
    assert abs(SWING_PRICE - outside_resistance) > (
        spec.resistance_distance_atr_threshold * outside_atr
    )

    volume = corpus["volume-threshold-failure"]
    prior_mean = sum(
        (bar.base_volume for bar in volume.bars_15m[-21:-1]),
        start=Decimal("0"),
    ) / Decimal("20")
    assert volume.bars_15m[-1].base_volume / prior_mean == Decimal("1.4")

    cvd_failure = corpus["cvd-divergence-failure"]
    _atr15, _atr4, cvd_swing, cvd_trigger = _confirmed_measurements(cvd_failure)
    assert cvd_trigger >= cvd_swing

    flow_failure = corpus["sell-imbalance-failure"]
    flow = bar_signed_quote_flow(
        identity=flow_failure.identity_15m,
        bar=flow_failure.bars_15m[-1],
        snapshot=_snapshot(flow_failure),
        evaluated_at=flow_failure.evaluated_at,
    )
    assert flow.signed_flow_ratio == Decimal("-0.05")
    assert not trigger_bar_aggressive_sell_imbalance(
        flow,
        threshold=spec.aggressive_sell_imbalance_threshold,
    )
    _atr15, _atr4, cvd_swing, cvd_trigger = _confirmed_measurements(flow_failure)
    assert cvd_trigger < cvd_swing


def test_invalidation_and_expiry_goldens(corpus: dict[str, Phase6Fixture]) -> None:
    spec = canonical_first_slice_authored_spec()
    invalidated = corpus["invalidated-by-price"]
    atr_value = _atr(invalidated.bars_15m).value
    assert atr_value is not None
    trigger = invalidated.bars_15m[-1]
    invalidation_price = trigger.high + max(
        spec.invalidation.atr_multiple * atr_value,
        spec.invalidation.tick_multiple * invalidated.tick_size,
    )
    assert invalidation_price == Decimal("100140.21428571428571429")
    assert invalidated.post_trigger_bars[0].high >= invalidation_price

    expiry = corpus["expiry"]
    assert len(expiry.post_trigger_bars) == spec.expiry_final_bars
    assert all(bar.finality is Finality.FINAL for bar in expiry.post_trigger_bars)
    assert all(bar.high < invalidation_price for bar in expiry.post_trigger_bars)


def _uniqueness(window: CanonicalEvidenceWindowV1) -> CandidateUniquenessTuple:
    return CandidateUniquenessTuple(
        organization_id=window.organization_id,
        strategy_version_id=window.strategy_version_id,
        setup_definition_id=window.compiled_setup_definition_id,
        fusion_policy_version=window.fusion_policy_version,
        direction=window.direction,
        evidence_venue=window.evidence_venue,
        evidence_market=window.evidence_market,
        evidence_instrument=window.evidence_instrument,
        timeframe=window.timeframe,
        evidence_window_hash=window.content_hash,
    )


def test_confirmed_fixture_produces_the_canonical_evidence_window_hash(
    corpus: dict[str, Phase6Fixture],
    windows: dict[str, CanonicalEvidenceWindowV1],
) -> None:
    window = windows["confirmed-setup"]
    assert window.schema_version == EVIDENCE_WINDOW_SCHEMA_VERSION == "CanonicalEvidenceWindowV1"
    assert window.content_hash == EXPECTED_CONFIRMED_WINDOW_HASH
    assert window.content_hash == hash_canonical_evidence_window(window)
    assert canonical_evidence_window(corpus["confirmed-setup"]).content_hash == window.content_hash
    assert not EVIDENCE_WINDOW_EXCLUDED_INPUTS.intersection(evidence_window_preimage(window))

    assert window.organization_id == ORGANIZATION_ID
    assert window.strategy_version_id == STRATEGY_VERSION_ID
    assert window.compiled_setup_definition_id == COMPILED_SETUP_DEFINITION_ID
    assert window.compiled_setup_content_hash == executable_setup_ref().content_hash
    assert window.fusion_policy_version == DEFAULT_FUSION_POLICY_VERSION
    assert window.direction is TradeDirection.SHORT
    assert window.evidence_venue is VenueId.BINANCE
    assert window.evidence_market is MarketType.PERPETUAL
    assert window.evidence_instrument == CANONICAL_IDENTITY_15M.instrument.instrument_id
    assert window.timeframe is Timeframe.M15
    assert window.mandatory_evidence_roles == tuple(
        sorted(MANDATORY_EVIDENCE_ROLES, key=lambda role: role.value)
    )
    trigger = corpus["confirmed-setup"].bars_15m[-1]
    assert window.trigger.natural_event_id == trigger.source_event_id
    assert window.trigger.revision == 1
    assert window.interval.start == trigger.interval_start
    assert window.interval.end == trigger.interval_end
    assert window.manual_level_revision is not None
    assert window.manual_level_revision.revision_number == 2
    assert window.tenant_assertions == ()

    by_role = dict.fromkeys(EvidenceRole, 0)
    for item in window.selected_public_observations:
        by_role[item.role] += 1
        assert item.finality is Finality.FINAL
    assert by_role[EvidenceRole.TRIGGER_OHLCV] == 100
    assert by_role[EvidenceRole.CONTEXT_OHLCV] == 30
    assert by_role[EvidenceRole.CVD_WINDOW] == len(corpus["confirmed-setup"].trades) == 34


def test_presentation_evidence_does_not_alter_canonical_identity(
    corpus: dict[str, Phase6Fixture],
    windows: dict[str, CanonicalEvidenceWindowV1],
) -> None:
    confirmed = windows["confirmed-setup"]
    presentation_fixture = corpus["presentation-enrichment"]
    presentation = windows["presentation-enrichment"]
    assert presentation_fixture.presentation_evidence
    assert presentation_fixture.presentation_assertions
    assert presentation.content_hash == confirmed.content_hash
    assert presentation.tenant_assertions == ()
    assert presentation_fixture.expected.evidence_identity_behavior is (
        EvidenceIdentityBehavior.PRESERVE_CANONICAL_IDENTITY
    )
    assert _uniqueness(presentation).canonical_hash() == _uniqueness(confirmed).canonical_hash()

    assertion = presentation_fixture.presentation_assertions[0]
    with pytest.raises(TenantAssertionSelectionError, match="PRESENTATION"):
        canonical_evidence_window(
            presentation_fixture,
            required_assertion_roles=(TenantAssertionRole.PRESENTATION,),
        )
    identity_forming = canonical_evidence_window(
        presentation_fixture,
        tenant_assertions=(
            SelectedTenantAssertion(
                role=TenantAssertionRole.USER_ASSERTION,
                assertion_id=assertion.assertion_id,
                content_hash=assertion.content_hash,
            ),
        ),
        required_assertion_roles=(TenantAssertionRole.USER_ASSERTION,),
    )
    assert identity_forming.content_hash != confirmed.content_hash
    assert len(identity_forming.tenant_assertions) == 1


def test_tenant_assertions_never_become_public_observations(
    corpus: dict[str, Phase6Fixture],
) -> None:
    fixture = corpus["presentation-enrichment"]
    assertion = fixture.presentation_assertions[0]
    assert assertion.organization_id == ORGANIZATION_ID
    with pytest.raises(TenantAssertionNotPublicError, match="cannot become"):
        refuse_tenant_assertion_as_public_observation(assertion)
    for _role, observation in public_observations(corpus["confirmed-setup"]):
        assert observation.privacy_class is PrivacyClass.PUBLIC_MARKET_DATA
        assert assert_public_observation_boundary(observation) is observation


def test_mandatory_semantic_evidence_changes_alter_canonical_identity(
    corpus: dict[str, Phase6Fixture],
    windows: dict[str, CanonicalEvidenceWindowV1],
) -> None:
    confirmed = windows["confirmed-setup"]
    corrected = windows["corrected-candle-revision"]
    mandatory = windows["mandatory-evidence-change"]
    adjacent = windows["adjacent-trigger-window"]

    assert corrected.trigger.revision == 2
    assert corrected.trigger.natural_event_id == confirmed.trigger.natural_event_id
    assert corrected.content_hash != confirmed.content_hash

    assert mandatory.manual_level_revision is not None
    assert mandatory.manual_level_revision.revision_number == 3
    assert mandatory.interval == confirmed.interval
    assert mandatory.trigger == confirmed.trigger
    assert mandatory.content_hash != confirmed.content_hash

    assert adjacent.interval.start == confirmed.interval.end
    assert adjacent.trigger.natural_event_id != confirmed.trigger.natural_event_id
    assert adjacent.content_hash != confirmed.content_hash

    for fixture_id in (
        "corrected-candle-revision",
        "mandatory-evidence-change",
        "adjacent-trigger-window",
    ):
        assert corpus[fixture_id].expected.evidence_identity_behavior is (
            EvidenceIdentityBehavior.DISTINCT_EVIDENCE_WINDOW
        )
        assert _uniqueness(windows[fixture_id]).canonical_hash() != (
            _uniqueness(confirmed).canonical_hash()
        )
    for fixture_id in ("invalidated-by-price", "expiry"):
        assert windows[fixture_id].content_hash == confirmed.content_hash
        assert corpus[fixture_id].expected.evidence_identity_behavior is (
            EvidenceIdentityBehavior.PRESERVE_CANONICAL_IDENTITY
        )
    # Reconnect lineage is transport metadata (TradeEvent excludes source_connection_id
    # from its content hash), so the public semantic facts hash identically; coverage
    # gates, not identity, must refuse that fixture.
    same_as_confirmed = {
        fixture_id
        for fixture_id, window in windows.items()
        if window.content_hash == confirmed.content_hash
    }
    assert same_as_confirmed == {
        "confirmed-setup",
        "presentation-enrichment",
        "invalidated-by-price",
        "expiry",
        "reconnect-discontinuity",
    }
    distinct = [w.content_hash for fid, w in windows.items() if fid not in same_as_confirmed]
    assert len(distinct) == len(set(distinct)) == len(windows) - len(same_as_confirmed)


def test_forming_and_final_have_distinct_immutable_observation_identities(
    corpus: dict[str, Phase6Fixture],
) -> None:
    forming_fixture = corpus["forming-candle"]
    forming = trigger_observation(forming_fixture)
    final = trigger_observation(corpus["confirmed-setup"])
    assert forming.finality is Finality.FORMING
    assert final.finality is Finality.FINAL
    assert forming.source_event_id == final.source_event_id
    assert forming.observation_id != final.observation_id
    assert forming.observation_id == observation_id_for(
        forming.source_event_id, finality=Finality.FORMING, revision=1
    )
    assert final.observation_id == observation_id_for(
        final.source_event_id, finality=Finality.FINAL, revision=1
    )
    require_distinct_observation_for_finality_change(forming, final)
    with pytest.raises(
        (ValidationError, FormingObservationNotExecutableError), match="cannot select"
    ):
        SelectedPublicObservation(
            role=EvidenceRole.TRIGGER_OHLCV,
            content_hash=forming.content_hash,
            finality=forming.finality,
            venue=forming.identity.venue,
            market_type=forming.identity.market_type,
            instrument_id=forming.identity.instrument.instrument_id,
            timeframe=forming.identity.timeframe,
            observation_id=forming.observation_id,
        )
    with pytest.raises(
        (ValidationError, FormingObservationNotExecutableError), match="cannot select"
    ):
        canonical_evidence_window(forming_fixture)


def test_corrected_final_revision_is_a_distinct_immutable_observation(
    corpus: dict[str, Phase6Fixture],
) -> None:
    first = trigger_observation(corpus["confirmed-setup"])
    corrected = trigger_observation(corpus["corrected-candle-revision"])
    assert corrected.finality is Finality.FINAL
    assert corrected.revision == 2
    assert corrected.source_event_id == first.source_event_id
    assert corrected.observation_id != first.observation_id
    assert corrected.observation_id == observation_id_for(
        first.source_event_id, finality=Finality.FINAL, revision=2
    )
    assert corrected.payload_content_hash != first.payload_content_hash
    require_distinct_observation_for_finality_change(first, corrected)
    replay = trigger_observation(corpus["confirmed-setup"])
    assert replay.observation_id == first.observation_id
    assert replay.content_hash == first.content_hash


@pytest.mark.parametrize(
    ("fixture_id", "message"),
    [
        ("wrong-venue", "wrong venue"),
        ("wrong-market", "wrong market"),
        ("spot-substitution", "wrong market"),
        ("wrong-instrument", "wrong instrument"),
    ],
)
def test_wrong_identity_fixtures_are_structurally_valid_negative_evidence(
    corpus: dict[str, Phase6Fixture],
    fixture_id: str,
    message: str,
) -> None:
    fixture = corpus[fixture_id]
    observation = trigger_observation(fixture)
    assert observation.finality is Finality.FINAL
    assert assert_public_observation_boundary(observation) is observation
    with pytest.raises(EvidenceIdentityMismatchError, match=message):
        require_observation_matches_evidence(
            observation,
            evidence_identity=CANONICAL_IDENTITY_15M,
            role=EvidenceRole.TRIGGER_OHLCV,
        )
    assert fixture.expected.assessment_state is SetupAssessmentState.NO_SETUP
    assert fixture.expected.reason_codes == (AssessmentReasonCode.WRONG_VENUE_OR_MARKET,)
    assert fixture.expected.candidate_creation is False


def test_wrong_venue_and_instrument_windows_are_self_consistent_but_distinct(
    windows: dict[str, CanonicalEvidenceWindowV1],
) -> None:
    confirmed = windows["confirmed-setup"]
    wrong_venue = windows["wrong-venue"]
    wrong_instrument = windows["wrong-instrument"]
    assert wrong_venue.evidence_venue is VenueId.BLOFIN
    assert wrong_venue.evidence_instrument != confirmed.evidence_instrument
    assert wrong_instrument.evidence_venue is VenueId.BINANCE
    assert wrong_instrument.evidence_instrument.endswith("ETHUSDT")
    assert (
        len({confirmed.content_hash, wrong_venue.content_hash, wrong_instrument.content_hash}) == 3
    )


def test_non_perpetual_fixtures_cannot_fill_the_cvd_window_role(
    corpus: dict[str, Phase6Fixture],
) -> None:
    for fixture_id in ("wrong-market", "spot-substitution"):
        fixture = corpus[fixture_id]
        assert fixture.trades == ()
        with pytest.raises((ValidationError, EvidenceWindowContractError), match="cvd_window"):
            canonical_evidence_window(fixture)


def test_candidate_identity_expectations_follow_canonical_contracts(
    corpus: dict[str, Phase6Fixture],
    windows: dict[str, CanonicalEvidenceWindowV1],
) -> None:
    candidate_ids = {
        fixture.fixture_id for fixture in corpus.values() if fixture.expected.candidate_creation
    }
    assert candidate_ids == CANDIDATE_FIXTURE_IDS
    spec = canonical_first_slice_authored_spec()
    for fixture_id in sorted(candidate_ids):
        fixture = corpus[fixture_id]
        window = windows[fixture_id]
        trigger = fixture.bars_15m[-1]
        candidate = build_confirmed_candidate(
            candidate_id=uuid5(ATR_REVISION_NAMESPACE, f"candidate:{fixture_id}"),
            organization_id=window.organization_id,
            strategy_version_id=window.strategy_version_id,
            executable_setup=executable_setup_ref(),
            fusion_policy_version=window.fusion_policy_version,
            direction=window.direction,
            assessment_id=uuid5(ATR_REVISION_NAMESPACE, f"assessment:{fixture_id}"),
            evidence_window_hash=window.content_hash,
            evidence_identity=fixture.identity_15m,
            evidence_venue=window.evidence_venue,
            evidence_market=window.evidence_market,
            evidence_instrument=window.evidence_instrument,
            timeframe=window.timeframe,
            created_at=fixture.evaluated_at,
            valid_until=trigger.interval_end + timedelta(minutes=15 * spec.expiry_final_bars),
            idempotency_key=f"fixture-candidate-{fixture_id}",
            correlation_id=uuid5(ATR_REVISION_NAMESPACE, f"correlation:{fixture_id}"),
        )
        assert candidate.state is CandidateState.ACTIVE
        assert candidate.uniqueness_tuple() == _uniqueness(window)
    for fixture_id, fixture in corpus.items():
        if fixture_id in candidate_ids:
            continue
        assert fixture.expected.evidence_identity_behavior is EvidenceIdentityBehavior.NO_CANDIDATE
        assert fixture.expected.assessment_state is not SetupAssessmentState.CONFIRMED_SETUP


def test_assessment_state_alignment_matrix(
    corpus: dict[str, Phase6Fixture],
    windows: dict[str, CanonicalEvidenceWindowV1],
) -> None:
    expected_counts = {
        SetupAssessmentState.CONFIRMED_SETUP: 5,
        SetupAssessmentState.NO_SETUP: 12,
        SetupAssessmentState.WATCH: 2,
        SetupAssessmentState.PARTIAL_MATCH: 4,
        SetupAssessmentState.INVALIDATED: 1,
        SetupAssessmentState.EXPIRED: 1,
    }
    actual_counts = {
        state: sum(fixture.expected.assessment_state is state for fixture in corpus.values())
        for state in SetupAssessmentState
    }
    assert actual_counts == expected_counts
    assert sum(expected_counts.values()) == FIXTURE_COUNT

    confirmed = windows["confirmed-setup"]
    lifecycle = {
        "confirmed-setup": (SetupAssessmentState.PARTIAL_MATCH, confirmed.content_hash),
        "invalidated-by-price": (SetupAssessmentState.CONFIRMED_SETUP, confirmed.content_hash),
        "expiry": (SetupAssessmentState.CONFIRMED_SETUP, confirmed.content_hash),
    }
    for fixture_id, (previous_state, previous_hash) in lifecycle.items():
        fixture = corpus[fixture_id]
        window = windows[fixture_id]
        assert fixture.expected.assessment_state in ALLOWED_ASSESSMENT_TRANSITIONS[previous_state]
        assessed_at = fixture.lifecycle_evaluated_at or fixture.evaluated_at
        transition = build_setup_assessment_transition(
            previous_assessment_id=uuid5(ATR_REVISION_NAMESPACE, f"previous:{fixture_id}"),
            previous_state=previous_state,
            previous_evidence_window_hash=previous_hash,
            new_state=fixture.expected.assessment_state,
            evidence_window_hash=window.content_hash,
            evidence_observation_hashes=tuple(
                item.content_hash for item in window.selected_public_observations
            ),
            rule_results=(),
            threshold=Decimal("1"),
            reason_codes=fixture.expected.reason_codes,
            assessed_at=assessed_at,
            valid_until=assessed_at + timedelta(minutes=15),
            correlation_id=uuid5(ATR_REVISION_NAMESPACE, f"correlation:{fixture_id}"),
        )
        assert transition.new_state is fixture.expected.assessment_state


def test_corpus_serialization_is_byte_stable() -> None:
    first = corpus_bytes()
    second = corpus_bytes()
    assert first == second
    assert hashlib.sha256(first).hexdigest() == EXPECTED_CORPUS_SHA256
    assert canonical_sha256({"fixtures": json.loads(first)["fixtures"]}) == EXPECTED_CORPUS_SHA256
