"""Worker loop driver supporting standalone-process and in-process execution."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import structlog

from app.workers.service import WorkerService

logger = structlog.get_logger(__name__)


class WorkerLoopDriver:
    """Drives :class:`WorkerService.run_cycle` on a fixed interval.

    The same driver runs either as a dedicated process (``run``) or inside the
    API process on a daemon thread (``start_background_thread``). ``max_cycles``
    and an injectable ``sleeper`` make the loop deterministically testable.
    """

    def __init__(
        self,
        service: WorkerService,
        *,
        interval_seconds: float,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._service = service
        self._interval = interval_seconds
        self._sleeper = sleeper
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def stop(self) -> None:
        self._stop.set()

    def run(
        self,
        *,
        max_cycles: int | None = None,
        should_continue: Callable[[], bool] | None = None,
    ) -> int:
        """Run the loop until stopped/max_cycles reached; returns cycles run."""
        cycles = 0
        while not self._stop.is_set():
            if should_continue is not None and not should_continue():
                break
            try:
                self._service.run_cycle()
            except Exception:  # pragma: no cover - service already dead-letters
                logger.error("worker_loop_iteration_error", exc_info=True)
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            self._sleeper(self._interval)
        return cycles

    def start_background_thread(self) -> threading.Thread:
        """Start the loop on a daemon thread (in-process mode)."""
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop.clear()
        thread = threading.Thread(target=self.run, name="worker-loop", daemon=True)
        thread.start()
        self._thread = thread
        logger.info("worker_in_process_started")
        return thread
