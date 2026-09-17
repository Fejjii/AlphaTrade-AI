"""Deterministic Phase 6 first-slice fixture factories.

This module is test infrastructure only. It assembles Phase 5 market contracts,
Phase 3 strategy/compiler contracts, and the frozen Phase 6 ``app.signal_fusion``
contracts without implementing a production evaluator, fusion service, or
candidate persistence. Evidence identity is always the canonical
``CanonicalEvidenceWindowV1``; no fixture-specific semantic hash exists.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from app.analysis.wilder_atr_v1 import FINALITY_POLICY_VERSION
from app.market_contracts.enums import (
    ContractStyle,
    FreshnessState,
    MarketType,
    ProductFamily,
    SourceFamily,
    VenueId,
)
from app.market_contracts.first_slice import (
    CANONICAL_EVALUATED_AT,
    CANONICAL_TRIGGER_INTERVAL_START,
    FIRST_SLICE_PATTERN_NAME,
    first_slice_identity,
)
from app.market_contracts.freshness import FIRST_SLICE_FRESHNESS_POLICY_VERSION
from app.market_contracts.identity import (
    ADAPTER_VERSION,
    AGGRESSOR_CONVENTION,
    EvidenceMarketIdentity,
    InstrumentIdentity,
    ProviderProvenance,
    SourceIdentity,
    binance_usdm_btcusdt,
    canonical_instrument_id,
)
from app.market_contracts.models import CanonicalModel
from app.market_contracts.observation import (
    PublicMarketObservation,
    observation_from_ohlcv,
    observation_from_trade,
)
from app.market_contracts.ohlcv import OhlcvBar, build_ohlcv_bar
from app.market_contracts.trades import TradeEvent, build_trade_event
from app.schemas.common import Timeframe, TradeDirection
from app.schemas.strategy_lifecycle import ManualLevelRevisionRecord
from app.schemas.strategy_pattern_spec import canonical_first_slice_authored_spec
from app.services.canonical_serialization import canonical_json_bytes
from app.services.manual_level_service import manual_level_revision_content_hash
from app.services.setup_ast_compiler import compile_from_spec
from app.signal_fusion.enums import (
    AssertionSource,
    AssessmentReasonCode,
    EvidenceRole,
    SetupAssessmentState,
    SetupIdentityKind,
    TenantAssertionRole,
)
from app.signal_fusion.evidence_window import (
    CanonicalEvidenceWindowV1,
    build_canonical_evidence_window_v1,
)
from app.signal_fusion.observation import (
    TenantExternalAssertion,
    build_tenant_external_assertion,
)
from app.signal_fusion.policy import (
    DEFAULT_CORRECTION_SELECTION_POLICY,
    DEFAULT_FUSION_POLICY_VERSION,
    first_slice_role_timeframes,
)
from app.signal_fusion.types import (
    ExecutableSetupRef,
    HalfOpenInterval,
    ManualLevelRevisionRef,
    PresentationEvidenceRef,
    SelectedPublicObservation,
    SelectedTenantAssertion,
    SemanticSourceIdentity,
    TriggerIdentity,
    selected_observation_from_public,
)

FIXTURE_NAMESPACE = UUID("f64e9110-fc12-49cc-90e2-8cae1b4d7610")
BASE_CONNECTION_ID = UUID("622aa569-934f-4cb7-90b1-862167480001")
RECONNECT_CONNECTION_ID = UUID("622aa569-934f-4cb7-90b1-862167480002")
ORGANIZATION_ID = UUID("622aa569-934f-4cb7-90b1-862167480003")
USER_ID = UUID("622aa569-934f-4cb7-90b1-862167480004")
LEVEL_ID = UUID("622aa569-934f-4cb7-90b1-862167480005")
STRATEGY_VERSION_ID = UUID("622aa569-934f-4cb7-90b1-862167480006")
COMPILED_SETUP_DEFINITION_ID = UUID("622aa569-934f-4cb7-90b1-862167480007")
PRESENTATION_ASSERTION_ID = UUID("622aa569-934f-4cb7-90b1-862167480008")
STRATEGY_NAME = FIRST_SLICE_PATTERN_NAME
DIRECTION = TradeDirection.SHORT
TICK_SIZE = Decimal("0.10")
SWING_INDEX = 96
SWING_PRICE = Decimal("100100")
RESISTANCE_PRICE = Decimal("100250")
FIRST_TRADE_SEQUENCE = 9_000_000
CVD_WINDOW_BARS = 33
# Canonical first-slice roles bound by ``first_slice_role_timeframes``.
MANDATORY_EVIDENCE_ROLES: tuple[EvidenceRole, ...] = (
    EvidenceRole.TRIGGER_OHLCV,
    EvidenceRole.CONTEXT_OHLCV,
    EvidenceRole.CVD_WINDOW,
)


class EvidenceIdentityBehavior(StrEnum):
    """Fixture relationship to the confirmed baseline CanonicalEvidenceWindowV1."""

    BASELINE = "BASELINE"
    NO_CANDIDATE = "NO_CANDIDATE"
    PRESERVE_CANONICAL_IDENTITY = "PRESERVE_CANONICAL_IDENTITY"
    DISTINCT_EVIDENCE_WINDOW = "DISTINCT_EVIDENCE_WINDOW"


class ExpectedOutcome(CanonicalModel):
    """Expected canonical outcome. ``fixture_detail_code`` is not an architecture code."""

    assessment_state: SetupAssessmentState
    reason_codes: tuple[AssessmentReasonCode, ...]
    fixture_detail_code: str
    freshness_posture: str
    finality_posture: str
    candidate_creation: bool
    evidence_identity_behavior: EvidenceIdentityBehavior


class SwingHighEvidence(CanonicalModel):
    bar_index: int
    price: Decimal
    left_bars: int
    right_bars: int
    strict: bool


class Phase6Fixture(CanonicalModel):
    fixture_id: str
    purpose: str
    strategy_name: str
    direction: TradeDirection
    evaluated_at: datetime
    lifecycle_evaluated_at: datetime | None
    identity_15m: EvidenceMarketIdentity
    identity_4h: EvidenceMarketIdentity
    bars_15m: tuple[OhlcvBar, ...]
    bars_4h: tuple[OhlcvBar, ...]
    trades: tuple[TradeEvent, ...]
    manual_level_revisions: tuple[ManualLevelRevisionRecord, ...]
    active_manual_revision_id: UUID | None
    swing: SwingHighEvidence | None
    tick_size: Decimal
    post_trigger_bars: tuple[OhlcvBar, ...]
    presentation_evidence: tuple[PresentationEvidenceRef, ...]
    presentation_assertions: tuple[TenantExternalAssertion, ...]
    expected: ExpectedOutcome


def _fixture_uuid(name: str) -> UUID:
    return uuid5(FIXTURE_NAMESPACE, name)


def _blofin_instrument() -> InstrumentIdentity:
    base = binance_usdm_btcusdt()
    return base.model_copy(
        update={
            "venue": VenueId.BLOFIN,
            "instrument_id": canonical_instrument_id(
                venue=VenueId.BLOFIN,
                product_family=base.product_family,
                market_type=base.market_type,
                symbol=base.provider_symbol,
            ),
        }
    )


def _eth_instrument() -> InstrumentIdentity:
    symbol = "ETHUSDT"
    return InstrumentIdentity(
        venue=VenueId.BINANCE,
        market_type=MarketType.PERPETUAL,
        product_family=ProductFamily.USDM_FUTURES,
        contract_style=ContractStyle.LINEAR,
        instrument_id=canonical_instrument_id(
            venue=VenueId.BINANCE,
            product_family=ProductFamily.USDM_FUTURES,
            market_type=MarketType.PERPETUAL,
            symbol=symbol,
        ),
        provider_symbol=symbol,
        base_asset="ETH",
        quote_asset="USDT",
        settlement_asset="USDT",
        contract_multiplier=Decimal("1"),
        price_unit="USDT",
        base_quantity_unit="ETH",
        quote_quantity_unit="USDT",
    )


def _spot_instrument() -> InstrumentIdentity:
    symbol = "BTCUSDT"
    return InstrumentIdentity(
        venue=VenueId.BINANCE,
        market_type=MarketType.SPOT,
        product_family=ProductFamily.SPOT,
        contract_style=ContractStyle.LINEAR,
        instrument_id=canonical_instrument_id(
            venue=VenueId.BINANCE,
            product_family=ProductFamily.SPOT,
            market_type=MarketType.SPOT,
            symbol=symbol,
        ),
        provider_symbol=symbol,
        base_asset="BTC",
        quote_asset="USDT",
        settlement_asset="USDT",
        contract_multiplier=Decimal("1"),
        price_unit="USDT",
        base_quantity_unit="BTC",
        quote_quantity_unit="USDT",
    )


def _delivery_instrument() -> InstrumentIdentity:
    symbol = "BTCUSDT"
    return InstrumentIdentity(
        venue=VenueId.BINANCE,
        market_type=MarketType.DELIVERY,
        product_family=ProductFamily.USDM_FUTURES,
        contract_style=ContractStyle.LINEAR,
        instrument_id=canonical_instrument_id(
            venue=VenueId.BINANCE,
            product_family=ProductFamily.USDM_FUTURES,
            market_type=MarketType.DELIVERY,
            symbol=symbol,
        ),
        provider_symbol=symbol,
        base_asset="BTC",
        quote_asset="USDT",
        settlement_asset="USDT",
        contract_multiplier=Decimal("1"),
        price_unit="USDT",
        base_quantity_unit="BTC",
        quote_quantity_unit="USDT",
    )


def _identity_for(instrument: InstrumentIdentity, timeframe: Timeframe) -> EvidenceMarketIdentity:
    base = first_slice_identity(timeframe=timeframe, replay=True)
    return base.model_copy(
        update={
            "venue": instrument.venue,
            "market_type": instrument.market_type,
            "instrument": instrument,
        }
    )


def _spot_identity(timeframe: Timeframe) -> EvidenceMarketIdentity:
    instrument = _spot_instrument()
    source = SourceIdentity(
        family=SourceFamily.REPLAY_FIXTURE,
        provider_name="binance-spot-replay",
        adapter_version=ADAPTER_VERSION,
        aggressor_convention=AGGRESSOR_CONVENTION,
    )
    provenance = ProviderProvenance(
        provider_name=source.provider_name,
        source_family=source.family,
        adapter_version=source.adapter_version,
        is_live=False,
        fallback_used=False,
        is_mock=True,
        detail="Synthetic spot substitution.",
    )
    return EvidenceMarketIdentity(
        venue=VenueId.BINANCE,
        market_type=MarketType.SPOT,
        instrument=instrument,
        timeframe=timeframe,
        source=source,
        provenance=provenance,
    )


def _fallback_identity(timeframe: Timeframe) -> EvidenceMarketIdentity:
    base = first_slice_identity(timeframe=timeframe, replay=True)
    fallback = ProviderProvenance.model_construct(
        provider_name=base.provenance.provider_name,
        source_family=base.provenance.source_family,
        adapter_version=base.provenance.adapter_version,
        is_live=False,
        fallback_used=True,
        is_mock=True,
        regional_failure=False,
        detail="Intentionally invalid fallback evidence.",
    )
    return base.model_copy(update={"provenance": fallback})


def _bar(
    *,
    instrument: InstrumentIdentity,
    timeframe: Timeframe,
    interval_start: datetime,
    evaluated_at: datetime,
    open_: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    base_volume: Decimal,
    revision: int = 1,
    finality_evaluated_at: datetime | None = None,
) -> OhlcvBar:
    return build_ohlcv_bar(
        instrument=instrument,
        timeframe=timeframe,
        interval_start=interval_start,
        open_=open_,
        high=high,
        low=low,
        close=close,
        base_volume=base_volume,
        quote_volume=base_volume * close,
        evaluated_at=finality_evaluated_at or evaluated_at,
        grace=timedelta(0),
        trade_count=2,
        revision=revision,
        adapter_version=ADAPTER_VERSION,
    )


def _build_15m_bars(
    *,
    trigger_open: datetime,
    evaluated_at: datetime,
    instrument: InstrumentIdentity,
    mutation: str,
) -> list[OhlcvBar]:
    first_open = trigger_open - timedelta(minutes=15 * 99)
    bars: list[OhlcvBar] = []
    for index in range(100):
        start = first_open + timedelta(minutes=15 * index)
        open_ = Decimal("100000")
        high = Decimal("100050")
        low = Decimal("99950")
        close = Decimal("100000")
        volume = Decimal("10")
        revision = 1
        finality_clock: datetime | None = None

        if index == SWING_INDEX:
            high = SWING_PRICE if mutation != "no_swing" else Decimal("100050")
            low = Decimal("100000")
        if index == 99:
            open_ = Decimal("100100")
            high = Decimal("100130")
            low = Decimal("100040")
            close = Decimal("100050")
            volume = Decimal("15")
            if mutation == "watch":
                high = Decimal("100120")
            elif mutation == "partial_match":
                open_ = Decimal("100040")
            elif mutation == "volume_failure":
                volume = Decimal("14")
            elif mutation == "corrected_revision":
                high = Decimal("100131")
                revision = 2
            elif mutation == "forming":
                finality_clock = trigger_open + timedelta(minutes=5)

        bars.append(
            _bar(
                instrument=instrument,
                timeframe=Timeframe.M15,
                interval_start=start,
                evaluated_at=evaluated_at,
                open_=open_,
                high=high,
                low=low,
                close=close,
                base_volume=volume,
                revision=revision,
                finality_evaluated_at=finality_clock,
            )
        )
    return bars


def _build_4h_bars(*, evaluated_at: datetime, instrument: InstrumentIdentity) -> list[OhlcvBar]:
    last_open = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    first_open = last_open - timedelta(hours=4 * 29)
    return [
        _bar(
            instrument=instrument,
            timeframe=Timeframe.H4,
            interval_start=first_open + timedelta(hours=4 * index),
            evaluated_at=evaluated_at,
            open_=Decimal("100000"),
            high=Decimal("100200"),
            low=Decimal("99800"),
            close=Decimal("100000"),
            base_volume=Decimal("100"),
        )
        for index in range(30)
    ]


def _trade(
    *,
    instrument: InstrumentIdentity,
    sequence: int,
    event_time: datetime,
    evaluated_at: datetime,
    quantity: Decimal,
    buyer_is_maker: bool,
    connection_id: UUID = BASE_CONNECTION_ID,
) -> TradeEvent:
    return build_trade_event(
        instrument=instrument,
        venue_trade_id=str(sequence),
        sequence=sequence,
        price=Decimal("100000"),
        quantity=quantity,
        buyer_is_maker=buyer_is_maker,
        event_timestamp=event_time,
        receive_timestamp=evaluated_at,
        source_connection_id=connection_id,
        adapter_version=ADAPTER_VERSION,
    )


def _build_trades(
    *,
    bars: list[OhlcvBar],
    evaluated_at: datetime,
    instrument: InstrumentIdentity,
    mutation: str,
) -> list[TradeEvent]:
    if instrument.market_type is not MarketType.PERPETUAL:
        return []
    window_bars = bars[-33:]
    trades: list[TradeEvent] = []
    sequence = FIRST_TRADE_SEQUENCE
    for relative_index, bar in enumerate(window_bars):
        is_trigger = relative_index == 32
        if not is_trigger:
            buyer_is_maker = mutation == "flow_failure" and relative_index in {30, 31}
            quantity = Decimal("0.001")
            if mutation == "cvd_failure" and relative_index in {30, 31}:
                quantity = Decimal("0.010")
            trades.append(
                _trade(
                    instrument=instrument,
                    sequence=sequence,
                    event_time=bar.interval_start + timedelta(minutes=7),
                    evaluated_at=evaluated_at,
                    quantity=quantity,
                    buyer_is_maker=buyer_is_maker,
                )
            )
            sequence += 1
            continue

        buy_quantity = Decimal("0.003")
        sell_quantity = Decimal("0.007")
        if mutation == "flow_failure":
            buy_quantity = Decimal("0.00475")
            sell_quantity = Decimal("0.00525")
        trades.extend(
            [
                _trade(
                    instrument=instrument,
                    sequence=sequence,
                    event_time=bar.interval_start + timedelta(minutes=5),
                    evaluated_at=evaluated_at,
                    quantity=buy_quantity,
                    buyer_is_maker=False,
                ),
                _trade(
                    instrument=instrument,
                    sequence=sequence + 1,
                    event_time=evaluated_at - timedelta(seconds=11 if mutation == "stale" else 10),
                    evaluated_at=evaluated_at,
                    quantity=sell_quantity,
                    buyer_is_maker=True,
                ),
            ]
        )
        sequence += 2

    if mutation == "sequence_gap":
        del trades[10]
    if mutation == "reconnect":
        split = len(trades) // 2
        trades = trades[:split] + [
            trade.model_copy(update={"source_connection_id": RECONNECT_CONNECTION_ID})
            for trade in trades[split:]
        ]
    return trades


def _manual_revision(
    *,
    revision_number: int,
    value: Decimal,
    supersedes: UUID | None,
    suffix: str,
) -> ManualLevelRevisionRecord:
    revision_id = _fixture_uuid(f"manual-level-{suffix}")
    created_at = datetime(2026, 1, 15, 8 + revision_number, 0, tzinfo=UTC)
    content_hash = manual_level_revision_content_hash(
        level_id=LEVEL_ID,
        revision_id=revision_id,
        revision_number=revision_number,
        organization_id=ORGANIZATION_ID,
        actor_user_id=USER_ID,
        instrument="BTCUSDT",
        exchange="binance",
        venue="binance",
        market_type="perpetual",
        price_unit="USDT",
        timeframe="4h",
        level_type="resistance",
        value=value,
        price_low=None,
        price_high=None,
        valid=True,
        effective_at=created_at,
        created_at=created_at,
        supersedes_revision_id=supersedes,
    )
    return ManualLevelRevisionRecord(
        id=revision_id,
        level_id=LEVEL_ID,
        revision_number=revision_number,
        organization_id=ORGANIZATION_ID,
        user_id=USER_ID,
        instrument="BTCUSDT",
        exchange="binance",
        timeframe="4h",
        level_type="resistance",
        value=value,
        price_low=None,
        price_high=None,
        valid=True,
        actor_user_id=USER_ID,
        venue="binance",
        market_type="perpetual",
        price_unit="USDT",
        content_hash=content_hash,
        supersedes_revision_id=supersedes,
        created_at=created_at,
        effective_at=created_at,
    )


def _manual_revisions(mutation: str) -> tuple[ManualLevelRevisionRecord, ...]:
    if mutation == "missing_resistance":
        return ()
    first = _manual_revision(
        revision_number=1,
        value=Decimal("100300"),
        supersedes=None,
        suffix="r1",
    )
    second_value = Decimal("100350") if mutation == "resistance_outside" else RESISTANCE_PRICE
    second = _manual_revision(
        revision_number=2,
        value=second_value,
        supersedes=first.id,
        suffix="r2-outside" if mutation == "resistance_outside" else "r2",
    )
    if mutation != "mandatory_evidence_change":
        return first, second
    third = _manual_revision(
        revision_number=3,
        value=RESISTANCE_PRICE,
        supersedes=second.id,
        suffix="r3-mandatory-change",
    )
    return first, second, third


def _post_trigger_bars(
    *,
    trigger: OhlcvBar,
    instrument: InstrumentIdentity,
    invalidated: bool,
) -> tuple[OhlcvBar, ...]:
    lifecycle_clock = trigger.interval_end + timedelta(minutes=30, seconds=5)
    highs = (
        (Decimal("100150"), Decimal("100120"))
        if invalidated
        else (Decimal("100120"), Decimal("100115"))
    )
    return tuple(
        _bar(
            instrument=instrument,
            timeframe=Timeframe.M15,
            interval_start=trigger.interval_end + timedelta(minutes=15 * index),
            evaluated_at=lifecycle_clock,
            open_=Decimal("100050"),
            high=high,
            low=Decimal("99980"),
            close=Decimal("100000"),
            base_volume=Decimal("10"),
        )
        for index, high in enumerate(highs)
    )


def _expected(
    state: SetupAssessmentState,
    reason_codes: tuple[AssessmentReasonCode, ...],
    detail: str,
    *,
    candidate: bool,
    identity_behavior: EvidenceIdentityBehavior,
    freshness: str = "fresh_at_10s_boundary",
    finality: str = "100_final_15m_and_30_final_4h",
) -> ExpectedOutcome:
    return ExpectedOutcome(
        assessment_state=state,
        reason_codes=reason_codes,
        fixture_detail_code=detail,
        freshness_posture=freshness,
        finality_posture=finality,
        candidate_creation=candidate,
        evidence_identity_behavior=identity_behavior,
    )


def _no_candidate(
    state: SetupAssessmentState,
    reason_codes: tuple[AssessmentReasonCode, ...],
    detail: str,
    *,
    freshness: str = "fresh_at_10s_boundary",
    finality: str = "100_final_15m_and_30_final_4h",
) -> ExpectedOutcome:
    return _expected(
        state,
        reason_codes,
        detail,
        candidate=False,
        identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        freshness=freshness,
        finality=finality,
    )


_CONFIRMED = (AssessmentReasonCode.ALL_MANDATORY_EVIDENCE_CONFIRMED,)
_DISTINCT_CONFIRMED = (
    AssessmentReasonCode.ALL_MANDATORY_EVIDENCE_CONFIRMED,
    AssessmentReasonCode.DISTINCT_EVIDENCE_WINDOW,
)
_WRONG_MARKET = (AssessmentReasonCode.WRONG_VENUE_OR_MARKET,)
_LIFECYCLE_FINALITY = "100_final_15m_plus_2_final_post_trigger_and_30_final_4h"

_FIXTURE_CASES: tuple[
    tuple[
        str,
        str,
        str,
        ExpectedOutcome,
    ],
    ...,
] = (
    (
        "confirmed-setup",
        f"Exact confirmed setup for {STRATEGY_NAME}.",
        "base",
        _expected(
            SetupAssessmentState.CONFIRMED_SETUP,
            _CONFIRMED,
            "all_first_slice_predicates_confirmed",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.BASELINE,
        ),
    ),
    (
        "no-setup",
        "No strict confirmed L2/R2 swing high exists.",
        "no_swing",
        _no_candidate(SetupAssessmentState.NO_SETUP, (), "confirmed_swing_missing"),
    ),
    (
        "watch",
        "Resistance context is valid while the sweep threshold is not yet reached.",
        "watch",
        _no_candidate(
            SetupAssessmentState.WATCH,
            (AssessmentReasonCode.PRECONDITIONS_PASSED,),
            "awaiting_liquidity_sweep",
        ),
    ),
    (
        "partial-match",
        "All numeric trigger evidence passes but the trigger candle is not bearish.",
        "partial_match",
        _no_candidate(
            SetupAssessmentState.PARTIAL_MATCH,
            (AssessmentReasonCode.SEQUENCE_STEP_PASSED,),
            "trigger_not_bearish",
        ),
    ),
    (
        "invalidated-by-price",
        "A confirmed candidate is invalidated by the first subsequent final bar.",
        "invalidated",
        _expected(
            SetupAssessmentState.INVALIDATED,
            (AssessmentReasonCode.PATTERN_INVALIDATED,),
            "price_invalidation_reached",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.PRESERVE_CANONICAL_IDENTITY,
            finality=_LIFECYCLE_FINALITY,
        ),
    ),
    (
        "stale-source",
        "Latest perpetual trade is one second outside the freshness bound.",
        "stale",
        _no_candidate(
            SetupAssessmentState.NO_SETUP,
            (AssessmentReasonCode.REQUIRED_SOURCE_STALE,),
            "latest_trade_stale",
            freshness="stale_at_11s",
        ),
    ),
    (
        "sequence-gap",
        "The ordered perpetual trade stream omits one venue sequence.",
        "sequence_gap",
        _no_candidate(
            SetupAssessmentState.NO_SETUP,
            (AssessmentReasonCode.REQUIRED_SOURCE_GAPPED,),
            "trade_sequence_gap",
        ),
    ),
    (
        "reconnect-discontinuity",
        "The CVD window crosses two source connection epochs.",
        "reconnect",
        _no_candidate(
            SetupAssessmentState.NO_SETUP,
            (AssessmentReasonCode.REQUIRED_SOURCE_GAPPED,),
            "cross_connection_cvd_forbidden",
        ),
    ),
    (
        "wrong-venue",
        "Blofin BTCUSDT perpetual evidence is supplied for the Binance slice.",
        "wrong_venue",
        _no_candidate(SetupAssessmentState.NO_SETUP, _WRONG_MARKET, "wrong_venue"),
    ),
    (
        "wrong-instrument",
        "ETHUSDT perpetual evidence is supplied for the BTCUSDT slice.",
        "wrong_instrument",
        _no_candidate(SetupAssessmentState.NO_SETUP, _WRONG_MARKET, "wrong_instrument"),
    ),
    (
        "wrong-market",
        "The evidence envelope is labelled as a delivery market.",
        "wrong_market",
        _no_candidate(SetupAssessmentState.NO_SETUP, _WRONG_MARKET, "wrong_market"),
    ),
    (
        "spot-substitution",
        "BTCUSDT spot evidence is substituted for perpetual evidence.",
        "spot",
        _no_candidate(SetupAssessmentState.NO_SETUP, _WRONG_MARKET, "spot_not_perpetual"),
    ),
    (
        "fallback-source",
        "Evidence provenance declares a forbidden fallback source.",
        "fallback",
        _no_candidate(
            SetupAssessmentState.NO_SETUP,
            (AssessmentReasonCode.REQUIRED_SOURCE_FALLBACK,),
            "fallback_source_forbidden",
            freshness="untrusted_fallback",
        ),
    ),
    (
        "incomplete-warmup",
        "Only 99 final 15m bars are available.",
        "incomplete_warmup",
        _no_candidate(
            SetupAssessmentState.NO_SETUP,
            (),
            "trigger_warmup_incomplete",
            finality="99_final_15m_and_30_final_4h",
        ),
    ),
    (
        "forming-candle",
        "The trigger candle is still forming at its source finality clock.",
        "forming",
        _no_candidate(
            SetupAssessmentState.NO_SETUP,
            (),
            "forming_trigger_candle",
            finality="99_final_plus_1_forming_15m_and_30_final_4h",
        ),
    ),
    (
        "missing-manual-resistance",
        "No active versioned 4h manual resistance is available.",
        "missing_resistance",
        _no_candidate(SetupAssessmentState.WATCH, (), "manual_resistance_missing"),
    ),
    (
        "resistance-outside-tolerance",
        "Nearest active resistance is beyond 0.50 ATR4h from the swing.",
        "resistance_outside",
        _no_candidate(SetupAssessmentState.NO_SETUP, (), "resistance_outside_atr_tolerance"),
    ),
    (
        "volume-threshold-failure",
        "Trigger volume is 1.40 times the prior 20-bar mean.",
        "volume_failure",
        _no_candidate(
            SetupAssessmentState.PARTIAL_MATCH,
            (AssessmentReasonCode.SEQUENCE_STEP_PASSED,),
            "trigger_volume_ratio_below_threshold",
        ),
    ),
    (
        "cvd-divergence-failure",
        "CVD at trigger close is not below CVD at swing close.",
        "cvd_failure",
        _no_candidate(
            SetupAssessmentState.PARTIAL_MATCH,
            (AssessmentReasonCode.SEQUENCE_STEP_PASSED,),
            "bearish_cvd_divergence_missing",
        ),
    ),
    (
        "sell-imbalance-failure",
        "Trigger signed quote-flow ratio is -0.05, above the -0.10 threshold.",
        "flow_failure",
        _no_candidate(
            SetupAssessmentState.PARTIAL_MATCH,
            (AssessmentReasonCode.SEQUENCE_STEP_PASSED,),
            "aggressive_sell_imbalance_missing",
        ),
    ),
    (
        "expiry",
        "A confirmed candidate expires after two additional final 15m bars.",
        "expiry",
        _expected(
            SetupAssessmentState.EXPIRED,
            (AssessmentReasonCode.VALIDITY_INTERVAL_ELAPSED,),
            "two_final_bars_elapsed",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.PRESERVE_CANONICAL_IDENTITY,
            finality=_LIFECYCLE_FINALITY,
        ),
    ),
    (
        "corrected-candle-revision",
        "A final trigger candle correction has revision 2 and a distinct evidence window.",
        "corrected_revision",
        _expected(
            SetupAssessmentState.CONFIRMED_SETUP,
            _DISTINCT_CONFIRMED,
            "corrected_final_candle_re_evaluated",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.DISTINCT_EVIDENCE_WINDOW,
            finality="100_final_15m_with_trigger_revision_2_and_30_final_4h",
        ),
    ),
    (
        "presentation-enrichment",
        "Presentation evidence and a PRESENTATION tenant assertion leave identity unchanged.",
        "presentation",
        _expected(
            SetupAssessmentState.CONFIRMED_SETUP,
            _CONFIRMED,
            "optional_presentation_evidence_added",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.PRESERVE_CANONICAL_IDENTITY,
        ),
    ),
    (
        "mandatory-evidence-change",
        "A new active manual-level revision creates a distinct evidence window.",
        "mandatory_evidence_change",
        _expected(
            SetupAssessmentState.CONFIRMED_SETUP,
            _DISTINCT_CONFIRMED,
            "mandatory_evidence_revision_changed",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.DISTINCT_EVIDENCE_WINDOW,
        ),
    ),
    (
        "adjacent-trigger-window",
        "The same setup in the adjacent 15m trigger window has a distinct identity.",
        "adjacent",
        _expected(
            SetupAssessmentState.CONFIRMED_SETUP,
            _DISTINCT_CONFIRMED,
            "adjacent_trigger_window",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.DISTINCT_EVIDENCE_WINDOW,
        ),
    ),
)


def _instrument_for(mutation: str) -> InstrumentIdentity:
    if mutation == "wrong_venue":
        return _blofin_instrument()
    if mutation == "wrong_instrument":
        return _eth_instrument()
    if mutation == "wrong_market":
        return _delivery_instrument()
    if mutation == "spot":
        return _spot_instrument()
    return binance_usdm_btcusdt()


def _identities(
    mutation: str, instrument: InstrumentIdentity
) -> tuple[EvidenceMarketIdentity, EvidenceMarketIdentity]:
    if mutation == "spot":
        return _spot_identity(Timeframe.M15), _spot_identity(Timeframe.H4)
    if mutation == "fallback":
        return _fallback_identity(Timeframe.M15), _fallback_identity(Timeframe.H4)
    return _identity_for(instrument, Timeframe.M15), _identity_for(instrument, Timeframe.H4)


def _presentation_assertion(
    *, instrument: InstrumentIdentity, evaluated_at: datetime
) -> TenantExternalAssertion:
    """Tenant-owned chart annotation. Never a public observation; never identity-forming."""
    return build_tenant_external_assertion(
        assertion_id=PRESENTATION_ASSERTION_ID,
        organization_id=ORGANIZATION_ID,
        user_id=USER_ID,
        source=AssertionSource.USER_ASSERTION,
        source_event_id="chart-annotation-bearish-sweep-at-4h-resistance",
        venue=instrument.venue,
        market_type=instrument.market_type,
        instrument_id=instrument.instrument_id,
        received_at=evaluated_at,
        recorded_at=evaluated_at + timedelta(seconds=1),
    )


_BAR_MUTATIONS = frozenset(
    {"no_swing", "watch", "partial_match", "volume_failure", "corrected_revision", "forming"}
)
_TRADE_MUTATIONS = frozenset({"stale", "sequence_gap", "reconnect", "cvd_failure", "flow_failure"})


def _build_fixture(
    fixture_id: str,
    purpose: str,
    mutation: str,
    expected: ExpectedOutcome,
) -> Phase6Fixture:
    shift = timedelta(minutes=15) if mutation == "adjacent" else timedelta(0)
    trigger_open = CANONICAL_TRIGGER_INTERVAL_START + shift
    evaluated_at = CANONICAL_EVALUATED_AT + shift
    instrument = _instrument_for(mutation)
    bars_15m = _build_15m_bars(
        trigger_open=trigger_open,
        evaluated_at=evaluated_at,
        instrument=instrument,
        mutation=mutation if mutation in _BAR_MUTATIONS else "base",
    )
    if mutation == "incomplete_warmup":
        bars_15m = bars_15m[1:]
    bars_4h = _build_4h_bars(evaluated_at=evaluated_at, instrument=instrument)
    identity_15m, identity_4h = _identities(mutation, instrument)
    trades = _build_trades(
        bars=bars_15m,
        evaluated_at=evaluated_at,
        instrument=instrument,
        mutation=mutation if mutation in _TRADE_MUTATIONS else "base",
    )
    revisions = _manual_revisions(mutation)
    active_revision_id = revisions[-1].id if revisions else None
    swing = (
        None
        if mutation == "no_swing"
        else SwingHighEvidence(
            bar_index=SWING_INDEX - (1 if mutation == "incomplete_warmup" else 0),
            price=SWING_PRICE,
            left_bars=2,
            right_bars=2,
            strict=True,
        )
    )
    post_bars: tuple[OhlcvBar, ...] = ()
    lifecycle_evaluated_at: datetime | None = None
    if mutation in {"invalidated", "expiry"}:
        post_bars = _post_trigger_bars(
            trigger=bars_15m[-1],
            instrument=instrument,
            invalidated=mutation == "invalidated",
        )
        lifecycle_evaluated_at = post_bars[-1].interval_end + timedelta(seconds=5)
    presentation: tuple[PresentationEvidenceRef, ...] = ()
    presentation_assertions: tuple[TenantExternalAssertion, ...] = ()
    if mutation == "presentation":
        assertion = _presentation_assertion(instrument=instrument, evaluated_at=evaluated_at)
        presentation = (
            PresentationEvidenceRef(
                label="chart-annotation",
                content_hash=assertion.content_hash,
                note="Bearish sweep at versioned 4h resistance (UI only).",
            ),
        )
        presentation_assertions = (assertion,)
    return Phase6Fixture(
        fixture_id=fixture_id,
        purpose=purpose,
        strategy_name=STRATEGY_NAME,
        direction=DIRECTION,
        evaluated_at=evaluated_at,
        lifecycle_evaluated_at=lifecycle_evaluated_at,
        identity_15m=identity_15m,
        identity_4h=identity_4h,
        bars_15m=tuple(bars_15m),
        bars_4h=tuple(bars_4h),
        trades=tuple(trades),
        manual_level_revisions=revisions,
        active_manual_revision_id=active_revision_id,
        swing=swing,
        tick_size=TICK_SIZE,
        post_trigger_bars=post_bars,
        presentation_evidence=presentation,
        presentation_assertions=presentation_assertions,
        expected=expected,
    )


def build_fixture_corpus() -> tuple[Phase6Fixture, ...]:
    """Build all matrix rows in stable manifest order."""
    return tuple(_build_fixture(*case) for case in _FIXTURE_CASES)


def executable_setup_ref() -> ExecutableSetupRef:
    """Tenant-owned CompiledSetupDefinition reference bound to the compiled first-slice AST."""
    compiled = compile_from_spec(canonical_first_slice_authored_spec())
    if compiled.document is None:
        raise ValueError("Canonical first-slice spec must compile to an executable document.")
    return ExecutableSetupRef(
        setup_definition_id=COMPILED_SETUP_DEFINITION_ID,
        kind=SetupIdentityKind.COMPILED_SETUP_DEFINITION,
        content_hash=compiled.document.content_hash,
    )


def bar_observation(
    bar: OhlcvBar,
    *,
    identity: EvidenceMarketIdentity,
    observed_at: datetime,
) -> PublicMarketObservation:
    """Phase 5 public envelope for one bar; observation identity is revision-aware."""
    return observation_from_ohlcv(
        bar,
        identity=identity,
        observed_at=observed_at,
        receive_time=observed_at,
        freshness_state=FreshnessState.FRESH,
    )


def trigger_observation(fixture: Phase6Fixture) -> PublicMarketObservation:
    return bar_observation(
        fixture.bars_15m[-1],
        identity=fixture.identity_15m,
        observed_at=fixture.evaluated_at,
    )


def public_observations(
    fixture: Phase6Fixture,
) -> tuple[tuple[EvidenceRole, PublicMarketObservation], ...]:
    """Role-bound Phase 5 public observations forming the fixture's semantic input set.

    Trigger-timeframe OHLCV, context-timeframe OHLCV, and the CVD-window trade
    events are the public facts every first-slice predicate is derived from.
    """
    trigger_series = tuple(
        (
            EvidenceRole.TRIGGER_OHLCV,
            bar_observation(bar, identity=fixture.identity_15m, observed_at=fixture.evaluated_at),
        )
        for bar in fixture.bars_15m
    )
    context_series = tuple(
        (
            EvidenceRole.CONTEXT_OHLCV,
            bar_observation(bar, identity=fixture.identity_4h, observed_at=fixture.evaluated_at),
        )
        for bar in fixture.bars_4h
    )
    cvd_window = tuple(
        (
            EvidenceRole.CVD_WINDOW,
            observation_from_trade(
                trade,
                identity=fixture.identity_15m,
                observed_at=fixture.evaluated_at,
                freshness_state=FreshnessState.FRESH,
            ),
        )
        for trade in fixture.trades
    )
    return trigger_series + context_series + cvd_window


def selected_public_observations(
    fixture: Phase6Fixture,
) -> tuple[SelectedPublicObservation, ...]:
    return tuple(
        selected_observation_from_public(observation, role=role)
        for role, observation in public_observations(fixture)
    )


def manual_level_revision_ref(fixture: Phase6Fixture) -> ManualLevelRevisionRef | None:
    if fixture.active_manual_revision_id is None:
        return None
    active = next(
        revision
        for revision in fixture.manual_level_revisions
        if revision.id == fixture.active_manual_revision_id
    )
    return ManualLevelRevisionRef(
        level_id=active.level_id,
        revision_number=active.revision_number,
        content_hash=active.content_hash,
    )


def semantic_source_set(fixture: Phase6Fixture) -> tuple[SemanticSourceIdentity, ...]:
    return (
        SemanticSourceIdentity(
            venue=fixture.identity_15m.venue,
            market_type=fixture.identity_15m.market_type,
            source_family=fixture.identity_15m.source.family,
        ),
    )


def trigger_identity(fixture: Phase6Fixture) -> TriggerIdentity:
    trigger = fixture.bars_15m[-1]
    return TriggerIdentity(natural_event_id=trigger.source_event_id, revision=trigger.revision)


def trigger_interval(fixture: Phase6Fixture) -> HalfOpenInterval:
    trigger = fixture.bars_15m[-1]
    return HalfOpenInterval(start=trigger.interval_start, end=trigger.interval_end)


def presentation_tenant_assertions(
    fixture: Phase6Fixture,
) -> tuple[SelectedTenantAssertion, ...]:
    return tuple(
        SelectedTenantAssertion(
            role=TenantAssertionRole.PRESENTATION,
            assertion_id=assertion.assertion_id,
            content_hash=assertion.content_hash,
        )
        for assertion in fixture.presentation_assertions
    )


def canonical_evidence_window(
    fixture: Phase6Fixture,
    *,
    tenant_assertions: tuple[SelectedTenantAssertion, ...] | None = None,
    required_assertion_roles: tuple[TenantAssertionRole, ...] = (),
) -> CanonicalEvidenceWindowV1:
    """Project a fixture into the canonical Phase 6 evidence window.

    Presentation evidence and PRESENTATION-role tenant assertions are passed on
    purpose: the canonical builder must drop them from the hash preimage.
    """
    return build_canonical_evidence_window_v1(
        organization_id=ORGANIZATION_ID,
        strategy_version_id=STRATEGY_VERSION_ID,
        compiled_setup_definition_id=COMPILED_SETUP_DEFINITION_ID,
        compiled_setup_content_hash=executable_setup_ref().content_hash,
        fusion_policy_version=DEFAULT_FUSION_POLICY_VERSION,
        finality_policy_version=FINALITY_POLICY_VERSION,
        freshness_policy_version=FIRST_SLICE_FRESHNESS_POLICY_VERSION,
        direction=fixture.direction,
        evidence_identity=fixture.identity_15m,
        interval=trigger_interval(fixture),
        trigger=trigger_identity(fixture),
        mandatory_evidence_roles=MANDATORY_EVIDENCE_ROLES,
        selected_public_observations=selected_public_observations(fixture),
        source_set=semantic_source_set(fixture),
        tenant_assertions=(
            presentation_tenant_assertions(fixture)
            if tenant_assertions is None
            else tenant_assertions
        ),
        required_assertion_roles=required_assertion_roles,
        role_timeframes=first_slice_role_timeframes(),
        manual_level_revision=manual_level_revision_ref(fixture),
        correction_selection_policy=DEFAULT_CORRECTION_SELECTION_POLICY,
        presentation_evidence=fixture.presentation_evidence,
    )


def corpus_bytes() -> bytes:
    """Canonical byte-stable serialization of the complete corpus."""
    return canonical_json_bytes(
        {"fixtures": [fixture.model_dump(mode="python") for fixture in build_fixture_corpus()]}
    )


def manifest_rows() -> list[dict[str, object]]:
    """Expected-outcome rows mirrored by the checked-in JSON manifest."""
    return [
        {
            "fixture_id": fixture.fixture_id,
            "purpose": fixture.purpose,
            "strategy_name": fixture.strategy_name,
            "direction": fixture.direction.value,
            "expected_assessment_state": fixture.expected.assessment_state.value,
            "expected_reason_codes": [code.value for code in fixture.expected.reason_codes],
            "fixture_detail_code": fixture.expected.fixture_detail_code,
            "expected_freshness_posture": fixture.expected.freshness_posture,
            "expected_finality_posture": fixture.expected.finality_posture,
            "expected_candidate_creation": fixture.expected.candidate_creation,
            "expected_evidence_identity_behavior": (
                fixture.expected.evidence_identity_behavior.value
            ),
        }
        for fixture in build_fixture_corpus()
    ]
