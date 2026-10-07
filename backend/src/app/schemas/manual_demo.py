"""Explicit owner confirmation of a hash-bound manual demo market order."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.trade_plan import CanonicalModel, EntrySide, PositiveCanonicalDecimal


class ManualDemoPreviewRequest(CanonicalModel):
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    side: EntrySide
    quantity: PositiveCanonicalDecimal  # Venue contracts, never base coins.
    stop: PositiveCanonicalDecimal
    target: PositiveCanonicalDecimal
    order_type: Literal["MARKET"] = "MARKET"

    @field_validator("quantity", "stop", "target", mode="before")
    @classmethod
    def _bounded_decimal(cls, value: object) -> object:
        if len(str(value)) > 64:
            raise ValueError("Manual demo decimal exceeds the input budget.")
        try:
            parsed = Decimal(str(value))
        except Exception as exc:
            raise ValueError("A finite base-10 decimal is required.") from exc
        if (
            not parsed.is_finite()
            or len(parsed.as_tuple().digits) > 24
            or abs(int(parsed.as_tuple().exponent)) > 18
        ):
            raise ValueError("Manual demo decimal exceeds the precision budget.")
        return value


class ManualDemoConfirmation(CanonicalModel):
    revision_id: UUID
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: Literal[True]
    label: Literal["manual demo test"]


class ManualDemoPreview(CanonicalModel):
    origin: Literal["manual demo test"] = "manual demo test"
    account_id: UUID
    revision_id: UUID
    content_hash: str
    instrument: str
    side: EntrySide
    order_type: Literal["MARKET"] = "MARKET"
    quantity: Decimal
    quantity_unit: Literal["CONTRACTS"] = "CONTRACTS"
    base_quantity: Decimal
    reference_price: Decimal
    limit_price: None = None
    entry_lower: Decimal
    entry_upper: Decimal
    stop: Decimal
    target: Decimal
    maximum_planned_loss: Decimal
    gross_reward_risk: Decimal
    valid_until: datetime
    warnings: tuple[str, ...] = (
        "Demo market entry; final fill price is unknown until venue reconciliation.",
        "Planned loss includes fee/slippage allowances; gaps may exceed it.",
        "Excluded from strategy validation. No strategy or execution flags are changed.",
    )


class ManualDemoStatus(CanonicalModel):
    origin: Literal["manual demo test"] = "manual demo test"
    revision_id: UUID
    command_id: UUID
    client_order_id: str
    venue_order_id: str | None = None
    protection_order_ids: tuple[str, ...] = ()
    status: str
    filled_quantity: Decimal
    remaining_quantity: Decimal
    average_fill_price: Decimal | None
    fees: Decimal | None
    protection: str
    journal_trade_id: UUID | None
    missing_evidence: tuple[str, ...]


class ManualDemoCancelRequest(CanonicalModel):
    confirm: Literal[True]
