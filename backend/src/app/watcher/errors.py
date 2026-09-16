"""Typed errors for watcher orchestration. Never include secrets."""

from __future__ import annotations

from app.core.errors import AppError, ConflictError


class WatcherError(AppError):
    """Base watcher orchestration error."""

    code = "watcher_error"


class WatcherDisabledError(WatcherError):
    code = "watcher_disabled"
    status_code = 403


class WatcherIdempotencyConflictError(ConflictError):
    """Same opaque key with a different semantic scan request."""

    code = "watcher_idempotency_conflict"


class StaleFenceError(ConflictError):
    """Worker write rejected because the fencing epoch no longer matches."""

    code = "watcher_stale_fence"


class LeaseConflictError(ConflictError):
    """Another fenced worker currently owns the scan scope."""

    code = "watcher_lease_conflict"


class WatcherContractError(WatcherError):
    """Evaluation outcome violated orchestration honesty invariants."""

    code = "watcher_contract_error"


class SimulatedWorkerCrashError(RuntimeError):
    """Test-only crash injected at a named persistence boundary."""

    def __init__(self, checkpoint: str) -> None:
        super().__init__(f"simulated worker crash at {checkpoint}")
        self.checkpoint = checkpoint
