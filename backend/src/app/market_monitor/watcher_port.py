"""Read-only monitor port reserved for a later Watcher wiring task.

This module does not start the Watcher worker, does not mint Candidates, and
does not change Watcher flags.
"""

from __future__ import annotations

from app.market_monitor.monitor import PerpetualMarketMonitor
from app.market_monitor.types import SymbolMonitorSnapshot


class MarketMonitorWatcherPort:
    """Latest monitor snapshot for a future Watcher consumer.

    Not registered on the worker. Watcher remains disabled.
    """

    def __init__(self, monitor: PerpetualMarketMonitor) -> None:
        self._monitor = monitor

    def latest(self, symbol: str = "BTCUSDT") -> SymbolMonitorSnapshot:
        return self._monitor.snapshot(symbol, force=True)
