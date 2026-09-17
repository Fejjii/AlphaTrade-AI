"""Map Settings onto watcher orchestration runtime config.

Imported only by callers that already depend on Settings. The orchestrator
package itself does not import application Settings.
"""

from __future__ import annotations

from app.core.config import Settings
from app.watcher.contracts import WatcherRuntimeConfig


def runtime_config_from_settings(settings: Settings) -> WatcherRuntimeConfig:
    """Watcher orchestration remains disabled unless the dedicated flag is true."""

    return WatcherRuntimeConfig(
        enabled=settings.watcher_orchestration_enabled,
        lease_ttl_seconds=settings.watcher_lease_ttl_seconds,
        heartbeat_stale_after_seconds=settings.watcher_heartbeat_stale_after_seconds,
    )
