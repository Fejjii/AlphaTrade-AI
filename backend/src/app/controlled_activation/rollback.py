"""Fail-closed rollback for the whole paper package. Nothing is applied here."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PackageRollbackStep:
    order: int
    action: str


PACKAGE_ROLLBACK_STEPS: tuple[str, ...] = (
    "Send SIGTERM to the dedicated Watcher process and any Telegram intake process.",
    "Confirm both processes have exited.",
    "Set TELEGRAM_PAPER_ACTIVATION_ARMED=false.",
    "Set TELEGRAM_INBOUND_MODE=off.",
    "Clear TELEGRAM_WEBHOOK_SECRET. Do not log the previous value.",
    "Set TELEGRAM_NETWORK_PERMITTED=false.",
    "Set TELEGRAM_INTERACTION_ENABLED=false.",
    "Keep TELEGRAM_ALERTS_ENABLED=false and AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false.",
    "Set WATCHER_PAPER_STAGING_ACTIVATION=false.",
    "Set WATCHER_ORCHESTRATION_ENABLED=false.",
    "Keep MARKET_WATCHER_ENABLED=false and both bridge flags false.",
    "Set PERPETUAL_EVIDENCE_SOURCE=replay only after both Watcher flags are false.",
    "Keep EXECUTION_MODE=paper and ENABLE_REAL_TRADING=false.",
    "Keep EXCHANGE_MODE=paper_internal. Do not add exchange credentials.",
    "Leave outbox, audit, cursor, send-ledger, Candidate, Journal, and lease rows in place.",
    "Do not downgrade Alembic as part of this rollback.",
    "Leave the kill switch unchanged.",
    "Restart the API and worker so Settings reloads.",
    "Confirm GET /health worker_runtime shows disarmed workers and real_trading_enabled=false.",
    "Confirm perpetual_evidence_source=replay and perpetual_evidence_activation=inactive.",
    "Confirm watcher flags are false and telegram flags are disarmed.",
    "Confirm GET /health/telegram-paper-activation shows verdict NOT_ARMED.",
)


def plan_package_rollback() -> tuple[PackageRollbackStep, ...]:
    """Operator checklist. This function does not edit env, deploy, or delete rows."""

    return tuple(
        PackageRollbackStep(order=index, action=action)
        for index, action in enumerate(PACKAGE_ROLLBACK_STEPS, start=1)
    )


def rollback_refuses_apply() -> str:
    return (
        "Refusing to edit environment variables, staging config, or deployments. "
        "Follow the printed checklist and restart the process. "
        "Do not delete database rows."
    )
