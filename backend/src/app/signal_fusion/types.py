"""Shared frozen types for Phase 6 contracts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.enums import Finality, MarketType, SourceFamily, VenueId
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.market_contracts.observation import PublicMarketObservation
from app.schemas.common import Timeframe
from app.signal_fusion.enums import EvidenceRole, SetupIdentityKind, TenantAssertionRole
from app.signal_fusion.errors import (
    EvidenceIdentityMismatchError,
    FormingObservationNotExecutableError,
    IllegalSetupIdentityError,
)

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
PolicyVersion = Annotated[str, Field(min_length=3, max_length=120)]
SCHEMA_VERSION_1_0: Literal["1.0"] = "1.0"


class HalfOpenInterval(CanonicalModel):
    """Half-open event-time interval ``[start, end)``."""

    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def _ordered_bounds(self) -> HalfOpenInterval:
        if self.end <= self.start:
            raise ValueError("Half-open interval end must be after start.")
        return self


class ExecutableSetupRef(CanonicalModel):
    """Tenant-owned CompiledSetupDefinition. Legacy global templates are illegal here."""

    setup_definition_id: UUID
    kind: SetupIdentityKind
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _compiled_only(self) -> ExecutableSetupRef:
        if self.kind is not SetupIdentityKind.COMPILED_SETUP_DEFINITION:
            raise IllegalSetupIdentityError(
                "setup_definition_id must reference a tenant-owned "
                "CompiledSetupDefinition; GlobalSetupTemplate is compatibility-only."
            )
        return self


class TriggerIdentity(CanonicalModel):
    """Natural trigger identity and selected revision."""

    natural_event_id: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=1)


class ManualLevelRevisionRef(CanonicalModel):
    """Immutable manual-level revision included in the evidence window."""

    level_id: UUID
    revision_number: int = Field(ge=1)
    content_hash: Sha256Hex


class TenantAssertionRef(CanonicalModel):
    """Tenant assertion identity hashed into CanonicalEvidenceWindowV1 when required."""

    assertion_id: UUID
    content_hash: Sha256Hex


class SelectedTenantAssertion(CanonicalModel):
    """Role-bound tenant assertion selected by FusionPolicy for identity hashing.

    ``TenantAssertionRole.PRESENTATION`` is legal on the transport/command
    boundary and is never written into CanonicalEvidenceWindowV1.
    """

    role: TenantAssertionRole
    assertion_id: UUID
    content_hash: Sha256Hex


class RoleTimeframeBinding(CanonicalModel):
    """Policy-aware timeframe required for one evidence role.

    Trigger and context evidence may legally use different timeframes.
    """

    role: EvidenceRole
    timeframe: Timeframe


class SelectedPublicObservation(CanonicalModel):
    """Selected public observation occupying a mandatory or optional evidence role."""

    role: EvidenceRole
    content_hash: Sha256Hex
    finality: Finality
    venue: VenueId
    market_type: MarketType
    instrument_id: str = Field(min_length=8, max_length=80)
    timeframe: Timeframe | None = None
    observation_id: UUID | None = None

    @model_validator(mode="after")
    def _executable_finality(self) -> SelectedPublicObservation:
        if self.finality is not Finality.FINAL:
            raise FormingObservationNotExecutableError(
                f"Role {self.role.value} cannot select a {self.finality.value} observation."
            )
        return self


class PresentationEvidenceRef(CanonicalModel):
    """Optional presentation-only evidence. Excluded from CanonicalEvidenceWindowV1."""

    label: str = Field(min_length=1, max_length=80)
    content_hash: Sha256Hex
    note: str | None = Field(default=None, max_length=300)


class SemanticSourceIdentity(CanonicalModel):
    """Semantic public source identity. Adapter names are not part of this set."""

    venue: VenueId
    market_type: MarketType
    source_family: SourceFamily


class RuleWeight(CanonicalModel):
    rule_id: str = Field(min_length=1, max_length=80)
    weight: CanonicalDecimal


class RuleResult(CanonicalModel):
    """Per-rule deterministic result. Weights cannot be altered by account state."""

    rule_id: str = Field(min_length=1, max_length=80)
    passed: bool
    weight: CanonicalDecimal
    reason_code: str | None = Field(default=None, max_length=80)
    evidence_role: EvidenceRole | None = None


def selected_observation_from_public(
    observation: PublicMarketObservation,
    *,
    role: EvidenceRole,
) -> SelectedPublicObservation:
    """Bind a Phase 5 public observation into a fusion evidence role."""
    identity = observation.identity
    return SelectedPublicObservation(
        role=role,
        content_hash=observation.content_hash,
        finality=observation.finality,
        venue=identity.venue,
        market_type=identity.market_type,
        instrument_id=identity.instrument.instrument_id,
        timeframe=identity.timeframe,
        observation_id=observation.observation_id,
    )


def timeframe_bindings_by_role(
    bindings: Sequence[RoleTimeframeBinding],
) -> dict[EvidenceRole, Timeframe]:
    """Index role-timeframe bindings. Identical duplicates collapse; conflicts fail."""
    mapping: dict[EvidenceRole, Timeframe] = {}
    for binding in bindings:
        previous = mapping.get(binding.role)
        if previous is not None and previous is not binding.timeframe:
            raise EvidenceIdentityMismatchError(
                f"Conflicting timeframe binding for role {binding.role.value}."
            )
        mapping[binding.role] = binding.timeframe
    return mapping


def require_observation_matches_evidence(
    observation: PublicMarketObservation | SelectedPublicObservation,
    *,
    evidence_identity: EvidenceMarketIdentity,
    role: EvidenceRole,
    role_timeframes: Sequence[RoleTimeframeBinding] = (),
) -> None:
    """Fail closed when a selected observation is not the authoritative market.

    Venue, market type, and instrument must always match. Timeframe is checked
    only when the policy binds that role, so trigger and context may differ.
    """
    if isinstance(observation, PublicMarketObservation):
        venue = observation.identity.venue
        market_type = observation.identity.market_type
        instrument_id = observation.identity.instrument.instrument_id
        timeframe = observation.identity.timeframe
    else:
        venue = observation.venue
        market_type = observation.market_type
        instrument_id = observation.instrument_id
        timeframe = observation.timeframe
    if venue is not evidence_identity.venue:
        raise EvidenceIdentityMismatchError(
            f"wrong venue: selected {venue.value}, evidence {evidence_identity.venue.value}."
        )
    if market_type is not evidence_identity.market_type:
        raise EvidenceIdentityMismatchError(
            f"wrong market: selected {market_type.value}, "
            f"evidence {evidence_identity.market_type.value}."
        )
    expected_instrument = evidence_identity.instrument.instrument_id
    if instrument_id != expected_instrument:
        raise EvidenceIdentityMismatchError(
            f"wrong instrument: selected {instrument_id}, evidence {expected_instrument}."
        )
    expected_timeframe = timeframe_bindings_by_role(role_timeframes).get(role)
    if expected_timeframe is not None and timeframe is not expected_timeframe:
        selected = "none" if timeframe is None else timeframe.value
        raise EvidenceIdentityMismatchError(
            f"wrong timeframe for role {role.value}: selected {selected}, "
            f"policy {expected_timeframe.value}."
        )


def hashed_model[T: CanonicalModel](value: T) -> T:
    """Fill ``content_hash`` from the semantic dump, excluding the hash field itself."""
    return with_content_hash(value)
