"""Closed (FINAL) OHLCV contracts. Forming candles never confirm."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.enums import Finality, SourceFamily
from app.market_contracts.errors import (
    FormingCandleError,
    GapDetectedError,
    MarketContractError,
    WrongInstrumentError,
    WrongMarketError,
)
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import (
    ADAPTER_VERSION,
    EvidenceMarketIdentity,
    InstrumentIdentity,
    interval_timedelta,
    require_instrument,
    require_perpetual,
)
from app.market_contracts.models import (
    CanonicalDecimal,
    CanonicalModel,
    NonNegativeCanonicalDecimal,
    PositiveCanonicalDecimal,
)
from app.schemas.common import Timeframe

_OBSERVATION_NAMESPACE = UUID("6f2c1b1e-5a47-4d8a-9c11-0f3a91b8e015")


class OhlcvBar(CanonicalModel):
    """One venue kline after normalization."""

    instrument: InstrumentIdentity
    timeframe: Timeframe
    interval_start: AwareDatetime
    interval_end: AwareDatetime
    open: PositiveCanonicalDecimal
    high: PositiveCanonicalDecimal
    low: PositiveCanonicalDecimal
    close: PositiveCanonicalDecimal
    base_volume: NonNegativeCanonicalDecimal
    quote_volume: NonNegativeCanonicalDecimal
    trade_count: int | None = Field(default=None, ge=0)
    source_event_id: str = Field(min_length=3, max_length=80)
    provider_complete: bool
    finality: Finality
    revision: int = Field(ge=1, le=1_000_000)
    source_time: AwareDatetime
    adapter_version: str = Field(min_length=3, max_length=80)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _ohlc_invariants(self) -> OhlcvBar:
        if self.interval_end <= self.interval_start:
            raise ValueError("interval_end must be after interval_start.")
        if self.high < self.low:
            raise ValueError("high cannot be below low.")
        if self.high < self.open or self.high < self.close:
            raise ValueError("high must be at least open and close.")
        if self.low > self.open or self.low > self.close:
            raise ValueError("low must be at most open and close.")
        expected_end = self.interval_start + interval_timedelta(self.timeframe)
        if self.interval_end != expected_end:
            raise ValueError("interval_end must equal interval_start + timeframe duration.")
        return self


class ClosedOhlcvSeries(CanonicalModel):
    """Contiguous FINAL bars for one venue/market/instrument/timeframe."""

    identity: EvidenceMarketIdentity
    timeframe: Timeframe
    bars: list[OhlcvBar] = Field(min_length=1)
    evaluated_at: AwareDatetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _closed_contiguous(self) -> ClosedOhlcvSeries:
        try:
            assert_closed_series_bars(self.identity, self.timeframe, self.bars)
        except MarketContractError as exc:
            raise ValueError(str(exc)) from exc
        return self


def assert_closed_series_bars(
    identity: EvidenceMarketIdentity,
    timeframe: Timeframe,
    bars: list[OhlcvBar],
) -> None:
    require_perpetual(identity)
    if identity.timeframe is not None and identity.timeframe is not timeframe:
        raise ValueError("Series timeframe does not match identity timeframe.")
    expected = identity.instrument
    previous_end: datetime | None = None
    seen_ids: set[str] = set()
    for bar in bars:
        if bar.instrument.instrument_id != expected.instrument_id:
            raise WrongInstrumentError("OHLCV bar instrument does not match series identity.")
        if bar.timeframe is not timeframe:
            raise ValueError("Mixed timeframes are not allowed in a closed series.")
        if bar.finality is not Finality.FINAL:
            raise FormingCandleError(
                f"Closed series rejected {bar.finality.value} candle {bar.source_event_id}."
            )
        if not bar.provider_complete:
            raise FormingCandleError(
                f"Closed series rejected incomplete candle {bar.source_event_id}."
            )
        if bar.source_event_id in seen_ids:
            raise GapDetectedError(f"Duplicate OHLCV source_event_id {bar.source_event_id}.")
        seen_ids.add(bar.source_event_id)
        if previous_end is not None and bar.interval_start != previous_end:
            raise GapDetectedError(
                "OHLCV interval gap between "
                f"{previous_end.isoformat()} and {bar.interval_start.isoformat()}."
            )
        previous_end = bar.interval_end


def kline_source_event_id(
    instrument_id: str, timeframe: Timeframe, interval_start: datetime
) -> str:
    start = interval_start.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return f"kline:{instrument_id}:{timeframe.value}:{start}"


def classify_kline_finality(
    *,
    interval_end: datetime,
    evaluated_at: datetime,
    grace: timedelta,
    provider_complete: bool,
) -> Finality:
    if not provider_complete:
        return Finality.FORMING
    if evaluated_at < interval_end + grace:
        return Finality.FORMING
    return Finality.FINAL


def build_ohlcv_bar(
    *,
    instrument: InstrumentIdentity,
    timeframe: Timeframe,
    interval_start: datetime,
    open_: CanonicalDecimal,
    high: CanonicalDecimal,
    low: CanonicalDecimal,
    close: CanonicalDecimal,
    base_volume: CanonicalDecimal,
    quote_volume: CanonicalDecimal,
    evaluated_at: datetime,
    grace: timedelta,
    provider_complete: bool | None = None,
    trade_count: int | None = None,
    revision: int = 1,
    adapter_version: str = ADAPTER_VERSION,
) -> OhlcvBar:
    start = interval_start.astimezone(UTC)
    end = start + interval_timedelta(timeframe)
    complete = provider_complete if provider_complete is not None else evaluated_at >= end
    finality = classify_kline_finality(
        interval_end=end,
        evaluated_at=evaluated_at.astimezone(UTC),
        grace=grace,
        provider_complete=complete,
    )
    source_event_id = kline_source_event_id(instrument.instrument_id, timeframe, start)
    bar = OhlcvBar(
        instrument=instrument,
        timeframe=timeframe,
        interval_start=start,
        interval_end=end,
        open=open_,
        high=high,
        low=low,
        close=close,
        base_volume=base_volume,
        quote_volume=quote_volume,
        trade_count=trade_count,
        source_event_id=source_event_id,
        provider_complete=complete,
        finality=finality,
        revision=revision,
        source_time=start,
        adapter_version=adapter_version,
        content_hash="0" * 64,
    )
    return with_content_hash(bar)


def observation_id_for(
    source_event_id: str,
    *,
    finality: Finality | None = None,
    revision: int = 1,
) -> UUID:
    """Deterministic immutable-append identity for a public observation.

    Phase 6 requires FORMING, FINAL, and corrected revisions of the same
    natural event to be distinct observations. The identity key is
    ``source_event_id|finality|revision``.

    Callers that omit ``finality`` receive the legacy natural-event UUID
    (``uuid5(namespace, source_event_id)``) used before revision-aware
    append identity. ``observation_from_ohlcv`` always passes finality and
    revision. Exact replay of the same revision is stable. Old observations
    are never mutated.
    """
    if revision < 1:
        raise ValueError("revision must be >= 1")
    if finality is None:
        return uuid5(_OBSERVATION_NAMESPACE, source_event_id)
    return uuid5(_OBSERVATION_NAMESPACE, f"{source_event_id}|{finality.value}|{revision}")


def require_closed_series(
    bars: list[OhlcvBar],
    *,
    identity: EvidenceMarketIdentity,
    timeframe: Timeframe,
    evaluated_at: datetime,
    min_bars: int,
) -> ClosedOhlcvSeries:
    require_perpetual(identity)
    require_instrument(identity, identity.instrument)
    if identity.source.family not in {
        SourceFamily.BINANCE_USDM_FUTURES_PUBLIC,
        SourceFamily.OKX_USDT_SWAP_PUBLIC,
        SourceFamily.REPLAY_FIXTURE,
    }:
        raise WrongMarketError("OHLCV source family is not a contracted perpetual source.")
    if identity.timeframe is not None and identity.timeframe is not timeframe:
        raise ValueError("Identity timeframe does not match requested timeframe.")
    forming = [bar.source_event_id for bar in bars if bar.finality is not Finality.FINAL]
    if forming:
        raise FormingCandleError(f"Forming candles cannot confirm evidence: {forming[0]}.")
    if len(bars) < min_bars:
        raise FormingCandleError(
            f"Need at least {min_bars} final {timeframe.value} candles; received {len(bars)}."
        )
    selected = bars[-min_bars:] if len(bars) > min_bars else bars
    assert_closed_series_bars(identity, timeframe, selected)
    series = ClosedOhlcvSeries(
        identity=identity,
        timeframe=timeframe,
        bars=selected,
        evaluated_at=evaluated_at.astimezone(UTC),
        content_hash="0" * 64,
    )
    return with_content_hash(series)
