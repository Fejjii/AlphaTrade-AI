"""Resolve the read-only perpetual evidence source from settings."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.market_activation.profile import LIVE_MODES, REPLAY_MODES
from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.adapters.evidence_pool import shared_binance_evidence_pool
from app.market_contracts.adapters.failover import FailoverPerpetualSource
from app.market_contracts.adapters.okx_usdt_swap import OkxUsdtSwapPerpetualSource
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.catalog import PerpetualInstrumentCatalog
from app.market_contracts.errors import FallbackForbiddenError
from app.market_contracts.identity import binance_usdm_btcusdt, okx_usdt_swap_btcusdt

PerpetualEvidenceSource = (
    ReplayPerpetualSource
    | BinanceUsdmPerpetualSource
    | OkxUsdtSwapPerpetualSource
    | FailoverPerpetualSource
)


def perpetual_source_is_replay(settings: Settings) -> bool:
    return settings.perpetual_evidence_source.strip().lower() in REPLAY_MODES


def canonical_evidence_source_for_process(
    state: Any,
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
    catalog: PerpetualInstrumentCatalog | None = None,
) -> PerpetualEvidenceSource:
    """Return the process source stored on ``state``. One HTTP app shares it."""

    current = getattr(state, "canonical_perpetual_evidence_source", None)
    if isinstance(
        current,
        ReplayPerpetualSource
        | BinanceUsdmPerpetualSource
        | OkxUsdtSwapPerpetualSource
        | FailoverPerpetualSource,
    ):
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
) -> PerpetualEvidenceSource:
    mode = settings.perpetual_evidence_source.strip().lower()
    secondary = settings.perpetual_evidence_secondary_source.strip().lower()
    if mode in REPLAY_MODES:
        return ReplayPerpetualSource()
    if mode == "okx_usdt_swap":
        return _okx_source(settings, transport=transport)
    if mode in LIVE_MODES and secondary == "okx_usdt_swap":
        return FailoverPerpetualSource(
            _binance_source(settings, transport=transport, catalog=catalog, shared=shared),
            _okx_source(settings, transport=transport),
            primary_instrument=binance_usdm_btcusdt(),
            secondary_instrument=okx_usdt_swap_btcusdt(),
        )
    if mode in LIVE_MODES:
        return _binance_source(settings, transport=transport, catalog=catalog, shared=shared)
    raise FallbackForbiddenError(
        f"Unknown perpetual_evidence_source={mode}; refusing silent fallback."
    )


def _binance_source(
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None,
    catalog: PerpetualInstrumentCatalog | None,
    shared: bool,
) -> BinanceUsdmPerpetualSource:
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


def _okx_source(
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None,
) -> OkxUsdtSwapPerpetualSource:
    return OkxUsdtSwapPerpetualSource(
        base_url=settings.okx_swap_base_url,
        timeout_seconds=settings.perpetual_evidence_timeout_seconds,
        transport=transport,
        max_retries=settings.binance_request_max_retries,
        max_backoff_seconds=settings.binance_request_max_backoff_seconds,
        max_trade_pages=settings.okx_trade_history_max_pages,
    )
