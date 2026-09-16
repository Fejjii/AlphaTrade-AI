"""Append-only execution transitions and rebuildable projections."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.db.models import ExecutionProjection, ExecutionReceipt, ExecutionTransition
from app.repositories.execution_protocol import (
    ExecutionProjectionRepository,
    ExecutionTransitionRepository,
)
from app.schemas.execution_protocol import (
    EXECUTION_POLICY_PROTOCOL_VERSION,
    ExecutionReceiptState,
    ExecutionReconciliationStatus,
)
from app.services.canonical_serialization import canonical_sha256
from app.services.execution_fills import cumulative_weighted_price


def append_transition(
    session: Session,
    *,
    receipt: ExecutionReceipt,
    prior_state: ExecutionReceiptState | None,
    new_state: ExecutionReceiptState,
    source_fact: str,
    source_identity: str,
    occurred_at: datetime,
    observed_at: datetime,
    recorded_at: datetime,
    actor: str,
    quantity: Decimal | None = None,
    quantity_unit: str | None = None,
    unit_price: Decimal | None = None,
    policy_version: str = EXECUTION_POLICY_PROTOCOL_VERSION,
) -> ExecutionTransition:
    transitions = ExecutionTransitionRepository(session)
    sequence = transitions.next_sequence(receipt.id)
    preimage = {
        "receipt_id": str(receipt.id),
        "sequence": sequence,
        "prior_state": prior_state.value if prior_state is not None else None,
        "new_state": new_state.value,
        "source_fact": source_fact,
        "source_identity": source_identity,
        "quantity": str(quantity) if quantity is not None else None,
        "quantity_unit": quantity_unit,
        "unit_price": str(unit_price) if unit_price is not None else None,
        "occurred_at": occurred_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "actor": actor,
        "policy_version": policy_version,
    }
    row = ExecutionTransition(
        receipt_id=receipt.id,
        sequence=sequence,
        prior_state=prior_state.value if prior_state is not None else None,
        new_state=new_state,
        source_fact=source_fact,
        source_identity=source_identity,
        quantity=quantity,
        quantity_unit=quantity_unit,
        unit_price=unit_price,
        occurred_at=occurred_at,
        observed_at=observed_at,
        recorded_at=recorded_at,
        actor=actor,
        policy_version=policy_version,
        content_hash=canonical_sha256(preimage),
    )
    transitions.add(row)
    return row


def apply_projection_transition(
    session: Session,
    *,
    projection: ExecutionProjection,
    transition: ExecutionTransition,
    filled_quantity: Decimal | None = None,
    remaining_quantity: Decimal | None = None,
    weighted_price: Decimal | None = None,
    fees: Decimal | None = None,
    funding: Decimal | None = None,
    position_id: uuid.UUID | None = None,
    reconciliation_status: ExecutionReconciliationStatus | None = None,
    updated_at: datetime,
) -> ExecutionProjection:
    repo = ExecutionProjectionRepository(session)
    values: dict[str, Any] = {
        "version": int(projection.version) + 1,
        "state": transition.new_state,
        "event_watermark": transition.sequence,
        "updated_at": updated_at,
    }
    if filled_quantity is not None:
        values["filled_quantity"] = filled_quantity
    if remaining_quantity is not None:
        values["remaining_quantity"] = remaining_quantity
    if weighted_price is not None:
        values["weighted_price"] = weighted_price
    if fees is not None:
        values["fees"] = fees
    if funding is not None:
        values["funding"] = funding
    if position_id is not None:
        values["position_id"] = position_id
    if reconciliation_status is not None:
        values["reconciliation_status"] = reconciliation_status
    updated = repo.compare_and_set_version(
        receipt_id=projection.receipt_id,
        expected_version=int(projection.version),
        values=values,
    )
    if not updated:
        raise ConflictError(
            "Execution projection version conflict.",
            details={
                "reason": "projection_version_conflict",
                "receipt_id": str(projection.receipt_id),
            },
        )
    session.refresh(projection)
    return projection


def rebuild_projection_from_transitions(
    receipt: ExecutionReceipt,
    transitions: list[ExecutionTransition],
    *,
    initial_remaining: Decimal,
    quantity_unit: str,
) -> dict[str, object]:
    """Pure rebuild used to prove projection is a function of the log."""

    filled = Decimal("0")
    remaining = initial_remaining
    state: ExecutionReceiptState | None = None
    watermark = 0
    weighted: Decimal | None = None
    for item in sorted(transitions, key=lambda row: row.sequence):
        state = item.new_state
        watermark = item.sequence
        if item.quantity is not None and item.source_fact == "unique_fill":
            if item.unit_price is not None:
                weighted = cumulative_weighted_price(
                    previous_filled=filled,
                    previous_weighted=weighted,
                    fill_quantity=item.quantity,
                    fill_price=item.unit_price,
                )
            filled += item.quantity
            remaining = remaining - item.quantity
            if remaining < 0:
                remaining = Decimal("0")
    if state is None:
        raise ValueError("Cannot rebuild a projection without transitions.")
    recon = ExecutionReconciliationStatus.NOT_REQUIRED
    if state in {
        ExecutionReceiptState.RECONCILIATION_REQUIRED,
        ExecutionReceiptState.ABSENCE_PENDING,
        ExecutionReceiptState.ABSENCE_PROVEN,
        ExecutionReceiptState.RESUBMIT_AUTHORIZED,
        ExecutionReceiptState.OPERATOR_HOLD,
    }:
        recon = ExecutionReconciliationStatus.REQUIRED
        if state is ExecutionReceiptState.OPERATOR_HOLD:
            recon = ExecutionReconciliationStatus.OPERATOR_HOLD
    return {
        "receipt_id": receipt.id,
        "state": state,
        "filled_quantity": filled,
        "remaining_quantity": remaining,
        "quantity_unit": quantity_unit,
        "weighted_price": weighted,
        "event_watermark": watermark,
        "reconciliation_status": recon,
    }
