"""Deterministic Phase 6 first-slice fixture factories.

This module is test infrastructure only. It assembles existing Phase 5 market
contracts and Phase 3 strategy/compiler contracts without implementing a
production detector, fusion service, or candidate model.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from app.market_contracts.enums import (
    ContractStyle,
    MarketType,
    ProductFamily,
    SourceFamily,
    VenueId,
)
from app.market_contracts.first_slice import (
    CANONICAL_EVALUATED_AT,
    CANONICAL_TRIGGER_INTERVAL_START,
    first_slice_identity,
)
from app.market_contracts.hashing import with_content_hash
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
from app.market_contracts.ohlcv import OhlcvBar, build_ohlcv_bar
from app.market_contracts.trades import TradeEvent, build_trade_event
from app.schemas.common import Timeframe
from app.schemas.strategy_lifecycle import ManualLevelRevisionRecord
from app.services.canonical_serialization import canonical_json_bytes, canonical_sha256
from app.services.manual_level_service import manual_level_revision_content_hash

FIXTURE_NAMESPACE = UUID("f64e9110-fc12-49cc-90e2-8cae1b4d7610")
BASE_CONNECTION_ID = UUID("622aa569-934f-4cb7-90b1-862167480001")
RECONNECT_CONNECTION_ID = UUID("622aa569-934f-4cb7-90b1-862167480002")
ORGANIZATION_ID = UUID("622aa569-934f-4cb7-90b1-862167480003")
USER_ID = UUID("622aa569-934f-4cb7-90b1-862167480004")
LEVEL_ID = UUID("622aa569-934f-4cb7-90b1-862167480005")
TICK_SIZE = Decimal("0.10")
SWING_INDEX = 96
SWING_PRICE = Decimal("100100")
RESISTANCE_PRICE = Decimal("100250")
FIRST_TRADE_SEQUENCE = 9_000_000


class AssessmentState(StrEnum):
    CONFIRMED = "CONFIRMED"
    NO_SETUP = "NO_SETUP"
    WATCH = "WATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


class EvidenceIdentityBehavior(StrEnum):
    BASELINE = "BASELINE"
    NO_CANDIDATE = "NO_CANDIDATE"
    PRESERVE_SEMANTIC_IDENTITY = "PRESERVE_SEMANTIC_IDENTITY"
    NEW_SEMANTIC_WINDOW = "NEW_SEMANTIC_WINDOW"


class ExpectedOutcome(CanonicalModel):
    assessment_state: AssessmentState
    reason_codes: tuple[str, ...]
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
    presentation_evidence: dict[str, str]
    expected: ExpectedOutcome


def _fixture_uuid(name: str) -> UUID:
    return uuid5(FIXTURE_NAMESPACE, name)


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


def _build_4h_bars(
    *, evaluated_at: datetime, instrument: InstrumentIdentity
) -> list[OhlcvBar]:
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
                    event_time=evaluated_at
                    - timedelta(seconds=11 if mutation == "stale" else 10),
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
    state: AssessmentState,
    reason: str,
    *,
    candidate: bool,
    identity_behavior: EvidenceIdentityBehavior,
    freshness: str = "fresh_at_10s_boundary",
    finality: str = "100_final_15m_and_30_final_4h",
) -> ExpectedOutcome:
    return ExpectedOutcome(
        assessment_state=state,
        reason_codes=(reason,),
        freshness_posture=freshness,
        finality_posture=finality,
        candidate_creation=candidate,
        evidence_identity_behavior=identity_behavior,
    )


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
        "Exact confirmed bearish liquidity sweep exhaustion setup.",
        "base",
        _expected(
            AssessmentState.CONFIRMED,
            "all_first_slice_predicates_confirmed",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.BASELINE,
        ),
    ),
    (
        "no-setup",
        "No strict confirmed L2/R2 swing high exists.",
        "no_swing",
        _expected(
            AssessmentState.NO_SETUP,
            "confirmed_swing_missing",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "watch",
        "Resistance context is valid while the sweep threshold is not yet reached.",
        "watch",
        _expected(
            AssessmentState.WATCH,
            "awaiting_liquidity_sweep",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "partial-match",
        "All numeric trigger evidence passes but the trigger candle is not bearish.",
        "partial_match",
        _expected(
            AssessmentState.PARTIAL_MATCH,
            "trigger_not_bearish",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "invalidated-by-price",
        "A confirmed candidate is invalidated by the first subsequent final bar.",
        "invalidated",
        _expected(
            AssessmentState.INVALIDATED,
            "price_invalidation_reached",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.PRESERVE_SEMANTIC_IDENTITY,
            finality="100_final_15m_plus_2_final_post_trigger_and_30_final_4h",
        ),
    ),
    (
        "stale-source",
        "Latest perpetual trade is one second outside the freshness bound.",
        "stale",
        _expected(
            AssessmentState.NO_SETUP,
            "latest_trade_stale",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
            freshness="stale_at_11s",
        ),
    ),
    (
        "sequence-gap",
        "The ordered perpetual trade stream omits one venue sequence.",
        "sequence_gap",
        _expected(
            AssessmentState.NO_SETUP,
            "trade_sequence_gap",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "reconnect-discontinuity",
        "The CVD window crosses two source connection epochs.",
        "reconnect",
        _expected(
            AssessmentState.NO_SETUP,
            "cross_connection_cvd_forbidden",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "wrong-instrument",
        "ETHUSDT perpetual evidence is supplied for the BTCUSDT slice.",
        "wrong_instrument",
        _expected(
            AssessmentState.NO_SETUP,
            "wrong_instrument",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "wrong-market",
        "The evidence envelope is labelled as a delivery market.",
        "wrong_market",
        _expected(
            AssessmentState.NO_SETUP,
            "wrong_market",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "spot-substitution",
        "BTCUSDT spot evidence is substituted for perpetual evidence.",
        "spot",
        _expected(
            AssessmentState.NO_SETUP,
            "spot_not_perpetual",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "fallback-source",
        "Evidence provenance declares a forbidden fallback source.",
        "fallback",
        _expected(
            AssessmentState.NO_SETUP,
            "fallback_source_forbidden",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
            freshness="untrusted_fallback",
        ),
    ),
    (
        "incomplete-warmup",
        "Only 99 final 15m bars are available.",
        "incomplete_warmup",
        _expected(
            AssessmentState.NO_SETUP,
            "trigger_warmup_incomplete",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
            finality="99_final_15m_and_30_final_4h",
        ),
    ),
    (
        "forming-candle",
        "The trigger candle is still forming at its source finality clock.",
        "forming",
        _expected(
            AssessmentState.NO_SETUP,
            "forming_trigger_candle",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
            finality="99_final_plus_1_forming_15m_and_30_final_4h",
        ),
    ),
    (
        "missing-manual-resistance",
        "No active versioned 4h manual resistance is available.",
        "missing_resistance",
        _expected(
            AssessmentState.WATCH,
            "manual_resistance_missing",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "resistance-outside-tolerance",
        "Nearest active resistance is beyond 0.50 ATR4h from the swing.",
        "resistance_outside",
        _expected(
            AssessmentState.NO_SETUP,
            "resistance_outside_atr_tolerance",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "volume-threshold-failure",
        "Trigger volume is 1.40 times the prior 20-bar mean.",
        "volume_failure",
        _expected(
            AssessmentState.PARTIAL_MATCH,
            "trigger_volume_ratio_below_threshold",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "cvd-divergence-failure",
        "CVD at trigger close is not below CVD at swing close.",
        "cvd_failure",
        _expected(
            AssessmentState.PARTIAL_MATCH,
            "bearish_cvd_divergence_missing",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "sell-imbalance-failure",
        "Trigger signed quote-flow ratio is -0.05, above the -0.10 threshold.",
        "flow_failure",
        _expected(
            AssessmentState.PARTIAL_MATCH,
            "aggressive_sell_imbalance_missing",
            candidate=False,
            identity_behavior=EvidenceIdentityBehavior.NO_CANDIDATE,
        ),
    ),
    (
        "expiry",
        "A confirmed candidate expires after two additional final 15m bars.",
        "expiry",
        _expected(
            AssessmentState.EXPIRED,
            "two_final_bars_elapsed",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.PRESERVE_SEMANTIC_IDENTITY,
            finality="100_final_15m_plus_2_final_post_trigger_and_30_final_4h",
        ),
    ),
    (
        "corrected-candle-revision",
        "A final trigger candle correction has revision 2 and changed semantic evidence.",
        "corrected_revision",
        _expected(
            AssessmentState.CONFIRMED,
            "corrected_final_candle_re_evaluated",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.NEW_SEMANTIC_WINDOW,
            finality="100_final_15m_with_trigger_revision_2_and_30_final_4h",
        ),
    ),
    (
        "presentation-enrichment",
        "Optional presentation evidence is enriched without changing semantic identity.",
        "presentation",
        _expected(
            AssessmentState.CONFIRMED,
            "optional_presentation_evidence_added",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.PRESERVE_SEMANTIC_IDENTITY,
        ),
    ),
    (
        "mandatory-evidence-change",
        "A new active manual-level revision creates a new semantic window.",
        "mandatory_evidence_change",
        _expected(
            AssessmentState.CONFIRMED,
            "mandatory_evidence_revision_changed",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.NEW_SEMANTIC_WINDOW,
        ),
    ),
    (
        "adjacent-trigger-window",
        "The same setup in the adjacent 15m trigger window has a distinct identity.",
        "adjacent",
        _expected(
            AssessmentState.CONFIRMED,
            "adjacent_trigger_window",
            candidate=True,
            identity_behavior=EvidenceIdentityBehavior.NEW_SEMANTIC_WINDOW,
        ),
    ),
)


def _build_fixture(
    fixture_id: str,
    purpose: str,
    mutation: str,
    expected: ExpectedOutcome,
) -> Phase6Fixture:
    trigger_open = (
        CANONICAL_TRIGGER_INTERVAL_START + timedelta(minutes=15)
        if mutation == "adjacent"
        else CANONICAL_TRIGGER_INTERVAL_START
    )
    evaluated_at = (
        CANONICAL_EVALUATED_AT + timedelta(minutes=15)
        if mutation == "adjacent"
        else CANONICAL_EVALUATED_AT
    )
    instrument = (
        _eth_instrument()
        if mutation == "wrong_instrument"
        else _spot_instrument()
        if mutation == "spot"
        else binance_usdm_btcusdt()
    )
    bar_mutation = mutation if mutation in {
        "no_swing",
        "watch",
        "partial_match",
        "volume_failure",
        "corrected_revision",
        "forming",
    } else "base"
    bars_15m = _build_15m_bars(
        trigger_open=trigger_open,
        evaluated_at=evaluated_at,
        instrument=instrument,
        mutation=bar_mutation,
    )
    if mutation == "incomplete_warmup":
        bars_15m = bars_15m[1:]
    bars_4h = _build_4h_bars(evaluated_at=evaluated_at, instrument=instrument)

    if mutation == "spot":
        identity_15m = _spot_identity(Timeframe.M15)
        identity_4h = _spot_identity(Timeframe.H4)
    elif mutation == "fallback":
        identity_15m = _fallback_identity(Timeframe.M15)
        identity_4h = _fallback_identity(Timeframe.H4)
    else:
        identity_15m = _identity_for(instrument, Timeframe.M15)
        identity_4h = _identity_for(instrument, Timeframe.H4)
    if mutation == "wrong_market":
        identity_15m = identity_15m.model_copy(update={"market_type": MarketType.DELIVERY})
        identity_4h = identity_4h.model_copy(update={"market_type": MarketType.DELIVERY})

    trade_mutation = mutation if mutation in {
        "stale",
        "sequence_gap",
        "reconnect",
        "cvd_failure",
        "flow_failure",
    } else "base"
    trades = _build_trades(
        bars=bars_15m,
        evaluated_at=evaluated_at,
        instrument=instrument,
        mutation=trade_mutation,
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
    presentation = (
        {"chart_annotation": "Bearish sweep at versioned 4h resistance"}
        if mutation == "presentation"
        else {}
    )
    return Phase6Fixture(
        fixture_id=fixture_id,
        purpose=purpose,
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
        expected=expected,
    )


def build_fixture_corpus() -> tuple[Phase6Fixture, ...]:
    """Build all matrix rows in stable manifest order."""
    return tuple(_build_fixture(*case) for case in _FIXTURE_CASES)


def semantic_window_hash(fixture: Phase6Fixture) -> str:
    """Hash mandatory evidence only; presentation enrichment is deliberately excluded."""
    return canonical_sha256(
        {
            "identity_15m": fixture.identity_15m.model_dump(mode="python"),
            "identity_4h": fixture.identity_4h.model_dump(mode="python"),
            "bars_15m": [bar.content_hash for bar in fixture.bars_15m],
            "bars_4h": [bar.content_hash for bar in fixture.bars_4h],
            "trades": [
                {
                    "content_hash": trade.content_hash,
                    "sequence": trade.sequence,
                    "source_connection_id": trade.source_connection_id,
                }
                for trade in fixture.trades
            ],
            "manual_level_revisions": [
                revision.content_hash for revision in fixture.manual_level_revisions
            ],
            "active_manual_revision_id": fixture.active_manual_revision_id,
            "swing": (
                fixture.swing.model_dump(mode="python") if fixture.swing is not None else None
            ),
            "tick_size": fixture.tick_size,
            "trigger_interval_start": fixture.bars_15m[-1].interval_start,
            "trigger_interval_end": fixture.bars_15m[-1].interval_end,
        }
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
            "expected_assessment_state": fixture.expected.assessment_state.value,
            "expected_reason_codes": list(fixture.expected.reason_codes),
            "expected_freshness_posture": fixture.expected.freshness_posture,
            "expected_finality_posture": fixture.expected.finality_posture,
            "expected_candidate_creation": fixture.expected.candidate_creation,
            "expected_evidence_identity_behavior": (
                fixture.expected.evidence_identity_behavior.value
            ),
        }
        for fixture in build_fixture_corpus()
    ]
