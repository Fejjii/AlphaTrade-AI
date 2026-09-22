"""Rollback checklist. This module does not edit environment files or deploy."""

from __future__ import annotations

from app.telegram_activation.contracts import RollbackPlan, RollbackStep

_STEPS: tuple[tuple[str, str], ...] = (
    (
        "Set TELEGRAM_PAPER_ACTIVATION_ARMED=false and restart the process.",
        "TELEGRAM_PAPER_ACTIVATION_ARMED",
    ),
    (
        "Set TELEGRAM_INBOUND_MODE=off so polling and the webhook both stop.",
        "TELEGRAM_INBOUND_MODE",
    ),
    (
        "Clear TELEGRAM_WEBHOOK_SECRET. Do not log the previous value.",
        "TELEGRAM_WEBHOOK_SECRET",
    ),
    (
        "Set TELEGRAM_NETWORK_PERMITTED=false so no Telegram HTTP client can run.",
        "TELEGRAM_NETWORK_PERMITTED",
    ),
    (
        "Set TELEGRAM_INTERACTION_ENABLED=false.",
        "TELEGRAM_INTERACTION_ENABLED",
    ),
    (
        "Keep TELEGRAM_ALERTS_ENABLED=false and AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false.",
        "TELEGRAM_ALERTS_ENABLED",
    ),
    (
        "Do not change WATCHER_ORCHESTRATION_ENABLED or MARKET_WATCHER_ENABLED.",
        "WATCHER_ORCHESTRATION_ENABLED",
    ),
    (
        "Do not change ENABLE_REAL_TRADING, EXECUTION_MODE, or EXCHANGE_MODE.",
        "ENABLE_REAL_TRADING",
    ),
    (
        "Leave outbox, audit, cursor, and send-ledger rows in place.",
        "telegram_security_outbox",
    ),
    (
        "Revoke a recipient binding only as a separate explicit operator action.",
        "telegram_binding",
    ),
    (
        "Confirm GET /health/telegram-paper-activation shows verdict NOT_ARMED.",
        "/health/telegram-paper-activation",
    ),
)


def plan_rollback() -> RollbackPlan:
    """Return the ordered human checklist. Nothing is mutated."""
    steps = tuple(
        RollbackStep(order=index, action=action, target=target)
        for index, (action, target) in enumerate(_STEPS, start=1)
    )
    return RollbackPlan(steps=steps)


def rollback_refuses_apply() -> str:
    """Operators apply rollback in the environment UI. This process will not."""
    return (
        "Refusing to edit environment variables, staging config, or deployments. "
        "Follow the printed checklist and restart the process."
    )
