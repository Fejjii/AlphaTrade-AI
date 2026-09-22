"""Read-only monitor port consumed by the canonical Watcher evidence path.

Does not start the Watcher worker, mint Candidates, or change Watcher flags.
"""

from __future__ import annotations

from app.market_monitor.monitor import PerpetualMarketMonitor
from app.market_monitor.types import SymbolMonitorSnapshot
from app.market_monitor.watcher_gate import watcher_evidence_error_for_monitor

__all__ = ["MarketMonitorWatcherPort", "watcher_evidence_error_for_monitor"]


class MarketMonitorWatcherPort:
    """Latest monitor snapshot for Watcher scan evidence gating."""

    def __init__(self, monitor: PerpetualMarketMonitor) -> None:
        self._monitor = monitor

    def latest(self, symbol: str = "BTCUSDT") -> SymbolMonitorSnapshot:
        return self._monitor.snapshot(symbol, force=True)
