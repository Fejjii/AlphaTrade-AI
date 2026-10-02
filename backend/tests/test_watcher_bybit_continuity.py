"""Mocked read-only production SymbolMarketFactory/monitor continuity comparison."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from app.core.config import Settings
from app.market_contracts.provider_contracts import ContractBook
from app.market_monitor.watcher_gate import watcher_evidence_error_for_monitor
from app.watcher.memory import InMemoryWatcherStore
from app.workers.watcher_market import SymbolMarketFactory

T0 = datetime(2026, 9, 30, 12, 0, 10, tzinfo=UTC)


def trade(symbol, i, delta):
    return {
        "execId": f"exec-{i}",
        "symbol": symbol,
        "price": "100",
        "size": "1",
        "side": "Buy",
        "time": str(int((T0 + timedelta(seconds=delta)).timestamp() * 1000)),
    }


def run(symbol, failover, release, assemble_between=False):
    reads = 0
    canonical = False

    def handler(request):
        nonlocal reads, canonical
        assert request.method == "GET"
        path = request.url.path
        if path.endswith("exchangeInfo"):
            return httpx.Response(
                200,
                json={
                    "futuresType": "U_MARGINED",
                    "symbols": [
                        {
                            "symbol": symbol,
                            "baseAsset": symbol[:-4],
                            "quoteAsset": "USDT",
                            "contractType": "PERPETUAL",
                            "status": "TRADING",
                        }
                    ],
                },
            )
        if request.url.host == "fapi.binance.com":
            return httpx.Response(451)
        if path.endswith("instruments-info"):
            result = {
                "category": "linear",
                "list": [
                    {
                        "symbol": symbol,
                        "baseCoin": symbol[:-4],
                        "quoteCoin": "USDT",
                        "contractType": "LinearPerpetual",
                        "status": "Trading",
                    }
                ],
            }
        elif path.endswith("recent-trade"):
            pages = [
                [trade(symbol, 1, -10), trade(symbol, 2, -2), trade(symbol, 3, -1)],
                [trade(symbol, 3, -1), trade(symbol, 4, 1)],
                [trade(symbol, 4, 1), trade(symbol, 5, 3)],
            ]
            result = {
                "category": "linear",
                "symbol": symbol,
                "list": pages[0] if canonical else pages[reads],
            }
            if not canonical:
                reads += 1
        elif path.endswith("/kline"):
            minutes = int(request.url.params["interval"])
            limit = int(request.url.params["limit"])
            last_end = T0.replace(minute=0, second=0, microsecond=0)
            rows = [
                [
                    str(int((last_end - timedelta(minutes=minutes * i)).timestamp() * 1000)),
                    "100",
                    "110",
                    "90",
                    "105",
                    "1",
                    "100",
                ]
                for i in range(1, limit + 1)
            ]
            result = {"category": "linear", "symbol": symbol, "list": rows}
        elif path.endswith("/time"):
            result = {}
        else:
            raise AssertionError(path)
        return httpx.Response(200, json={"retCode": 0, "retMsg": "OK", "result": result})

    config = Settings(
        _env_file=None,
        environment="local",
        execution_mode="paper",
        enable_real_trading=False,
        real_trading_enabled=False,
        perpetual_evidence_source="binance_usdm" if failover else "bybit_usdt_perpetual",
        perpetual_evidence_secondary_source="bybit_usdt_perpetual" if failover else "",
        binance_request_max_retries=0,
    )
    factory = SymbolMarketFactory(config, transport=httpx.MockTransport(handler))
    factory.discovery(ContractBook(()), [symbol])
    _source, _catalog, monitor, raw = factory.composition(symbol)
    rows = []
    for i in range(3):
        snapshot = monitor.tick(symbol, now=T0 + timedelta(seconds=2 * i))
        gate = watcher_evidence_error_for_monitor(snapshot)
        rows.append(
            {
                "cycle": i + 1,
                "reason": snapshot.reason.value,
                "availability": snapshot.availability.value,
                "last_sequence": snapshot.stream.last_sequence,
                "last_event_id": snapshot.stream.last_event_id,
                "source_ranks": dict(raw[-1]._rank_by_exec),
                "watcher_gate": None if gate is None else gate.reason_code,
                "connection_identity": str(snapshot.stream.connection_identity),
            }
        )
        if assemble_between and i == 0:
            canonical = True
            evidence = factory(None, InMemoryWatcherStore(), symbol)
            try:
                evidence._assembler.assemble(
                    organization_id=uuid4(), symbol=symbol, evaluated_at=T0
                )
            except Exception as exc:
                rows[-1]["canonical_attempt"] = {
                    "exception": type(exc).__name__,
                    "message": str(exc),
                }
            rows[-1]["source_connection_after_canonical"] = str(raw[-1]._rank_connection)
            canonical = False
        if release:
            factory.release_symbol_history(symbol)
        counts = factory.memory_counts()
        assert counts["market_compositions"] == 1
        assert 1 <= counts["bybit_lineages"] <= 3
        assert counts["bybit_ranks"] == len(raw[-1]._rank_by_exec)
        assert counts["bybit_proven_prints"] <= 3 * (1000 if release else 10000)
    factory.retain(())
    assert not factory._entries
    assert not factory._reads
    return rows


@pytest.mark.parametrize("symbol", ["BTCUSDT", "ETHUSDT", "ZECUSDT", "TAOUSDT", "HYPEUSDT"])
@pytest.mark.parametrize("failover", [False, True])
@pytest.mark.parametrize("release,assemble_between", [(True, False), (False, True), (True, True)])
def test_repeated_bybit_monitor_cleanup_and_canonical_reads(
    symbol, failover, release, assemble_between
):
    rows = run(symbol, failover, release, assemble_between)
    assert [r["watcher_gate"] for r in rows] == [None, None, None]
    assert [r["availability"] for r in rows] == ["fresh"] * 3
    assert [r["last_sequence"] for r in rows] == [3, 4, 5]
    assert [r["last_event_id"] for r in rows] == ["exec-3", "exec-4", "exec-5"]
    assert len({r["connection_identity"] for r in rows}) == 1
    if assemble_between:
        assert rows[0]["canonical_attempt"]["exception"] == "IncompleteTradeWindowError"


@pytest.mark.parametrize("release", [False, True])
def test_bybit_retention_is_bounded_and_evicted_prefixes_fail_closed(release):
    from app.market_contracts.adapters.bybit_usdt_perpetual import (
        _MAX_LINEAGE_PROOFS,
        _MAX_PROVEN_TRADES,
        _RECENT_TRADE_LIMIT,
        BybitUsdtPerpetualSource,
    )
    from app.market_contracts.cvd import accumulate_signed_quote
    from app.market_contracts.errors import (
        DuplicateDataError,
        GapDetectedError,
        IncompleteTradeWindowError,
    )
    from app.market_contracts.first_slice import first_slice_identity
    from app.market_contracts.identity import bybit_usdt_perpetual_btcusdt
    from app.schemas.common import Timeframe

    first = 0
    conflict = False

    def handler(request):
        assert request.url.path.endswith("recent-trade")
        prints = [
            {
                "execId": f"exec-{i:08d}",
                "symbol": "BTCUSDT",
                "price": "100",
                "size": "1",
                "side": "Buy",
                "time": str(int(T0.timestamp() * 1000) + i),
            }
            for i in range(first, first + _RECENT_TRADE_LIMIT)
        ]
        if conflict:
            prints[-1]["price"] = "999"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "result": {"category": "linear", "symbol": "BTCUSDT", "list": prints},
            },
        )

    source = BybitUsdtPerpetualSource(transport=httpx.MockTransport(handler), max_retries=0)
    instrument = bybit_usdt_perpetual_btcusdt()
    identity = first_slice_identity(
        timeframe=Timeframe.M15, instrument=instrument, replay=False, is_live=True
    )
    connection = uuid4()

    def fetch(start, *, lineage=connection):
        return source.fetch_ordered_trades(
            identity=identity,
            instrument=instrument,
            start=start,
            end=T0 + timedelta(milliseconds=first + _RECENT_TRADE_LIMIT),
            source_connection_id=lineage,
            receive_at=T0 + timedelta(milliseconds=first + _RECENT_TRADE_LIMIT),
        )

    try:
        for page in range(25):
            first = page * (_RECENT_TRADE_LIMIT - 1)
            batch = fetch(T0 + timedelta(milliseconds=first))
            assert [t.sequence for t in batch.trades] == list(
                range(first + 1, first + _RECENT_TRADE_LIMIT + 1)
            )
            assert accumulate_signed_quote(batch.trades) == (
                100 * _RECENT_TRADE_LIMIT,
                100 * _RECENT_TRADE_LIMIT,
            )
            # Failed historical reads on distinct lineages cannot reset the monitor.
            with pytest.raises(IncompleteTradeWindowError):
                fetch(T0 - timedelta(hours=1), lineage=uuid4())
            if release:
                source.release_symbol_history("BTCUSDT")
            limit = _RECENT_TRADE_LIMIT if release else _MAX_PROVEN_TRADES
            assert len(source._lineages) <= _MAX_LINEAGE_PROOFS
            assert all(len(p.proven) <= limit for p in source._lineages.values())
            assert len(source._rank_by_exec) <= 2 * limit + _RECENT_TRADE_LIMIT
            assert source._signature_by_exec.keys() == source._rank_by_exec.keys()
        with pytest.raises(IncompleteTradeWindowError):
            fetch(T0)
        conflict = True
        with pytest.raises(DuplicateDataError):
            fetch(T0 + timedelta(milliseconds=first))
        conflict = False
        first += 2 * _RECENT_TRADE_LIMIT
        with pytest.raises(GapDetectedError):
            fetch(T0 + timedelta(milliseconds=first))
    finally:
        source.close()


def test_cleanup_does_not_claim_a_partially_retained_timestamp_bucket():
    from app.market_contracts.adapters.bybit_usdt_perpetual import BybitUsdtPerpetualSource
    from app.market_contracts.errors import IncompleteTradeWindowError
    from app.market_contracts.first_slice import first_slice_identity
    from app.market_contracts.identity import bybit_usdt_perpetual_btcusdt
    from app.schemas.common import Timeframe

    page = 0

    def handler(_request):
        ranges = [range(750), range(749, 1500), range(1499, 1501)]
        rows = [
            {
                "execId": f"exec-{i:08d}",
                "symbol": "BTCUSDT",
                "price": "100",
                "size": "1",
                "side": "Buy",
                "time": str(int(T0.timestamp() * 1000) + (2 if i == 1500 else 0)),
            }
            for i in ranges[page]
        ]
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "result": {"category": "linear", "symbol": "BTCUSDT", "list": rows},
            },
        )

    source = BybitUsdtPerpetualSource(transport=httpx.MockTransport(handler), max_retries=0)
    instrument = bybit_usdt_perpetual_btcusdt()
    identity = first_slice_identity(
        timeframe=Timeframe.M15, instrument=instrument, replay=False, is_live=True
    )
    connection = uuid4()

    def fetch(start):
        return source.fetch_ordered_trades(
            identity=identity,
            instrument=instrument,
            start=start,
            end=T0 + timedelta(milliseconds=3),
            source_connection_id=connection,
            receive_at=T0 + timedelta(milliseconds=3),
        )

    try:
        assert len(fetch(T0).trades) == 750
        page = 1
        assert len(fetch(T0).trades) == 1500
        source.release_symbol_history("BTCUSDT")
        with pytest.raises(IncompleteTradeWindowError):
            fetch(T0)
        page = 2
        tail = fetch(T0 + timedelta(milliseconds=1))
        assert [t.venue_trade_id for t in tail.trades] == ["exec-00001500"]
        assert tail.trades[0].sequence == 1501
    finally:
        source.close()
