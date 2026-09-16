"""Trade-stream cursor, reconnect epochs, and fail-closed gap detection."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.enums import GapState, ReconnectState, WarmUpStatus
from app.market_contracts.errors import (
    CursorRecoveryError,
    DuplicateDataError,
    GapDetectedError,
    OutOfOrderTradesError,
    UnrecoverableGapError,
)
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import EvidenceMarketIdentity, require_perpetual
from app.market_contracts.models import CanonicalModel
from app.market_contracts.trades import TradeEvent, order_trades


class TradeStreamCursor(CanonicalModel):
    cursor_id: UUID
    identity: EvidenceMarketIdentity
    connection_identity: UUID
    last_event_id: str | None = None
    last_sequence: int | None = Field(default=None, ge=0)
    connected_at: AwareDatetime
    last_event_at: AwareDatetime | None = None
    reconnect_count: int = Field(ge=0)
    reconnect_state: ReconnectState
    gap_state: GapState
    gap_start: int | None = Field(default=None, ge=0)
    gap_end: int | None = Field(default=None, ge=0)
    warm_up_status: WarmUpStatus
    updated_at: AwareDatetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _gap_bounds(self) -> TradeStreamCursor:
        require_perpetual(self.identity)
        if (self.gap_start is None) != (self.gap_end is None):
            raise ValueError("gap_start and gap_end must both be set or both omitted.")
        start = self.gap_start
        end = self.gap_end
        if start is not None and end is not None and end < start:
            raise ValueError("gap_end cannot precede gap_start.")
        if self.gap_state is GapState.NONE and self.gap_start is not None:
            raise ValueError("gap bounds must be empty when gap_state is none.")
        return self


class TradeStreamSnapshot(CanonicalModel):
    cursor: TradeStreamCursor
    trades: list[TradeEvent]
    usable: bool


def _hash_cursor(cursor: TradeStreamCursor) -> TradeStreamCursor:
    return with_content_hash(cursor)


def initial_cursor(
    *,
    identity: EvidenceMarketIdentity,
    connected_at: datetime,
    connection_identity: UUID | None = None,
) -> TradeStreamCursor:
    now = connected_at.astimezone(UTC)
    connection = connection_identity or uuid4()
    cursor = TradeStreamCursor(
        cursor_id=uuid4(),
        identity=identity,
        connection_identity=connection,
        last_event_id=None,
        last_sequence=None,
        connected_at=now,
        last_event_at=None,
        reconnect_count=0,
        reconnect_state=ReconnectState.INITIAL,
        gap_state=GapState.NONE,
        gap_start=None,
        gap_end=None,
        warm_up_status=WarmUpStatus.EMPTY,
        updated_at=now,
        content_hash="0" * 64,
    )
    return _hash_cursor(cursor)


def detect_sequence_gap(
    previous_sequence: int | None, next_sequence: int
) -> tuple[int, int] | None:
    if previous_sequence is None:
        return None
    if next_sequence == previous_sequence + 1:
        return None
    if next_sequence <= previous_sequence:
        return None
    return previous_sequence + 1, next_sequence - 1


def _assert_contiguous(sequences: list[int]) -> None:
    if not sequences:
        return
    previous = sequences[0]
    for current in sequences[1:]:
        if current == previous:
            raise DuplicateDataError(f"Duplicate sequence {current}.")
        if current != previous + 1:
            raise GapDetectedError(f"Confirmed sequence gap {previous + 1}-{current - 1}.")
        previous = current


def _retag_connection(trade: TradeEvent, connection_id: UUID) -> TradeEvent:
    if trade.source_connection_id == connection_id:
        return trade
    updated = trade.model_copy(update={"source_connection_id": connection_id})
    return with_content_hash(updated, extra_exclude=frozenset({"source_connection_id"}))


class TradeStreamAssembler:
    """In-memory ordered trade assembler with fail-closed reconnect semantics.

    V1: every reconnect starts a new connection epoch. Current CVD is unusable
    until contiguous backfill and a fresh warm-up complete. Unresolved gaps fail
    closed. Cross-connection CVD windows are not supported.
    """

    def __init__(
        self,
        identity: EvidenceMarketIdentity,
        *,
        connected_at: datetime,
        connection_identity: UUID | None = None,
        expected_contiguous_count: int | None = None,
    ) -> None:
        self._identity = identity
        self._expected_contiguous_count = expected_contiguous_count
        self._cursor = initial_cursor(
            identity=identity,
            connected_at=connected_at,
            connection_identity=connection_identity,
        )
        self._by_id: dict[str, TradeEvent] = {}
        self._ordered: list[TradeEvent] = []
        self._watermark_sequence: int | None = None

    @property
    def cursor(self) -> TradeStreamCursor:
        return self._cursor

    @property
    def connection_identity(self) -> UUID:
        return self._cursor.connection_identity

    def accepted_trades(self) -> list[TradeEvent]:
        return list(self._ordered)

    def ingest(
        self,
        trades: list[TradeEvent],
        *,
        observed_at: datetime,
        allow_empty: bool = False,
    ) -> TradeStreamSnapshot:
        if self._cursor.gap_state is GapState.UNRECOVERABLE:
            raise UnrecoverableGapError("Stream is closed after an unrecoverable gap.")
        if self._cursor.reconnect_state is ReconnectState.RECONNECTING:
            raise CursorRecoveryError("Ingest during reconnect requires recover_from_backfill.")
        if not trades and not allow_empty:
            raise GapDetectedError("Empty trade ingest is not a contiguous stream proof.")

        ordered = order_trades(trades)
        self._accept_live(ordered, observed_at=observed_at)
        self._refresh_warm_up(observed_at)
        return self._snapshot()

    def begin_reconnect(self, *, observed_at: datetime) -> TradeStreamCursor:
        now = observed_at.astimezone(UTC)
        self._watermark_sequence = self._cursor.last_sequence
        self._cursor = _hash_cursor(
            self._cursor.model_copy(
                update={
                    "cursor_id": uuid4(),
                    "connection_identity": uuid4(),
                    "reconnect_count": self._cursor.reconnect_count + 1,
                    "reconnect_state": ReconnectState.RECONNECTING,
                    "gap_state": GapState.SUSPECTED,
                    "warm_up_status": WarmUpStatus.BACKFILLING,
                    "last_event_id": None,
                    "last_sequence": None,
                    "last_event_at": None,
                    "connected_at": now,
                    "updated_at": now,
                }
            )
        )
        return self._cursor

    def recover_from_backfill(
        self,
        backfill: list[TradeEvent],
        *,
        observed_at: datetime,
        live_resume: list[TradeEvent] | None = None,
    ) -> TradeStreamSnapshot:
        if self._cursor.reconnect_state is not ReconnectState.RECONNECTING:
            raise CursorRecoveryError("recover_from_backfill requires RECONNECTING state.")

        combined = self._dedupe_ordered(list(backfill) + list(live_resume or []))
        if not combined:
            self._fail_unrecoverable(observed_at, gap_start=self._watermark_sequence, gap_end=None)
            raise UnrecoverableGapError("Reconnect backfill was empty; gap remains unresolved.")

        try:
            _assert_contiguous([trade.sequence for trade in combined])
            self._assert_watermark_coverage(combined)
        except (GapDetectedError, DuplicateDataError) as exc:
            sequences = [trade.sequence for trade in combined]
            self._fail_unrecoverable(
                observed_at,
                gap_start=min(sequences),
                gap_end=max(sequences),
            )
            raise UnrecoverableGapError(str(exc)) from exc

        connection = self._cursor.connection_identity
        epoch_trades = [_retag_connection(trade, connection) for trade in combined]
        self._ordered = epoch_trades
        for trade in epoch_trades:
            self._by_id[trade.venue_trade_id] = trade

        last = epoch_trades[-1]
        now = observed_at.astimezone(UTC)
        self._cursor = _hash_cursor(
            self._cursor.model_copy(
                update={
                    "last_event_id": last.venue_trade_id,
                    "last_sequence": last.sequence,
                    "last_event_at": last.event_timestamp,
                    "reconnect_state": ReconnectState.RECOVERED,
                    "gap_state": GapState.NONE,
                    "gap_start": None,
                    "gap_end": None,
                    "updated_at": now,
                }
            )
        )
        self._refresh_warm_up(observed_at)
        if self._cursor.warm_up_status is WarmUpStatus.COMPLETE:
            self._cursor = _hash_cursor(
                self._cursor.model_copy(
                    update={"reconnect_state": ReconnectState.CONTINUOUS, "updated_at": now}
                )
            )
        return self._snapshot()

    def _dedupe_ordered(self, trades: list[TradeEvent]) -> list[TradeEvent]:
        ordered = order_trades(trades)
        unique: list[TradeEvent] = []
        seen: dict[str, str] = {}
        for trade in ordered:
            prior = seen.get(trade.venue_trade_id)
            if prior is None:
                seen[trade.venue_trade_id] = trade.content_hash
                unique.append(trade)
                continue
            if prior != trade.content_hash:
                raise DuplicateDataError(
                    f"Conflicting content for venue trade {trade.venue_trade_id}."
                )
        return unique

    def _assert_watermark_coverage(self, combined: list[TradeEvent]) -> None:
        watermark = self._watermark_sequence
        if watermark is None:
            return
        present = {trade.sequence for trade in combined}
        max_seq = max(present)
        if max_seq < watermark + 1:
            raise GapDetectedError(f"Reconnect backfill never resumed after sequence {watermark}.")
        missing = [seq for seq in range(watermark + 1, max_seq + 1) if seq not in present]
        if missing:
            raise GapDetectedError(f"Confirmed sequence gap {missing[0]}-{missing[-1]}.")

    def _accept_live(self, ordered: list[TradeEvent], *, observed_at: datetime) -> None:
        now = observed_at.astimezone(UTC)
        for trade in ordered:
            if trade.source_connection_id != self._cursor.connection_identity:
                raise CursorRecoveryError(
                    "Trade connection epoch does not match the current cursor epoch."
                )
            existing = self._by_id.get(trade.venue_trade_id)
            if existing is not None:
                if existing.content_hash != trade.content_hash:
                    raise DuplicateDataError(
                        f"Conflicting content for venue trade {trade.venue_trade_id}."
                    )
                continue

            last_seq = self._cursor.last_sequence
            if last_seq is not None and trade.sequence < last_seq:
                raise OutOfOrderTradesError(
                    f"Trade sequence {trade.sequence} arrived after {last_seq} without reconnect."
                )
            if last_seq is not None and trade.sequence == last_seq:
                raise DuplicateDataError(f"Duplicate sequence {trade.sequence}.")

            gap = detect_sequence_gap(last_seq, trade.sequence)
            if gap is not None:
                start, end = gap
                self._cursor = _hash_cursor(
                    self._cursor.model_copy(
                        update={
                            "gap_state": GapState.CONFIRMED,
                            "gap_start": start,
                            "gap_end": end,
                            "updated_at": now,
                        }
                    )
                )
                raise GapDetectedError(
                    f"Confirmed sequence gap {start}-{end} on {trade.venue_trade_id}."
                )

            self._by_id[trade.venue_trade_id] = trade
            self._ordered.append(trade)
            reconnect_state = self._cursor.reconnect_state
            if reconnect_state in {ReconnectState.INITIAL, ReconnectState.RECOVERED}:
                reconnect_state = ReconnectState.CONTINUOUS
            self._cursor = _hash_cursor(
                self._cursor.model_copy(
                    update={
                        "last_event_id": trade.venue_trade_id,
                        "last_sequence": trade.sequence,
                        "last_event_at": trade.event_timestamp,
                        "reconnect_state": reconnect_state,
                        "gap_state": GapState.NONE,
                        "gap_start": None,
                        "gap_end": None,
                        "updated_at": now,
                    }
                )
            )

    def _refresh_warm_up(self, observed_at: datetime) -> None:
        now = observed_at.astimezone(UTC)
        if self._cursor.gap_state is not GapState.NONE:
            status = WarmUpStatus.FAILED
        elif not self._ordered:
            status = WarmUpStatus.EMPTY
        elif (
            self._expected_contiguous_count is not None
            and len(self._ordered) < self._expected_contiguous_count
        ):
            status = WarmUpStatus.BACKFILLING
        else:
            status = WarmUpStatus.COMPLETE
        self._cursor = _hash_cursor(
            self._cursor.model_copy(update={"warm_up_status": status, "updated_at": now})
        )

    def _fail_unrecoverable(
        self, observed_at: datetime, *, gap_start: int | None, gap_end: int | None
    ) -> None:
        now = observed_at.astimezone(UTC)
        start = gap_start if gap_start is not None else 0
        end = gap_end if gap_end is not None else start
        if end < start:
            end = start
        self._cursor = _hash_cursor(
            self._cursor.model_copy(
                update={
                    "gap_state": GapState.UNRECOVERABLE,
                    "gap_start": start,
                    "gap_end": end,
                    "warm_up_status": WarmUpStatus.FAILED,
                    "updated_at": now,
                }
            )
        )

    def _snapshot(self) -> TradeStreamSnapshot:
        usable = (
            self._cursor.gap_state is GapState.NONE
            and self._cursor.warm_up_status is WarmUpStatus.COMPLETE
            and self._cursor.reconnect_state
            in {ReconnectState.CONTINUOUS, ReconnectState.RECOVERED}
        )
        return TradeStreamSnapshot(cursor=self._cursor, trades=list(self._ordered), usable=usable)
