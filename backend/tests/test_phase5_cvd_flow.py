"""Phase 5 CVD exact arithmetic and signed quote flow."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.market_contracts.cursor import TradeStreamAssembler
from app.market_contracts.cvd import (
    FIRST_SLICE_CVD_LOOKBACK_BARS,
    accumulate_signed_quote,
    cvd_at_close,
    first_slice_baseline_open,
    first_slice_cvd_window,
)
from app.market_contracts.errors import IncompleteWarmUpError
from app.market_contracts.flow import bar_signed_quote_flow
from app.market_contracts.ohlcv import require_closed_series
from app.market_contracts.replay_fixtures import (
    FIXTURE_CONNECTION_ID,
    canonical_first_slice_fixture,
)
from app.market_contracts.trades import signed_quote_value
from app.schemas.common import Timeframe
from tests.support.phase5_market import (
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
        trades=snapshot.trades,
        source_connection_id=FIXTURE_CONNECTION_ID,
        start_cursor_id=snapshot.cursor.cursor_id,
        end_cursor_id=snapshot.cursor.cursor_id,
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
