"""Tests for the BloFin demo execution provider (Slice 61).

All network access is mocked via ``httpx.MockTransport`` — no real venue is
contacted. These tests assert the hard safety gates (real trading impossible,
demo-host enforced) and correct order-body construction / fill parsing.
"""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.providers.exchange.base import ExchangeOrderRequest
from app.providers.exchange.blofin_client import BloFinClient
from app.providers.exchange.blofin_execution import (
    BloFinDemoExecutionProvider,
    DemoExecutionDisabledError,
)
from app.providers.exchange.errors import (
    ExchangeAuthError,
    ExchangeRequestError,
    ExchangeUnavailableError,
)
from app.providers.exchange.factory import resolve_exchange_execution_provider
from app.schemas.common import OrderSide, OrderType

_DEMO_URL = "https://demo-trading-openapi.blofin.com"

_DEMO_SETTINGS = {
    "exchange_mode": "paper_exchange_demo",
    "blofin_demo_enabled": True,
    "blofin_api_key": "demo-key",
    "blofin_api_secret": "demo-secret",
    "blofin_api_passphrase": "demo-pass",
    "blofin_demo_rest_base_url": _DEMO_URL,
}


def _client(handler, **kwargs) -> BloFinClient:
    return BloFinClient(
        base_url=_DEMO_URL,
        api_key="demo-key",
        api_secret="demo-secret",
        api_passphrase="demo-pass",
        transport=httpx.MockTransport(handler),
        sleeper=lambda _seconds: None,
        max_retries=1,
        **kwargs,
    )


def _provider(handler, **kwargs) -> BloFinDemoExecutionProvider:
    return BloFinDemoExecutionProvider(
        _client(handler),
        real_trading_enabled=False,
        exchange_demo_active=True,
        **kwargs,
    )


def _order_request() -> ExchangeOrderRequest:
    return ExchangeOrderRequest(
        symbol="BTCUSDT",
        inst_id="BTC-USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        size=Decimal("0.01"),
        client_order_id="idem-123",
    )


# --- safety gates ----------------------------------------------------------


def test_refuses_when_real_trading_enabled() -> None:
    provider = BloFinDemoExecutionProvider(
        _client(lambda r: httpx.Response(200, json={"code": "0", "data": []})),
        real_trading_enabled=True,
        exchange_demo_active=True,
    )
    with pytest.raises(DemoExecutionDisabledError, match="real_trading_enabled"):
        provider.place_order(_order_request())


def test_refuses_when_not_demo_mode() -> None:
    provider = BloFinDemoExecutionProvider(
        _client(lambda r: httpx.Response(200, json={"code": "0", "data": []})),
        real_trading_enabled=False,
        exchange_demo_active=False,
    )
    with pytest.raises(DemoExecutionDisabledError, match="paper_exchange_demo"):
        provider.place_order(_order_request())


def test_place_order_refuses_non_demo_host() -> None:
    # The client itself refuses to be constructed against a production host.
    with pytest.raises(ValueError, match="production host"):
        BloFinClient(
            base_url="https://openapi.blofin.com",
            api_key="k",
            api_secret="s",
            api_passphrase="p",
        )


# --- order placement -------------------------------------------------------


def test_place_order_sends_signed_body_and_parses_fills() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    {
                        "orderId": "demo-777",
                        "clientOrderId": "idem-123",
                        "state": "filled",
                        "filledSize": "0.01",
                        "averagePrice": "65000.0",
                        "fills": [
                            {
                                "tradeId": "t1",
                                "fillPrice": "65000.0",
                                "fillSize": "0.01",
                                "fee": "0.02",
                                "feeCurrency": "USDT",
                            }
                        ],
                    }
                ],
            },
        )

    result = _provider(handler).place_order(_order_request())

    body = captured["body"]
    assert body["instId"] == "BTC-USDT"
    assert body["side"] == "buy"
    assert body["orderType"] == "market"
    assert body["size"] == "0.01"
    assert body["positionSide"] == "net"
    assert body["marginMode"] == "cross"
    assert body["clientOrderId"] == "idem-123"
    assert captured["headers"]["access-key"] == "demo-key"

    assert result.exchange_order_id == "demo-777"
    assert result.status == "filled"
    assert result.filled_size == Decimal("0.01")
    assert result.average_price == Decimal("65000.0")
    assert len(result.fills) == 1
    assert result.fills[0].fee == Decimal("0.02")
    assert result.fills[0].fee_currency == "USDT"


def test_place_limit_order_includes_price_and_reduce_only() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"code": "0", "data": [{"orderId": "x"}]})

    req = ExchangeOrderRequest(
        symbol="ETHUSDT",
        inst_id="ETH-USDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        size=Decimal("1"),
        price=Decimal("3500.5"),
        reduce_only=True,
    )
    _provider(handler).place_order(req)
    body = captured["body"]
    assert body["price"] == "3500.5"
    assert body["reduceOnly"] == "true"
    assert body["positionSide"] == "net"


def test_place_order_includes_position_side_net() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"code": "0", "data": [{"orderId": "x"}]})

    _provider(handler).place_order(_order_request())
    assert captured["body"]["positionSide"] == "net"


# --- factory resolution ----------------------------------------------------


def test_resolver_returns_none_without_demo_mode() -> None:
    settings = Settings(_env_file=None)  # defaults: paper_internal
    assert resolve_exchange_execution_provider(settings) is None


def test_resolver_returns_provider_in_demo_mode() -> None:
    settings = Settings(_env_file=None, **_DEMO_SETTINGS)
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"code": "0", "data": []}))
    provider = resolve_exchange_execution_provider(settings, transport=transport)
    assert isinstance(provider, BloFinDemoExecutionProvider)


# --- venue rejection diagnostics (mocked; no real network) -----------------


def _limit_order_request(**overrides: object) -> ExchangeOrderRequest:
    base = {
        "symbol": "BTCUSDT",
        "inst_id": "BTC-USDT",
        "side": OrderSide.BUY,
        "order_type": OrderType.LIMIT,
        "size": Decimal("0.1"),
        "price": Decimal("44716.5"),
        "client_order_id": "slice66b001",
    }
    base.update(overrides)
    return ExchangeOrderRequest(**base)  # type: ignore[arg-type]


def test_place_order_price_band_rejection_persists_sanitized_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": "51008",
                "msg": "Order price is out of the allowable range",
                "data": None,
            },
        )

    with pytest.raises(ExchangeRequestError) as exc_info:
        _provider(handler).place_order(_limit_order_request())
    details = exc_info.value.details
    assert details is not None
    assert details.venue_error_code == "51008"
    assert details.http_status == 200
    assert details.endpoint_name == "POST /api/v1/trade/order"
    assert "allowable range" in (details.venue_error_message or "")


def test_place_order_invalid_instrument_rejection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": "51001", "msg": "Instrument ID does not exist", "data": None},
        )

    with pytest.raises(ExchangeRequestError) as exc_info:
        _provider(handler).place_order(_limit_order_request(inst_id="NOT-A-PAIR"))
    assert exc_info.value.details is not None
    assert exc_info.value.details.venue_error_code == "51001"


def test_place_order_invalid_order_type_rejection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["orderType"] == "limit"
        return httpx.Response(
            200,
            json={"code": "51000", "msg": "Parameter orderType error", "data": None},
        )

    with pytest.raises(ExchangeRequestError) as exc_info:
        _provider(handler).place_order(_limit_order_request(order_type=OrderType.LIMIT))
    assert exc_info.value.details is not None
    assert "orderType" in (exc_info.value.details.venue_error_message or "")


def test_place_order_missing_required_field_rejection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": "51000", "msg": "Parameter positionSide error", "data": None},
        )

    with pytest.raises(ExchangeRequestError) as exc_info:
        _provider(handler).place_order(_limit_order_request())
    assert exc_info.value.details is not None
    assert "positionSide" in (exc_info.value.details.venue_error_message or "")


def test_place_order_read_only_or_trade_denied() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"code": "403", "msg": "API key read-only", "data": None})

    with pytest.raises(ExchangeAuthError) as exc_info:
        _provider(handler).place_order(_limit_order_request())
    details = exc_info.value.details
    assert details is not None
    assert details.http_status == 403
    assert details.endpoint_name == "POST /api/v1/trade/order"


def test_place_order_venue_4xx_http_rejection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    with pytest.raises(ExchangeRequestError) as exc_info:
        _provider(handler).place_order(_limit_order_request())
    details = exc_info.value.details
    assert details is not None
    assert details.http_status == 400
    assert details.venue_error_code == "400"


def test_place_order_venue_5xx_http_rejection() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="unavailable")

    with pytest.raises(ExchangeUnavailableError) as exc_info:
        _provider(handler).place_order(_limit_order_request())
    details = exc_info.value.details
    assert details is not None
    assert details.http_status == 503
    assert details.endpoint_name == "POST /api/v1/trade/order"
    assert calls["n"] == 2


def test_rejection_diagnostics_do_not_leak_secrets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": "1001",
                "msg": "api_key=supersecret",
                "data": None,
            },
        )

    with pytest.raises(ExchangeRequestError) as exc_info:
        _provider(handler).place_order(_limit_order_request(client_order_id="idem12345"))
    details_msg = exc_info.value.details.venue_error_message if exc_info.value.details else ""
    assert "supersecret" not in str(exc_info.value)
    assert "supersecret" not in (details_msg or "")
    assert "***REDACTED***" in str(exc_info.value) or "***REDACTED***" in (details_msg or "")


def test_place_order_nested_error_surfaces_per_order_reason() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": "1",
                "msg": "All operations failed",
                "data": [
                    {
                        "code": "51020",
                        "msg": "Position side mismatch",
                        "clientOrderId": "AT123",
                    }
                ],
            },
        )

    with pytest.raises(ExchangeRequestError) as exc_info:
        _provider(handler).place_order(_limit_order_request())
    details = exc_info.value.details
    assert details is not None
    assert details.venue_error_code == "51020"
    assert "Position side mismatch" in (details.venue_error_message or "")
    assert details.http_status == 200


def test_place_order_nested_error_redacts_secrets_in_data_msg() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": "1",
                "msg": "All operations failed",
                "data": [{"code": "51000", "msg": "api_key=supersecret", "clientOrderId": "x"}],
            },
        )

    with pytest.raises(ExchangeRequestError) as exc_info:
        _provider(handler).place_order(_limit_order_request())
    details_msg = exc_info.value.details.venue_error_message if exc_info.value.details else ""
    assert "supersecret" not in str(exc_info.value)
    assert "supersecret" not in (details_msg or "")


def test_place_order_envelope_success_with_nested_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "code": "51008",
                        "msg": "Order price is out of the allowable range",
                        "clientOrderId": "x",
                    }
                ],
            },
        )

    with pytest.raises(ExchangeRequestError) as exc_info:
        _provider(handler).place_order(_limit_order_request())
    details = exc_info.value.details
    assert details is not None
    assert details.venue_error_code == "51008"
    assert "allowable range" in (details.venue_error_message or "")
