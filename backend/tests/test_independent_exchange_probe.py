"""Read-only operator probes expose supported components without substituting them."""

import httpx

from app.evidence_pipeline.probe import probe_exchange
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.derivatives import DerivativeMetric
from app.market_contracts.enums import VenueId
from tests.support.phase5_market import EVALUATED_AT
from tests.test_live_evidence_pipeline import _fixture_usdm_handler
from tests.test_market_intelligence_cvd_orderflow import NOW, provider
from tests.test_market_intelligence_oi_funding import contract_payload, payload


def test_binance_probe_proves_all_components_with_exact_identity():
    base = _fixture_usdm_handler()

    def handle(request):
        if request.url.path.endswith("exchangeInfo"):
            return httpx.Response(200, json=contract_payload(VenueId.BINANCE))
        if request.url.path.endswith(("openInterest", "fundingRate")):
            metric = (
                DerivativeMetric.OPEN_INTEREST
                if request.url.path.endswith("openInterest")
                else DerivativeMetric.FUNDING
            )
            return httpx.Response(
                200,
                json=payload(VenueId.BINANCE, metric, stamp=int(EVALUATED_AT.timestamp() * 1000)),
            )
        return base.handle_request(request)

    source = BinanceUsdmPerpetualSource(transport=httpx.MockTransport(handle), max_retries=0)
    result = probe_exchange(source, clock=lambda: EVALUATED_AT)
    assert result["canonical_market_window_complete"]
    assert result["all_requested_components_available"]
    assert not result["watcher_acceptance_verified"]
    assert result["source"]["instrument_id"] == "binance:usdm_futures:perpetual:BTCUSDT"
    assert result["source"]["market_type"] == "perpetual"
    assert result["proof"]["cvd_event_count"] > 0
    assert result["proof"]["coverage_content_hash"]
    assert result["proof"]["order_flow_5m"]["coverage_content_hash"]
    assert len(source.evidence_cache) == 0


def test_bybit_supported_intelligence_does_not_replace_missing_canonical_history():
    source, _ = provider(VenueId.BYBIT)
    result = probe_exchange(source, clock=lambda: NOW)
    assert not result["canonical_market_window_complete"]
    assert not result["all_requested_components_available"]
    assert result["source"]["instrument_id"] == "bybit:usdm_futures:perpetual:BTCUSDT"
    for key in ("current_price", "open_interest", "funding", "order_flow_5m"):
        assert key in result["proof"]
    assert "cvd_content_hash" not in result["proof"]
    assert any(
        row["component"] == "ohlcv_15m" and row["status"] == "unavailable"
        for row in result["diagnostics"]
    )
