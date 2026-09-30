"""Paper-worker memory: released tapes match full trades and stay bounded."""

from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
import tracemalloc
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.core.config import Settings
from app.market_contracts.adapters.aggtrade_cache import (
    ClosedAggTradeCache,
    closed_agg_trade_window_key,
)
from app.market_contracts.adapters.aggtrades import AGGTRADE_PAGE_LIMIT, ONE_HOUR_MS, datetime_to_ms
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.coverage import trade_set_content_hash
from app.market_contracts.cursor import TradeStreamSnapshot
from app.market_contracts.cvd import (
    cvd_at_close,
    event_set_hash,
    first_slice_baseline_open,
    first_slice_cvd_window,
    signed_quote_delta_until,
)
from app.market_contracts.errors import IncompleteTradeWindowError
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.flow import bar_signed_quote_flow as signed_flow
from app.market_contracts.identity import ADAPTER_VERSION, binance_usdm_btcusdt
from app.market_contracts.ohlcv import require_closed_series
from app.market_contracts.replay_fixtures import (
    FIXTURE_CONNECTION_ID,
    canonical_first_slice_fixture,
)
from app.market_contracts.streaming_hash import TradeSetHasher, VenueIdSetHasher
from app.market_contracts.trade_reduction import build_released_trade_snapshot
from app.market_contracts.trades import TradeEvent, build_trade_event
from app.market_monitor.backoff import BackoffPolicy
from app.market_monitor.runtime import SymbolMonitorRuntime
from app.observability.process_memory import memory_status_fields, read_process_memory
from app.persistence.runtime_health import project_worker_component
from app.schemas.common import Timeframe
from app.schemas.health import WorkerComponentObservation
from tests.support.live_market_monitor import ScriptedPerpetualSource
from tests.support.phase5_market import CONNECTION, EVALUATED_AT, identity, proven_snapshot, trade

_STRESS_PATH = "/tmp/paper_worker_memory_stress.json"
_GROWTH_LIMIT = 32 * 1024 * 1024


def test_streaming_hash_matches_canonical_trade_set() -> None:
    fixture = canonical_first_slice_fixture()
    trades = list(fixture["trades"])[:6]
    trade_hasher = TradeSetHasher()
    id_hasher = VenueIdSetHasher()
    for item in trades:
        trade_hasher.add(
            venue_trade_id=item.venue_trade_id,
            sequence=item.sequence,
            content_hash=item.content_hash,
        )
        id_hasher.add(item.venue_trade_id)
    assert trade_hasher.hexdigest() == trade_set_content_hash(trades)
    assert id_hasher.hexdigest() == event_set_hash(trades)


def test_released_tape_matches_full_trade_evidence() -> None:
    fixture = canonical_first_slice_fixture()
    trades = list(fixture["trades"])
    series = require_closed_series(
        list(fixture["bars_15m"]),
        identity=identity(),
        timeframe=Timeframe.M15,
        evaluated_at=EVALUATED_AT,
        min_bars=100,
    )
    trigger = series.bars[-1]
    start = first_slice_baseline_open(trigger)
    end = trigger.interval_end
    retained = proven_snapshot(
        trades,
        start=start,
        end=end,
        connection=FIXTURE_CONNECTION_ID,
    )
    released = build_released_trade_snapshot(
        trades,
        identity=identity(),
        lineage_id=FIXTURE_CONNECTION_ID,
        window_start=start,
        window_end=end,
        observed_at=EVALUATED_AT,
    )
    assert released.trades == []
    assert released.released_tape is not None
    assert released.coverage.content_hash == retained.coverage.content_hash
    retained_cvd = first_slice_cvd_window(
        identity=identity(),
        series_15m=series,
        snapshot=retained,
        created_at=EVALUATED_AT,
        require_live_freshness=False,
    )
    released_cvd = first_slice_cvd_window(
        identity=identity(),
        series_15m=series,
        snapshot=released,
        created_at=EVALUATED_AT,
        require_live_freshness=False,
    )
    assert released_cvd.content_hash == retained_cvd.content_hash
    retained_flow = signed_flow(
        identity=identity(),
        bar=trigger,
        snapshot=retained,
        evaluated_at=EVALUATED_AT,
        require_live_freshness=False,
    )
    released_flow = signed_flow(
        identity=identity(),
        bar=trigger,
        snapshot=released,
        evaluated_at=EVALUATED_AT,
        require_live_freshness=False,
    )
    assert released_flow.content_hash == retained_flow.content_hash
    swing_end = series.bars[-3].interval_end
    assert signed_quote_delta_until(
        released, window_start=start, bar_end=end, baseline=Decimal("0")
    ) == cvd_at_close(list(retained.trades), window_start=start, bar_end=end, baseline=Decimal("0"))
    assert signed_quote_delta_until(
        released, window_start=start, bar_end=swing_end, baseline=Decimal("0")
    ) == cvd_at_close(
        list(retained.trades), window_start=start, bar_end=swing_end, baseline=Decimal("0")
    )


class _AggBook:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = sorted(rows, key=lambda row: int(row["a"]))
        self.requests = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        if not request.url.path.endswith("/fapi/v1/aggTrades"):
            return httpx.Response(404, json={"msg": "missing"})
        self.requests += 1
        params = dict(request.url.params)
        start = params.get("startTime")
        end = params.get("endTime")
        from_id = params.get("fromId")
        if start is not None and end is not None:
            matched = [row for row in self.rows if int(start) <= int(row["T"]) <= int(end)]
        elif from_id is not None:
            cursor = int(from_id)
            matched = [row for row in self.rows if int(row["a"]) >= cursor]
        else:
            return httpx.Response(400, json={"msg": "missing"})
        return httpx.Response(200, json=matched[:AGGTRADE_PAGE_LIMIT])


def _row(agg_id: int, moment: datetime) -> dict[str, Any]:
    return {
        "a": agg_id,
        "p": "100000",
        "q": "0.01",
        "f": agg_id,
        "l": agg_id,
        "T": datetime_to_ms(moment),
        "m": False,
    }


def test_reduce_matches_fetch_and_skips_raw_cache() -> None:
    start = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    rows = [_row(index, start + timedelta(seconds=index)) for index in range(1, 21)]
    book = _AggBook(rows)
    source = BinanceUsdmPerpetualSource(
        base_url="https://fapi.binance.com",
        transport=httpx.MockTransport(book.handler),
    )
    market = first_slice_identity(timeframe=Timeframe.M15, replay=False, is_live=True)
    fetched = source.fetch_ordered_trades(
        identity=market,
        instrument=binance_usdm_btcusdt(),
        start=start,
        end=end,
        source_connection_id=CONNECTION,
        receive_at=EVALUATED_AT,
    )
    reduced = source.reduce_ordered_trades(
        identity=market,
        instrument=binance_usdm_btcusdt(),
        start=start,
        end=end,
        source_connection_id=CONNECTION,
        receive_at=EVALUATED_AT,
    )
    assert reduced.trades == []
    assert reduced.coverage.content_hash == fetched.coverage.content_hash
    assert len(source.evidence_cache) == 1
    requests_after_first_reduce = book.requests
    again = source.reduce_ordered_trades(
        identity=market,
        instrument=binance_usdm_btcusdt(),
        start=start,
        end=end,
        source_connection_id=CONNECTION,
        receive_at=EVALUATED_AT,
    )
    assert again.coverage.content_hash == reduced.coverage.content_hash
    assert book.requests == requests_after_first_reduce
    assert again.cursor.cursor_id == reduced.cursor.cursor_id


def test_reduce_fails_closed_on_sequence_gap() -> None:
    start = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    rows = [_row(1, start + timedelta(seconds=1)), _row(4, start + timedelta(seconds=2))]
    book = _AggBook(rows)
    source = BinanceUsdmPerpetualSource(
        base_url="https://fapi.binance.com",
        transport=httpx.MockTransport(book.handler),
    )
    with pytest.raises(IncompleteTradeWindowError, match="sequence gap"):
        source.reduce_ordered_trades(
            identity=first_slice_identity(timeframe=Timeframe.M15, replay=False, is_live=True),
            instrument=binance_usdm_btcusdt(),
            start=start,
            end=end,
            source_connection_id=CONNECTION,
            receive_at=EVALUATED_AT,
        )


def test_raw_cache_refuses_oversized_windows() -> None:
    start = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    end = start + timedelta(minutes=15)
    cache = ClosedAggTradeCache(max_entries=2, ttl_seconds=60, max_rows=4)
    key = closed_agg_trade_window_key("BTCUSDT", start, end)
    assert cache.put(key, tuple({"a": index} for index in range(5))) is False
    assert cache.get(key) is None
    small = tuple({"a": index} for index in range(4))
    assert cache.put(key, small) is False
    assert cache.get(key) == small


def test_monitor_keeps_only_the_boundary_timestamp() -> None:
    moment = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)
    source = ScriptedPerpetualSource()
    source.enqueue(
        [
            trade(
                sequence=1,
                price="100",
                quantity="0.01",
                buyer_is_maker=False,
                event_time=moment,
            ),
            trade(
                sequence=2,
                price="101",
                quantity="0.01",
                buyer_is_maker=False,
                event_time=moment + timedelta(seconds=1),
            ),
            trade(
                sequence=3,
                price="102",
                quantity="0.01",
                buyer_is_maker=True,
                event_time=moment + timedelta(seconds=2),
            ),
        ]
    )
    runtime = SymbolMonitorRuntime(
        instrument=binance_usdm_btcusdt(),
        source=source,  # type: ignore[arg-type]
        replay=False,
        backoff=BackoffPolicy(),
        connected_at=moment,
    )
    snapshot = runtime.tick(moment + timedelta(seconds=3))
    kept = runtime._assembler.accepted_trades()
    assert [item.sequence for item in kept] == [3]
    assert snapshot.cvd.available is True
    assert snapshot.cvd.event_count == 3
    assert snapshot.current_price is not None


def _events(count: int, *, start: datetime, connection: UUID) -> list[TradeEvent]:
    instrument = binance_usdm_btcusdt()
    return [
        build_trade_event(
            instrument=instrument,
            venue_trade_id=str(index),
            sequence=index,
            price=Decimal("100000"),
            quantity=Decimal("0.01"),
            buyer_is_maker=index % 2 == 0,
            event_timestamp=start + timedelta(milliseconds=index),
            receive_timestamp=EVALUATED_AT,
            source_connection_id=connection,
            adapter_version=ADAPTER_VERSION,
        )
        for index in range(1, count + 1)
    ]


_RETENTION_FLOOR = 4 * 1024 * 1024

_ISOLATED_RSS_PROBE = """
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.identity import ADAPTER_VERSION, binance_usdm_btcusdt
from app.market_contracts.trade_reduction import build_released_trade_snapshot
from app.market_contracts.trades import build_trade_event
from app.observability.process_memory import read_process_memory, release_allocator_memory
from app.schemas.common import Timeframe
from tests.support.phase5_market import CONNECTION, EVALUATED_AT

def one(index, start, instrument):
    return build_trade_event(
        instrument=instrument,
        venue_trade_id=str(index),
        sequence=index,
        price=Decimal("100000"),
        quantity=Decimal("0.01"),
        buyer_is_maker=index % 2 == 0,
        event_timestamp=start + timedelta(milliseconds=index),
        receive_timestamp=EVALUATED_AT,
        source_connection_id=CONNECTION,
        adapter_version=ADAPTER_VERSION,
    )

release_allocator_memory()
before = read_process_memory().rss_bytes
start = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
instrument = binance_usdm_btcusdt()
if sys.argv[1] == "retain":
    retained = [one(index, start, instrument) for index in range(1, 5001)]
    after = read_process_memory().rss_bytes
    payload = {"delta": after - before, "trades": len(retained)}
else:
    end = start + timedelta(minutes=15)
    market = first_slice_identity(timeframe=Timeframe.M15, replay=False, is_live=True)
    released = build_released_trade_snapshot(
        (one(index, start, instrument) for index in range(1, 5001)),
        identity=market,
        lineage_id=CONNECTION,
        window_start=start,
        window_end=end,
        observed_at=EVALUATED_AT,
    )
    release_allocator_memory()
    after = read_process_memory().rss_bytes
    tape = released.released_tape
    payload = {
        "delta": after - before,
        "trades": len(released.trades),
        "event_count": None if tape is None else tape.event_count,
        "trade_set_hash": None if tape is None else tape.trade_set_hash,
        "event_set_hash": None if tape is None else tape.event_set_hash,
    }
print(json.dumps(payload))
"""


def test_traced_trade_retention_exceeds_the_released_tape() -> None:
    """Python allocations, not process RSS. This does not depend on arena reuse."""
    if tracemalloc.is_tracing():
        tracemalloc.stop()
    tracemalloc.start()
    baseline = tracemalloc.get_traced_memory()[0]
    start = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    end = start + timedelta(minutes=15)
    market = first_slice_identity(timeframe=Timeframe.M15, replay=False, is_live=True)
    retained = _events(5_000, start=start, connection=CONNECTION)
    held = tracemalloc.get_traced_memory()[0]
    del retained
    gc.collect()
    after_release_of_list = tracemalloc.get_traced_memory()[0]
    released = build_released_trade_snapshot(
        _events(5_000, start=start, connection=CONNECTION),
        identity=market,
        lineage_id=CONNECTION,
        window_start=start,
        window_end=end,
        observed_at=EVALUATED_AT,
    )
    taped = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    retain_bytes = held - baseline
    tape_bytes = taped - after_release_of_list
    tape = released.released_tape
    assert released.trades == []
    assert tape is not None
    assert tape.event_count == 5_000
    assert tape.trade_set_hash
    assert tape.event_set_hash
    assert retain_bytes > _RETENTION_FLOOR
    assert tape_bytes < retain_bytes


def test_retained_trades_cost_more_rss_than_a_released_tape() -> None:
    """Compare fresh interpreters so neither probe inherits the other's arenas.

    Measuring inside pytest reused freed arenas on PR 149; sequential probes
    in one child still retain malloc arenas on Darwin even after GC. Keep both
    fixture sizes and the retention floor, but isolate each allocator history.
    """
    backend = Path(__file__).resolve().parents[1]
    measurements = {}
    for mode in ("retain", "release"):
        completed = subprocess.run(
            [sys.executable, "-c", _ISOLATED_RSS_PROBE, mode],
            cwd=backend,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(("src", str(backend)))},
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        measurements[mode] = json.loads(completed.stdout)
    retained = measurements["retain"]
    released = measurements["release"]
    assert retained["trades"] == 5_000
    assert released["trades"] == 0
    assert released["event_count"] == 5_000
    assert released["trade_set_hash"]
    assert released["event_set_hash"]
    assert retained["delta"] > _RETENTION_FLOOR
    assert released["delta"] < retained["delta"]


def test_repeated_reduction_does_not_grow_rss() -> None:
    """Keep the 8x25,000 workload and limits; isolate unrelated pytest arenas.

    A prior test's arena release caused max(early peak)-min(later RSS) to exceed
    80 MiB even though retained memory fell. A fresh process measures this
    workload's complete peak/release range rather than unrelated suite history.
    """
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from tests.test_paper_worker_memory import _measure_repeated_reduction; "
            "_measure_repeated_reduction()",
        ],
        cwd=backend,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(("src", str(backend)))},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _measure_repeated_reduction() -> None:
    start = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    end = start + timedelta(minutes=15)
    market = first_slice_identity(timeframe=Timeframe.M15, replay=False, is_live=True)
    currents: list[int] = []
    peaks: list[int] = []
    for _cycle in range(8):
        seen = 0
        peak = read_process_memory().rss_bytes

        def generated() -> Any:
            nonlocal seen, peak
            instrument = binance_usdm_btcusdt()
            for index in range(1, 25_001):
                if index % 5_000 == 0:
                    peak = max(peak, read_process_memory().rss_bytes)
                seen += 1
                yield build_trade_event(
                    instrument=instrument,
                    venue_trade_id=str(index),
                    sequence=index,
                    price=Decimal("100000"),
                    quantity=Decimal("0.01"),
                    buyer_is_maker=index % 2 == 0,
                    event_timestamp=start + timedelta(milliseconds=index),
                    receive_timestamp=EVALUATED_AT,
                    source_connection_id=CONNECTION,
                    adapter_version=ADAPTER_VERSION,
                )

        snapshot = build_released_trade_snapshot(
            generated(),
            identity=market,
            lineage_id=CONNECTION,
            window_start=start,
            window_end=end,
            observed_at=EVALUATED_AT,
        )
        assert isinstance(snapshot, TradeStreamSnapshot)
        assert snapshot.trades == []
        assert seen == 25_000
        sample = read_process_memory()
        currents.append(sample.rss_bytes)
        peaks.append(max(peak, sample.rss_bytes))
        del snapshot
    report = {
        "cycles": 8,
        "trades_per_cycle": 25_000,
        "rss_after_bytes": currents,
        "rss_during_bytes": peaks,
        "growth_bytes": currents[-1] - currents[0],
        "during_growth_bytes": peaks[-1] - peaks[0],
    }
    with open(_STRESS_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle)
    assert currents[-1] - currents[0] < _GROWTH_LIMIT
    assert peaks[-1] - peaks[0] < _GROWTH_LIMIT
    assert max(peaks) - min(currents) < 80 * 1024 * 1024


def test_memory_status_is_numeric_and_real_trading_stays_off() -> None:
    sample = read_process_memory()
    assert sample.rss_bytes > 0
    assert sample.peak_rss_bytes >= sample.rss_bytes
    fields = memory_status_fields()
    assert set(fields) == {"process_rss_bytes", "process_rss_peak_bytes"}
    rendered = json.dumps(fields)
    assert "sk-" not in rendered
    assert "api_key" not in rendered
    settings = Settings()
    assert settings.enable_real_trading is False
    assert settings.real_trading_enabled is False
    blank = WorkerComponentObservation()
    assert blank.process_rss_bytes is None
    assert blank.process_rss_peak_bytes is None
    now = datetime(2026, 9, 28, 7, 0, tzinfo=UTC)
    row = type(
        "Row",
        (),
        {
            "heartbeat_at": now,
            "process_rss_bytes": 4096,
            "process_rss_peak_bytes": 8192,
        },
    )()
    observed = project_worker_component(row, now=now, stale_after_seconds=90)
    assert observed.process_rss_bytes == 4096
    assert observed.process_rss_peak_bytes == 8192


def test_chunk_span_constant_is_under_one_hour() -> None:
    assert ONE_HOUR_MS == 3_600_000
