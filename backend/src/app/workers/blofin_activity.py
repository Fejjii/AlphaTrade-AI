"""Importable single-tick entry point for existing workers; disarmed by default."""

import signal
from dataclasses import asdict
from threading import Event

from app.core.config import get_settings
from app.db.session import get_engine
from app.services.blofin_activity_config import get_activity_settings
from app.services.blofin_activity_service import run_activity_sync


def main() -> None:
    config = get_activity_settings()
    if not config.enabled:
        print("BloFin activity synchronization disabled.")
        return
    stop = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda _sig, _frame: stop.set())
    result = run_activity_sync(get_engine(), get_settings(), config, shutdown=stop.is_set)
    print(asdict(result))


if __name__ == "__main__":
    main()
