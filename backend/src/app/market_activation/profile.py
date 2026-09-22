"""Fail-closed profile for staging Binance USD-M read-only evidence.

Replay stays the process default so deterministic tests do not need the
network. Staging's intended evidence source is the public USD-M adapter.
Selecting that source refuses credentials, spot hosts, the legacy scanner,
legacy Telegram delivery, and live trading. The staging paper Watcher arm
may select it. Rollback is ``PERPETUAL_EVIDENCE_SOURCE=replay``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal, TypedDict
from urllib.parse import urlsplit

from app.core.config import Environment, ExchangeMode, ExecutionMode, Settings
from app.market_contracts.catalog import default_perpetual_catalog
from app.market_contracts.first_slice import (
    FIRST_SLICE_SYMBOL,
    FIRST_SLICE_TRADE_FRESHNESS_SECONDS,
)
from app.market_contracts.freshness import (
    FIRST_SLICE_FRESHNESS_POLICY_VERSION,
    first_slice_freshness_policy,
)

REPLAY_MODES = frozenset({"replay", "mock", "fixture"})
LIVE_MODES = frozenset({"binance_usdm", "binance-usdm", "usdm"})
LIVE_SOURCE: Literal["binance_usdm"] = "binance_usdm"
ROLLBACK_SOURCE: Literal["replay"] = "replay"
INTENDED_STAGING_SOURCE: Literal["binance_usdm"] = LIVE_SOURCE
APPROVED_FUTURES_ORIGIN = "https://fapi.binance.com"
LIVE_QUOTE_FRESHNESS_SECONDS: Literal[10] = 10
FIRST_PERPETUAL_SYMBOL: Literal["BTCUSDT"] = "BTCUSDT"

# Public market evidence must not observe exchange credentials. Names only.
FORBIDDEN_MARKET_CREDENTIAL_ENV = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_SECRET_KEY",
    "BINANCE_FUTURES_API_KEY",
    "BINANCE_FUTURES_API_SECRET",
    "FAPI_API_KEY",
    "FAPI_API_SECRET",
)

ActivationState = Literal["inactive", "active", "refused"]
ConfiguredSource = Literal["replay", "binance_usdm"]


class PerpetualEvidenceHealth(TypedDict):
    perpetual_evidence_source: ConfiguredSource
    perpetual_evidence_activation: ActivationState
    perpetual_evidence_intended_staging_source: Literal["binance_usdm"]
    perpetual_evidence_rollback_source: Literal["replay"]
    live_market_read_only: Literal[True]
    exchange_credentials_used_for_market_evidence: Literal[False]
    spot_fallback_permitted: Literal[False]
    fabricated_fallback_permitted: Literal[False]
    live_quote_freshness_seconds: Literal[10]
    first_perpetual_symbol: Literal["BTCUSDT"]


def canonicalize_perpetual_evidence_source(value: str) -> ConfiguredSource:
    """Map accepted aliases onto ``replay`` or ``binance_usdm``."""
    normalized = value.strip().lower()
    if normalized in REPLAY_MODES:
        return ROLLBACK_SOURCE
    if normalized in LIVE_MODES:
        return LIVE_SOURCE
    raise ValueError(
        "perpetual_evidence_source must be replay or binance_usdm "
        "(spot fallback is not a legal value)."
    )


def _configured_source(settings: Settings) -> ConfiguredSource:
    return canonicalize_perpetual_evidence_source(settings.perpetual_evidence_source)


def _env_is_set(environ: Mapping[str, str], name: str) -> bool:
    return any(key.upper() == name and str(value).strip() for key, value in environ.items())


def _futures_origin_errors(url: str) -> list[str]:
    parsed = urlsplit(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or host != "fapi.binance.com":
        return [
            "market_data_futures_base_url must be https://fapi.binance.com "
            "(spot, coin-m, and plain HTTP are not evidence sources)."
        ]
    if parsed.username or parsed.password:
        return ["market_data_futures_base_url must not carry credentials."]
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        return ["market_data_futures_base_url must be the origin only."]
    if parsed.port not in (None, 443):
        return ["market_data_futures_base_url must use the default HTTPS port."]
    return []


def _invariant_errors() -> list[str]:
    errors: list[str] = []
    policy = first_slice_freshness_policy()
    if (
        policy.trade_max_age_seconds != LIVE_QUOTE_FRESHNESS_SECONDS
        or FIRST_SLICE_TRADE_FRESHNESS_SECONDS != LIVE_QUOTE_FRESHNESS_SECONDS
        or policy.policy_version != FIRST_SLICE_FRESHNESS_POLICY_VERSION
    ):
        errors.append("live quote freshness must remain 10 seconds.")
    catalog = default_perpetual_catalog()
    if FIRST_SLICE_SYMBOL != FIRST_PERPETUAL_SYMBOL:
        errors.append("first-slice symbol must remain BTCUSDT.")
    if FIRST_PERPETUAL_SYMBOL not in catalog.enabled_symbols():
        errors.append("default perpetual catalog must keep BTCUSDT enabled.")
    return errors


def controlled_watcher_arm(settings: Settings) -> bool:
    """True for the staging paper-monitoring pair on public USD-M evidence."""

    return (
        settings.environment is Environment.STAGING
        and settings.watcher_paper_staging_activation
        and settings.watcher_orchestration_enabled
        and settings.execution_mode is ExecutionMode.PAPER
        and not settings.enable_real_trading
        and not settings.real_trading_enabled
        and settings.exchange_mode is ExchangeMode.PAPER_INTERNAL
        and not settings.market_watcher_enabled
        and not settings.market_watcher_bridge_enabled
        and not settings.market_watcher_bridge_auto_tick
        and not settings.telegram_alerts_enabled
        and not settings.automatic_telegram_delivery_enabled
    )


def _live_profile_errors(settings: Settings, environ: Mapping[str, str]) -> list[str]:
    errors = _futures_origin_errors(settings.market_data_futures_base_url)
    if settings.enable_real_trading or settings.real_trading_enabled:
        errors.append("live USD-M evidence cannot be combined with real trading.")
    if settings.execution_mode is not ExecutionMode.PAPER:
        errors.append("live USD-M evidence requires execution_mode=paper.")
    if settings.exchange_mode is not ExchangeMode.PAPER_INTERNAL:
        errors.append("live USD-M evidence requires exchange_mode=paper_internal.")
    if settings.blofin_demo_enabled:
        errors.append("blofin_demo_enabled must be false for live USD-M evidence.")
    if any(
        (
            settings.blofin_api_key.strip(),
            settings.blofin_api_secret.strip(),
            settings.blofin_api_passphrase.strip(),
        )
    ):
        errors.append("exchange credentials must be unset for live USD-M evidence.")
    present = [name for name in FORBIDDEN_MARKET_CREDENTIAL_ENV if _env_is_set(environ, name)]
    if present:
        errors.append(
            "Binance credentials must be unset for public USD-M evidence: "
            + ", ".join(present)
            + "."
        )
    if settings.market_watcher_enabled:
        errors.append("market_watcher_enabled must be false while live USD-M evidence is on.")
    if settings.market_watcher_bridge_enabled:
        errors.append(
            "market_watcher_bridge_enabled must be false while live USD-M evidence is on."
        )
    if settings.market_watcher_bridge_auto_tick:
        errors.append(
            "market_watcher_bridge_auto_tick must be false while live USD-M evidence is on."
        )
    if settings.watcher_orchestration_enabled and not controlled_watcher_arm(settings):
        errors.append(
            "watcher_orchestration_enabled must be false while live USD-M evidence is on "
            "unless the staging paper-monitoring arm is set."
        )
    if settings.watcher_paper_staging_activation and not settings.watcher_orchestration_enabled:
        errors.append(
            "watcher_paper_staging_activation requires watcher_orchestration_enabled "
            "for paper monitoring only."
        )
    if settings.telegram_alerts_enabled:
        errors.append("telegram_alerts_enabled must be false while live USD-M evidence is on.")
    if settings.telegram_interaction_enabled:
        errors.append("telegram_interaction_enabled must be false while live USD-M evidence is on.")
    if settings.automatic_telegram_delivery_enabled:
        errors.append(
            "automatic_telegram_delivery_enabled must be false while live USD-M evidence is on."
        )
    if settings.environment is Environment.PRODUCTION:
        errors.append(
            "binance_usdm evidence activation is staging-only; production stays on replay."
        )
    return errors


def live_market_activation_violations(
    settings: Settings,
    *,
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    """Return profile violations. Replay/rollback skips the live-only checks."""
    env = os.environ if environ is None else environ
    errors = _invariant_errors()
    if _configured_source(settings) == LIVE_SOURCE:
        errors.extend(_live_profile_errors(settings, env))
    return errors


def validate_live_market_activation(
    settings: Settings,
    *,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Raise when the selected evidence source violates the activation profile."""
    errors = live_market_activation_violations(settings, environ=environ)
    if errors:
        raise ValueError("live market activation check failed: " + " ".join(errors))


def activation_state(
    settings: Settings,
    *,
    environ: Mapping[str, str] | None = None,
) -> ActivationState:
    """``inactive`` is replay/rollback. ``active`` is a valid live profile."""
    if _configured_source(settings) != LIVE_SOURCE:
        return "inactive"
    if live_market_activation_violations(settings, environ=environ):
        return "refused"
    return "active"


def perpetual_evidence_health(
    settings: Settings,
    *,
    environ: Mapping[str, str] | None = None,
) -> PerpetualEvidenceHealth:
    """Redaction-safe evidence posture for ``/health`` and startup logs."""
    return {
        "perpetual_evidence_source": _configured_source(settings),
        "perpetual_evidence_activation": activation_state(settings, environ=environ),
        "perpetual_evidence_intended_staging_source": INTENDED_STAGING_SOURCE,
        "perpetual_evidence_rollback_source": ROLLBACK_SOURCE,
        "live_market_read_only": True,
        "exchange_credentials_used_for_market_evidence": False,
        "spot_fallback_permitted": False,
        "fabricated_fallback_permitted": False,
        "live_quote_freshness_seconds": LIVE_QUOTE_FRESHNESS_SECONDS,
        "first_perpetual_symbol": FIRST_PERPETUAL_SYMBOL,
    }


def market_activation_public(settings: Settings) -> dict[str, object]:
    """Operator fields embedded on canonical market status."""
    health = perpetual_evidence_health(settings)
    return {
        "state": health["perpetual_evidence_activation"],
        "configured_source": health["perpetual_evidence_source"],
        "intended_staging_source": INTENDED_STAGING_SOURCE,
        "rollback_source": ROLLBACK_SOURCE,
        "read_only": True,
        "exchange_credentials_used": False,
        "spot_fallback_permitted": False,
        "fabricated_fallback_permitted": False,
        "first_symbol": FIRST_PERPETUAL_SYMBOL,
        "trade_freshness_seconds": LIVE_QUOTE_FRESHNESS_SECONDS,
    }
