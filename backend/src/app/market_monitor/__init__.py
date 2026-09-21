"""Continuous read-only USD-M perpetual market monitoring.

Ticks existing Binance USD-M GET-only sources and Phase 5 stream contracts.
Does not enable Watcher, Telegram, execution, or live trading.
"""

from app.market_monitor.factory import build_perpetual_market_monitor
from app.market_monitor.monitor import PerpetualMarketMonitor
from app.market_monitor.service import PerpetualMarketMonitorService
from app.market_monitor.types import MarketAvailability, MarketMode, MonitorReason
from app.market_monitor.watcher_port import MarketMonitorWatcherPort

__all__ = [
    "MarketAvailability",
    "MarketMode",
    "MarketMonitorWatcherPort",
    "MonitorReason",
    "PerpetualMarketMonitor",
    "PerpetualMarketMonitorService",
    "build_perpetual_market_monitor",
]
