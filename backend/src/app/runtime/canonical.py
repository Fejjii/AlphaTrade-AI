"""Request-scoped PostgreSQL composition for the canonical paper lifecycle.

Adapters are the Phase 7 PostgreSQL ports. CandidateLifecycleService remains
the only Candidate authority. Watcher and Telegram flags are recorded and
default false; this module never starts those loops.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.persistence.candidate_postgres import PostgresCandidateRepository
from app.persistence.composition import (
    build_postgres_action_eligibility_store,
    build_postgres_candidate_repository,
    build_postgres_canonical_trade_plan_store,
)
from app.persistence.eligibility_postgres import PostgresActionEligibilityStore
from app.persistence.trade_plan_postgres import PostgresCanonicalTradePlanStore
from app.services.canonical_trade_plan import CanonicalTradePlanService
from app.signal_fusion.action_eligibility import ActionEligibilityService
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.signal_fusion.memory import UtcClock
from app.signal_fusion.ports import Clock


@dataclass(frozen=True, slots=True)
class CanonicalRuntimeFlags:
    """Explicit feature flags. Defaults keep Watcher and Telegram off."""

    watcher_orchestration_enabled: bool = False
    market_watcher_enabled: bool = False
    telegram_interaction_enabled: bool = False
    real_trading_enabled: bool = False


def runtime_flags_from_settings(settings: Settings) -> CanonicalRuntimeFlags:
    return CanonicalRuntimeFlags(
        watcher_orchestration_enabled=bool(settings.watcher_orchestration_enabled),
        market_watcher_enabled=bool(settings.market_watcher_enabled),
        telegram_interaction_enabled=bool(settings.telegram_interaction_enabled),
        real_trading_enabled=bool(settings.real_trading_enabled),
    )


@dataclass(frozen=True, slots=True)
class ProductionCanonicalRuntime:
    """Process-level canonical ports. Bind a Session before using them."""

    session_factory: sessionmaker[Session]
    clock: Clock
    candidate_repository: PostgresCandidateRepository
    eligibility_store: PostgresActionEligibilityStore
    plan_store: PostgresCanonicalTradePlanStore
    lifecycle: CandidateLifecycleService
    eligibility: ActionEligibilityService
    plans: CanonicalTradePlanService
    flags: CanonicalRuntimeFlags

    @property
    def watcher_enabled(self) -> bool:
        return self.flags.watcher_orchestration_enabled or self.flags.market_watcher_enabled

    @property
    def telegram_enabled(self) -> bool:
        return self.flags.telegram_interaction_enabled

    @contextmanager
    def bind_session(self, session: Session) -> Iterator[ProductionCanonicalRuntime]:
        """Join the caller's unit of work. Nested binds restore the previous session."""

        with ExitStack() as stack:
            stack.enter_context(self.candidate_repository.bind_session(session))
            stack.enter_context(self.eligibility_store.bind_session(session))
            stack.enter_context(self.plan_store.bind_session(session))
            yield self


def build_production_canonical_runtime(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings | None = None,
    clock: Clock | None = None,
) -> ProductionCanonicalRuntime:
    """Construct PostgreSQL-backed canonical authorities. Flags stay off by default."""

    flags = (
        runtime_flags_from_settings(settings) if settings is not None else CanonicalRuntimeFlags()
    )
    resolved_clock = clock or UtcClock()
    candidate_repository = build_postgres_candidate_repository(
        session_factory, clock=resolved_clock
    )
    eligibility_store = build_postgres_action_eligibility_store(session_factory)
    plan_store = build_postgres_canonical_trade_plan_store(
        session_factory, candidate_repository=candidate_repository
    )
    lifecycle = CandidateLifecycleService(repository=candidate_repository, clock=resolved_clock)
    eligibility = ActionEligibilityService(store=eligibility_store, clock=resolved_clock)
    plans = CanonicalTradePlanService(
        store=plan_store,
        lifecycle=lifecycle,
        eligibility=eligibility,
        clock=resolved_clock,
    )
    return ProductionCanonicalRuntime(
        session_factory=session_factory,
        clock=resolved_clock,
        candidate_repository=candidate_repository,
        eligibility_store=eligibility_store,
        plan_store=plan_store,
        lifecycle=lifecycle,
        eligibility=eligibility,
        plans=plans,
        flags=flags,
    )
