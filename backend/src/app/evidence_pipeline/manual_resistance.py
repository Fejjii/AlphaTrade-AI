"""Load persisted 4h resistance into Watcher evidence.

Chart levels are operator input, not a fabricated SetupAssessment. The Watcher
scan identity is the perpetual instrument, so a Binance level on that symbol is
projected as perpetual resistance. Missing or ineligible levels stay absent and
the evaluator fails closed.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ManualLevelRevision
from app.market_contracts.enums import MarketType, VenueId
from app.market_contracts.identity import binance_usdm_btcusdt
from app.schemas.common import ManualLevelType, Timeframe
from app.signal_fusion.first_slice_types import ManualResistanceEvidence
from app.signal_fusion.types import ManualLevelRevisionRef

_BINANCE_EXCHANGES = frozenset({"binance", "binance_usdm"})


def persisted_resistance_evidence(
    session: Session,
    *,
    organization_id: UUID,
    symbol: str,
) -> tuple[ManualResistanceEvidence, ...]:
    """Latest valid resistance revision per level for one tenant symbol."""

    rows = list(
        session.scalars(
            select(ManualLevelRevision)
            .where(
                ManualLevelRevision.organization_id == organization_id,
                ManualLevelRevision.instrument == symbol,
                ManualLevelRevision.valid.is_(True),
                ManualLevelRevision.level_type == ManualLevelType.RESISTANCE,
            )
            .order_by(
                ManualLevelRevision.level_id,
                ManualLevelRevision.revision_number.desc(),
            )
        ).all()
    )
    instrument = binance_usdm_btcusdt()
    if symbol.upper() != instrument.provider_symbol:
        return ()
    seen: set[UUID] = set()
    evidence: list[ManualResistanceEvidence] = []
    for row in rows:
        if row.level_id in seen:
            continue
        seen.add(row.level_id)
        if (row.timeframe or "").lower() not in {Timeframe.H4.value, "4h"}:
            continue
        if row.exchange.strip().lower() not in _BINANCE_EXCHANGES:
            continue
        if row.value is None:
            continue
        evidence.append(
            ManualResistanceEvidence(
                ref=ManualLevelRevisionRef(
                    level_id=row.level_id,
                    revision_number=row.revision_number,
                    content_hash=row.content_hash,
                ),
                price=row.value,
                timeframe=Timeframe.H4,
                effective_at=row.effective_at,
                valid=bool(row.valid),
                venue=VenueId.BINANCE,
                market_type=MarketType.PERPETUAL,
                instrument_id=instrument.instrument_id,
            )
        )
    return tuple(evidence)
