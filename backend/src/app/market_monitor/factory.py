"""Build the read-only perpetual market monitor from settings."""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.market_contracts.adapters.factory import (
    perpetual_source_is_replay,
    resolve_perpetual_evidence_source,
)
from app.market_contracts.adapters.protocol import PerpetualMarketSource
from app.market_contracts.catalog import PerpetualInstrumentCatalog
from app.market_monitor.backoff import BackoffPolicy
from app.market_monitor.monitor import Clock, PerpetualMarketMonitor


def build_perpetual_market_monitor(
    settings: Settings,
    *,
    source: PerpetualMarketSource | None = None,
    catalog: PerpetualInstrumentCatalog | None = None,
    transport: httpx.BaseTransport | None = None,
    clock: Clock | None = None,
) -> PerpetualMarketMonitor:
    replay = perpetual_source_is_replay(settings)
    resolved = source or resolve_perpetual_evidence_source(
        settings, transport=transport, catalog=catalog
    )
    return PerpetualMarketMonitor(
        resolved,
        replay=replay,
        catalog=catalog,
        backoff=BackoffPolicy(
            initial_seconds=settings.perpetual_monitor_backoff_initial_seconds,
            max_seconds=settings.perpetual_monitor_backoff_max_seconds,
        ),
        clock=clock,
        poll_seconds=settings.perpetual_monitor_poll_seconds,
    )
