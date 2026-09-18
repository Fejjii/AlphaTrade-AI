"""PostgreSQL persistence adapters for Watcher and Telegram security stores.

These adapters are constructed explicitly by tests or a later wiring task.
They are not imported by FastAPI, workers, or feature flags.
"""

from app.persistence.composition import (
    build_postgres_telegram_security_protocol,
    build_postgres_telegram_security_store,
    build_postgres_watcher_orchestrator,
    build_postgres_watcher_store,
)

__all__ = [
    "build_postgres_telegram_security_protocol",
    "build_postgres_telegram_security_store",
    "build_postgres_watcher_orchestrator",
    "build_postgres_watcher_store",
]
