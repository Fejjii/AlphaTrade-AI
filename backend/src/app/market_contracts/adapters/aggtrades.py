"""Deterministic Binance USD-M aggTrades retrieval contract.

Official USD-M `GET /fapi/v1/aggTrades` constraints encoded here:

- `startTime` / `endTime` are inclusive and must span less than one hour
- `fromId` must not be combined with `startTime` / `endTime`
- each page is at most 1000 rows; a full page requires a `fromId` continuation
- reconnects and later CVD cannot treat an undrained page as complete
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.market_contracts.cursor import require_contiguous_sequences
from app.market_contracts.errors import (
    DuplicateDataError,
    GapDetectedError,
    IncompleteTradeWindowError,
    WrongMarketError,
)

AGGTRADE_PATH = "/fapi/v1/aggTrades"
AGGTRADE_PAGE_LIMIT = 1000
# Inclusive start/end span must be strictly less than one hour.
AGGTRADE_MAX_INCLUSIVE_SPAN_MS = 3_599_999
ONE_HOUR_MS = 3_600_000
AGGTRADE_MAX_PAGES_PER_CHUNK = 200
AGGTRADE_RETRIEVAL_POLICY_VERSION = "binance-usdm-aggtrades/time-chunk-fromid/v1"

JsonGetter = Callable[[str, Mapping[str, str | int] | None], Any]


def datetime_to_ms(value: datetime) -> int:
    utc = value.astimezone(UTC)
    return int(utc.timestamp()) * 1000 + utc.microsecond // 1000


def inclusive_ms_window(start: datetime, end: datetime) -> tuple[int, int]:
    """Half-open [start, end) as inclusive Binance millisecond bounds."""
    start_ms = datetime_to_ms(start)
    end_ms = datetime_to_ms(end)
    if end_ms <= start_ms:
        raise WrongMarketError("Trade window end must be after start.")
    return start_ms, end_ms - 1


def iter_aggtrade_time_chunks(start: datetime, end: datetime) -> list[tuple[int, int]]:
    """Inclusive [chunk_start_ms, chunk_end_ms] slices each shorter than one hour."""
    start_ms, last_ms = inclusive_ms_window(start, end)
    chunks: list[tuple[int, int]] = []
    cursor = start_ms
    while cursor <= last_ms:
        chunk_end = min(cursor + AGGTRADE_MAX_INCLUSIVE_SPAN_MS, last_ms)
        if chunk_end - cursor >= ONE_HOUR_MS:
            raise IncompleteTradeWindowError("AggTrade time chunk would exceed the 1h bound.")
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + 1
    return chunks


@dataclass(frozen=True, slots=True)
class AggTradeQuery:
    """One allowlisted aggTrades request: either a time window or a fromId cursor."""

    symbol: str
    limit: int = AGGTRADE_PAGE_LIMIT
    start_time_ms: int | None = None
    end_time_ms: int | None = None
    from_id: int | None = None

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > AGGTRADE_PAGE_LIMIT:
            raise IncompleteTradeWindowError("AggTrade page limit must be between 1 and 1000.")
        timed = self.start_time_ms is not None or self.end_time_ms is not None
        if self.from_id is not None and timed:
            raise IncompleteTradeWindowError(
                "AggTrade fromId cannot be combined with startTime/endTime."
            )
        if self.from_id is None and (self.start_time_ms is None or self.end_time_ms is None):
            raise IncompleteTradeWindowError(
                "AggTrade request must be either a time window or a fromId cursor."
            )
        if self.from_id is None:
            start = self.start_time_ms
            end = self.end_time_ms
            if start is None or end is None or end < start:
                raise IncompleteTradeWindowError("AggTrade time window is malformed.")
            if end - start >= ONE_HOUR_MS:
                raise IncompleteTradeWindowError(
                    "AggTrade startTime/endTime must span less than one hour."
                )

    def params(self) -> dict[str, str | int]:
        payload: dict[str, str | int] = {"symbol": self.symbol, "limit": self.limit}
        if self.from_id is not None:
            payload["fromId"] = self.from_id
            return payload
        assert self.start_time_ms is not None
        assert self.end_time_ms is not None
        payload["startTime"] = self.start_time_ms
        payload["endTime"] = self.end_time_ms
        return payload


def _row_id(row: Mapping[str, Any]) -> int:
    try:
        return int(row["a"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WrongMarketError("USD-M aggTrade is missing aggregate trade id.") from exc


def _row_event_ms(row: Mapping[str, Any]) -> int:
    try:
        return int(row["T"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WrongMarketError("USD-M aggTrade is missing event time.") from exc


def _dedupe_row(existing: Mapping[str, Any], incoming: Mapping[str, Any], agg_id: int) -> None:
    if (
        str(existing.get("p")) != str(incoming.get("p"))
        or str(existing.get("q")) != str(incoming.get("q"))
        or int(existing["T"]) != int(incoming["T"])
        or bool(existing.get("m")) != bool(incoming.get("m"))
    ):
        raise DuplicateDataError(f"Conflicting aggTrade content for id {agg_id}.")


def prove_aggtrade_coverage(
    rows: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Dedupe, keep half-open [start, end), and require contiguous aggregate ids."""
    start_ms, last_ms = inclusive_ms_window(start, end)
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise WrongMarketError("USD-M aggTrade row is malformed.")
        agg_id = _row_id(row)
        event_ms = _row_event_ms(row)
        if event_ms < start_ms or event_ms > last_ms:
            continue
        prior = by_id.get(agg_id)
        if prior is not None:
            _dedupe_row(prior, row, agg_id)
            continue
        by_id[agg_id] = dict(row)
    ordered_ids = sorted(by_id)
    try:
        require_contiguous_sequences(ordered_ids)
    except (DuplicateDataError, GapDetectedError) as exc:
        raise IncompleteTradeWindowError(str(exc)) from exc
    return [by_id[agg_id] for agg_id in ordered_ids]


def fetch_complete_agg_trade_rows(
    *,
    get_json: JsonGetter,
    symbol: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Retrieve every USD-M aggTrade in [start, end) with fail-closed pagination."""
    collected: list[dict[str, Any]] = []
    chunks = iter_aggtrade_time_chunks(start, end)
    overall_last_ms = inclusive_ms_window(start, end)[1]
    for chunk_start_ms, chunk_end_ms in chunks:
        from_id: int | None = None
        for _page in range(AGGTRADE_MAX_PAGES_PER_CHUNK):
            query = (
                AggTradeQuery(symbol=symbol, from_id=from_id)
                if from_id is not None
                else AggTradeQuery(
                    symbol=symbol,
                    start_time_ms=chunk_start_ms,
                    end_time_ms=chunk_end_ms,
                )
            )
            payload = get_json(AGGTRADE_PATH, query.params())
            if not isinstance(payload, list):
                raise WrongMarketError("USD-M aggTrades payload is not a list.")
            if not payload:
                break
            page_rows: list[dict[str, Any]] = []
            for raw in payload:
                if not isinstance(raw, dict):
                    raise WrongMarketError("USD-M aggTrade row is malformed.")
                page_rows.append(raw)
            page_rows.sort(key=_row_id)
            crossed_chunk_end = False
            for row in page_rows:
                event_ms = _row_event_ms(row)
                if event_ms > overall_last_ms:
                    crossed_chunk_end = True
                    continue
                if from_id is not None and event_ms > chunk_end_ms:
                    crossed_chunk_end = True
                    continue
                if event_ms < chunk_start_ms and from_id is None:
                    continue
                collected.append(row)
            if crossed_chunk_end or len(payload) < AGGTRADE_PAGE_LIMIT:
                break
            from_id = _row_id(page_rows[-1]) + 1
        else:
            raise IncompleteTradeWindowError(
                "AggTrade pagination exceeded the per-chunk page bound; window is incomplete."
            )
    return prove_aggtrade_coverage(collected, start=start, end=end)
