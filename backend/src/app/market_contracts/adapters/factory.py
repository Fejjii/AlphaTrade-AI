"""Resolve the read-only perpetual evidence source from settings."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.market_activation.profile import LIVE_MODES, REPLAY_MODES
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.adapters.evidence_pool import shared_binance_evidence_pool
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.catalog import PerpetualInstrumentCatalog
from app.market_contracts.errors import FallbackForbiddenError


def perpetual_source_is_replay(settings: Settings) -> bool:
    return settings.perpetual_evidence_source.strip().lower() in REPLAY_MODES


def canonical_evidence_source_for_process(
    state: Any,
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
    catalog: PerpetualInstrumentCatalog | None = None,
) -> ReplayPerpetualSource | BinanceUsdmPerpetualSource:
    """Return the process source stored on ``state``. One HTTP app shares it."""

    current = getattr(state, "canonical_perpetual_evidence_source", None)
    if isinstance(current, ReplayPerpetualSource | BinanceUsdmPerpetualSource):
        return current
    source = resolve_perpetual_evidence_source(
        settings,
        transport=transport,
        catalog=catalog,
        shared=True,
    )
    state.canonical_perpetual_evidence_source = source
    return source


def resolve_perpetual_evidence_source(
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
    catalog: PerpetualInstrumentCatalog | None = None,
    shared: bool = False,
) -> ReplayPerpetualSource | BinanceUsdmPerpetualSource:
    mode = settings.perpetual_evidence_source.strip().lower()
    if mode in REPLAY_MODES:
        return ReplayPerpetualSource()
    if mode in LIVE_MODES:
        pool = shared_binance_evidence_pool(settings) if shared else None
        return BinanceUsdmPerpetualSource(
            base_url=settings.market_data_futures_base_url,
            timeout_seconds=settings.perpetual_evidence_timeout_seconds,
            transport=transport,
            catalog=catalog,
            max_retries=settings.binance_request_max_retries,
            weight_per_minute=settings.binance_request_weight_per_minute,
            max_backoff_seconds=settings.binance_request_max_backoff_seconds,
            trade_cache_entries=settings.binance_evidence_cache_entries,
            cache_ttl_seconds=settings.binance_evidence_cache_ttl_seconds,
            trade_cache=None if pool is None else pool.cache,
            budget=None if pool is None else pool.budget,
        )
    raise FallbackForbiddenError(
        f"Unknown perpetual_evidence_source={mode}; refusing silent fallback."
    )
