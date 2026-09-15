"""Permanent exact-paper-mode invariant (architecture §21 / Phase 1 slice 1).

Every Settings construction, API, worker, task runner, direct service, provider
factory and test composition root must satisfy:

    EXECUTION_MODE == PAPER
    ENABLE_REAL_TRADING == false
    EXCHANGE_MODE in {paper_internal, paper_exchange_demo}
    trade_live == tombstoned and rejected
    execution-capable process + READ_ONLY == invalid

This module only tightens existing ``deployment_safety`` / ``exchange_safety``
checks. It never introduces a path that can enable real trading.
"""

from __future__ import annotations

from app.core.config import ExchangeMode, ExecutionMode, Settings
from app.core.exchange_safety import BLOFIN_PRODUCTION_HOSTS, _host_of

_ALLOWED_EXCHANGE_MODES = frozenset({ExchangeMode.PAPER_INTERNAL, ExchangeMode.PAPER_EXCHANGE_DEMO})


def _settings_imply_execution_capability(settings: Settings) -> bool:
    """True when this Settings object configures an execution-capable process.

    The FastAPI app and ExecutionService are execution-capable regardless of
    these flags; they call :func:`assert_execution_capable_composition_root`.
    Flags here catch worker/scheduler/demo composition at Settings construction.
    """
    return (
        settings.worker_enabled
        or settings.enable_paper_scheduler
        or settings.paper_signal_orchestration_enabled
        or settings.blofin_demo_enabled
        or settings.exchange_mode is ExchangeMode.PAPER_EXCHANGE_DEMO
    )


def _latent_live_host_errors(settings: Settings) -> list[str]:
    """Reject production/live venue hosts even when demo mode is not selected."""
    errors: list[str] = []
    for attr in ("blofin_demo_rest_base_url", "blofin_demo_ws_url"):
        url = getattr(settings, attr).strip()
        if not url:
            continue
        host = _host_of(url)
        if host in BLOFIN_PRODUCTION_HOSTS:
            errors.append(f"{attr} must not point at a BloFin production/live host")
    return errors


def validate_permanent_paper_settings(settings: Settings) -> None:
    """Raise ``ValueError`` when Settings violate the permanent paper invariant.

    Called from Settings construction in every environment (local/test/staging/prod).
    """
    errors: list[str] = []

    if settings.enable_real_trading:
        errors.append(
            "ENABLE_REAL_TRADING=true is permanently rejected. Real trading cannot be enabled."
        )
    if settings.execution_mode is ExecutionMode.TRADE:
        errors.append(
            "execution_mode=trade is permanently rejected. Only PAPER is a valid trading mode."
        )
    if settings.exchange_mode is ExchangeMode.TRADE_LIVE:
        errors.append(
            "exchange_mode=trade_live is permanently disabled. Real exchange execution "
            "is not implemented and must never be enabled."
        )
    if settings.exchange_mode not in _ALLOWED_EXCHANGE_MODES:
        errors.append(
            "exchange_mode must be paper_internal or paper_exchange_demo "
            f"(got {settings.exchange_mode.value})"
        )
    if settings.execution_mode is ExecutionMode.READ_ONLY and _settings_imply_execution_capability(
        settings
    ):
        errors.append(
            "execution-capable process + execution_mode=read_only is an invalid configuration"
        )
    errors.extend(_latent_live_host_errors(settings))

    if errors:
        raise ValueError("paper safety check failed: " + "; ".join(errors))


def assert_permanent_paper_mode(settings: Settings) -> None:
    """Re-check the paper invariant before mutations or provider construction."""
    validate_permanent_paper_settings(settings)
    if settings.real_trading_enabled:
        raise ValueError("real_trading_enabled is permanently false; refusing composition.")


def assert_execution_capable_composition_root(settings: Settings) -> None:
    """Refuse to build an execution-capable composition root in READ_ONLY mode.

    READ_ONLY Settings may exist for a future read-only process. They cannot be
    used to construct the API, worker, AgentRuntime, or ExecutionService.
    """
    assert_permanent_paper_mode(settings)
    if settings.execution_mode is ExecutionMode.READ_ONLY:
        raise ValueError(
            "execution-capable process cannot be built with execution_mode=read_only. "
            "READ_ONLY may perform approved reads but cannot place even an internal paper order."
        )
    if settings.execution_mode is not ExecutionMode.PAPER:
        raise ValueError(
            "execution-capable process requires execution_mode=paper "
            f"(got {settings.execution_mode.value})"
        )


def assert_paper_execution_allowed(settings: Settings) -> None:
    """Gate used immediately before any execution-capable service call."""
    assert_execution_capable_composition_root(settings)
    if settings.enable_real_trading or settings.real_trading_enabled:
        raise ValueError("Refusing execution: real trading is permanently disabled.")
