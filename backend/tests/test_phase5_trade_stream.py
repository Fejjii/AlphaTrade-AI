"""Phase 5 ordered trades, cursor recovery, and gap detection."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.market_contracts.adapters.http import ReadOnlyHttpGetClient
from app.market_contracts.cursor import TradeStreamAssembler, detect_sequence_gap
from app.market_contracts.enums import (
    AggressorSide,
    DataCompleteness,
    GapState,
    MarketType,
    ReconnectState,
    WarmUpStatus,
)
from app.market_contracts.errors import (
    CursorRecoveryError,
    DuplicateDataError,
    GapDetectedError,
    NetworkMutationForbiddenError,
    OutOfOrderTradesError,
    UnknownAggressorError,
    WrongInstrumentError,
    WrongMarketError,
    WrongSourceError,
)
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import binance_usdm_btcusdt
from app.market_contracts.trades import aggressor_from_buyer_is_maker, build_trade_event
from tests.support.phase5_market import (
    CONNECTION,
    EVALUATED_AT,
    TRIGGER_OPEN,
    eth_instrument,
    identity,
    trade,
)


def _assembler(*, expected: int | None = None) -> TradeStreamAssembler:
    return TradeStreamAssembler(
        identity(),
        connected_at=EVALUATED_AT,
        connection_identity=CONNECTION,
        expected_contiguous_count=expected,
    )


def test_trade_aggressor_semantics() -> None:
    assert aggressor_from_buyer_is_maker(True) is AggressorSide.SELL
    assert aggressor_from_buyer_is_maker(False) is AggressorSide.BUY
    sell = trade(
        sequence=1,
        price="100",
        quantity="1",
        buyer_is_maker=True,
        event_time=TRIGGER_OPEN + timedelta(seconds=1),
    )
    buy = trade(
        sequence=2,
        price="100",
        quantity="1",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN + timedelta(seconds=2),
    )
    assert sell.aggressor_side is AggressorSide.SELL
    assert buy.aggressor_side is AggressorSide.BUY


def test_unknown_aggressor_fails_closed() -> None:
    with pytest.raises(UnknownAggressorError):
        build_trade_event(
            instrument=binance_usdm_btcusdt(),
            venue_trade_id="9",
            sequence=9,
            price=trade(
                sequence=1,
                price="1",
                quantity="1",
                buyer_is_maker=False,
                event_time=TRIGGER_OPEN,
            ).price,
            quantity=trade(
                sequence=1,
                price="1",
                quantity="1",
                buyer_is_maker=False,
                event_time=TRIGGER_OPEN,
            ).quantity,
            buyer_is_maker=None,
            event_timestamp=TRIGGER_OPEN,
            receive_timestamp=EVALUATED_AT,
            source_connection_id=CONNECTION,
            adapter_version="binance-usdm-perpetual/v1",
        )


def test_gap_detection() -> None:
    assert detect_sequence_gap(10, 11) is None
    assert detect_sequence_gap(10, 13) == (11, 12)
    assembler = _assembler()
    first = trade(
        sequence=10,
        price="100",
        quantity="1",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN,
    )
    assembler.ingest([first], observed_at=EVALUATED_AT)
    skipped = trade(
        sequence=13,
        price="100",
        quantity="1",
        buyer_is_maker=True,
        event_time=TRIGGER_OPEN + timedelta(seconds=3),
    )
    with pytest.raises(GapDetectedError, match="gap 11-12"):
        assembler.ingest([skipped], observed_at=EVALUATED_AT)
    assert assembler.cursor.gap_state is GapState.CONFIRMED


def test_duplicate_trade_conflict() -> None:
    assembler = _assembler()
    original = trade(
        sequence=1,
        price="100",
        quantity="1",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN,
    )
    assembler.ingest([original], observed_at=EVALUATED_AT)
    conflict = trade(
        sequence=1,
        price="101",
        quantity="1",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN,
    )
    with pytest.raises(DuplicateDataError, match="Conflicting"):
        assembler.ingest([conflict], observed_at=EVALUATED_AT)


def test_duplicate_trade_idempotent_when_identical() -> None:
    assembler = _assembler()
    original = trade(
        sequence=1,
        price="100",
        quantity="1",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN,
    )
    assembler.ingest([original], observed_at=EVALUATED_AT)
    snapshot = assembler.ingest([original], observed_at=EVALUATED_AT)
    assert len(snapshot.trades) == 1


def test_out_of_order_trades() -> None:
    assembler = _assembler()
    later = trade(
        sequence=2,
        price="100",
        quantity="1",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN + timedelta(seconds=2),
    )
    assembler.ingest([later], observed_at=EVALUATED_AT)
    earlier = trade(
        sequence=1,
        price="100",
        quantity="1",
        buyer_is_maker=True,
        event_time=TRIGGER_OPEN,
    )
    with pytest.raises(OutOfOrderTradesError):
        assembler.ingest([earlier], observed_at=EVALUATED_AT)


def test_stream_ingestion_rejects_wrong_instrument() -> None:
    wrong = trade(
        sequence=1,
        price="100",
        quantity="1",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN,
        instrument=eth_instrument(),
    )
    with pytest.raises(WrongInstrumentError):
        _assembler().ingest([wrong], observed_at=EVALUATED_AT)


def test_stream_ingestion_rejects_wrong_market() -> None:
    valid = trade(
        sequence=1,
        price="100",
        quantity="1",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN,
    )
    wrong = with_content_hash(valid.model_copy(update={"market_type": MarketType.SPOT}))
    with pytest.raises(WrongMarketError):
        _assembler().ingest([wrong], observed_at=EVALUATED_AT)


def test_stream_ingestion_rejects_wrong_source_identity() -> None:
    wrong = build_trade_event(
        instrument=binance_usdm_btcusdt(),
        venue_trade_id="1",
        sequence=1,
        price=trade(
            sequence=1,
            price="100",
            quantity="1",
            buyer_is_maker=False,
            event_time=TRIGGER_OPEN,
        ).price,
        quantity=trade(
            sequence=1,
            price="100",
            quantity="1",
            buyer_is_maker=False,
            event_time=TRIGGER_OPEN,
        ).quantity,
        buyer_is_maker=False,
        event_timestamp=TRIGGER_OPEN,
        receive_timestamp=EVALUATED_AT,
        source_connection_id=CONNECTION,
        adapter_version="unapproved-source/v1",
    )
    with pytest.raises(WrongSourceError):
        _assembler().ingest([wrong], observed_at=EVALUATED_AT)


def test_cursor_recovery_contiguous_backfill() -> None:
    assembler = _assembler(expected=3)
    t1 = trade(sequence=1, price="100", quantity="1", buyer_is_maker=False, event_time=TRIGGER_OPEN)
    t2 = trade(
        sequence=2,
        price="100",
        quantity="1",
        buyer_is_maker=True,
        event_time=TRIGGER_OPEN + timedelta(seconds=1),
    )
    assembler.ingest([t1, t2], observed_at=EVALUATED_AT)
    assembler.begin_reconnect(observed_at=EVALUATED_AT + timedelta(seconds=1))
    assert assembler.cursor.reconnect_state is ReconnectState.RECONNECTING
    t3 = trade(
        sequence=3,
        price="100",
        quantity="1",
        buyer_is_maker=False,
        event_time=TRIGGER_OPEN + timedelta(seconds=2),
        connection=assembler.connection_identity,
    )
    snapshot = assembler.recover_from_backfill(
        [t1, t2, t3],
        observed_at=EVALUATED_AT + timedelta(seconds=2),
    )
    assert snapshot.cursor.gap_state is GapState.NONE
    assert snapshot.cursor.warm_up_status is WarmUpStatus.COMPLETE
    assert snapshot.coverage.completeness is DataCompleteness.PARTIAL
    assert snapshot.usable is False
    assert [item.sequence for item in snapshot.trades] == [1, 2, 3]


def test_cursor_recovery_unresolved_gap_fails_closed() -> None:
    assembler = _assembler()
    t1 = trade(sequence=1, price="100", quantity="1", buyer_is_maker=False, event_time=TRIGGER_OPEN)
    assembler.ingest([t1], observed_at=EVALUATED_AT)
    assembler.begin_reconnect(observed_at=EVALUATED_AT + timedelta(seconds=1))
    cursor_id = assembler.cursor.cursor_id
    connection = assembler.connection_identity
    t4 = trade(
        sequence=4,
        price="100",
        quantity="1",
        buyer_is_maker=True,
        event_time=TRIGGER_OPEN + timedelta(seconds=4),
        connection=connection,
    )
    with pytest.raises(CursorRecoveryError):
        assembler.recover_from_backfill([t4], observed_at=EVALUATED_AT + timedelta(seconds=2))
    assert assembler.cursor.gap_state is GapState.CONFIRMED
    assert assembler.cursor.reconnect_state is ReconnectState.RECONNECTING
    assert assembler.cursor.cursor_id == cursor_id
    assert assembler.connection_identity == connection
    filled = [
        trade(
            sequence=sequence,
            price="100",
            quantity="1",
            buyer_is_maker=False,
            event_time=TRIGGER_OPEN + timedelta(seconds=sequence),
            connection=connection,
        )
        for sequence in (2, 3, 4)
    ]
    recovered = assembler.recover_from_backfill(
        filled, observed_at=EVALUATED_AT + timedelta(seconds=5)
    )
    assert recovered.cursor.gap_state is GapState.NONE
    assert recovered.cursor.connection_identity == connection
    assert recovered.cursor.reconnect_state in {
        ReconnectState.RECOVERED,
        ReconnectState.CONTINUOUS,
    }
    assert recovered.usable is False


def test_read_only_client_rejects_mutations() -> None:
    client = ReadOnlyHttpGetClient(
        base_url="https://fapi.binance.com",
        timeout_seconds=5.0,
    )
    with pytest.raises(NetworkMutationForbiddenError, match="POST"):
        client.request_json("POST", "/fapi/v1/order")
    with pytest.raises(NetworkMutationForbiddenError, match="allowlist"):
        client.request_json("GET", "/fapi/v1/order")
    client.close()
