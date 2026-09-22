"""Current perpetual price from an already-contracted terminal trade."""

from __future__ import annotations

from datetime import datetime

from app.evidence_pipeline.current_price import current_price_presentation
from app.evidence_pipeline.types import CurrentPricePresentation, CurrentPriceQuote
from app.market_contracts.enums import FreshnessState, ReconnectState
from app.market_contracts.errors import StaleEvidenceError
from app.market_contracts.freshness import evaluate_freshness, first_slice_freshness_policy
from app.market_contracts.identity import EvidenceMarketIdentity, InstrumentIdentity
from app.market_contracts.trades import TradeEvent


def quote_from_terminal_trade(
    trade: TradeEvent,
    *,
    identity: EvidenceMarketIdentity,
    instrument: InstrumentIdentity,
    evaluated_at: datetime,
    replay: bool,
    reconnect_state: ReconnectState,
    stream_healthy: bool,
) -> CurrentPriceQuote | None:
    """Last contracted trade. Empty or stale windows return None — never a fabricated mark."""
    if identity.provenance.fallback_used:
        return None
    policy = first_slice_freshness_policy()
    try:
        freshness = evaluate_freshness(
            source_time=trade.event_timestamp,
            evaluated_at=evaluated_at,
            policy=policy,
            require_fresh=True,
        )
    except StaleEvidenceError:
        return None
    live_ok = (
        identity.provenance.is_live
        and not identity.provenance.is_mock
        and not identity.provenance.fallback_used
        and not replay
        and stream_healthy
        and reconnect_state in {ReconnectState.CONTINUOUS, ReconnectState.RECOVERED}
        and freshness.state in {FreshnessState.FRESH, FreshnessState.AGING}
    )
    if replay:
        presentation = CurrentPricePresentation.REPLAY_FIXTURE
    elif live_ok:
        presentation = CurrentPricePresentation.LIVE_MARK
    elif freshness.state is FreshnessState.STALE:
        presentation = CurrentPricePresentation.STALE
    else:
        presentation = current_price_presentation(
            replay=replay, usable=False, freshness_state=freshness.state
        )
        if not stream_healthy or reconnect_state is ReconnectState.RECONNECTING:
            presentation = CurrentPricePresentation.DEGRADED
    return CurrentPriceQuote(
        price=trade.price,
        source_time=trade.event_timestamp,
        venue_trade_id=trade.venue_trade_id,
        freshness=freshness,
        usable_as_current_market_price=live_ok,
        presentation=presentation,
        is_live=identity.provenance.is_live,
        is_mock=identity.provenance.is_mock,
        fallback_used=False,
        provider_name=identity.provenance.provider_name,
        source_family=identity.source.family,
        instrument_id=instrument.instrument_id,
        provider_symbol=instrument.provider_symbol,
    )
