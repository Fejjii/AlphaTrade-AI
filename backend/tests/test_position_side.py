"""Tests for BloFin positionSide resolution (net vs hedge modes)."""

from __future__ import annotations

import pytest

from app.providers.exchange.errors import ExchangeRequestError
from app.providers.exchange.position_side import resolve_position_side
from app.schemas.common import OrderSide


def test_net_mode_buy_returns_net() -> None:
    assert resolve_position_side("net_mode", OrderSide.BUY, reduce_only=False) == "net"


def test_net_mode_sell_returns_net() -> None:
    assert resolve_position_side("net_mode", OrderSide.SELL, reduce_only=False) == "net"


def test_net_mode_reduce_only_returns_net() -> None:
    assert resolve_position_side("net_mode", OrderSide.BUY, reduce_only=True) == "net"
    assert resolve_position_side("net_mode", OrderSide.SELL, reduce_only=True) == "net"


def test_hedge_mode_buy_open_returns_long() -> None:
    assert resolve_position_side("long_short_mode", OrderSide.BUY, reduce_only=False) == "long"


def test_hedge_mode_sell_open_returns_short() -> None:
    assert resolve_position_side("long_short_mode", OrderSide.SELL, reduce_only=False) == "short"


def test_hedge_mode_reduce_only_raises() -> None:
    with pytest.raises(ExchangeRequestError, match="reduce-only is not supported"):
        resolve_position_side("long_short_mode", OrderSide.BUY, reduce_only=True)
    with pytest.raises(ExchangeRequestError, match="reduce-only is not supported"):
        resolve_position_side("long_short_mode", OrderSide.SELL, reduce_only=True)


def test_hedge_mode_reduce_only_includes_position_mode() -> None:
    with pytest.raises(ExchangeRequestError) as exc_info:
        resolve_position_side("long_short_mode", OrderSide.BUY, reduce_only=True)
    assert exc_info.value.position_mode == "long_short_mode"


def test_unknown_mode_raises() -> None:
    with pytest.raises(ExchangeRequestError, match="unknown BloFin position mode"):
        resolve_position_side("invalid_mode", OrderSide.BUY, reduce_only=False)


def test_empty_mode_raises() -> None:
    with pytest.raises(ExchangeRequestError, match="unknown BloFin position mode"):
        resolve_position_side("", OrderSide.BUY, reduce_only=False)
    with pytest.raises(ExchangeRequestError, match="unknown BloFin position mode"):
        resolve_position_side("   ", OrderSide.SELL, reduce_only=False)
