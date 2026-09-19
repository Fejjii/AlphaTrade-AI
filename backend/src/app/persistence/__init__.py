"""PostgreSQL persistence adapters for Watcher, Telegram, Candidate, eligibility, and plans.

These adapters are constructed explicitly by tests or a later wiring task.
They are not imported by FastAPI, workers, or feature flags.
"""

from app.persistence.candidate_postgres import (
    PostgresCandidateRepository,
    WorkerCandidateWriteFence,
)
from app.persistence.composition import (
    build_postgres_action_eligibility,
    build_postgres_action_eligibility_store,
    build_postgres_candidate_lifecycle,
    build_postgres_candidate_repository,
    build_postgres_canonical_trade_plan,
    build_postgres_canonical_trade_plan_store,
    build_postgres_telegram_security_protocol,
    build_postgres_telegram_security_store,
    build_postgres_watcher_orchestrator,
    build_postgres_watcher_store,
)
from app.persistence.eligibility_postgres import PostgresActionEligibilityStore
from app.persistence.trade_plan_postgres import PostgresCanonicalTradePlanStore

__all__ = [
    "PostgresActionEligibilityStore",
    "PostgresCandidateRepository",
    "PostgresCanonicalTradePlanStore",
    "WorkerCandidateWriteFence",
    "build_postgres_action_eligibility",
    "build_postgres_action_eligibility_store",
    "build_postgres_candidate_lifecycle",
    "build_postgres_candidate_repository",
    "build_postgres_canonical_trade_plan",
    "build_postgres_canonical_trade_plan_store",
    "build_postgres_telegram_security_protocol",
    "build_postgres_telegram_security_store",
    "build_postgres_watcher_orchestrator",
    "build_postgres_watcher_store",
]
