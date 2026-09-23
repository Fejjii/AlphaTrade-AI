"""Policy for the combined paper activation package. No network and no orders."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.controlled_activation.profile import controlled_telegram_projection, package_disarmed
from app.controlled_activation.rollback import plan_package_rollback, rollback_refuses_apply
from app.core.config import Settings
from app.market_activation.profile import activation_state, live_market_activation_violations
from app.telegram_activation.preflight import (
    configuration_blockers,
    defaults_are_safe,
    run_preflight,
)
from app.workers.watcher_activation import evaluate_activation, staging_static_arm_ok
from tests.test_watcher_paper_activation import _config, _observations, _worker

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
    "provider_mode": "fallback",
    "rate_limit_use_redis": True,
    "rate_limit_allow_in_memory_fallback": False,
    "trusted_proxy_hops": 1,
    "debug": False,
    "perpetual_evidence_source": "binance_usdm",
    "market_data_futures_base_url": "https://fapi.binance.com",
}


def _package(**overrides: object) -> Settings:
    payload: dict[str, object] = {
        **_STAGING,
        "watcher_orchestration_enabled": True,
        "watcher_paper_staging_activation": True,
        "telegram_interaction_enabled": True,
        "telegram_paper_activation_armed": True,
        "telegram_inbound_mode": "polling",
        "telegram_bot_id": "bot-100",
        "telegram_chat_id": "tg-chat-1",
        "telegram_bot_token": "123456789:AAHtestTokenValueForStagingPackage",
        "telegram_alerts_enabled": False,
        "automatic_telegram_delivery_enabled": False,
        "telegram_network_permitted": True,
    }
    payload.update(overrides)
    return Settings(**payload)


def test_full_package_constructs_and_partial_flags_do_not() -> None:
    armed = _package()
    assert controlled_telegram_projection(armed) is True
    assert package_disarmed(armed) is False
    assert staging_static_arm_ok(armed) is True
    assert activation_state(armed) == "active"
    assert live_market_activation_violations(armed) == []
    assert "staging_package_incomplete" not in configuration_blockers(armed)
    assert "environment_forbidden" not in configuration_blockers(armed)

    with pytest.raises(ValidationError, match="telegram_inbound_mode"):
        _package(telegram_inbound_mode="webhook", telegram_webhook_secret="w" * 32)
    with pytest.raises(ValidationError, match="telegram_paper_activation_armed"):
        _package(telegram_network_permitted=False)

    with pytest.raises(ValidationError, match="telegram_interaction_enabled"):
        _package(watcher_orchestration_enabled=False, watcher_paper_staging_activation=False)
    with pytest.raises(ValidationError, match="telegram_paper_activation_armed"):
        Settings(**{**_STAGING, "telegram_paper_activation_armed": True})
    with pytest.raises(ValidationError, match="telegram_inbound_mode"):
        Settings(**{**_STAGING, "telegram_inbound_mode": "polling"})
    with pytest.raises(ValidationError, match="telegram_network_permitted"):
        Settings(**{**_STAGING, "telegram_network_permitted": True})
    with pytest.raises(ValidationError, match="telegram_webhook_secret"):
        Settings(**{**_STAGING, "telegram_webhook_secret": "w" * 32})
    with pytest.raises(ValidationError, match="telegram_alerts_enabled"):
        _package(telegram_alerts_enabled=True)
    with pytest.raises(ValidationError, match="replay evidence"):
        _package(perpetual_evidence_source="replay")
    with pytest.raises(ValidationError, match="telegram_interaction_enabled"):
        Settings(
            environment="local",
            perpetual_evidence_source="binance_usdm",
            telegram_interaction_enabled=True,
        )
    with pytest.raises(ValidationError, match="watcher_paper_staging_activation"):
        _package(environment="production", perpetual_evidence_source="replay")


def test_disarmed_defaults_and_preflight_are_not_armable() -> None:
    settings = Settings()
    assert package_disarmed(settings) is True
    assert defaults_are_safe(settings) is True
    assert controlled_telegram_projection(settings) is False
    report = run_preflight(settings=settings)
    assert report.runtime_armable is False
    assert report.verdict.value == "NOT_ARMED"

    staging = Settings(**_STAGING)
    assert controlled_telegram_projection(staging) is False
    assert "staging_package_incomplete" in configuration_blockers(staging)
    assert staging_static_arm_ok(staging) is False
    production = Settings(
        **{**_STAGING, "environment": "production", "perpetual_evidence_source": "replay"}
    )
    assert "environment_forbidden" in configuration_blockers(production)


def test_activation_gate_allows_only_the_controlled_pair() -> None:
    worker_id = _worker()
    healthy = _observations(worker_id)
    assert evaluate_activation(_config(), healthy).allowed is True
    pair = _config(
        telegram_paper_activation_armed=True,
        telegram_interaction_enabled=True,
        telegram_inbound_mode="polling",
        telegram_network_permitted=True,
    )
    assert evaluate_activation(pair, healthy).allowed is True
    refused = {
        "replay": (
            _config(evidence_source="replay"),
            healthy,
            "replay_evidence_while_live_required",
        ),
        "provider": (
            _config(),
            _observations(worker_id, provider_state="unavailable"),
            "provider_unavailable",
        ),
        "lineage": (
            _config(),
            _observations(worker_id, lineage_valid=False),
            "strategy_lineage_invalid",
        ),
        "trading": (_config(enable_real_trading=True), healthy, "real_trading_enabled"),
        "migration": (
            _config(),
            _observations(worker_id, migration_revision="not-a-head"),
            "migration_unhealthy",
        ),
        "alerts": (_config(telegram_alerts_enabled=True), healthy, "telegram_forbidden"),
        "partial": (_config(telegram_interaction_enabled=True), healthy, "telegram_forbidden"),
        "network": (_config(telegram_network_permitted=True), healthy, "telegram_forbidden"),
        "webhook": (
            _config(
                telegram_paper_activation_armed=True,
                telegram_interaction_enabled=True,
                telegram_inbound_mode="webhook",
                telegram_network_permitted=True,
            ),
            healthy,
            "telegram_forbidden",
        ),
    }
    for name, (config, observations, reason) in refused.items():
        decision = evaluate_activation(config, observations)
        assert decision.allowed is False, name
        assert decision.primary_reason == reason, name


def test_package_rollback_plan_is_fail_closed() -> None:
    text = "\n".join(step.action for step in plan_package_rollback())
    assert "PERPETUAL_EVIDENCE_SOURCE=replay" in text
    assert "WATCHER_ORCHESTRATION_ENABLED=false" in text
    assert "TELEGRAM_PAPER_ACTIVATION_ARMED=false" in text
    assert "ENABLE_REAL_TRADING=false" in text
    assert "Do not downgrade Alembic" in text
    assert "ENABLE_REAL_TRADING=true" not in text
    assert "database rows" in rollback_refuses_apply()
