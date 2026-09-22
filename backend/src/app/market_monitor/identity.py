"""Semantic identity for monitor snapshots.

Transport metadata (connection ids, receive times, backoff, retries) is excluded.
Market corrections — a different trade, price, CVD, or OHLCV series — change the hash.
"""

from __future__ import annotations

from typing import Any

from app.market_monitor.types import SymbolMonitorSnapshot
from app.services.canonical_serialization import canonical_sha256


def monitor_semantic_preimage(snapshot: SymbolMonitorSnapshot) -> dict[str, Any]:
    price = snapshot.current_price
    return {
        "symbol": snapshot.symbol,
        "mode": snapshot.mode.value,
        "instrument_id": snapshot.instrument_id,
        "provider_symbol": snapshot.provider_symbol,
        "source_family": snapshot.source_family.value,
        "provider_name": snapshot.provider_name,
        "is_live": snapshot.is_live,
        "is_mock": snapshot.is_mock,
        "fallback_used": snapshot.fallback_used,
        "perpetual": snapshot.perpetual,
        "price": None
        if price is None
        else {
            "price": str(price.price),
            "source_time": price.source_time.isoformat(),
            "venue_trade_id": price.venue_trade_id,
            "presentation": price.presentation.value,
            "usable_as_current_market_price": price.usable_as_current_market_price,
        },
        "coverage_first_trade_id": snapshot.coverage.first_trade_id,
        "coverage_last_trade_id": snapshot.coverage.last_trade_id,
        "cvd_available": snapshot.cvd.available,
        "cvd_signed_quote_delta": snapshot.cvd.signed_quote_delta,
        "cvd_event_set_hash": snapshot.cvd.event_set_hash,
        "ohlcv_15m_hash": snapshot.ohlcv.series_15m_hash,
        "ohlcv_4h_hash": snapshot.ohlcv.series_4h_hash,
        "latest_15m_close": snapshot.ohlcv.latest_15m_close,
    }


def monitor_semantic_hash(snapshot: SymbolMonitorSnapshot) -> str:
    return canonical_sha256(monitor_semantic_preimage(snapshot))
