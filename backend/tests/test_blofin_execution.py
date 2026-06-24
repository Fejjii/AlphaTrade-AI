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


# --- factory resolution ----------------------------------------------------


def test_resolver_returns_none_without_demo_mode() -> None:
    settings = Settings(_env_file=None)  # defaults: paper_internal
    assert resolve_exchange_execution_provider(settings) is None


def test_resolver_returns_provider_in_demo_mode() -> None:
    settings = Settings(_env_file=None, **_DEMO_SETTINGS)
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"code": "0", "data": []}))
    provider = resolve_exchange_execution_provider(settings, transport=transport)
    assert isinstance(provider, BloFinDemoExecutionProvider)
