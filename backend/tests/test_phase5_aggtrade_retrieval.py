"""Binance USD-M aggTrades retrieval contract: time chunks, fromId cursor, coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.market_contracts.adapters.aggtrades import (
    AGGTRADE_PAGE_LIMIT,
    ONE_HOUR_MS,
    AggTradeQuery,
    datetime_to_ms,
    fetch_complete_agg_trade_rows,
    iter_aggtrade_time_chunks,
)
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.enums import DataCompleteness, GapState
from app.market_contracts.errors import (
    IncompleteTradeWindowError,
    UnapprovedEvidenceHostError,
)
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.identity import binance_usdm_btcusdt
from app.schemas.common import Timeframe
from tests.support.phase5_market import CONNECTION, EVALUATED_AT, TRIGGER_OPEN


def _ms(value: datetime) -> int:
    return datetime_to_ms(value)


def _agg_row(agg_id: int, event_time: datetime, *, price: str = "100000") -> dict[str, Any]:
    return {
        "a": agg_id,
        "p": price,
        "q": "0.01",
        "f": agg_id,
        "l": agg_id,
        "T": _ms(event_time),
        "m": False,
    }


class _BinanceLikeAggTrades:
    """Mock that enforces official USD-M aggTrades query constraints."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = sorted(rows, key=lambda row: int(row["a"]))
        self.requests: list[dict[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            return httpx.Response(405, json={"msg": "method not allowed"})
        path = request.url.path
        if path.endswith("/fapi/v1/ping"):
            return httpx.Response(200, json={})
        if not path.endswith("/fapi/v1/aggTrades"):
            return httpx.Response(404, json={"msg": "missing"})
        params = dict(request.url.params)
        self.requests.append(params)
        from_id = params.get("fromId")
        start = params.get("startTime")
        end = params.get("endTime")
        if from_id is not None and (start is not None or end is not None):
            return httpx.Response(
                400, json={"msg": "fromId cannot be used together with startTime/endTime"}
            )
        if start is not None and end is not None:
            start_ms = int(start)
            end_ms = int(end)
            if end_ms - start_ms >= ONE_HOUR_MS:
                return httpx.Response(400, json={"msg": "startTime/endTime must span < 1h"})
            matched = [row for row in self.rows if start_ms <= int(row["T"]) <= end_ms]
        elif from_id is not None:
            cursor = int(from_id)
            matched = [row for row in self.rows if int(row["a"]) >= cursor]
        else:
            return httpx.Response(400, json={"msg": "missing time window or fromId"})
        return httpx.Response(200, json=matched[:AGGTRADE_PAGE_LIMIT])


def test_aggtrade_query_rejects_mixed_fromid_and_time() -> None:
    with pytest.raises(IncompleteTradeWindowError, match="cannot be combined"):
        AggTradeQuery(
            symbol="BTCUSDT",
            start_time_ms=1,
            end_time_ms=2,
            from_id=9,
        )


def test_aggtrade_time_chunks_stay_under_one_hour() -> None:
    start = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    end = datetime(2026, 1, 15, 16, 15, tzinfo=UTC)
    chunks = iter_aggtrade_time_chunks(start, end)
    assert len(chunks) >= 9
    assert all(end_ms - start_ms < ONE_HOUR_MS for start_ms, end_ms in chunks)
    assert chunks[0][0] == _ms(start)
    assert chunks[-1][1] == _ms(end) - 1


def test_live_aggtrades_paginates_more_than_one_hour_and_1000_records() -> None:
    window_start = TRIGGER_OPEN - timedelta(hours=2)
    window_end = TRIGGER_OPEN
    hour1 = [
        _agg_row(index, window_start + timedelta(milliseconds=index), price=str(100000 + index))
        for index in range(1, 1006)
    ]
    later = [
        _agg_row(1006, window_start + timedelta(hours=1, minutes=10)),
        _agg_row(1007, window_start + timedelta(hours=1, minutes=40)),
    ]
    book = _BinanceLikeAggTrades(hour1 + later)
    source = BinanceUsdmPerpetualSource(
        base_url="https://fapi.binance.com",
        transport=httpx.MockTransport(book.handler),
    )
    live_identity = first_slice_identity(timeframe=Timeframe.M15, replay=False, is_live=True)
    batch = source.fetch_ordered_trades(
        identity=live_identity,
        instrument=binance_usdm_btcusdt(),
        start=window_start,
        end=window_end,
        source_connection_id=CONNECTION,
        receive_at=EVALUATED_AT,
    )
    assert len(batch.trades) == 1007
    assert batch.coverage.completeness is DataCompleteness.COMPLETE
    assert batch.coverage.gap_state is GapState.NONE
    assert batch.coverage.requested_start == window_start
    assert batch.coverage.requested_end == window_end
    assert batch.coverage.actual_covered_start == window_start
    assert batch.coverage.actual_covered_end == window_end
    assert batch.coverage.lineage_id == CONNECTION
    assert [trade.sequence for trade in batch.trades[:3]] == [1, 2, 3]
    assert batch.trades[-1].sequence == 1007
    assert any("fromId" in params and "startTime" not in params for params in book.requests)
    assert all(not ("fromId" in params and "startTime" in params) for params in book.requests)
    timed = [params for params in book.requests if "startTime" in params]
    assert len(timed) >= 2
    for params in timed:
        span = int(params["endTime"]) - int(params["startTime"])
        assert span < ONE_HOUR_MS


def test_live_aggtrades_fails_closed_on_incomplete_id_coverage() -> None:
    window_start = TRIGGER_OPEN - timedelta(hours=2)
    window_end = TRIGGER_OPEN
    first_hour = [
        _agg_row(index, window_start + timedelta(seconds=index)) for index in range(1, 11)
    ]
    second_hour = [
        _agg_row(40, window_start + timedelta(hours=1, minutes=1)),
        _agg_row(41, window_start + timedelta(hours=1, minutes=2)),
    ]
    book = _BinanceLikeAggTrades(first_hour + second_hour)
    source = BinanceUsdmPerpetualSource(
        base_url="https://fapi.binance.com",
        transport=httpx.MockTransport(book.handler),
    )
    with pytest.raises(IncompleteTradeWindowError, match="sequence gap"):
        source.fetch_ordered_trades(
            identity=first_slice_identity(timeframe=Timeframe.M15, replay=False, is_live=True),
            instrument=binance_usdm_btcusdt(),
            start=window_start,
            end=window_end,
            source_connection_id=CONNECTION,
            receive_at=EVALUATED_AT,
        )


def test_aggtrade_page_bound_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.market_contracts.adapters.aggtrades.AGGTRADE_MAX_PAGES_PER_CHUNK",
        3,
    )
    start = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    end = datetime(2026, 1, 15, 8, 30, tzinfo=UTC)

    def getter(_path: str, params: dict[str, str | int] | None) -> Any:
        payload = dict(params or {})
        cursor = int(payload["fromId"]) if "fromId" in payload else 1
        return [
            _agg_row(cursor + offset, start + timedelta(milliseconds=offset))
            for offset in range(AGGTRADE_PAGE_LIMIT)
        ]

    with pytest.raises(IncompleteTradeWindowError, match="page bound"):
        fetch_complete_agg_trade_rows(
            get_json=getter,
            symbol="BTCUSDT",
            start=start,
            end=end,
        )


def test_unknown_host_rejected() -> None:
    with pytest.raises(UnapprovedEvidenceHostError, match="not an approved"):
        BinanceUsdmPerpetualSource(base_url="https://evil.example")


def test_plain_http_fapi_rejected() -> None:
    with pytest.raises(UnapprovedEvidenceHostError, match="HTTPS"):
        BinanceUsdmPerpetualSource(base_url="http://fapi.binance.com")
