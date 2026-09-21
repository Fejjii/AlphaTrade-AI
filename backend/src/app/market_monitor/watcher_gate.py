"""Fail-closed gate from the live monitor into Watcher scan evidence.

The monitor is the current-quote and trade-stream authority. Canonical
``FirstSliceEvidenceAssembler`` remains the sole CanonicalEvidenceWindowV1
producer. Watcher must not assemble when this gate refuses.

Replay stays usable for deterministic tests and is never a live mark.
"""

from __future__ import annotations

from app.market_contracts.enums import FreshnessState
from app.market_monitor.types import MarketAvailability, MonitorReason, SymbolMonitorSnapshot
from app.watcher.errors import WatcherEvidenceUnavailableError

_OUTAGE_REASONS = frozenset(
    {
        MonitorReason.PROVIDER_UNAVAILABLE,
        MonitorReason.PROVIDER_ERROR,
        MonitorReason.SPOT_REJECTED,
        MonitorReason.WRONG_SOURCE,
        MonitorReason.SYMBOL_MISMATCH,
        MonitorReason.UNRECOVERABLE_GAP,
        MonitorReason.OUT_OF_ORDER,
        MonitorReason.DUPLICATE_CONFLICT,
    }
)


def watcher_evidence_error_for_monitor(
    snapshot: SymbolMonitorSnapshot,
) -> WatcherEvidenceUnavailableError | None:
    """Return a fail-closed Watcher error, or None when assembly may proceed.

    Replay is allowed. Stale streams and provider failures never mint evidence.
    Rate-limited degraded snapshots may proceed only while the last contracted
    trade is still inside the freshness window.
    """

    if snapshot.availability is MarketAvailability.REPLAY:
        return None
    if snapshot.availability is MarketAvailability.FRESH:
        return None
    if snapshot.availability is MarketAvailability.STALE or snapshot.reason is MonitorReason.STALE_STREAM:
        return WatcherEvidenceUnavailableError(
            "Canonical scan evidence is stale.",
            reason_code="stale_evidence",
        )
    if snapshot.availability is MarketAvailability.UNAVAILABLE or snapshot.reason in _OUTAGE_REASONS:
        if snapshot.reason in _OUTAGE_REASONS:
            return WatcherEvidenceUnavailableError(
                "Perpetual market provider is unavailable.",
                reason_code="provider_outage",
            )
        return WatcherEvidenceUnavailableError(
            "Canonical scan evidence is unavailable.",
            reason_code="canonical_evidence_unavailable",
        )
    if snapshot.availability is MarketAvailability.DEGRADED:
        if snapshot.reason is MonitorReason.RATE_LIMITED and _quote_still_fresh(snapshot):
            return None
        if snapshot.reason is MonitorReason.RATE_LIMITED:
            return WatcherEvidenceUnavailableError(
                "Canonical scan evidence is stale.",
                reason_code="stale_evidence",
            )
        return WatcherEvidenceUnavailableError(
            "Canonical scan evidence is unavailable.",
            reason_code="canonical_evidence_unavailable",
        )
    return WatcherEvidenceUnavailableError(
        "Canonical scan evidence is unavailable.",
        reason_code="canonical_evidence_unavailable",
    )


def _quote_still_fresh(snapshot: SymbolMonitorSnapshot) -> bool:
    quote = snapshot.current_price
    if quote is None:
        return False
    return quote.freshness.state in {FreshnessState.FRESH, FreshnessState.AGING}


__all__ = ["watcher_evidence_error_for_monitor"]
