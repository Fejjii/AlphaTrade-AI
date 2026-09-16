"""Resolve the read-only perpetual evidence source from settings."""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.errors import FallbackForbiddenError

REPLAY_MODES = frozenset({"replay", "mock", "fixture"})
LIVE_MODES = frozenset({"binance_usdm", "binance-usdm", "usdm"})


def resolve_perpetual_evidence_source(
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> ReplayPerpetualSource | BinanceUsdmPerpetualSource:
    mode = settings.perpetual_evidence_source.strip().lower()
    if mode in REPLAY_MODES:
        return ReplayPerpetualSource()
    if mode in LIVE_MODES:
        return BinanceUsdmPerpetualSource(
            base_url=settings.market_data_futures_base_url,
            timeout_seconds=settings.perpetual_evidence_timeout_seconds,
            transport=transport,
        )
    raise FallbackForbiddenError(
        f"Unknown perpetual_evidence_source={mode}; refusing silent fallback."
    )
