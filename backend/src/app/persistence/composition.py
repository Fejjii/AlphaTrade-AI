"""Explicit PostgreSQL adapter construction.

FastAPI and the worker attach Candidate, ActionEligibility, and canonical
TradePlan through ``ProductionCanonicalRuntime``. Watcher and Telegram builders
remain explicit and default disabled. This module never starts those loops or
enables live trading.

Transaction boundaries
----------------------
Watcher: every store method opens and commits its own SQLAlchemy transaction.
Evaluation, clocks, and crash barriers run *between* those methods, never inside
an open DB transaction. Lease claim linearizes on
``SELECT ... FOR UPDATE`` of ``watcher_worker_leases (organization_id, scan_scope)``
(or the unique insert of that key).

Candidate: every repository method opens and commits its own SQLAlchemy
transaction unless ``bind_session`` joins an outer unit of work. Worker-originated
Candidate writes, when a Watcher fence is bound, lock that same lease row
``FOR UPDATE`` and prove current fencing authority in the Candidate persist
transaction before inserting the projection or appending a transition. A stale
worker cannot commit Candidate authority after losing its lease.

Telegram: ``transaction()`` takes a transaction-scoped advisory lock, matching
the in-memory store's process lock, then uses row locks for nonce CAS and outbox
claims. ``deliver_pending`` claims under ``transaction()`` and performs transport
I/O only after that transaction commits. Conflicting inbound replays fail closed
on first-writer unique keys ``(bot_id, update_id)`` and ``(bot_id, callback_query_id)``.

These builders never enable ``WATCHER_ORCHESTRATION_ENABLED``,
``MARKET_WATCHER_ENABLED``, or ``TELEGRAM_INTERACTION_ENABLED``.

ActionEligibility and canonical TradePlan: each store method opens its own
transaction unless ``bind_session`` joins an outer unit of work. Plan insert
locks the canonical Candidate, writes the compatibility TradeProposal +
revision + lineage, then runs ``PLAN_CREATED`` in that same transaction.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.persistence.candidate_postgres import PostgresCandidateRepository
from app.persistence.eligibility_postgres import PostgresActionEligibilityStore
from app.persistence.telegram_paper_agent import PostgresPaperAgentStore
from app.persistence.telegram_postgres import PostgresTelegramSecurityStore
from app.persistence.trade_plan_postgres import PostgresCanonicalTradePlanStore
from app.persistence.watcher_postgres import PostgresWatcherStore
from app.services.canonical_trade_plan import CanonicalTradePlanService
from app.signal_fusion.action_eligibility import ActionEligibilityService
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.signal_fusion.ports import Clock as CandidateClock
from app.telegram_security.backoff import DeliveryBackoff
from app.telegram_security.clock import Clock, FrozenClock
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.rate_limit import ProtocolRateLimiter, RateLimitPolicy
from app.telegram_security.transport import FakeTelegramTransport, TelegramTransport
from app.watcher.composition import build_orchestrator
from app.watcher.contracts import WatcherRuntimeConfig
from app.watcher.memory import ScriptedEvaluationBoundary, SideEffectProbe
from app.watcher.orchestrator import WatcherOrchestrator
from app.watcher.ports import (
    Clock as WatcherClock,
)
from app.watcher.ports import (
    CrashBarrier,
    NoCrashBarrier,
    SideEffectPorts,
    WatcherEvaluationBoundary,
)


def build_postgres_candidate_repository(
    session_factory: sessionmaker[Session],
    *,
    clock: CandidateClock | None = None,
) -> PostgresCandidateRepository:
    """Construct a PostgreSQL CandidateRepository. Callers must inject it explicitly."""

    return PostgresCandidateRepository(session_factory, clock=clock)


def build_postgres_candidate_lifecycle(
    session_factory: sessionmaker[Session],
    *,
    clock: CandidateClock,
) -> CandidateLifecycleService:
    """Lifecycle authority backed by PostgreSQL. Production uses ProductionCanonicalRuntime."""

    return CandidateLifecycleService(
        repository=build_postgres_candidate_repository(session_factory, clock=clock),
        clock=clock,
    )


def build_postgres_action_eligibility_store(
    session_factory: sessionmaker[Session],
) -> PostgresActionEligibilityStore:
    """Construct a PostgreSQL ActionEligibilityStore. Callers must inject it explicitly."""

    return PostgresActionEligibilityStore(session_factory)


def build_postgres_action_eligibility(
    session_factory: sessionmaker[Session],
    *,
    clock: CandidateClock,
) -> ActionEligibilityService:
    """Eligibility authority backed by PostgreSQL. Production uses ProductionCanonicalRuntime."""

    return ActionEligibilityService(
        store=build_postgres_action_eligibility_store(session_factory),
        clock=clock,
    )


def build_postgres_canonical_trade_plan_store(
    session_factory: sessionmaker[Session],
    *,
    candidate_repository: PostgresCandidateRepository | None = None,
) -> PostgresCanonicalTradePlanStore:
    """Construct a PostgreSQL CanonicalTradePlanStore. Callers must inject it explicitly."""

    return PostgresCanonicalTradePlanStore(
        session_factory, candidate_repository=candidate_repository
    )


def build_postgres_canonical_trade_plan(
    session_factory: sessionmaker[Session],
    *,
    clock: CandidateClock,
) -> CanonicalTradePlanService:
    """Canonical plan authority backed by PostgreSQL. Production uses ProductionCanonicalRuntime."""

    candidate_repository = build_postgres_candidate_repository(session_factory, clock=clock)
    return CanonicalTradePlanService(
        store=build_postgres_canonical_trade_plan_store(
            session_factory, candidate_repository=candidate_repository
        ),
        lifecycle=CandidateLifecycleService(repository=candidate_repository, clock=clock),
        eligibility=build_postgres_action_eligibility(session_factory, clock=clock),
        clock=clock,
    )


def build_postgres_watcher_store(
    session_factory: sessionmaker[Session],
) -> PostgresWatcherStore:
    """Construct a PostgreSQL WatcherStore. Callers must inject it explicitly."""

    return PostgresWatcherStore(session_factory)


def build_postgres_telegram_security_store(
    session_factory: sessionmaker[Session],
) -> PostgresTelegramSecurityStore:
    """Construct a PostgreSQL TelegramSecurityStore. Callers must inject it explicitly."""

    return PostgresTelegramSecurityStore(session_factory)


def build_postgres_paper_agent_store(
    session_factory: sessionmaker[Session],
) -> PostgresPaperAgentStore:
    """Paper Telegram identity store. Callers must inject it explicitly. Disabled by default."""

    return PostgresPaperAgentStore(session_factory)


def build_postgres_watcher_orchestrator(
    session_factory: sessionmaker[Session],
    *,
    enabled: bool = False,
    lease_ttl_seconds: int = 30,
    heartbeat_stale_after_seconds: int = 90,
    evaluator: WatcherEvaluationBoundary | None = None,
    clock: WatcherClock | None = None,
    side_effects: SideEffectPorts | None = None,
    crash: CrashBarrier | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> WatcherOrchestrator:
    """Isolated orchestrator backed by PostgreSQL. Remains disabled unless enabled=True."""

    return build_orchestrator(
        enabled=enabled,
        lease_ttl_seconds=lease_ttl_seconds,
        heartbeat_stale_after_seconds=heartbeat_stale_after_seconds,
        store=build_postgres_watcher_store(session_factory),
        evaluator=evaluator if evaluator is not None else ScriptedEvaluationBoundary(),
        clock=clock,
        side_effects=side_effects if side_effects is not None else SideEffectProbe(),
        crash=crash if crash is not None else NoCrashBarrier(),
        id_factory=id_factory,
    )


def build_postgres_telegram_security_protocol(
    session_factory: sessionmaker[Session],
    *,
    enabled: bool = False,
    clock: Clock | None = None,
    transport: TelegramTransport | None = None,
    token_factory: Callable[[], str] | None = None,
    rate_limit_policy: RateLimitPolicy | None = None,
    enrollment_ttl: timedelta = timedelta(minutes=15),
    nonce_ttl: timedelta = timedelta(minutes=10),
    outbox_max_attempts: int = 3,
    outbox_lease: timedelta = timedelta(seconds=30),
    lease_owner: str = "telegram-security-protocol",
    retry_backoff: DeliveryBackoff | None = None,
) -> TelegramSecurityProtocol:
    """Isolated protocol backed by PostgreSQL. Remains disabled unless enabled=True."""

    resolved_clock = clock or FrozenClock()
    limiter = (
        ProtocolRateLimiter(resolved_clock, policy=rate_limit_policy)
        if rate_limit_policy is not None
        else ProtocolRateLimiter(resolved_clock)
    )
    return TelegramSecurityProtocol(
        store=build_postgres_telegram_security_store(session_factory),
        transport=transport or FakeTelegramTransport(),
        clock=resolved_clock,
        enabled=enabled,
        token_factory=token_factory,
        rate_limiter=limiter,
        enrollment_ttl=enrollment_ttl,
        nonce_ttl=nonce_ttl,
        outbox_max_attempts=outbox_max_attempts,
        outbox_lease=outbox_lease,
        lease_owner=lease_owner,
        retry_backoff=retry_backoff,
    )


def postgres_watcher_runtime_config(
    *,
    enabled: bool = False,
    lease_ttl_seconds: int = 30,
    heartbeat_stale_after_seconds: int = 90,
) -> WatcherRuntimeConfig:
    return WatcherRuntimeConfig(
        enabled=enabled,
        lease_ttl_seconds=lease_ttl_seconds,
        heartbeat_stale_after_seconds=heartbeat_stale_after_seconds,
    )
