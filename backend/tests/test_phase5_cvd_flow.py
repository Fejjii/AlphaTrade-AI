"""Phase 5 CVD and signed-flow arithmetic, identity, coverage, and freshness."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.market_contracts.cursor import TradeStreamSnapshot
from app.market_contracts.cvd import (
    accumulate_signed_quote,
    build_cvd_window,
    cvd_at_close,
    first_slice_baseline_open,
    first_slice_cvd_window,
)
from app.market_contracts.errors import (
    GapDetectedError,
    IncompleteTradeWindowError,
    IncompleteWarmUpError,
    StaleEvidenceError,
    WrongInstrumentError,
    WrongMarketError,
)
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.flow import bar_signed_quote_flow
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.ohlcv import ClosedOhlcvSeries, OhlcvBar, require_closed_series
from app.market_contracts.replay_fixtures import (
    FIXTURE_CONNECTION_ID,
    canonical_first_slice_fixture,
)
from app.market_contracts.trades import TradeEvent, signed_quote_value
from app.schemas.common import Timeframe
from tests.support.phase5_market import (
    EVALUATED_AT,
    TRIGGER_OPEN,
    consecutive_bars,
    eth_instrument,
    identity,
    proven_snapshot,
    spot_identity,
    trade,
)


def _first_slice_series() -> ClosedOhlcvSeries:
    fixture = canonical_first_slice_fixture()
    return require_closed_series(
        list(fixture["bars_15m"]),
        identity=identity(),
        timeframe=Timeframe.M15,
        evaluated_at=EVALUATED_AT,
        min_bars=100,
    )


def _cvd_bounds(series: ClosedOhlcvSeries) -> tuple:
    trigger = series.bars[-1]
    return first_slice_baseline_open(trigger), trigger.interval_end


def _complete_cvd_snapshot(series: ClosedOhlcvSeries) -> TradeStreamSnapshot:
    fixture = canonical_first_slice_fixture()
    start, end = _cvd_bounds(series)
    return proven_snapshot(
        list(fixture["trades"]),
        start=start,
        end=end,
        connection=FIXTURE_CONNECTION_ID,
    )


def _trigger_bar() -> OhlcvBar:
    return consecutive_bars(1)[0]


def _trigger_trades(*, terminal_age_seconds: int = 7) -> list[TradeEvent]:
    bar = _trigger_bar()
    return [
        trade(
            sequence=1,
            price="10",
            quantity="2",
            buyer_is_maker=False,
            event_time=bar.interval_start + timedelta(seconds=1),
        ),
        trade(
            sequence=2,
            price="10",
            quantity="8",
            buyer_is_maker=True,
            event_time=EVALUATED_AT - timedelta(seconds=terminal_age_seconds),
        ),
    ]


def _complete_trigger_snapshot(
    trades: list[TradeEvent] | None = None,
) -> TradeStreamSnapshot:
    bar = _trigger_bar()
    return proven_snapshot(
        trades or _trigger_trades(),
        start=bar.interval_start,
        end=bar.interval_end,
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


def test_first_slice_cvd_exact_complete_window_passes() -> None:
    series = _first_slice_series()
    snapshot = _complete_cvd_snapshot(series)
    trigger = series.bars[-1]
    baseline_open = first_slice_baseline_open(trigger)
    window = first_slice_cvd_window(
        identity=identity(),
        series_15m=series,
        snapshot=snapshot,
        created_at=EVALUATED_AT,
    )
    assert snapshot.usable is True
    assert window.window_start == baseline_open
    assert window.window_end == trigger.interval_end
    assert window.baseline == Decimal("0")
    assert window.coverage_proof_id == snapshot.coverage.coverage_proof_id
    cvd_trigger = cvd_at_close(
        snapshot.trades,
        window_start=window.window_start,
        bar_end=trigger.interval_end,
        baseline=window.baseline,
    )
    assert cvd_trigger == window.baseline + window.signed_quote_delta


def test_first_slice_cvd_snapshot_starts_after_required_baseline() -> None:
    series = _first_slice_series()
    start, end = _cvd_bounds(series)
    fixture = canonical_first_slice_fixture()
    late_start = start + timedelta(minutes=15)
    late_trades = [item for item in fixture["trades"] if late_start <= item.event_timestamp < end]
    snapshot = proven_snapshot(
        late_trades,
        start=late_start,
        end=end,
        connection=FIXTURE_CONNECTION_ID,
    )
    with pytest.raises(IncompleteTradeWindowError, match="starts after"):
        first_slice_cvd_window(
            identity=identity(),
            series_15m=series,
            snapshot=snapshot,
            created_at=EVALUATED_AT,
        )


def test_first_slice_cvd_snapshot_ends_before_required_window() -> None:
    series = _first_slice_series()
    start, end = _cvd_bounds(series)
    early_end = end - timedelta(minutes=15)
    fixture = canonical_first_slice_fixture()
    early_trades = [item for item in fixture["trades"] if start <= item.event_timestamp < early_end]
    snapshot = proven_snapshot(
        early_trades,
        start=start,
        end=early_end,
        connection=FIXTURE_CONNECTION_ID,
    )
    with pytest.raises(IncompleteTradeWindowError, match="ends before"):
        first_slice_cvd_window(
            identity=identity(),
            series_15m=series,
            snapshot=snapshot,
            created_at=EVALUATED_AT,
        )


def test_first_slice_cvd_internal_sequence_gap_fails() -> None:
    series = _first_slice_series()
    complete = _complete_cvd_snapshot(series)
    missing = complete.trades[:10] + complete.trades[11:]
    forged = TradeStreamSnapshot.model_construct(
        cursor=complete.cursor,
        trades=missing,
        coverage=complete.coverage,
        usable=True,
    )
    with pytest.raises(GapDetectedError, match="sequence gap"):
        first_slice_cvd_window(
            identity=identity(),
            series_15m=series,
            snapshot=forged,
            created_at=EVALUATED_AT,
        )


@pytest.mark.parametrize(
    "wrong_identity",
    [
        first_slice_identity(timeframe=Timeframe.M15, replay=False, is_live=True),
        spot_identity(),
        identity().model_copy(update={"instrument": eth_instrument()}),
    ],
)
def test_cvd_identity_must_exactly_match_snapshot(
    wrong_identity: EvidenceMarketIdentity,
) -> None:
    series = _first_slice_series()
    snapshot = _complete_cvd_snapshot(series)
    start, end = _cvd_bounds(series)
    with pytest.raises(WrongMarketError, match="does not exactly match"):
        build_cvd_window(
            identity=wrong_identity,
            snapshot=snapshot,
            window_start=start,
            window_end=end,
            baseline=Decimal("0"),
            created_at=EVALUATED_AT,
        )


def test_first_slice_cvd_rejects_stale_terminal_trade() -> None:
    series = _first_slice_series()
    start, end = _cvd_bounds(series)
    trades = [
        trade(
            sequence=1,
            price="100",
            quantity="1",
            buyer_is_maker=False,
            event_time=start + timedelta(seconds=1),
        ),
        trade(
            sequence=2,
            price="100",
            quantity="1",
            buyer_is_maker=True,
            event_time=EVALUATED_AT - timedelta(seconds=11),
        ),
    ]
    snapshot = proven_snapshot(trades, start=start, end=end)
    with pytest.raises(StaleEvidenceError):
        first_slice_cvd_window(
            identity=identity(),
            series_15m=series,
            snapshot=snapshot,
            created_at=EVALUATED_AT,
        )


def test_signed_quote_flow_exact_complete_trigger_coverage() -> None:
    bar = _trigger_bar()
    snapshot = _complete_trigger_snapshot()
    flow = bar_signed_quote_flow(
        identity=identity(),
        bar=bar,
        snapshot=snapshot,
        evaluated_at=EVALUATED_AT,
    )
    assert flow.signed_quote_delta == Decimal("-60")
    assert flow.total_quote_volume == Decimal("100")
    assert flow.signed_flow_ratio == Decimal("-0.6")
    assert flow.buy_quote_volume == Decimal("20")
    assert flow.sell_quote_volume == Decimal("80")
    assert flow.coverage_proof_id == snapshot.coverage.coverage_proof_id


def test_signed_flow_missing_trigger_prefix_fails() -> None:
    bar = _trigger_bar()
    late_start = bar.interval_start + timedelta(minutes=1)
    trades = [
        trade(
            sequence=1,
            price="10",
            quantity="1",
            buyer_is_maker=True,
            event_time=EVALUATED_AT - timedelta(seconds=7),
        )
    ]
    snapshot = proven_snapshot(trades, start=late_start, end=bar.interval_end)
    with pytest.raises(IncompleteTradeWindowError, match="starts after"):
        bar_signed_quote_flow(
            identity=identity(),
            bar=bar,
            snapshot=snapshot,
            evaluated_at=EVALUATED_AT,
        )


def test_signed_flow_missing_trigger_suffix_fails() -> None:
    bar = _trigger_bar()
    early_end = bar.interval_end - timedelta(minutes=1)
    trades = [
        trade(
            sequence=1,
            price="10",
            quantity="1",
            buyer_is_maker=True,
            event_time=early_end - timedelta(seconds=1),
        )
    ]
    snapshot = proven_snapshot(trades, start=bar.interval_start, end=early_end)
    with pytest.raises(IncompleteTradeWindowError, match="ends before"):
        bar_signed_quote_flow(
            identity=identity(),
            bar=bar,
            snapshot=snapshot,
            evaluated_at=EVALUATED_AT,
        )


def test_signed_flow_internal_gap_fails() -> None:
    bar = _trigger_bar()
    complete = _complete_trigger_snapshot(
        [
            trade(
                sequence=index,
                price="10",
                quantity="1",
                buyer_is_maker=False,
                event_time=bar.interval_start + timedelta(seconds=index),
            )
            for index in range(1, 4)
        ]
    )
    forged = TradeStreamSnapshot.model_construct(
        cursor=complete.cursor,
        trades=[complete.trades[0], complete.trades[2]],
        coverage=complete.coverage,
        usable=True,
    )
    with pytest.raises(GapDetectedError, match="sequence gap"):
        bar_signed_quote_flow(
            identity=identity(),
            bar=bar,
            snapshot=forged,
            evaluated_at=EVALUATED_AT,
        )


def test_signed_flow_wrong_instrument_fails() -> None:
    bar = _trigger_bar()
    complete = _complete_trigger_snapshot()
    wrong = trade(
        sequence=1,
        price="10",
        quantity="2",
        buyer_is_maker=False,
        event_time=bar.interval_start + timedelta(seconds=1),
        instrument=eth_instrument(),
    )
    forged = TradeStreamSnapshot.model_construct(
        cursor=complete.cursor,
        trades=[wrong, complete.trades[-1]],
        coverage=complete.coverage,
        usable=True,
    )
    with pytest.raises(WrongInstrumentError):
        bar_signed_quote_flow(
            identity=identity(),
            bar=bar,
            snapshot=forged,
            evaluated_at=EVALUATED_AT,
        )


def test_signed_flow_wrong_market_identity_fails() -> None:
    with pytest.raises(WrongMarketError):
        bar_signed_quote_flow(
            identity=spot_identity(),
            bar=_trigger_bar(),
            snapshot=_complete_trigger_snapshot(),
            evaluated_at=EVALUATED_AT,
        )


def test_signed_flow_stale_terminal_evidence_fails() -> None:
    bar = _trigger_bar()
    snapshot = _complete_trigger_snapshot(_trigger_trades(terminal_age_seconds=11))
    with pytest.raises(StaleEvidenceError):
        bar_signed_quote_flow(
            identity=identity(),
            bar=bar,
            snapshot=snapshot,
            evaluated_at=EVALUATED_AT,
        )


def test_signed_flow_fails_when_volume_is_zero() -> None:
    bar = _trigger_bar()
    snapshot = proven_snapshot([], start=bar.interval_start, end=bar.interval_end)
    with pytest.raises(IncompleteWarmUpError):
        bar_signed_quote_flow(
            identity=identity(),
            bar=bar,
            snapshot=snapshot,
            evaluated_at=EVALUATED_AT,
        )
