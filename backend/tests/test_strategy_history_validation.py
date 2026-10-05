"""Focused harness contracts; all prices and HTTP responses here are unit fixtures."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.catalog import catalog_for_symbols
from app.market_contracts.enums import Finality, VenueId
from app.market_contracts.errors import MarketContractError
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import binance_usdm_perpetual, interval_timedelta
from app.market_contracts.ohlcv import kline_source_event_id, require_closed_series
from app.schemas.common import Timeframe, TradeDirection
from app.schemas.nested_continuation import NestedContinuationSpec
from app.schemas.strategy_replay import ReplayCandleEvidence, SfpReplayEvidence
from tests.test_sfp_detector import BEAR, BULL, evidence, spec
from tests.test_strategy_brain_nested import PRICES, bars

MODULE = importlib.util.spec_from_file_location(
    "validate_strategy_history", Path(__file__).parents[1] / "scripts/validate_strategy_history.py"
)
harness = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(harness)


def series_of(candles, identity=None):
    first = candles[0]
    identity = identity or first_slice_identity(
        timeframe=first.timeframe, replay=True, instrument=first.instrument
    )
    return require_closed_series(
        list(candles),
        identity=identity,
        timeframe=first.timeframe,
        evaluated_at=candles[-1].interval_end,
        min_bars=len(candles),
    )


@pytest.mark.parametrize("symbol", harness.SYMBOLS)
@pytest.mark.parametrize("timeframe", [Timeframe(t) for t in harness.TIMEFRAMES])
def test_nested_defaults_independent_directions_and_timeframes(symbol, timeframe):
    instrument = binance_usdm_perpetual(symbol)
    candles = tuple(
        with_content_hash(
            b.model_copy(
                update={
                    "instrument": instrument,
                    "source_event_id": kline_source_event_id(
                        instrument.instrument_id, timeframe, b.interval_start
                    ),
                }
            )
        )
        for b in bars(timeframe=timeframe)
    )
    result, records = harness.evaluate_series(
        series_of(candles), sfp_spec=None, sfp_evidence=SfpReplayEvidence()
    )
    expected = harness.detect_nested(
        candles,
        NestedContinuationSpec(symbol=symbol, trigger_timeframe=timeframe),
        evaluated_at=candles[-1].interval_end,
    )
    native_confirmations = [e for e in expected if e.state.value == "CONFIRMED"]
    assert result["nested_continuation"]["long"]["counts"]["CONFIRMED"] == len(native_confirmations)
    assert [e.stage for e in native_confirmations] == ["N1", "N2", "N3", "N4_PLUS"]
    assert all(
        result["nested_continuation"]["long"]["counts"][stage] == 1
        for stage in ("N1", "N2", "N3", "N4_PLUS")
    )
    short_native = harness.detect_nested(
        candles,
        NestedContinuationSpec(
            symbol=symbol, trigger_timeframe=timeframe, direction=TradeDirection.SHORT
        ),
        evaluated_at=candles[-1].interval_end,
    )
    assert result["nested_continuation"]["short"]["detector_snapshots"] == len(short_native)
    assert all(r["symbol"] == symbol and r["timeframe"] == timeframe.value for r in records)
    assert result["sfp"]["long"]["counts"] is None
    assert result["sfp"]["long"]["reason_codes"] == [
        "authored_sfp_parameters_missing",
        "historical_candle_receipts_missing",
    ]


def test_nested_repeated_forming_snapshots_count_one_setup_and_preserve_reason_codes():
    series = series_of(bars(PRICES[:12]))
    result, records = harness.evaluate_series(
        series, sfp_spec=None, sfp_evidence=SfpReplayEvidence()
    )
    long = result["nested_continuation"]["long"]
    assert long["counts"]["FORMING"] == 1
    assert long["counts"]["N1"] == 0  # Forming N1 is not a completed continuation.
    assert long["detector_snapshots"] > long["counts"]["FORMING"]
    assert any("awaiting_closed_structural_break" in r["reason_codes"] for r in records)
    assert long["representatives"]["FORMING"][0]["candle_open_utc"]


@pytest.mark.parametrize("bearish", [False, True])
def test_sfp_uses_existing_explicit_parameters_and_receipts(bearish):
    candles, observations = evidence(BEAR if bearish else BULL)
    proof = SfpReplayEvidence(
        candles=[
            ReplayCandleEvidence(bar=b, observation=o)
            for b, o in zip(candles, observations, strict=True)
        ]
    )
    authored = spec(bearish=bearish)
    original = authored.model_dump(mode="json")
    result, records = harness.evaluate_series(
        series_of(candles, observations[0].identity), sfp_spec=authored, sfp_evidence=proof
    )
    side = "short" if bearish else "long"
    summary = result["sfp"][side]
    assert summary["status"] == "evaluated"
    for role in ("reference_level", "sweep", "reclaim", "confirmation"):
        assert summary["counts"][role] >= 1
    confirmed = summary["representatives"]["confirmation"][0]
    assert confirmed["reference_level"]["price"] == "100"
    assert confirmed["reclaim"]["close_utc"] == candles[4].interval_end.isoformat()
    assert confirmed["confirmation"]["close_utc"] == candles[5].interval_end.isoformat()
    assert confirmed["reason_codes"] == ["closed_break_of_reclaim_extreme"]
    assert all(
        r["optional_evidence"]["cvd"] != "AVAILABLE"
        and r["optional_evidence"]["order_flow"] != "AVAILABLE"
        for r in records
        if r["strategy_family"] == "sfp"
    )
    assert authored.model_dump(mode="json") == original


def test_sfp_missing_receipts_remain_unavailable_even_with_real_prices_and_spec():
    candles, observations = evidence()
    result, _ = harness.evaluate_series(
        series_of(candles, observations[0].identity),
        sfp_spec=spec(),
        sfp_evidence=SfpReplayEvidence(),
    )
    assert result["sfp"]["long"]["status"] == "unavailable"
    assert result["sfp"]["long"]["reason_codes"] == ["historical_candle_receipts_missing"]


@pytest.mark.parametrize(
    "tail,role,reason",
    [
        ([(101, 102, 99, 99)], "failed_reclaim", "closed_reclaim_lost"),
        ([(101, 102, 97, 101)], "invalidation", "closed_structural_extreme_breached"),
        ([(101, 102, 100, 101)] * 3, "expiry", "confirmation_window_elapsed"),
    ],
)
def test_sfp_terminal_roles_preserve_native_reasons(tail, role, reason):
    candles, observations = evidence([*BULL[:5], *tail])
    proof = SfpReplayEvidence(
        candles=[
            ReplayCandleEvidence(bar=b, observation=o)
            for b, o in zip(candles, observations, strict=True)
        ]
    )
    result, _ = harness.evaluate_series(
        series_of(candles, observations[0].identity), sfp_spec=spec(), sfp_evidence=proof
    )
    summary = result["sfp"]["long"]
    assert summary["counts"][role] >= 1
    assert any(reason in e["reason_codes"] for e in summary["representatives"][role])


@pytest.mark.parametrize("bearish", [False, True])
@pytest.mark.parametrize("tail,role", [([95], "INVALIDATED"), ([109] * 30, "EXPIRED")])
def test_nested_terminal_roles_with_unchanged_defaults(bearish, tail, role):
    series = series_of(bars([*PRICES[:12], *tail], bearish=bearish))
    result, _ = harness.evaluate_series(series, sfp_spec=None, sfp_evidence=SfpReplayEvidence())
    summary = result["nested_continuation"]["short" if bearish else "long"]
    assert summary["counts"][role] >= 1


def test_distinct_timeframes_have_distinct_sequence_ids():
    sequences = []
    for timeframe in (Timeframe.M15, Timeframe.H1, Timeframe.H4):
        result, _ = harness.evaluate_series(
            series_of(bars(timeframe=timeframe)), sfp_spec=None, sfp_evidence=SfpReplayEvidence()
        )
        sequences.append(
            result["nested_continuation"]["long"]["representatives"]["CONFIRMED"][0]["sequence_id"]
        )
    assert len(set(sequences)) == 3


@pytest.mark.parametrize("timeframe", [Timeframe(t) for t in harness.TIMEFRAMES])
def test_history_native_interval_cutoff_and_finality_allow_shorter_listings(timeframe):
    instrument = binance_usdm_perpetual("HYPEUSDT")
    identity = first_slice_identity(
        timeframe=timeframe, instrument=instrument, replay=False, is_live=True
    )
    # A Monday is also the native Binance weekly open.
    start = datetime(2026, 6, 1, tzinfo=UTC)
    delta = interval_timedelta(timeframe)
    cutoff = start + delta * 3 + timedelta(seconds=1)
    requests = []

    def handler(request):
        requests.append(request)
        rows = []
        for i in range(4):
            opened = start + delta * i
            rows.append(
                [
                    int(opened.timestamp() * 1000),
                    "100",
                    "101",
                    "99",
                    "100",
                    "10",
                    int((opened + delta).timestamp() * 1000) - 1,
                    "1000",
                    5,
                ]
            )
        return httpx.Response(200, json=rows)

    source = BinanceUsdmPerpetualSource(
        catalog=catalog_for_symbols(("HYPEUSDT",), venue=VenueId.BINANCE),
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )
    try:
        history = source.fetch_closed_ohlcv_history(
            identity=identity,
            instrument=instrument,
            timeframe=timeframe,
            evaluated_at=cutoff,
            limit=10,
        )
        assert 0 < len(history.bars) < 10
        assert all(
            b.finality is Finality.FINAL and b.provider_complete and b.interval_end <= cutoff
            for b in history.bars
        )
        assert requests[0].method == "GET"
        assert requests[0].url.params["interval"] == timeframe.value
        assert requests[0].url.params["limit"] == "12"
        assert int(requests[0].url.params["endTime"]) < int(cutoff.timestamp() * 1000)
    finally:
        source.close()


@pytest.mark.parametrize("failure", ["gap", "duplicate", "wrong_close_time"])
def test_history_rejects_broken_provider_contract(failure):
    instrument = binance_usdm_perpetual("BTCUSDT")
    timeframe = Timeframe.M15
    identity = first_slice_identity(timeframe=timeframe, replay=False, is_live=True)
    start = datetime(2026, 6, 1, tzinfo=UTC)
    delta = interval_timedelta(timeframe)
    rows = [
        [
            int((start + delta * i).timestamp() * 1000),
            "100",
            "101",
            "99",
            "100",
            "10",
            int((start + delta * (i + 1)).timestamp() * 1000) - 1,
            "1000",
        ]
        for i in range(4)
    ]
    if failure == "gap":
        rows.pop(1)
    elif failure == "duplicate":
        rows.insert(1, rows[0])
    else:
        rows[0][6] += 1
    source = BinanceUsdmPerpetualSource(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=rows))
    )
    try:
        with pytest.raises((MarketContractError, ValueError)):
            source.fetch_closed_ohlcv_history(
                identity=identity,
                instrument=instrument,
                timeframe=timeframe,
                evaluated_at=start + delta * 5,
                limit=2,
            )
    finally:
        source.close()


def test_live_provider_failure_is_not_reported_as_zero_signals_or_mock_data():
    requests = []

    def blocked(request):
        requests.append(request)
        raise httpx.ProxyError("403 Forbidden")

    source = BinanceUsdmPerpetualSource(transport=httpx.MockTransport(blocked), max_retries=0)
    try:
        report, history, events = harness.run_validation(
            symbols=("BTCUSDT",),
            timeframes=(Timeframe.M5, Timeframe.M15),
            bars=1000,
            as_of=datetime(2026, 9, 1, tzinfo=UTC),
            source=source,
        )
    finally:
        source.close()
    assert len(requests) == 1  # Reuse symbol contract failure across isolated timeframes.
    assert history == events == []
    assert report["live_acquisition"] == {
        "acquired_series": 0,
        "requested_series": 2,
        "final_candles": 0,
    }
    for row in report["results"]:
        assert row["acquisition"]["final_bars"] is None
        assert row["acquisition"]["error_chain"][1]["message"] == "403 Forbidden"
        assert row["families"]["nested_continuation"]["long"]["counts"] is None
    report["rerun_command"] = "unit-fixture-command"
    markdown = harness.markdown_report(report)
    assert "unavailable / unavailable" in markdown
    assert "No representative detections" in markdown
    assert "403 Forbidden" in markdown


def test_successful_acquisition_keeps_actual_short_history_and_detector_results():
    candles = bars()
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/fapi/v1/exchangeInfo":
            return httpx.Response(
                200,
                json={
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDT",
                            "contractType": "PERPETUAL",
                            "status": "TRADING",
                        }
                    ]
                },
            )
        assert request.url.path == "/fapi/v1/klines"
        return httpx.Response(
            200,
            json=[
                [
                    int(b.interval_start.timestamp() * 1000),
                    str(b.open),
                    str(b.high),
                    str(b.low),
                    str(b.close),
                    str(b.base_volume),
                    int(b.interval_end.timestamp() * 1000) - 1,
                    str(b.quote_volume),
                ]
                for b in candles
            ],
        )

    source = BinanceUsdmPerpetualSource(transport=httpx.MockTransport(handler), max_retries=0)
    try:
        report, history, events = harness.run_validation(
            symbols=("BTCUSDT",),
            timeframes=(Timeframe.M15,),
            bars=1000,
            as_of=candles[-1].interval_end + timedelta(seconds=5),
            source=source,
        )
    finally:
        source.close()
    row = report["results"][0]
    assert len(requests) == 2 and all(r.method == "GET" for r in requests)
    assert row["acquisition"]["status"] == "acquired_partial"
    assert row["acquisition"]["final_bars"] == len(candles)
    assert len(history[0]["series"]["bars"]) == len(candles)
    assert row["families"]["nested_continuation"]["long"]["counts"]["CONFIRMED"] == 4
    assert row["families"]["sfp"]["long"]["status"] == "unavailable"
    assert events and all(e["strategy_family"] == "nested_continuation" for e in events)


@pytest.mark.parametrize(
    "key,value",
    [
        ("ENABLE_REAL_TRADING", "true"),
        ("EXECUTION_MODE", "trade"),
        ("EXCHANGE_MODE", "paper_exchange_demo"),
    ],
)
def test_unsafe_execution_settings_fail_before_any_provider_read(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        harness.require_paper_settings()
