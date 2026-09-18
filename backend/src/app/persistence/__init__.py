"""PostgreSQL persistence adapters for Watcher, Telegram, and Candidate stores.

These adapters are constructed explicitly by tests or a later wiring task.
They are not imported by FastAPI, workers, or feature flags.
"""

from app.persistence.candidate_postgres import (
    PostgresCandidateRepository,
    WorkerCandidateWriteFence,
)
from app.persistence.composition import (
    build_postgres_candidate_lifecycle,
    build_postgres_candidate_repository,
    build_postgres_telegram_security_protocol,
    build_postgres_telegram_security_store,
    build_postgres_watcher_orchestrator,
    build_postgres_watcher_store,
)

__all__ = [
    "PostgresCandidateRepository",
    "WorkerCandidateWriteFence",
    "build_postgres_candidate_lifecycle",
    "build_postgres_candidate_repository",
    "build_postgres_telegram_security_protocol",
    "build_postgres_telegram_security_store",
    "build_postgres_watcher_orchestrator",
    "build_postgres_watcher_store",
]
