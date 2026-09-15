"""Unique fill facts, cumulative weighted price, and reservation conversion."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.db.models import AccountRiskAccountingState, RiskReservation
from app.schemas.execution_protocol import RiskReservationReleaseReason, RiskReservationReleaseState
from app.services.canonical_serialization import canonical_sha256


def fill_content_hash(
    *,
    receipt_id: str,
    command_id: str,
    venue_source: str,
    source_fill_identity: str,
    quantity: Decimal,
    price: Decimal,
    unit: str,
    occurred_at: datetime,
) -> str:
    return canonical_sha256(
        {
            "receipt_id": receipt_id,
            "command_id": command_id,
            "venue_source": venue_source,
            "source_fill_identity": source_fill_identity,
            "quantity": str(quantity),
            "price": str(price),
            "unit": unit,
            "occurred_at": occurred_at.isoformat(),
        }
    )


def cumulative_weighted_price(
    *,
    previous_filled: Decimal,
    previous_weighted: Decimal | None,
    fill_quantity: Decimal,
    fill_price: Decimal,
) -> Decimal:
    if fill_quantity <= 0:
        raise ValueError("Fill quantity must be positive.")
    if previous_filled <= 0 or previous_weighted is None:
        return fill_price
    total = previous_filled + fill_quantity
    return (previous_filled * previous_weighted + fill_quantity * fill_price) / total


def adjust_symbol_map(
    mapping: dict[str, object] | None, instrument: str, delta: Decimal
) -> dict[str, str]:
    updated: dict[str, str] = {}
    for key, value in dict(mapping or {}).items():
        updated[str(key)] = str(value)
    current = Decimal(updated.get(instrument, "0"))
    next_value = current + delta
    if next_value < 0:
        next_value = Decimal("0")
    updated[instrument] = str(next_value)
    return updated


def convert_reservation_for_fill(
    *,
    reservation: RiskReservation,
    accounting: AccountRiskAccountingState,
    fill_quantity: Decimal,
    fill_price: Decimal,
    now: datetime,
) -> Decimal:
    """Convert reserved notional into actual exposure for one unique fill.

    Unused remainder stays charged. Daily-loss allocation stays reserved while
    the position remains open. Trade slots convert once per reservation.
    """

    fill_notional = fill_quantity * fill_price
    convert = min(fill_notional, reservation.remaining_reserved_notional)
    reservation.remaining_reserved_notional -= convert
    reservation.release_reason = RiskReservationReleaseReason.FILL_CONVERSION
    reservation.release_state = RiskReservationReleaseState.PARTIALLY_RELEASED
    reservation.updated_at = now

    accounting.reserved_notional -= convert
    if accounting.reserved_notional < 0:
        accounting.reserved_notional = Decimal("0")
    accounting.actual_notional += fill_notional
    accounting.symbol_reserved = adjust_symbol_map(
        accounting.symbol_reserved, reservation.instrument, -convert
    )
    accounting.symbol_actual = adjust_symbol_map(
        accounting.symbol_actual, reservation.instrument, fill_notional
    )

    unconverted_slots = int(reservation.daily_trade_allocation) - int(
        reservation.converted_trade_slots
    )
    if unconverted_slots > 0:
        accounting.reserved_trade_slots -= unconverted_slots
        if accounting.reserved_trade_slots < 0:
            accounting.reserved_trade_slots = 0
        accounting.actual_trade_count += unconverted_slots
        reservation.converted_trade_slots = int(reservation.daily_trade_allocation)

    accounting.version = int(accounting.version) + 1
    return convert
