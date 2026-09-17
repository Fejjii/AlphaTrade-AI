"""Isolated watcher orchestration foundation (Phase 7 worker contracts).

No market adapters, candidate lifecycle, Telegram, execution, journal, or ORM
models. Persistence is a typed port with a deterministic in-memory repository
until a later integration phase binds PostgreSQL.
"""

from __future__ import annotations

from app.watcher.composition import build_orchestrator
from app.watcher.contracts import (
    EvaluationMode,
    EvaluationStatus,
    ScanTrigger,
    WatcherHealthState,
    WatcherRuntimeConfig,
)
from app.watcher.orchestrator import WatcherOrchestrator

__all__ = [
    "EvaluationMode",
    "EvaluationStatus",
    "ScanTrigger",
    "WatcherHealthState",
    "WatcherOrchestrator",
    "WatcherRuntimeConfig",
    "build_orchestrator",
]
