"""Immutable authoritative coverage proofs for ordered perpetual trade windows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.enums import DataCompleteness, GapState
from app.market_contracts.errors import (
    GapDetectedError,
    IncompleteTradeWindowError,
    WrongInstrumentError,
    WrongMarketError,
    WrongSourceError,
)
from app.market_contracts.hashing import (
    CONTENT_HASH_EXCLUDE,
    semantic_content_hash,
    with_content_hash,
)
from app.market_contracts.identity import EvidenceMarketIdentity, require_perpetual
from app.market_contracts.models import CanonicalModel

if TYPE_CHECKING:
    from app.market_contracts.trades import TradeEvent

TRADE_WINDOW_COVERAGE_POLICY_VERSION = "trade-window-coverage/half-open/v1"
_COVERAGE_NAMESPACE = UUID("eaf6fe6f-c3e9-4971-a88d-413db4ac7576")
_MIN_EXCLUSIVE_INCREMENT = timedelta(microseconds=1)


class TradeWindowCoverageProof(CanonicalModel):
    """Authoritative statement that one lineage covered a half-open trade window."""

    coverage_proof_id: UUID
    identity: EvidenceMarketIdentity
    lineage_id: UUID
    requested_start: AwareDatetime
    requested_end: AwareDatetime
    actual_covered_start: AwareDatetime | None
    actual_covered_end: AwareDatetime | None
    gap_state: GapState
    completeness: DataCompleteness
    first_trade_id: str | None = Field(default=None, max_length=40)
    last_trade_id: str | None = Field(default=None, max_length=40)
    first_sequence: int | None = Field(default=None, ge=0)
    last_sequence: int | None = Field(default=None, ge=0)
    trade_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_version: str = Field(min_length=3, max_length=80)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_coverage_bounds(self) -> TradeWindowCoverageProof:
        require_perpetual(self.identity)
        if self.requested_end <= self.requested_start:
            raise ValueError("Trade coverage requested_end must be after requested_start.")
        if (self.actual_covered_start is None) != (self.actual_covered_end is None):
            raise ValueError("Actual coverage bounds must both be present or both be absent.")
        if (
            self.actual_covered_start is not None
            and self.actual_covered_end is not None
            and self.actual_covered_end <= self.actual_covered_start
        ):
            raise ValueError("Actual trade coverage must be a non-empty half-open interval.")
        trade_identity_fields = (
            self.first_trade_id,
            self.last_trade_id,
            self.first_sequence,
            self.last_sequence,
        )
        if any(value is None for value in trade_identity_fields) and any(
            value is not None for value in trade_identity_fields
        ):
            raise ValueError("First/last trade identities and sequences must be all set or absent.")
        if (
            self.first_sequence is not None
            and self.last_sequence is not None
            and self.last_sequence < self.first_sequence
        ):
            raise ValueError("Coverage last_sequence cannot precede first_sequence.")
        if self.completeness is DataCompleteness.COMPLETE:
            if self.gap_state is not GapState.NONE:
                raise ValueError("Complete trade coverage cannot contain an unresolved gap.")
            if self.actual_covered_start is None or self.actual_covered_end is None:
                raise ValueError("Complete trade coverage requires actual coverage bounds.")
            if self.actual_covered_start > self.requested_start:
                raise ValueError("Complete coverage cannot start after the requested window.")
            if self.actual_covered_end < self.requested_end:
                raise ValueError("Complete coverage cannot end before the requested window.")
        return self


def require_trade_matches_identity(
    trade: TradeEvent,
    identity: EvidenceMarketIdentity,
) -> None:
    """Validate every identity facet represented by a normalized trade event."""
    if trade.instrument != identity.instrument:
        raise WrongInstrumentError(
            "Trade instrument identity does not exactly match the evidence market identity."
        )
    if trade.instrument.venue is not identity.venue:
        raise WrongMarketError("Trade venue does not match the evidence market identity.")
    if trade.market_type is not identity.market_type:
        raise WrongMarketError("Trade market type does not match the evidence market identity.")
    if trade.adapter_version != identity.source.adapter_version:
        raise WrongSourceError("Trade adapter version does not match the evidence source identity.")
    if trade.aggressor_convention != identity.source.aggressor_convention:
        raise WrongSourceError(
            "Trade aggressor convention does not match the evidence source identity."
        )


def trade_set_content_hash(trades: list[TradeEvent]) -> str:
    """Bind proof contents to ordered natural identities and semantic event hashes."""
    return semantic_content_hash(
        {
            "events": [
                {
                    "venue_trade_id": trade.venue_trade_id,
                    "sequence": trade.sequence,
                    "content_hash": trade.content_hash,
                }
                for trade in trades
            ]
        }
    )


def _require_contiguous_trade_sequences(trades: list[TradeEvent]) -> None:
    if not trades:
        return
    previous = trades[0].sequence
    for trade in trades[1:]:
        if trade.sequence != previous + 1:
            raise GapDetectedError(f"Confirmed sequence gap {previous + 1}-{trade.sequence - 1}.")
        previous = trade.sequence


def build_trade_window_coverage_proof(
    *,
    identity: EvidenceMarketIdentity,
    lineage_id: UUID,
    requested_start: datetime,
    requested_end: datetime,
    actual_covered_start: datetime | None,
    actual_covered_end: datetime | None,
    gap_state: GapState,
    completeness: DataCompleteness,
    trades: list[TradeEvent],
) -> TradeWindowCoverageProof:
    """Create a content-bound proof at a retrieval or assembly boundary."""
    requested_start_utc = requested_start.astimezone(UTC)
    requested_end_utc = requested_end.astimezone(UTC)
    actual_start_utc = (
        actual_covered_start.astimezone(UTC) if actual_covered_start is not None else None
    )
    actual_end_utc = actual_covered_end.astimezone(UTC) if actual_covered_end is not None else None
    ordered = sorted(
        trades,
        key=lambda trade: (trade.sequence, trade.event_timestamp, trade.venue_trade_id),
    )
    for trade in ordered:
        require_trade_matches_identity(trade, identity)
        if trade.source_connection_id != lineage_id:
            raise WrongSourceError("Trade lineage does not match the coverage proof lineage.")
        if not requested_start_utc <= trade.event_timestamp < requested_end_utc:
            raise IncompleteTradeWindowError(
                "Trade event falls outside the coverage proof requested window."
            )
    if completeness is DataCompleteness.COMPLETE:
        _require_contiguous_trade_sequences(ordered)
    first = ordered[0] if ordered else None
    last = ordered[-1] if ordered else None
    trade_hash = trade_set_content_hash(ordered)
    proof_name = ":".join(
        (
            identity.instrument.instrument_id,
            identity.source.provider_name,
            str(lineage_id),
            requested_start_utc.isoformat(),
            requested_end_utc.isoformat(),
            trade_hash,
        )
    )
    proof = TradeWindowCoverageProof(
        coverage_proof_id=uuid5(_COVERAGE_NAMESPACE, proof_name),
        identity=identity,
        lineage_id=lineage_id,
        requested_start=requested_start_utc,
        requested_end=requested_end_utc,
        actual_covered_start=actual_start_utc,
        actual_covered_end=actual_end_utc,
        gap_state=gap_state,
        completeness=completeness,
        first_trade_id=first.venue_trade_id if first is not None else None,
        last_trade_id=last.venue_trade_id if last is not None else None,
        first_sequence=first.sequence if first is not None else None,
        last_sequence=last.sequence if last is not None else None,
        trade_set_hash=trade_hash,
        policy_version=TRADE_WINDOW_COVERAGE_POLICY_VERSION,
        content_hash="0" * 64,
    )
    return with_content_hash(proof)


def build_complete_trade_window_coverage(
    *,
    identity: EvidenceMarketIdentity,
    lineage_id: UUID,
    requested_start: datetime,
    requested_end: datetime,
    trades: list[TradeEvent],
) -> TradeWindowCoverageProof:
    """Create exact complete coverage after a retrieval boundary drained every page."""
    return build_trade_window_coverage_proof(
        identity=identity,
        lineage_id=lineage_id,
        requested_start=requested_start,
        requested_end=requested_end,
        actual_covered_start=requested_start,
        actual_covered_end=requested_end,
        gap_state=GapState.NONE,
        completeness=DataCompleteness.COMPLETE,
        trades=trades,
    )


def build_partial_assembly_coverage(
    *,
    identity: EvidenceMarketIdentity,
    lineage_id: UUID,
    requested_start: datetime,
    requested_end: datetime,
    trades: list[TradeEvent],
    gap_state: GapState,
) -> TradeWindowCoverageProof:
    """Describe observed raw-stream bounds without claiming full requested coverage."""
    ordered = sorted(
        trades,
        key=lambda trade: (trade.sequence, trade.event_timestamp, trade.venue_trade_id),
    )
    actual_start = ordered[0].event_timestamp if ordered else None
    actual_end = (
        max(ordered[-1].event_timestamp + _MIN_EXCLUSIVE_INCREMENT, actual_start)
        if actual_start is not None
        else None
    )
    return build_trade_window_coverage_proof(
        identity=identity,
        lineage_id=lineage_id,
        requested_start=requested_start,
        requested_end=requested_end,
        actual_covered_start=actual_start,
        actual_covered_end=actual_end,
        gap_state=gap_state,
        completeness=DataCompleteness.PARTIAL,
        trades=ordered,
    )


def verify_trade_window_coverage(
    proof: TradeWindowCoverageProof,
    *,
    identity: EvidenceMarketIdentity,
    lineage_id: UUID,
    trades: list[TradeEvent],
) -> None:
    """Verify immutable proof hash, identities, lineage, and exact bound trade set."""
    if proof.identity != identity:
        raise WrongMarketError("Trade coverage identity does not exactly match snapshot identity.")
    if proof.lineage_id != lineage_id:
        raise WrongSourceError("Trade coverage lineage does not match snapshot lineage.")
    expected_hash = semantic_content_hash(proof, extra_exclude=CONTENT_HASH_EXCLUDE)
    if proof.content_hash != expected_hash:
        raise IncompleteTradeWindowError("Trade coverage proof content hash is invalid.")
    ordered = sorted(
        trades,
        key=lambda trade: (trade.sequence, trade.event_timestamp, trade.venue_trade_id),
    )
    for trade in ordered:
        require_trade_matches_identity(trade, identity)
        if trade.source_connection_id != lineage_id:
            raise WrongSourceError("Trade lineage does not match the coverage proof lineage.")
        if not proof.requested_start <= trade.event_timestamp < proof.requested_end:
            raise IncompleteTradeWindowError(
                "Snapshot trade falls outside the coverage proof requested window."
            )
    if proof.completeness is DataCompleteness.COMPLETE:
        _require_contiguous_trade_sequences(ordered)
    if proof.trade_set_hash != trade_set_content_hash(ordered):
        raise IncompleteTradeWindowError(
            "Trade coverage proof does not bind the snapshot trade set."
        )
    first = ordered[0] if ordered else None
    last = ordered[-1] if ordered else None
    expected_terminal = (
        first.venue_trade_id if first else None,
        last.venue_trade_id if last else None,
        first.sequence if first else None,
        last.sequence if last else None,
    )
    actual_terminal = (
        proof.first_trade_id,
        proof.last_trade_id,
        proof.first_sequence,
        proof.last_sequence,
    )
    if actual_terminal != expected_terminal:
        raise IncompleteTradeWindowError("Trade coverage terminal identities do not match trades.")


def require_complete_window_coverage(
    proof: TradeWindowCoverageProof,
    *,
    identity: EvidenceMarketIdentity,
    lineage_id: UUID,
    trades: list[TradeEvent],
    required_start: datetime,
    required_end: datetime,
) -> None:
    """Fail closed unless proof covers the complete required half-open window."""
    verify_trade_window_coverage(
        proof,
        identity=identity,
        lineage_id=lineage_id,
        trades=trades,
    )
    if proof.gap_state is not GapState.NONE:
        raise GapDetectedError("Trade coverage has an unresolved gap.")
    if proof.completeness is not DataCompleteness.COMPLETE:
        raise IncompleteTradeWindowError("Trade coverage proof is not complete.")
    required_start_utc = required_start.astimezone(UTC)
    required_end_utc = required_end.astimezone(UTC)
    actual_start = proof.actual_covered_start
    actual_end = proof.actual_covered_end
    if actual_start is None or actual_end is None:
        raise IncompleteTradeWindowError("Trade coverage proof has no actual covered bounds.")
    if proof.requested_start > required_start_utc or actual_start > required_start_utc:
        raise IncompleteTradeWindowError(
            "Trade snapshot starts after the required evidence window."
        )
    if proof.requested_end < required_end_utc or actual_end < required_end_utc:
        raise IncompleteTradeWindowError("Trade snapshot ends before the required evidence window.")
