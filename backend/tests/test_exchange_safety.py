"""Tests for the exchange-connectivity safety axis (Slice 56A).

The exchange axis must be independent from the trading-safety axis, must refuse
``trade_live`` outright, and must only allow ``paper_exchange_demo`` against an
allowlisted BloFin demo host with credentials present.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import ExchangeMode, Settings
from app.core.exchange_safety import (
    BLOFIN_DEMO_HOST_ALLOWLIST,
    assert_demo_host,
    is_allowlisted_demo_host,
)

_DEMO_HOST = next(iter(BLOFIN_DEMO_HOST_ALLOWLIST))
_DEMO_REST = f"https://{_DEMO_HOST}"
_DEMO_WS = f"wss://{_DEMO_HOST}/ws/public"

_DEMO_OK = {
    "exchange_mode": "paper_exchange_demo",
    "blofin_demo_enabled": True,
    "blofin_api_key": "demo-key",
    "blofin_api_secret": "demo-secret",
    "blofin_api_passphrase": "demo-pass",
    "blofin_demo_rest_base_url": _DEMO_REST,
    "blofin_demo_ws_url": _DEMO_WS,
}


def test_default_exchange_mode_is_internal_and_safe() -> None:
    settings = Settings()
    assert settings.exchange_mode is ExchangeMode.PAPER_INTERNAL
    assert settings.exchange_demo_active is False
    assert settings.blofin_demo_configured is False


def test_exchange_mode_normalized_from_mixed_case() -> None:
    settings = Settings(exchange_mode="  Paper_Internal ")
    assert settings.exchange_mode is ExchangeMode.PAPER_INTERNAL


def test_trade_live_is_permanently_blocked() -> None:
    with pytest.raises(ValidationError, match="trade_live is permanently disabled"):
        Settings(exchange_mode="trade_live")


def test_paper_exchange_demo_valid_config_passes() -> None:
    settings = Settings(**_DEMO_OK)
    assert settings.exchange_demo_active is True
    assert settings.blofin_demo_configured is True


def test_paper_exchange_demo_requires_enabled_flag() -> None:
    with pytest.raises(ValidationError, match="blofin_demo_enabled=true"):
        Settings(**{**_DEMO_OK, "blofin_demo_enabled": False})


def test_paper_exchange_demo_requires_credentials() -> None:
    with pytest.raises(ValidationError, match="BloFin demo credentials"):
        Settings(**{**_DEMO_OK, "blofin_api_secret": ""})


def test_paper_exchange_demo_requires_rest_url() -> None:
    with pytest.raises(ValidationError, match="blofin_demo_rest_base_url"):
        Settings(**{**_DEMO_OK, "blofin_demo_rest_base_url": ""})


def test_paper_exchange_demo_rejects_production_host() -> None:
    with pytest.raises(ValidationError, match="production host"):
        Settings(**{**_DEMO_OK, "blofin_demo_rest_base_url": "https://openapi.blofin.com"})


def test_paper_exchange_demo_rejects_non_allowlisted_host() -> None:
    with pytest.raises(ValidationError, match="allowlisted BloFin demo host"):
        Settings(**{**_DEMO_OK, "blofin_demo_rest_base_url": "https://evil.example.com"})


def test_paper_exchange_demo_rejects_plaintext_http() -> None:
    with pytest.raises(ValidationError, match="allowlisted BloFin demo host"):
        Settings(**{**_DEMO_OK, "blofin_demo_rest_base_url": f"http://{_DEMO_HOST}"})


def test_paper_exchange_demo_rejects_bad_ws_host() -> None:
    with pytest.raises(ValidationError, match="blofin_demo_ws_url"):
        Settings(**{**_DEMO_OK, "blofin_demo_ws_url": "wss://openapi.blofin.com/ws"})


def test_paper_exchange_demo_requires_paper_execution_mode() -> None:
    with pytest.raises(ValidationError, match="requires execution_mode=paper"):
        Settings(**{**_DEMO_OK, "execution_mode": "read_only"})


def test_demo_axis_does_not_enable_real_trading() -> None:
    settings = Settings(**_DEMO_OK)
    assert settings.real_trading_enabled is False
    assert settings.enable_real_trading is False


def test_is_allowlisted_demo_host_helper() -> None:
    assert is_allowlisted_demo_host(_DEMO_REST) is True
    assert is_allowlisted_demo_host(_DEMO_WS) is True
    assert is_allowlisted_demo_host("https://openapi.blofin.com") is False
    assert is_allowlisted_demo_host(f"http://{_DEMO_HOST}") is False


def test_assert_demo_host_guard() -> None:
    assert_demo_host(_DEMO_REST)  # no raise
    with pytest.raises(ValueError, match="production host"):
        assert_demo_host("https://openapi.blofin.com")
    with pytest.raises(ValueError, match="not an allowlisted demo host"):
        assert_demo_host("https://evil.example.com")
