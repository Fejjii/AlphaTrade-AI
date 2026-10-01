"""Persist canonical envelopes without changing their identity or receipt clocks."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.public_market_observations import PublicMarketObservationRow
from app.market_contracts.errors import DuplicateDataError
from app.market_contracts.hashing import semantic_content_hash
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.observation import PublicMarketObservation
from app.market_contracts.ohlcv import OhlcvBar
from app.services.canonical_serialization import canonical_sha256


def remember_observation(
    session: Session, observation: PublicMarketObservation, *, bar: OhlcvBar | None = None
) -> PublicMarketObservation:
    if observation.content_hash != semantic_content_hash(
        observation, extra_exclude=frozenset({"content_hash"})
    ):
        raise DuplicateDataError("Invalid canonical observation content hash.")
    if bar is not None and (
        bar.content_hash != semantic_content_hash(bar, extra_exclude=frozenset({"content_hash"}))
        or observation.payload_content_hash != bar.content_hash
        or observation.identity.instrument != bar.instrument
        or observation.identity.timeframe != bar.timeframe
        or observation.source_event_id != bar.source_event_id
        or observation.revision != bar.revision
        or observation.finality != bar.finality
        or observation.interval_start != bar.interval_start
        or observation.interval_end != bar.interval_end
    ):
        raise DuplicateDataError("Canonical OHLCV payload does not match its observation.")
    key = (canonical_sha256(observation.identity), observation.observation_id)
    row = session.get(PublicMarketObservationRow, key)
    if row is None:
        try:
            with session.begin_nested():
                row = PublicMarketObservationRow(
                    identity_hash=key[0],
                    observation_id=key[1],
                    payload=observation.model_dump(mode="json"),
                    bar_start=bar.interval_start if bar else None,
                    ohlcv=bar.model_dump(mode="json") if bar else None,
                )
                session.add(row)
                session.flush()
        except IntegrityError:
            row = session.get(PublicMarketObservationRow, key)
            if row is None:
                raise
    assert row is not None
    stored = PublicMarketObservation.model_validate(row.payload)
    if bar is not None and row.ohlcv != bar.model_dump(mode="json"):
        raise DuplicateDataError("Canonical receipt must preserve its original OHLCV payload.")
    # A revision is a distinct canonical observation, never an in-place correction.
    fields = (
        "identity",
        "observation_type",
        "source_event_id",
        "interval_start",
        "interval_end",
        "event_time",
        "source_time",
        "finality",
        "revision",
        "payload_content_hash",
    )
    if any(getattr(stored, name) != getattr(observation, name) for name in fields):
        raise DuplicateDataError("Conflicting content for an immutable canonical observation.")
    # Never backdate a late historical download or advance known-at on a restart.
    return stored


def observed_ohlcv_history(
    session: Session,
    *,
    identity: EvidenceMarketIdentity,
    since: datetime,
    evaluated_at: datetime,
    limit: int,
) -> tuple[tuple[OhlcvBar, PublicMarketObservation], ...]:
    rows = session.scalars(
        select(PublicMarketObservationRow)
        .where(
            PublicMarketObservationRow.identity_hash == canonical_sha256(identity),
            PublicMarketObservationRow.bar_start >= since,
            PublicMarketObservationRow.bar_start < evaluated_at,
            PublicMarketObservationRow.ohlcv.is_not(None),
        )
        .order_by(
            PublicMarketObservationRow.bar_start.desc(), PublicMarketObservationRow.observation_id
        )
        .limit(limit)
    )
    result: dict[str, tuple[OhlcvBar, PublicMarketObservation]] = {}
    for row in rows:
        observation = PublicMarketObservation.model_validate(row.payload)
        if max(observation.observed_at, observation.receive_time) <= evaluated_at:
            bar = OhlcvBar.model_validate(row.ohlcv)
            previous = result.get(bar.source_event_id)
            if previous is None or previous[0].revision < bar.revision:
                result[bar.source_event_id] = (bar, observation)
    return tuple(sorted(result.values(), key=lambda pair: pair[0].interval_start))
