"""Version-one semantic execution payload derived only from approved plan state."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.trade_plan import (
    AccountMode,
    CanonicalModel,
    EntryOrderType,
    EntrySide,
    ExecutionMode,
    MarginMode,
    PlanOperation,
    SemanticAmount,
    TimeInForce,
)


class CanonicalExecutionPrincipalV1(CanonicalModel):
    user_id: UUID
    account_id: UUID
    exchange_account_id: UUID | None


class CanonicalAccountBindingV1(CanonicalModel):
    account_id: UUID
    exchange_account_id: UUID | None
    execution_mode: Literal[ExecutionMode.PAPER] = ExecutionMode.PAPER
    expected_account_mode: Literal[AccountMode.NET] = AccountMode.NET
    margin_mode: MarginMode
    position_mode: Literal[AccountMode.NET] = AccountMode.NET


class CanonicalExecutionPayloadV1(CanonicalModel):
    """Exact V1 hash preimage; transport and retry metadata cannot be represented."""

    serializer_version: Literal["CanonicalExecutionPayloadV1"] = "CanonicalExecutionPayloadV1"
    organization_id: UUID
    principal: CanonicalExecutionPrincipalV1
    operation: Literal[PlanOperation.SUBMIT_ENTRY] = PlanOperation.SUBMIT_ENTRY
    plan_id: UUID
    immutable_plan_revision_id: UUID
    approval_authorization_id: UUID
    plan_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_venue: str
    execution_instrument: str
    side: EntrySide
    order_type: EntryOrderType
    time_in_force: TimeInForce
    quantity: SemanticAmount
    price: SemanticAmount | None
    market_marker: bool
    reduce_only: Literal[False] = False
    position_binding: None = None
    account_binding: CanonicalAccountBindingV1
    instrument_rule_version: str
    execution_policy_version: str


class CanonicalExecutionSerializationV1(CanonicalModel):
    payload: CanonicalExecutionPayloadV1
    canonical_bytes: bytes
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
