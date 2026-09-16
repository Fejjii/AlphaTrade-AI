"""Phase 5 CVD exact arithmetic and signed quote flow."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.market_contracts.cursor import TradeStreamAssembler, TradeStreamCursor, TradeStreamSnapshot
from app.market_contracts.cvd import (
    FIRST_SLICE_CVD_LOOKBACK_BARS,
    accumulate_signed_quote,
    cvd_at_close,
    first_slice_baseline_open,
    first_slice_cvd_window,
)
from app.market_contracts.enums import GapState, ReconnectState, WarmUpStatus
from app.market_contracts.errors import GapDetectedError, IncompleteWarmUpError, StaleEvidenceError
from app.market_contracts.flow import bar_signed_quote_flow
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.ohlcv import require_closed_series
from app.market_contracts.replay_fixtures import (
    FIXTURE_CONNECTION_ID,
    canonical_first_slice_fixture,
)
from app.market_contracts.trades import signed_quote_value
from app.schemas.common import Timeframe
from tests.support.phase5_market import (
    CONNECTION,
    EVALUATED_AT,
    TRIGGER_OPEN,
    consecutive_bars,
    identity,
    trade,
)


def test_cvd_exact_arithmetic() -> None:
    buy = trade(
        sequence=1,
        price="100.5",
        quantity="0.2",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN + timedelta(seconds=1),
    )
    sell = trade(
        sequence=2,
        price="99.25",
        quantity="0.4",
        buyer_is_maker=True,
        event_time=TRIGGER_OPEN + timedelta(seconds=2),
    )
    assert signed_quote_value(buy) == Decimal("20.10")
    assert signed_quote_value(sell) == Decimal("-39.70")
    signed, total = accumulate_signed_quote([buy, sell])
    assert signed == Decimal("-19.60")
    assert total == Decimal("59.80")
    assert buy.quote_quantity == buy.price * buy.quantity
    assert sell.quote_quantity == sell.price * sell.quantity


def test_signed_quote_delta_ratio() -> None:
    bar = consecutive_bars(1)[0]
    buy = trade(
        sequence=1,
        price="10",
        quantity="2",
        buyer_is_maker=False,
        event_time=bar.interval_start + timedelta(seconds=1),
    )
    sell = trade(
        sequence=2,
        price="10",
        quantity="8",
        buyer_is_maker=True,
        event_time=bar.interval_start + timedelta(seconds=2),
    )
    flow = bar_signed_quote_flow(identity=identity(), bar=bar, trades=[buy, sell])
    assert flow.signed_quote_delta == Decimal("-60")
    assert flow.total_quote_volume == Decimal("100")
    assert flow.signed_flow_ratio == Decimal("-0.6")
    assert flow.buy_quote_volume == Decimal("20")
    assert flow.sell_quote_volume == Decimal("80")


def test_signed_flow_fails_when_volume_is_zero() -> None:
    bar = consecutive_bars(1)[0]
    with pytest.raises(IncompleteWarmUpError):
        bar_signed_quote_flow(identity=identity(), bar=bar, trades=[])


def test_first_slice_cvd_baseline_is_t_minus_32_open() -> None:
    fixture = canonical_first_slice_fixture()
    bars = fixture["bars_15m"]
    trigger = bars[-1]
    baseline_open = first_slice_baseline_open(trigger)
    assert baseline_open == bars[-(FIRST_SLICE_CVD_LOOKBACK_BARS + 1)].interval_start
    assembler = TradeStreamAssembler(
        identity(),
        connected_at=EVALUATED_AT,
        connection_identity=FIXTURE_CONNECTION_ID,
        expected_contiguous_count=len(fixture["trades"]),
    )
    snapshot = assembler.ingest(list(fixture["trades"]), observed_at=EVALUATED_AT)
    series = require_closed_series(
        bars,
        identity=identity(),
        timeframe=Timeframe.M15,
        evaluated_at=EVALUATED_AT,
        min_bars=100,
    )
    window = first_slice_cvd_window(
        identity=identity(),
        series_15m=series,
        snapshot=snapshot,
        created_at=EVALUATED_AT,
    )
    assert window.window_start == baseline_open
    assert window.window_end == trigger.interval_end
    assert window.baseline == Decimal("0")
    assert window.warm_up_complete is True
    cvd_trigger = cvd_at_close(
        snapshot.trades,
        window_start=window.window_start,
        bar_end=trigger.interval_end,
        baseline=window.baseline,
    )
    assert cvd_trigger == window.baseline + window.signed_quote_delta
    assert window.event_count == len(fixture["trades"])


def _forged_usable_snapshot(trades: list) -> TradeStreamSnapshot:
    last = trades[-1]
    cursor = with_content_hash(
        TradeStreamCursor(
            cursor_id=uuid4(),
            identity=identity(),
            connection_identity=CONNECTION,
            last_event_id=last.venue_trade_id,
            last_sequence=last.sequence,
            connected_at=EVALUATED_AT,
            last_event_at=last.event_timestamp,
            reconnect_count=0,
            reconnect_state=ReconnectState.CONTINUOUS,
            gap_state=GapState.NONE,
            warm_up_status=WarmUpStatus.COMPLETE,
            updated_at=EVALUATED_AT,
            content_hash="0" * 64,
        )
    )
    return TradeStreamSnapshot(cursor=cursor, trades=trades, usable=True)


def _first_slice_series() -> object:
    bars = consecutive_bars(FIRST_SLICE_CVD_LOOKBACK_BARS + 1)
    return require_closed_series(
        bars,
        identity=identity(),
        timeframe=Timeframe.M15,
        evaluated_at=EVALUATED_AT,
        min_bars=FIRST_SLICE_CVD_LOOKBACK_BARS + 1,
    )


def test_cvd_missing_sequence_fails_even_if_marked_complete() -> None:
    start = TRIGGER_OPEN - timedelta(minutes=15 * FIRST_SLICE_CVD_LOOKBACK_BARS)
    t1 = trade(
        sequence=1,
        price="100",
        quantity="1",
        buyer_is_maker=False,
        event_time=start + timedelta(seconds=1),
    )
    t3 = trade(
        sequence=3,
        price="100",
        quantity="1",
        buyer_is_maker=True,
        event_time=TRIGGER_OPEN + timedelta(seconds=1),
    )
    snapshot = _forged_usable_snapshot([t1, t3])
    assert snapshot.usable is True
    assert snapshot.cursor.gap_state is GapState.NONE
    with pytest.raises(GapDetectedError, match="sequence gap"):
        first_slice_cvd_window(
            identity=identity(),
            series_15m=_first_slice_series(),
            snapshot=snapshot,
            created_at=EVALUATED_AT,
        )


def test_first_slice_cvd_rejects_stale_terminal_trade() -> None:
    start = TRIGGER_OPEN - timedelta(minutes=15 * FIRST_SLICE_CVD_LOOKBACK_BARS)
    trades = [
        trade(
            sequence=index,
            price="100",
            quantity="1",
            buyer_is_maker=index % 2 == 0,
            event_time=start + timedelta(seconds=index),
            connection=CONNECTION,
        )
        for index in range(1, 6)
    ]
    trades[-1] = trade(
        sequence=5,
        price="100",
        quantity="1",
        buyer_is_maker=True,
        event_time=EVALUATED_AT - timedelta(seconds=11),
        connection=CONNECTION,
    )
    assembler = TradeStreamAssembler(
        identity(),
        connected_at=EVALUATED_AT,
        connection_identity=CONNECTION,
        expected_contiguous_count=len(trades),
    )
    snapshot = assembler.ingest(trades, observed_at=EVALUATED_AT)
    with pytest.raises(StaleEvidenceError):
        first_slice_cvd_window(
            identity=identity(),
            series_15m=_first_slice_series(),
            snapshot=snapshot,
            created_at=EVALUATED_AT,
        )
