"""Stored BloFin secrets stay sealed during paper Binance USD-M evidence."""

from __future__ import annotations

import json

import httpx
import pytest
import structlog.testing
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import ExecutionMode, Settings
from app.core.errors import ExchangeDemoInactiveError
from app.core.exchange_demo_access import (
    get_demo_account_provider,
    get_demo_execution_provider,
)
from app.core.execution_credentials import (
    CredentialAccessDeniedError,
    blofin_execution_authorized,
    load_blofin_execution_credentials,
    paper_credential_isolation_active,
)
from app.main import create_app
from app.market_activation.profile import activation_state, live_market_activation_violations
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.adapters.factory import resolve_perpetual_evidence_source
from app.providers.exchange.blofin_client import BloFinClient
from app.providers.exchange.factory import (
    build_blofin_client,
    resolve_exchange_execution_provider,
    resolve_exchange_provider,
)

_KEY = "stored-blofin-key-9f3a"
_SECRET = "stored-blofin-secret-9f3a"
_PASSPHRASE = "stored-blofin-pass-9f3a"
_SECRETS = (_KEY, _SECRET, _PASSPHRASE)
_DEMO_REST = "https://demo-trading-openapi.blofin.com"

_STAGING: dict[str, object] = {
    "environment": "staging",
    "jwt_secret": "x" * 32,
    "database_url": "postgresql+psycopg://user:pass@db.example.com:5432/alphatrade",
    "redis_url": "redis://redis.example.com:6379/0",
    "qdrant_url": "https://qdrant.example.com",
    "openai_api_key": "sk-test-not-a-real-key",
    "cors_origins": "https://app.example.com",
    "auth_refresh_cookie_enabled": True,
    "auth_cookie_secure": True,
    "auth_cookie_samesite": "none",
    "enable_real_trading": False,
    "execution_mode": "paper",
    "exchange_mode": "paper_internal",
    "blofin_demo_enabled": False,
    "provider_mode": "fallback",
    "rate_limit_use_redis": True,
    "rate_limit_allow_in_memory_fallback": False,
    "trusted_proxy_hops": 1,
    "debug": False,
    "perpetual_evidence_source": "binance_usdm",
    "market_data_futures_base_url": "https://fapi.binance.com",
    "blofin_api_key": _KEY,
    "blofin_api_secret": _SECRET,
    "blofin_api_passphrase": _PASSPHRASE,
}


def _local(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": "local",
        "execution_mode": "paper",
        "enable_real_trading": False,
        "exchange_mode": "paper_internal",
        "blofin_demo_enabled": False,
        "provider_mode": "mock",
        "rate_limit_use_redis": False,
        "market_data_cache_use_redis": False,
        "access_token_denylist_use_redis": False,
        "perpetual_evidence_source": "binance_usdm",
        "market_data_futures_base_url": "https://fapi.binance.com",
        "blofin_api_key": _KEY,
        "blofin_api_secret": _SECRET,
        "blofin_api_passphrase": _PASSPHRASE,
    }
    base.update(overrides)
    return Settings(**base)


def _assert_secrets_absent(text: str) -> None:
    for secret in _SECRETS:
        assert secret not in text


def test_staging_settings_boot_with_stored_blofin_credentials() -> None:
    settings = Settings(**_STAGING)
    assert settings.perpetual_evidence_source == "binance_usdm"
    assert settings.execution_mode is ExecutionMode.PAPER
    assert settings.enable_real_trading is False
    assert settings.real_trading_enabled is False
    assert settings.exchange_mode.value == "paper_internal"
    assert settings.blofin_demo_enabled is False
    assert paper_credential_isolation_active(settings) is True
    assert blofin_execution_authorized(settings) is False
    assert activation_state(settings) == "active"
    assert live_market_activation_violations(settings) == []
    _assert_secrets_absent(repr(settings))


def test_stored_credentials_do_not_reach_market_or_paper_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _local()
    constructed: list[str] = []
    requests: list[httpx.Request] = []

    def _refuse_client(self: BloFinClient, **kwargs: object) -> None:
        constructed.append("client")
        raise AssertionError("authenticated BloFin client must not be constructed")

    def _refuse_request(self: BloFinClient, *args: object, **kwargs: object) -> None:
        requests.append(httpx.Request("GET", "https://demo-trading-openapi.blofin.com"))
        raise AssertionError("authenticated BloFin request must not run")

    monkeypatch.setattr(BloFinClient, "__init__", _refuse_client)
    monkeypatch.setattr(BloFinClient, "request", _refuse_request)

    resolved = resolve_exchange_provider(settings)
    assert resolved.execution is None
    assert resolved.account is None
    assert resolved.market_data is None
    assert resolved.is_demo is False
    assert resolve_exchange_execution_provider(settings) is None
    with pytest.raises(ExchangeDemoInactiveError):
        get_demo_execution_provider(settings)
    with pytest.raises(ExchangeDemoInactiveError):
        get_demo_account_provider(settings)
    with pytest.raises(CredentialAccessDeniedError) as denied:
        build_blofin_client(settings)
    _assert_secrets_absent(str(denied.value))

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "fapi.binance.com"
        lowered = {key.lower() for key in request.headers}
        assert "x-mbx-apikey" not in lowered
        assert "authorization" not in lowered
        return httpx.Response(200, json={})

    source = resolve_perpetual_evidence_source(
        settings,
        transport=httpx.MockTransport(handler),
    )
    assert isinstance(source, BinanceUsdmPerpetualSource)
    dumped = json.dumps(source.__dict__, default=str)
    _assert_secrets_absent(dumped)
    source._get("/fapi/v1/ping", None)
    assert requests
    assert all(item.url.host == "fapi.binance.com" for item in requests)
    assert constructed == []


def test_secrets_do_not_leak_through_logs_errors_or_health() -> None:
    with structlog.testing.capture_logs() as captured:
        settings = _local()
        app = create_app(settings)
        with TestClient(app) as client:
            health = client.get("/health").json()
    blob = json.dumps({"health": health, "logs": captured}, default=str)
    _assert_secrets_absent(blob)
    _assert_secrets_absent(repr(settings))
    assert health["execution_mode"] == "paper"
    assert health["real_trading_enabled"] is False
    assert health["perpetual_evidence_source"] == "binance_usdm"
    assert health["perpetual_evidence_activation"] == "active"
    assert health["exchange_credentials_used_for_market_evidence"] is False
    assert health["live_market_read_only"] is True

    with pytest.raises(ValidationError) as incomplete:
        _local(
            exchange_mode="paper_exchange_demo",
            blofin_demo_enabled=True,
            blofin_demo_rest_base_url=_DEMO_REST,
            blofin_api_passphrase="",
        )
    _assert_secrets_absent(str(incomplete.value))


def test_incomplete_execution_gate_fails_closed() -> None:
    sealed = _local(perpetual_evidence_source="replay")
    assert blofin_execution_authorized(sealed) is False
    with pytest.raises(CredentialAccessDeniedError) as denied:
        load_blofin_execution_credentials(sealed)
    _assert_secrets_absent(str(denied.value))
    assert resolve_exchange_provider(sealed).execution is None

    partial = _local(
        perpetual_evidence_source="replay",
        blofin_demo_enabled=True,
        blofin_demo_rest_base_url=_DEMO_REST,
    )
    assert paper_credential_isolation_active(partial) is False
    assert blofin_execution_authorized(partial) is False
    with pytest.raises(CredentialAccessDeniedError):
        build_blofin_client(partial)
    assert resolve_exchange_execution_provider(partial) is None

    with pytest.raises(ValidationError) as demo_off:
        _local(
            perpetual_evidence_source="replay",
            exchange_mode="paper_exchange_demo",
            blofin_demo_enabled=False,
            blofin_demo_rest_base_url=_DEMO_REST,
        )
    _assert_secrets_absent(str(demo_off.value))

    with pytest.raises(ValidationError) as live_demo:
        _local(
            blofin_demo_enabled=True,
            exchange_mode="paper_exchange_demo",
            blofin_demo_rest_base_url=_DEMO_REST,
        )
    _assert_secrets_absent(str(live_demo.value))
    assert "paper credential isolation" in str(live_demo.value)

    for overrides in (
        {"enable_real_trading": True},
        {"execution_mode": "trade"},
        {"exchange_mode": "trade_live"},
    ):
        with pytest.raises(ValidationError) as unsafe:
            _local(**overrides)
        _assert_secrets_absent(str(unsafe.value))


def test_complete_demo_gate_is_required_before_credentials_load() -> None:
    opened = _local(
        perpetual_evidence_source="replay",
        exchange_mode="paper_exchange_demo",
        blofin_demo_enabled=True,
        blofin_demo_rest_base_url=_DEMO_REST,
    )
    assert blofin_execution_authorized(opened) is True
    loaded = load_blofin_execution_credentials(opened)
    assert loaded.api_key == _KEY
    assert "redacted" in repr(loaded)
    _assert_secrets_absent(repr(loaded))
    _assert_secrets_absent(str(loaded))
