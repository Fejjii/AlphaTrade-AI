"""Public timing diagnostics explain refusals without changing freshness authority."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
import structlog
from structlog.testing import capture_logs

from app.core.errors import TradingPolicyError
from app.providers.exchange import demo_quote
from app.providers.exchange.demo_quote import DemoQuoteTimingError, quote_time_at_receipt
from app.schemas.manual_demo import ManualDemoPreviewRequest
from app.services import manual_demo_service
from tests.support.phase5_market import EVALUATED_AT
from tests.test_demo_preflight_diagnostics import PRIVATE_TEXT, provider, service
from tests.test_governed_blofin_demo import Venue

STAMP = int(EVALUATED_AT.timestamp() * 1000)


@pytest.fixture(autouse=True)
def fresh_loggers(monkeypatch):
    # Production caches bound loggers; preceding tests may initialize them before capture_logs.
    for module in (demo_quote, manual_demo_service):
        monkeypatch.setattr(module, "logger", structlog.get_logger(module.__name__))


@pytest.mark.parametrize("age_ms", [0, 1, 9999])
@pytest.mark.parametrize("as_string", [False, True])
def test_fresh_timestamp_and_non_utc_receipt_preserve_exact_milliseconds(age_ms, as_string):
    raw = STAMP - age_ms
    receipt = EVALUATED_AT.astimezone(timezone(timedelta(hours=2)))
    with capture_logs() as logs:
        observed = quote_time_at_receipt(str(raw) if as_string else raw, receipt)
    assert observed == EVALUATED_AT - timedelta(milliseconds=age_ms)
    assert observed.tzinfo is UTC
    assert logs[0]["raw_timestamp_ms"] == raw
    assert logs[0]["receipt_timestamp_utc"] == EVALUATED_AT.isoformat()
    assert logs[0]["quote_age_seconds"] == age_ms / 1000
    assert logs[0]["freshness_status"] == "fresh"


@pytest.mark.parametrize("age_ms,status", [(10000, "stale"), (60000, "stale"), (-1, "future")])
def test_preview_refusal_exposes_timing_in_http_details_and_existing_failure_log(age_ms, status):
    venue = Venue(Decimal("100000"))
    raw = STAMP - age_ms

    def handle(request):
        assert request.method == "GET"
        response = venue.handle(request)
        if request.url.path.endswith("/tickers"):
            payload = response.json()
            payload["data"][0].update(ts=str(raw), private_payload=PRIVATE_TEXT)
            return httpx.Response(200, json=payload)
        return response

    manual, session, tenant = service(provider(handle))
    with capture_logs() as logs, pytest.raises(TradingPolicyError) as caught:
        manual.preview(
            tenant,
            ManualDemoPreviewRequest(side="BUY", quantity="2", stop="99000", target="102000"),
        )
    evidence = caught.value.details["preflight"]
    assert evidence["stage"] == "quote"
    assert evidence["endpoint_name"] == "GET /api/v1/market/tickers"
    assert evidence["reason_code"] == "quote_stale_or_future"
    assert evidence["raw_timestamp_ms"] == raw
    assert (
        evidence["parsed_timestamp_utc"]
        == (EVALUATED_AT - timedelta(milliseconds=age_ms)).isoformat()
    )
    assert evidence["receipt_timestamp_utc"] == EVALUATED_AT.isoformat()
    assert evidence["quote_age_seconds"] == age_ms / 1000
    assert evidence["freshness_status"] == status
    failure = [log for log in logs if log["event"] == "manual_demo_preflight_failed"]
    assert len(failure) == 1
    assert failure[0]["raw_timestamp_ms"] == raw
    assert PRIVATE_TEXT not in str(logs) + str(evidence)
    assert venue.post_count == 0
    session.add.assert_not_called()


@pytest.mark.parametrize(
    "raw",
    [
        None,
        True,
        STAMP / 1000,
        {},
        [],
        PRIVATE_TEXT,
        "NaN",
        "1e12",
        str(STAMP) + ".0",
        "9" * 1000,
        -1,
        "9999999999999999",
    ],
)
def test_malformed_or_out_of_range_timestamp_refuses_with_bounded_evidence(raw):
    with pytest.raises(DemoQuoteTimingError) as caught:
        quote_time_at_receipt(raw, EVALUATED_AT)
    timing = caught.value.timing
    assert timing["freshness_status"] == "malformed_timestamp"
    assert timing["parsed_timestamp_utc"] is None
    assert timing["quote_age_seconds"] is None
    assert timing["receipt_timestamp_utc"] == EVALUATED_AT.isoformat()
    assert PRIVATE_TEXT not in str(timing) + str(caught.value)
    assert len(str(timing)) < 400


@pytest.mark.parametrize("raw", [STAMP // 1000, STAMP * 1000])
def test_wrong_units_are_never_guessed_or_promoted_to_fresh(raw):
    with pytest.raises(DemoQuoteTimingError) as caught:
        quote_time_at_receipt(raw, EVALUATED_AT)
    assert caught.value.timing["freshness_status"] != "fresh"
    assert caught.value.timing["timestamp_unit"] == "unix_milliseconds"


def test_naive_receipt_clock_is_refused_without_inventing_utc():
    with pytest.raises(DemoQuoteTimingError) as caught:
        quote_time_at_receipt(str(STAMP), datetime(2026, 10, 8))
    assert caught.value.timing["freshness_status"] == "invalid_receipt_clock"
    assert caught.value.timing["receipt_timestamp_utc"] is None
