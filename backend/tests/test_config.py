"""Tests for settings loading and trading-safety invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import ExecutionMode, Settings


def test_defaults_are_safe() -> None:
    settings = Settings()
    assert settings.execution_mode is ExecutionMode.PAPER
    assert settings.enable_real_trading is False
    assert settings.real_trading_enabled is False
    assert settings.provider_mode == "mock"
    assert settings.observability_strict_mode is False


def test_cors_origins_accepts_comma_separated_string() -> None:
    settings = Settings(cors_origins="http://a.test, http://b.test")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_auth_cookie_samesite_normalized() -> None:
    settings = Settings(auth_cookie_samesite="None")
    assert settings.auth_cookie_samesite == "none"


def test_trade_mode_requires_explicit_real_trading_flag() -> None:
    with pytest.raises(ValidationError, match="enable_real_trading"):
        Settings(execution_mode="trade", enable_real_trading=False)


def test_real_trading_enabled_only_when_fully_configured() -> None:
    settings = Settings(execution_mode="trade", enable_real_trading=True)
    assert settings.real_trading_enabled is True
