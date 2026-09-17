"""Compose an isolated watcher orchestrator. Not wired into the live worker."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.watcher.contracts import WatcherRuntimeConfig
from app.watcher.memory import (
    FakeClock,
    InMemoryWatcherStore,
    ScriptedEvaluationBoundary,
    SideEffectProbe,
)
from app.watcher.orchestrator import WatcherOrchestrator
from app.watcher.ports import (
    Clock,
    CrashBarrier,
    NoCrashBarrier,
    SideEffectPorts,
    WatcherEvaluationBoundary,
    WatcherStore,
)


def build_orchestrator(
    *,
    enabled: bool = False,
    lease_ttl_seconds: int = 30,
    heartbeat_stale_after_seconds: int = 90,
    store: WatcherStore | None = None,
    evaluator: WatcherEvaluationBoundary | None = None,
    clock: Clock | None = None,
    side_effects: SideEffectPorts | None = None,
    crash: CrashBarrier | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> WatcherOrchestrator:
    """Build a fully isolated orchestrator. Watcher stays disabled unless enabled=True."""

    return WatcherOrchestrator(
        store=store if store is not None else InMemoryWatcherStore(),
        evaluator=evaluator if evaluator is not None else ScriptedEvaluationBoundary(),
        clock=clock if clock is not None else FakeClock(),
        config=WatcherRuntimeConfig(
            enabled=enabled,
            lease_ttl_seconds=lease_ttl_seconds,
            heartbeat_stale_after_seconds=heartbeat_stale_after_seconds,
        ),
        side_effects=side_effects if side_effects is not None else SideEffectProbe(),
        crash=crash if crash is not None else NoCrashBarrier(),
        id_factory=id_factory,
    )
