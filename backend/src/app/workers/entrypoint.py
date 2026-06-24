"""Standalone background-worker entrypoint.

Run as a dedicated process (e.g. a Render *worker* service):

    python -m app.workers.entrypoint

The worker is disabled unless ``WORKER_ENABLED=true``. It never places real
orders; it only scans market data and records observability rows.
"""

from __future__ import annotations

import structlog

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import get_session_factory
from app.workers.lock import build_worker_lock
from app.workers.notifier import WorkerNotifier
from app.workers.runner import WorkerLoopDriver
from app.workers.scanner import build_market_scan_scanner
from app.workers.service import ScanResult, WorkerService

logger = structlog.get_logger(__name__)


def _build_cycle_notifier(settings: Settings):
    """Return an ``on_cycle`` hook that emits outbound system alerts."""
    notifier = WorkerNotifier(settings)

    def _on_cycle(result: ScanResult) -> None:
        if result.status == "success" and result.setups_detected > 0:
            notifier.notify_setup_detected(count=result.setups_detected)
        elif result.status == "failed" and result.error:
            notifier.notify_worker_error(result.error)

    return _on_cycle


def build_driver(settings: Settings) -> WorkerLoopDriver:
    """Wire the worker service + loop driver from settings."""
    service = WorkerService(
        get_session_factory(),
        build_worker_lock(settings),
        worker_name=settings.worker_name,
        scanner=build_market_scan_scanner(settings),
        on_cycle=_build_cycle_notifier(settings),
    )
    return WorkerLoopDriver(service, interval_seconds=settings.worker_scan_interval_seconds)


def main() -> None:
    settings = get_settings()
    configure_logging(log_level=settings.log_level, json_logs=settings.log_json)
    if not settings.worker_enabled:
        logger.warning("worker_disabled", hint="set WORKER_ENABLED=true to run the worker")
        return
    logger.info(
        "worker_starting",
        worker_name=settings.worker_name,
        interval_seconds=settings.worker_scan_interval_seconds,
        exchange_mode=settings.exchange_mode.value,
    )
    build_driver(settings).run()


if __name__ == "__main__":
    main()
