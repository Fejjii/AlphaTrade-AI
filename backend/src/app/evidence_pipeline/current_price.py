"""Truthful current perpetual price from contracted trades only."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from app.evidence_pipeline.types import CurrentPricePresentation, CurrentPriceQuote
from app.market_contracts.adapters.protocol import PerpetualMarketSource
from app.market_contracts.enums import FreshnessState
from app.market_contracts.errors import IncompleteWarmUpError
from app.market_contracts.freshness import evaluate_freshness, first_slice_freshness_policy
from app.market_contracts.identity import EvidenceMarketIdentity, InstrumentIdentity


def current_price_presentation(
    *,
    replay: bool,
    usable: bool,
    freshness_state: FreshnessState,
) -> CurrentPricePresentation:
    if usable:
        return CurrentPricePresentation.LIVE_MARK
    if replay:
        return CurrentPricePresentation.REPLAY_FIXTURE
    if freshness_state is FreshnessState.STALE:
        return CurrentPricePresentation.STALE
    return CurrentPricePresentation.UNAVAILABLE


def quote_current_price(
    source: PerpetualMarketSource,
    *,
    identity: EvidenceMarketIdentity,
    instrument: InstrumentIdentity,
    evaluated_at: datetime,
    connection_id: UUID,
    replay: bool,
) -> CurrentPriceQuote:
    """Last trade inside the freshness window. Empty windows fail closed."""
    if identity.provenance.fallback_used:
        raise IncompleteWarmUpError("Current price refuses fallback_used provenance.")
    policy = first_slice_freshness_policy()
    start = evaluated_at - timedelta(seconds=policy.trade_max_age_seconds)
    batch = source.fetch_ordered_trades(
        identity=identity,
        instrument=instrument,
        start=start,
        end=evaluated_at,
        source_connection_id=connection_id,
        receive_at=evaluated_at,
    )
    if not batch.trades:
        raise IncompleteWarmUpError(
            "No perpetual trades in the freshness window; refusing to fabricate a price."
        )
    terminal = batch.trades[-1]
    freshness = evaluate_freshness(
        source_time=terminal.event_timestamp,
        evaluated_at=evaluated_at,
        policy=policy,
        require_fresh=True,
    )
    usable = (
        identity.provenance.is_live
        and not identity.provenance.is_mock
        and not identity.provenance.fallback_used
        and not replay
        and freshness.state in {FreshnessState.FRESH, FreshnessState.AGING}
    )
    return CurrentPriceQuote(
        price=terminal.price,
        source_time=terminal.event_timestamp,
        venue_trade_id=terminal.venue_trade_id,
        freshness=freshness,
        usable_as_current_market_price=usable,
        presentation=current_price_presentation(
            replay=replay, usable=usable, freshness_state=freshness.state
        ),
        is_live=identity.provenance.is_live,
        is_mock=identity.provenance.is_mock,
        fallback_used=False,
        provider_name=identity.provenance.provider_name,
        source_family=identity.source.family,
        instrument_id=instrument.instrument_id,
        provider_symbol=instrument.provider_symbol,
    )
