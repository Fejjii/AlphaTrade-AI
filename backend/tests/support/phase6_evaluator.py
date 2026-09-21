"""Synthetic first-slice worlds for Phase 6 evaluator tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.evidence_pipeline.canonical import build_first_slice_assessment_command
from app.market_contracts.cursor import TradeStreamSnapshot
from app.market_contracts.cvd import (
    FIRST_SLICE_CVD_LOOKBACK_BARS,
    first_slice_baseline_open,
    first_slice_cvd_window,
)
from app.market_contracts.enums import FreshnessState, MarketType, VenueId
from app.market_contracts.first_slice import (
    FIRST_SLICE_MIN_FINAL_4H,
    FIRST_SLICE_MIN_FINAL_15M,
    first_slice_identity,
)
from app.market_contracts.flow import bar_signed_quote_flow
from app.market_contracts.freshness import (
    first_slice_freshness_policy,
    live_confirmation_window_open,
)
from app.market_contracts.identity import ADAPTER_VERSION, binance_usdm_btcusdt, interval_timedelta
from app.market_contracts.observation import PublicMarketObservation, observation_from_ohlcv
from app.market_contracts.ohlcv import OhlcvBar, build_ohlcv_bar, require_closed_series
from app.market_contracts.replay_fixtures import build_closed_bars
from app.market_contracts.trades import TradeEvent, build_trade_event
from app.schemas.common import Timeframe, TradeDirection
from app.signal_fusion.adapters import AssessmentCommand
from app.signal_fusion.enums import EvidenceAdapterKind, EvidenceRole
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle, ManualResistanceEvidence
from app.signal_fusion.policy import FusionPolicy
from app.signal_fusion.types import HalfOpenInterval, TriggerIdentity
from tests.support.phase5_market import EVALUATED_AT, TRIGGER_OPEN, proven_snapshot
from tests.support.phase6_fusion import (
    ORG_ID,
    STRATEGY_VERSION_ID,
    fusion_policy,
    manual_level,
    semantic_sources,
)

CONNECTION = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1")
SWING_HIGH = Decimal("100200")
SWING_INDEX = FIRST_SLICE_MIN_FINAL_15M - 4
LAST_4H_OPEN = datetime(2026, 1, 15, 12, 0, tzinfo=TRIGGER_OPEN.tzinfo)
FIRST_TRADE_SEQUENCE = 8_000_000
RESISTANCE_EFFECTIVE = TRIGGER_OPEN - timedelta(hours=4)


@dataclass(frozen=True)
class EvaluatorWorld:
    policy: FusionPolicy
    command: AssessmentCommand
    evidence: FirstSliceEvidenceBundle
    evaluated_at: datetime
    bars_15m: list[OhlcvBar]
    bars_4h: list[OhlcvBar]
    snapshot: TradeStreamSnapshot | None
    trigger: OhlcvBar


def _grace() -> timedelta:
    return timedelta(seconds=first_slice_freshness_policy().ohlcv_post_close_grace_seconds)


def build_pattern_15m_bars(
    *,
    trigger_volume: Decimal = Decimal("200"),
    quiet_volume: Decimal = Decimal("20"),
    trigger_revision: int = 1,
    forming_trigger: bool = False,
) -> list[OhlcvBar]:
    instrument = binance_usdm_btcusdt()
    count = FIRST_SLICE_MIN_FINAL_15M
    bars: list[OhlcvBar] = []
    for index in range(count):
        open_time = TRIGGER_OPEN - (interval_timedelta(Timeframe.M15) * (count - 1 - index))
        is_swing = index == SWING_INDEX
        is_trigger = index == count - 1
        if is_swing:
            open_, high, low, close = (
                Decimal("100000"),
                SWING_HIGH,
                Decimal("99990"),
                Decimal("100050"),
            )
            volume = quiet_volume
        elif is_trigger:
            open_, high, low, close = (
                Decimal("100210"),
                Decimal("100220"),
                Decimal("100050"),
                Decimal("100080"),
            )
            volume = trigger_volume
        else:
            open_, high, low, close = (
                Decimal("100000"),
                Decimal("100010"),
                Decimal("99990"),
                Decimal("100000"),
            )
            volume = quiet_volume
        quote = ((open_ + close) / Decimal("2")) * volume
        bars.append(
            build_ohlcv_bar(
                instrument=instrument,
                timeframe=Timeframe.M15,
                interval_start=open_time,
                open_=open_,
                high=high,
                low=low,
                close=close,
                base_volume=volume,
                quote_volume=quote,
                evaluated_at=EVALUATED_AT,
                grace=_grace(),
                provider_complete=not (is_trigger and forming_trigger),
                trade_count=2,
                adapter_version=ADAPTER_VERSION,
                revision=trigger_revision if is_trigger else 1,
            )
        )
    return bars


def build_context_4h_bars() -> list[OhlcvBar]:
    return build_closed_bars(
        timeframe=Timeframe.H4,
        count=FIRST_SLICE_MIN_FINAL_4H,
        last_open=LAST_4H_OPEN,
        evaluated_at=EVALUATED_AT,
        instrument=binance_usdm_btcusdt(),
    )


def build_slice_trades(
    bars_15m: list[OhlcvBar],
    *,
    mode: str = "confirmed",
) -> list[TradeEvent]:
    trigger = bars_15m[-1]
    window_bars = bars_15m[-(FIRST_SLICE_CVD_LOOKBACK_BARS + 1) :]
    trades: list[TradeEvent] = []
    sequence = FIRST_TRADE_SEQUENCE
    for bar in window_bars:
        is_trigger = bar.source_event_id == trigger.source_event_id
        offset = bars_15m.index(bar) - SWING_INDEX
        if is_trigger:
            specs = _trigger_trade_specs(mode, bar)
        elif offset in {1, 2}:
            specs = _post_swing_specs(mode, bar)
        else:
            specs = ((False, bar.interval_start, Decimal("0.001"), bar.open),)
        for buyer_is_maker, event_time, quantity, price in specs:
            trades.append(
                build_trade_event(
                    instrument=bar.instrument,
                    venue_trade_id=str(sequence),
                    sequence=sequence,
                    price=price,
                    quantity=quantity,
                    buyer_is_maker=buyer_is_maker,
                    event_timestamp=event_time,
                    receive_timestamp=EVALUATED_AT,
                    source_connection_id=CONNECTION,
                    adapter_version=ADAPTER_VERSION,
                )
            )
            sequence += 1
    return trades


def _trigger_trade_specs(
    mode: str, bar: OhlcvBar
) -> tuple[tuple[bool, datetime, Decimal, Decimal], ...]:
    terminal = bar.interval_end - timedelta(seconds=2)
    mid = bar.interval_start + timedelta(minutes=1)
    if mode == "imbalance_fail":
        return (
            (False, mid, Decimal("0.90"), bar.close),
            (True, terminal, Decimal("0.10"), bar.close),
        )
    quantity = Decimal("0.01") if mode == "cvd_fail" else Decimal("0.10")
    return (
        (True, mid, quantity, bar.close),
        (True, terminal, quantity, bar.close),
    )


def _post_swing_specs(
    mode: str, bar: OhlcvBar
) -> tuple[tuple[bool, datetime, Decimal, Decimal], ...]:
    event_time = bar.interval_start + timedelta(seconds=1)
    if mode == "cvd_fail":
        return ((False, event_time, Decimal("10"), bar.close),)
    if mode == "imbalance_fail":
        return ((True, event_time, Decimal("10"), bar.close),)
    return ((False, event_time, Decimal("0.001"), bar.close),)


def resistance_evidence(
    *,
    price: Decimal = SWING_HIGH,
    valid: bool = True,
    revision_number: int = 1,
    effective_at: datetime = RESISTANCE_EFFECTIVE,
) -> ManualResistanceEvidence:
    instrument = binance_usdm_btcusdt()
    ref = manual_level(revision_number=revision_number)
    return ManualResistanceEvidence(
        ref=ref,
        price=price,
        timeframe=Timeframe.H4,
        effective_at=effective_at,
        valid=valid,
        venue=VenueId.BINANCE,
        market_type=MarketType.PERPETUAL,
        instrument_id=instrument.instrument_id,
    )


def _observation(bar: OhlcvBar, timeframe: Timeframe) -> PublicMarketObservation:
    return observation_from_ohlcv(
        bar,
        identity=first_slice_identity(timeframe=timeframe, replay=True),
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=FreshnessState.FRESH,
    )


def make_command(
    *,
    trigger: OhlcvBar,
    context: OhlcvBar,
    adapter_kind: EvidenceAdapterKind,
    resistance: ManualResistanceEvidence | None,
    stale: bool = False,
    observation_order: tuple[int, ...] | None = None,
    snapshot: TradeStreamSnapshot | None = None,
    series_15m: list[OhlcvBar] | None = None,
) -> AssessmentCommand:
    policy = fusion_policy()
    if snapshot is not None and series_15m is not None:
        identity = first_slice_identity(timeframe=Timeframe.M15, replay=True)
        closed = require_closed_series(
            list(series_15m),
            identity=identity,
            timeframe=Timeframe.M15,
            evaluated_at=EVALUATED_AT,
            min_bars=min(len(series_15m), FIRST_SLICE_MIN_FINAL_15M),
        )
        live_window = live_confirmation_window_open(
            closed_interval_end=trigger.interval_end,
            evaluated_at=EVALUATED_AT,
        )
        cvd = first_slice_cvd_window(
            identity=identity,
            series_15m=closed,
            snapshot=snapshot,
            created_at=EVALUATED_AT,
            require_live_freshness=live_window,
        )
        signed_flow = bar_signed_quote_flow(
            identity=identity,
            bar=trigger,
            snapshot=snapshot,
            evaluated_at=EVALUATED_AT,
            require_live_freshness=live_window,
        )
        command = build_first_slice_assessment_command(
            organization_id=ORG_ID,
            policy=policy,
            trigger=trigger,
            context=context,
            trigger_identity=identity,
            context_identity=first_slice_identity(timeframe=Timeframe.H4, replay=True),
            evaluated_at=EVALUATED_AT,
            freshness_state=FreshnessState.FRESH,
            adapter_kind=adapter_kind,
            cvd=cvd,
            signed_flow=signed_flow,
            coverage=snapshot.coverage,
            manual_level_revision=None if resistance is None else resistance.ref,
        )
    else:
        trigger_obs = _observation(trigger, Timeframe.M15)
        context_obs = _observation(context, Timeframe.H4)
        cvd_obs = _observation(trigger, Timeframe.M15)
        command = AssessmentCommand(
            organization_id=ORG_ID,
            strategy_version_id=STRATEGY_VERSION_ID,
            executable_setup=policy.executable_setup,
            fusion_policy_version=policy.policy_version,
            finality_policy_version=policy.finality_policy_version,
            freshness_policy_version=policy.freshness_policy_version,
            direction=TradeDirection.SHORT,
            evidence_identity=first_slice_identity(timeframe=Timeframe.M15, replay=True),
            interval=HalfOpenInterval(start=trigger.interval_start, end=trigger.interval_end),
            trigger=TriggerIdentity(
                natural_event_id=trigger.source_event_id, revision=trigger.revision
            ),
            mandatory_evidence_roles=(
                EvidenceRole.TRIGGER_OHLCV,
                EvidenceRole.CONTEXT_OHLCV,
                EvidenceRole.CVD_WINDOW,
            ),
            public_observations=(trigger_obs, context_obs, cvd_obs),
            selected_roles=(
                EvidenceRole.TRIGGER_OHLCV,
                EvidenceRole.CONTEXT_OHLCV,
                EvidenceRole.CVD_WINDOW,
            ),
            source_set=semantic_sources(),
            manual_level_revision=None if resistance is None else resistance.ref,
            adapter_kind=adapter_kind,
        )
    if stale:
        observations = list(command.public_observations)
        observations[0] = observations[0].model_copy(
            update={"freshness_state": FreshnessState.STALE}
        )
        command = command.model_copy(update={"public_observations": tuple(observations)})
    if observation_order is not None:
        pairs = list(zip(command.public_observations, command.selected_roles, strict=True))
        reordered = [pairs[index] for index in observation_order]
        observations, roles = zip(*reordered, strict=True)
        command = command.model_copy(
            update={"public_observations": tuple(observations), "selected_roles": tuple(roles)}
        )
    return command


def subsequent_bars(trigger: OhlcvBar, *, count: int, high: Decimal) -> list[OhlcvBar]:
    bars: list[OhlcvBar] = []
    for index in range(count):
        open_time = trigger.interval_end + (interval_timedelta(Timeframe.M15) * index)
        open_ = Decimal("100000")
        close = Decimal("100000")
        low = Decimal("99990")
        bars.append(
            build_ohlcv_bar(
                instrument=trigger.instrument,
                timeframe=Timeframe.M15,
                interval_start=open_time,
                open_=open_,
                high=high,
                low=low,
                close=close,
                base_volume=Decimal("20"),
                quote_volume=Decimal("2000000"),
                evaluated_at=open_time + interval_timedelta(Timeframe.M15) + timedelta(seconds=5),
                grace=_grace(),
                adapter_version=ADAPTER_VERSION,
            )
        )
    return bars


def make_world(
    *,
    pattern_bars: bool = True,
    trigger_volume: Decimal = Decimal("200"),
    trade_mode: str = "confirmed",
    resistance_price: Decimal = SWING_HIGH,
    resistance_valid: bool = True,
    include_resistance: bool = True,
    include_snapshot: bool = True,
    forming_trigger: bool = False,
    trigger_revision: int = 1,
    adapter_kind: EvidenceAdapterKind = EvidenceAdapterKind.WATCHER,
    subsequent: tuple[OhlcvBar, ...] = (),
    bar_15m_count: int | None = None,
    stale_command: bool = False,
    observation_order: tuple[int, ...] | None = None,
    shuffle_bars: bool = False,
) -> EvaluatorWorld:
    if pattern_bars:
        bars_15m = build_pattern_15m_bars(
            trigger_volume=trigger_volume,
            trigger_revision=trigger_revision,
            forming_trigger=forming_trigger,
        )
    else:
        bars_15m = build_closed_bars(
            timeframe=Timeframe.M15,
            count=bar_15m_count or FIRST_SLICE_MIN_FINAL_15M,
            last_open=TRIGGER_OPEN,
            evaluated_at=EVALUATED_AT,
        )
    if bar_15m_count is not None and pattern_bars:
        bars_15m = bars_15m[-bar_15m_count:]
    bars_4h = build_context_4h_bars()
    trigger = bars_15m[-1]
    resistance = (
        resistance_evidence(price=resistance_price, valid=resistance_valid)
        if include_resistance
        else None
    )
    snapshot: TradeStreamSnapshot | None = None
    if include_snapshot and not forming_trigger:
        trades = build_slice_trades(bars_15m, mode=trade_mode)
        snapshot = proven_snapshot(
            trades,
            start=first_slice_baseline_open(trigger),
            end=trigger.interval_end,
            connection=CONNECTION,
        )
    stored_15m = list(reversed(bars_15m)) if shuffle_bars else bars_15m
    stored_4h = list(reversed(bars_4h)) if shuffle_bars else bars_4h
    resistances = () if resistance is None else (resistance,)
    if shuffle_bars and resistances:
        resistances = resistances
    command = make_command(
        trigger=trigger,
        context=bars_4h[-1],
        adapter_kind=adapter_kind,
        resistance=resistance,
        stale=stale_command,
        observation_order=observation_order,
        snapshot=snapshot,
        series_15m=bars_15m,
    )
    evidence = FirstSliceEvidenceBundle(
        bars_15m=tuple(stored_15m),
        bars_4h=tuple(stored_4h),
        snapshot=snapshot,
        resistances=resistances,
        subsequent_final_15m=subsequent,
    )
    return EvaluatorWorld(
        policy=fusion_policy(),
        command=command,
        evidence=evidence,
        evaluated_at=EVALUATED_AT,
        bars_15m=bars_15m,
        bars_4h=bars_4h,
        snapshot=snapshot,
        trigger=trigger,
    )
