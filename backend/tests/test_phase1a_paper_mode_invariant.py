"""Phase 1A slice 1 — permanent exact-paper-mode invariant."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents.runtime import AgentRuntime
from app.core.config import ExchangeMode, ExecutionMode, Settings
from app.core.exchange_safety import BLOFIN_DEMO_HOST_ALLOWLIST
from app.core.paper_safety import (
    assert_execution_capable_composition_root,
    assert_permanent_paper_mode,
)
from app.main import create_app
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService
from app.strategies.registry import build_default_registry
from app.tools.registry import build_default_registry as build_tools

_DEMO_HOST = next(iter(BLOFIN_DEMO_HOST_ALLOWLIST))
_DEMO_OK = {
    "exchange_mode": "paper_exchange_demo",
    "blofin_demo_enabled": True,
    "blofin_api_key": "demo-key",
    "blofin_api_secret": "demo-secret",
    "blofin_api_passphrase": "demo-pass",
    "blofin_demo_rest_base_url": f"https://{_DEMO_HOST}",
}


def test_safe_paper_settings_accepted() -> None:
    settings = Settings(execution_mode="paper", enable_real_trading=False)
    assert settings.execution_mode is ExecutionMode.PAPER
    assert settings.enable_real_trading is False
    assert settings.real_trading_enabled is False
    assert settings.exchange_mode is ExchangeMode.PAPER_INTERNAL
    assert_permanent_paper_mode(settings)
    assert_execution_capable_composition_root(settings)


_NON_LOCAL_BASE = {
    "jwt_secret": "x" * 32,
    "database_url": "postgresql+psycopg://user:pass@db.example.com:5432/alphatrade",
    "redis_url": "redis://redis.example.com:6379/0",
    "qdrant_url": "https://qdrant.example.com",
    "openai_api_key": "sk-test-not-a-real-key",
    "cors_origins": "https://app.example.com",
    "auth_refresh_cookie_enabled": True,
    "auth_cookie_secure": True,
    "auth_cookie_samesite": "none",
    "execution_mode": "paper",
    "provider_mode": "fallback",
    "rate_limit_use_redis": True,
    "rate_limit_allow_in_memory_fallback": False,
    "trusted_proxy_hops": 1,
    "debug": False,
}


def test_enable_real_trading_true_rejected_in_every_environment() -> None:
    with pytest.raises(ValidationError, match="ENABLE_REAL_TRADING=true"):
        Settings(environment="local", enable_real_trading=True, jwt_secret="x" * 32)
    for environment in ("staging", "production"):
        with pytest.raises(ValidationError, match="ENABLE_REAL_TRADING=true"):
            Settings(
                **{
                    **_NON_LOCAL_BASE,
                    "environment": environment,
                    "enable_real_trading": True,
                }
            )


def test_live_execution_mode_rejected() -> None:
    with pytest.raises(ValidationError, match="execution_mode=trade is permanently rejected"):
        Settings(execution_mode="trade", enable_real_trading=False)
    with pytest.raises(ValidationError, match="permanently rejected"):
        Settings(execution_mode="trade", enable_real_trading=True)


def test_production_live_exchange_host_rejected() -> None:
    with pytest.raises(ValidationError, match="production host"):
        Settings(blofin_demo_rest_base_url="https://openapi.blofin.com")


def test_trade_live_rejected() -> None:
    with pytest.raises(ValidationError, match="trade_live is permanently disabled"):
        Settings(exchange_mode="trade_live")


def test_read_only_plus_execution_capable_process_rejected() -> None:
    read_only = Settings(execution_mode="read_only", enable_real_trading=False)
    assert read_only.execution_mode is ExecutionMode.READ_ONLY
    with pytest.raises(ValueError, match="execution-capable process"):
        assert_execution_capable_composition_root(read_only)
    with pytest.raises(ValueError, match="execution-capable process"):
        create_app(settings=read_only)
    with pytest.raises(ValueError, match="execution-capable process"):
        AgentRuntime(
            settings=read_only,
            risk_service=RiskService(),
            strategy_service=StrategyService(registry=build_default_registry()),
            tool_registry=build_tools(read_only),
        )


def test_read_only_plus_worker_flag_rejected_at_settings() -> None:
    with pytest.raises(ValidationError, match="execution-capable process"):
        Settings(execution_mode="read_only", worker_enabled=True)


def test_demo_and_paper_internal_safe_combinations_accepted() -> None:
    internal = Settings(exchange_mode="paper_internal", execution_mode="paper")
    assert internal.exchange_demo_active is False
    demo = Settings(**_DEMO_OK)
    assert demo.exchange_demo_active is True
    assert demo.real_trading_enabled is False
    assert_execution_capable_composition_root(demo)
