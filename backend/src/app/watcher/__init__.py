"""Isolated watcher orchestration and Phase 6 fusion evaluation wiring.

Persistence remains the typed WatcherStore port. Fusion wiring is one evaluation
boundary that calls evaluate_setup and CandidateLifecycleService. Telegram,
execution, journal, TradePlan, and ORM/Alembic stay out of this package.
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
from app.watcher.fusion_evaluation import (
    BoundEvaluationClock,
    InMemoryWatcherScanEvidence,
    WatcherCanonicalScanEvidence,
    WatcherFusionEvaluationService,
    build_fusion_evaluation_service,
)
from app.watcher.orchestrator import WatcherOrchestrator

__all__ = [
    "BoundEvaluationClock",
    "EvaluationMode",
    "EvaluationStatus",
    "InMemoryWatcherScanEvidence",
    "ScanTrigger",
    "WatcherCanonicalScanEvidence",
    "WatcherFusionEvaluationService",
    "WatcherHealthState",
    "WatcherOrchestrator",
    "WatcherRuntimeConfig",
    "build_fusion_evaluation_service",
    "build_orchestrator",
]
