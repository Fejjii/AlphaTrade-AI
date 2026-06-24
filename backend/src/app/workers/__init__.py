"""Background worker package (Slice 59).

A separate, always-on process that periodically scans the configured watchlist
using the deterministic analysis engine, records heartbeats and scan runs, and
(in later slices) emits alerts. The worker never places real orders.
"""

from __future__ import annotations

from app.workers.lock import InMemoryWorkerLock, WorkerLock, build_worker_lock
from app.workers.service import ScanResult, WorkerService

__all__ = [
    "InMemoryWorkerLock",
    "ScanResult",
    "WorkerLock",
    "WorkerService",
    "build_worker_lock",
]
