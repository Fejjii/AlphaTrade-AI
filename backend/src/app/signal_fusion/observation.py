"""Public-market observation boundary for Phase 6.

Reuses the Phase 5 ``PublicMarketObservation`` envelope. Tenant assertions,
TradingView proprietary alerts, and user assertions stay tenant-scoped and
never become global public observations. FORMING cannot mutate into FINAL.
"""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.market_contracts.enums import MarketType, PrivacyClass, VenueId
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.models import CanonicalModel
from app.market_contracts.observation import PublicMarketObservation
from app.signal_fusion.enums import AssertionPrivacyClass, AssertionSource
from app.signal_fusion.errors import (
    FormingObservationMutationError,
    TenantAssertionNotPublicError,
)
from app.signal_fusion.types import Sha256Hex

_PUBLIC_OBSERVATION_FORBIDDEN_FIELDS = frozenset(
    {
        "organization_id",
        "user_id",
        "account_id",
        "tenant_id",
        "assertion_id",
    }
)


class TenantExternalAssertion(CanonicalModel):
    """Organization-owned assertion. Privacy class TENANT_CONFIDENTIAL."""

    assertion_id: UUID
    organization_id: UUID
    user_id: UUID | None = None
    privacy_class: AssertionPrivacyClass = AssertionPrivacyClass.TENANT_CONFIDENTIAL
    source: AssertionSource
    source_event_id: str = Field(min_length=1, max_length=160)
    venue: VenueId
    market_type: MarketType
    instrument_id: str = Field(min_length=8, max_length=80)
    received_at: AwareDatetime
    expiry_at: AwareDatetime | None = None
    public_observation_ids: tuple[UUID, ...] = ()
    content_hash: Sha256Hex
    recorded_at: AwareDatetime


def build_tenant_external_assertion(
    *,
    assertion_id: UUID,
    organization_id: UUID,
    source: AssertionSource,
    source_event_id: str,
    venue: VenueId,
    market_type: MarketType,
    instrument_id: str,
    received_at: AwareDatetime,
    recorded_at: AwareDatetime,
    user_id: UUID | None = None,
    expiry_at: AwareDatetime | None = None,
    public_observation_ids: tuple[UUID, ...] = (),
) -> TenantExternalAssertion:
    """Construct a hashed tenant assertion. Receive/record times are excluded from the hash."""
    draft = TenantExternalAssertion(
        assertion_id=assertion_id,
        organization_id=organization_id,
        user_id=user_id,
        source=source,
        source_event_id=source_event_id,
        venue=venue,
        market_type=market_type,
        instrument_id=instrument_id,
        received_at=received_at,
        expiry_at=expiry_at,
        public_observation_ids=public_observation_ids,
        content_hash="0" * 64,
        recorded_at=recorded_at,
    )
    return with_content_hash(
        draft,
        extra_exclude=frozenset({"assertion_id", "received_at", "recorded_at"}),
    )


def assert_public_observation_boundary(
    observation: PublicMarketObservation,
) -> PublicMarketObservation:
    """Confirm the Phase 5 envelope remains public-only."""
    leaked = set(type(observation).model_fields) & _PUBLIC_OBSERVATION_FORBIDDEN_FIELDS
    if leaked:
        raise TenantAssertionNotPublicError(
            "PublicMarketObservation must not carry tenant identity fields: "
            + ", ".join(sorted(leaked))
            + "."
        )
    if observation.privacy_class is not PrivacyClass.PUBLIC_MARKET_DATA:
        raise TenantAssertionNotPublicError(
            "PublicMarketObservation privacy_class must remain public_market_data."
        )
    return observation


def refuse_tenant_assertion_as_public_observation(
    assertion: TenantExternalAssertion,
) -> NoReturn:
    """Tenant assertions never enter the global public observation envelope."""
    raise TenantAssertionNotPublicError(
        f"{assertion.source.value} assertion {assertion.assertion_id} cannot become "
        "a PublicMarketObservation."
    )


def require_distinct_observation_for_finality_change(
    previous: PublicMarketObservation,
    following: PublicMarketObservation,
) -> None:
    """FORMING never becomes executable FINAL by mutating the same observation_id."""
    if (
        previous.observation_id == following.observation_id
        and previous.finality is not following.finality
    ):
        raise FormingObservationMutationError(
            "FORMING observations cannot mutate into FINAL; append a new observation."
        )
