"""Deterministic first-slice BTCUSDT perpetual replay fixtures (no network)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.market_contracts.cvd import FIRST_SLICE_CVD_LOOKBACK_BARS
from app.market_contracts.first_slice import (
    CANONICAL_EVALUATED_AT,
    CANONICAL_TRIGGER_INTERVAL_START,
    FIRST_SLICE_MIN_FINAL_4H,
    FIRST_SLICE_MIN_FINAL_15M,
    first_slice_identity,
)
from app.market_contracts.freshness import first_slice_freshness_policy
from app.market_contracts.identity import (
    ADAPTER_VERSION,
    InstrumentIdentity,
    binance_usdm_btcusdt,
    interval_timedelta,
)
from app.market_contracts.ohlcv import OhlcvBar, build_ohlcv_bar
from app.market_contracts.trades import TradeEvent, build_trade_event
from app.schemas.common import Timeframe

FIXTURE_ID = "first-slice-btcusdt-usdm/v1"
FIXTURE_CONNECTION_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1")
TRADES_PER_BAR = 4
FIRST_TRADE_SEQUENCE = 8_000_000


def _bar_open(last_open: datetime, timeframe: Timeframe, count: int, index: int) -> datetime:
    delta = interval_timedelta(timeframe)
    first_open = last_open - (delta * (count - 1))
    return first_open + (delta * index)


def _ohlc_for_index(
    index: int, *, timeframe: Timeframe
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    base = Decimal("100000") + Decimal(index)
    if timeframe is Timeframe.H4:
        base = Decimal("100000") + (Decimal(index) * Decimal("8"))
    open_ = base
    close = base + Decimal("2")
    high = close + Decimal("1")
    low = open_ - Decimal("1")
    return open_, high, low, close


def build_closed_bars(
    *,
    timeframe: Timeframe,
    count: int,
    last_open: datetime,
    evaluated_at: datetime,
    instrument: InstrumentIdentity | None = None,
) -> list[OhlcvBar]:
    inst = instrument or binance_usdm_btcusdt()
    grace = timedelta(seconds=first_slice_freshness_policy().ohlcv_post_close_grace_seconds)
    bars: list[OhlcvBar] = []
    for index in range(count):
        open_time = _bar_open(last_open, timeframe, count, index)
        open_, high, low, close = _ohlc_for_index(index, timeframe=timeframe)
        base_volume = Decimal("10") + Decimal(index)
        quote_volume = ((open_ + close) / Decimal("2")) * base_volume
        bars.append(
            build_ohlcv_bar(
                instrument=inst,
                timeframe=timeframe,
                interval_start=open_time,
                open_=open_,
                high=high,
                low=low,
                close=close,
                base_volume=base_volume,
                quote_volume=quote_volume,
                evaluated_at=evaluated_at,
                grace=grace,
                trade_count=TRADES_PER_BAR,
                adapter_version=ADAPTER_VERSION,
            )
        )
    return bars


def build_window_trades(
    bars: list[OhlcvBar],
    *,
    source_connection_id: UUID,
    receive_at: datetime,
    lookback: int = FIRST_SLICE_CVD_LOOKBACK_BARS,
) -> list[TradeEvent]:
    """Ordered trades covering [T-lookback open, T end) with exact Decimal arithmetic."""
    trigger = bars[-1]
    window_bars = bars[-(lookback + 1) :]
    trades: list[TradeEvent] = []
    sequence = FIRST_TRADE_SEQUENCE
    for bar in window_bars:
        step = (bar.interval_end - bar.interval_start) / (TRADES_PER_BAR + 1)
        is_trigger = bar.source_event_id == trigger.source_event_id
        for slot in range(TRADES_PER_BAR):
            # Buyer-initiated on even slots except the trigger bar, which is seller-led.
            buyer_is_maker = is_trigger or slot % 2 == 1
            price = bar.open + Decimal(slot)
            quantity = Decimal("0.01") + (Decimal(slot) * Decimal("0.001"))
            event_time = bar.interval_start + (step * (slot + 1))
            if is_trigger and slot == TRADES_PER_BAR - 1:
                # Keep the terminal in-window trade inside the 10s first-slice freshness bound.
                event_time = bar.interval_end - timedelta(seconds=2)
            trades.append(
                build_trade_event(
                    instrument=bar.instrument,
                    venue_trade_id=str(sequence),
                    sequence=sequence,
                    price=price,
                    quantity=quantity,
                    buyer_is_maker=buyer_is_maker,
                    event_timestamp=event_time,
                    receive_timestamp=receive_at,
                    source_connection_id=source_connection_id,
                    adapter_version=ADAPTER_VERSION,
                )
            )
            sequence += 1
    return trades


def canonical_first_slice_fixture(
    *,
    evaluated_at: datetime | None = None,
    connection_id: UUID | None = None,
) -> dict[str, Any]:
    clock = evaluated_at or CANONICAL_EVALUATED_AT
    connection = connection_id or FIXTURE_CONNECTION_ID
    instrument = binance_usdm_btcusdt()
    bars_15m = build_closed_bars(
        timeframe=Timeframe.M15,
        count=FIRST_SLICE_MIN_FINAL_15M,
        last_open=CANONICAL_TRIGGER_INTERVAL_START,
        evaluated_at=clock,
        instrument=instrument,
    )
    last_4h_open = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    bars_4h = build_closed_bars(
        timeframe=Timeframe.H4,
        count=FIRST_SLICE_MIN_FINAL_4H,
        last_open=last_4h_open,
        evaluated_at=clock,
        instrument=instrument,
    )
    trades = build_window_trades(
        bars_15m,
        source_connection_id=connection,
        receive_at=clock,
    )
    return {
        "fixture_id": FIXTURE_ID,
        "evaluated_at": clock,
        "connection_id": connection,
        "identity_15m": first_slice_identity(timeframe=Timeframe.M15, replay=True),
        "identity_4h": first_slice_identity(timeframe=Timeframe.H4, replay=True),
        "bars_15m": bars_15m,
        "bars_4h": bars_4h,
        "trades": trades,
    }
