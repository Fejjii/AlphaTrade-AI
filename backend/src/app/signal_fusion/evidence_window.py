"""CanonicalEvidenceWindowV1: versioned deterministic serialization and hash.

The hash preimage is the architecture §26 semantic input set. Transport
metadata and presentation-only evidence are excluded. Equivalent watcher,
detector, or TradingView semantic evidence must hash identically.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.market_contracts.enums import MarketType, VenueId
from app.market_contracts.identity import HASH_ALGORITHM_VERSION, EvidenceMarketIdentity
from app.market_contracts.models import CanonicalModel
from app.schemas.common import Timeframe, TradeDirection
from app.services.canonical_serialization import canonical_sha256
from app.signal_fusion.enums import EvidenceRole, TenantAssertionRole
from app.signal_fusion.errors import (
    ConflictingSemanticInputError,
    EvidenceIdentityMismatchError,
    EvidenceWindowContractError,
    TenantAssertionSelectionError,
)
from app.signal_fusion.policy import DEFAULT_CORRECTION_SELECTION_POLICY
from app.signal_fusion.types import (
    HalfOpenInterval,
    ManualLevelRevisionRef,
    PresentationEvidenceRef,
    RoleTimeframeBinding,
    SelectedPublicObservation,
    SelectedTenantAssertion,
    SemanticSourceIdentity,
    Sha256Hex,
    TenantAssertionRef,
    TriggerIdentity,
    require_observation_matches_evidence,
)

EVIDENCE_WINDOW_SCHEMA_VERSION: Literal["CanonicalEvidenceWindowV1"] = "CanonicalEvidenceWindowV1"

# Transport / presentation inputs accepted by the builder and dropped from the preimage.
EVIDENCE_WINDOW_EXCLUDED_INPUTS = frozenset(
    {
        "receive_time",
        "recorded_at",
        "scan_id",
        "action_id",
        "correlation_id",
        "presentation_evidence",
        "adapter_kind",
    }
)


class CanonicalEvidenceWindowV1(CanonicalModel):
    """Frozen semantic evidence window. ``content_hash`` is CanonicalEvidenceWindowV1."""

    schema_version: Literal["CanonicalEvidenceWindowV1"] = EVIDENCE_WINDOW_SCHEMA_VERSION
    hash_algorithm_version: str = HASH_ALGORITHM_VERSION
    organization_id: UUID
    strategy_version_id: UUID
    compiled_setup_definition_id: UUID
    compiled_setup_content_hash: Sha256Hex
    fusion_policy_version: str = Field(min_length=3, max_length=120)
    finality_policy_version: str = Field(min_length=3, max_length=120)
    freshness_policy_version: str = Field(min_length=3, max_length=120)
    direction: TradeDirection
    evidence_venue: VenueId
    evidence_market: MarketType
    evidence_instrument: str = Field(min_length=8, max_length=80)
    timeframe: Timeframe
    interval: HalfOpenInterval
    trigger: TriggerIdentity
    mandatory_evidence_roles: tuple[EvidenceRole, ...]
    selected_public_observations: tuple[SelectedPublicObservation, ...]
    tenant_assertions: tuple[TenantAssertionRef, ...] = ()
    manual_level_revision: ManualLevelRevisionRef | None = None
    source_set: tuple[SemanticSourceIdentity, ...]
    correction_selection_policy: str = Field(min_length=3, max_length=120)
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _roles_covered(self) -> CanonicalEvidenceWindowV1:
        if len(self.mandatory_evidence_roles) != len(set(self.mandatory_evidence_roles)):
            raise ConflictingSemanticInputError("Duplicate mandatory evidence roles.")
        source_keys = [
            (item.venue, item.market_type, item.source_family) for item in self.source_set
        ]
        if len(source_keys) != len(set(source_keys)):
            raise ConflictingSemanticInputError("Duplicate source set members.")
        assertion_ids = [item.assertion_id for item in self.tenant_assertions]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ConflictingSemanticInputError("Duplicate tenant assertions.")
        observation_keys = [
            (item.role, item.content_hash) for item in self.selected_public_observations
        ]
        if len(observation_keys) != len(set(observation_keys)):
            raise ConflictingSemanticInputError("Duplicate selected public observations.")
        for item in self.selected_public_observations:
            if item.venue is not self.evidence_venue:
                raise EvidenceIdentityMismatchError(
                    "wrong venue: selected "
                    f"{item.venue.value}, evidence {self.evidence_venue.value}."
                )
            if item.market_type is not self.evidence_market:
                raise EvidenceIdentityMismatchError(
                    f"wrong market: selected {item.market_type.value}, "
                    f"evidence {self.evidence_market.value}."
                )
            if item.instrument_id != self.evidence_instrument:
                raise EvidenceIdentityMismatchError(
                    f"wrong instrument: selected {item.instrument_id}, "
                    f"evidence {self.evidence_instrument}."
                )
        selected_roles = {item.role for item in self.selected_public_observations}
        missing = [role for role in self.mandatory_evidence_roles if role not in selected_roles]
        if missing:
            raise EvidenceWindowContractError(
                "Mandatory evidence roles missing from selected observations: "
                + ", ".join(role.value for role in missing)
                + "."
            )
        return self


def _unique_sorted_roles(roles: Sequence[EvidenceRole]) -> tuple[EvidenceRole, ...]:
    return tuple(sorted(frozenset(roles), key=lambda role: role.value))


def _sorted_observations(
    items: Sequence[SelectedPublicObservation],
) -> tuple[SelectedPublicObservation, ...]:
    return tuple(sorted(items, key=lambda item: (item.role.value, item.content_hash)))


def _canonical_observations(
    items: Sequence[SelectedPublicObservation],
) -> tuple[SelectedPublicObservation, ...]:
    """Collapse exact semantic duplicates; keep distinct hashes in one role."""
    unique: dict[tuple[EvidenceRole, str], SelectedPublicObservation] = {}
    by_observation_id: dict[tuple[EvidenceRole, UUID], str] = {}
    for item in items:
        if item.observation_id is not None:
            identity_key = (item.role, item.observation_id)
            previous_hash = by_observation_id.get(identity_key)
            if previous_hash is not None and previous_hash != item.content_hash:
                raise ConflictingSemanticInputError(
                    "Conflicting selected observation content for the same "
                    f"role {item.role.value} and observation_id."
                )
            by_observation_id[identity_key] = item.content_hash
        unique[(item.role, item.content_hash)] = item
    return _sorted_observations(tuple(unique.values()))


def _sorted_assertions(
    items: Sequence[TenantAssertionRef],
) -> tuple[TenantAssertionRef, ...]:
    return tuple(sorted(items, key=lambda item: (str(item.assertion_id), item.content_hash)))


def _canonical_assertion_refs(
    items: Sequence[TenantAssertionRef],
) -> tuple[TenantAssertionRef, ...]:
    unique: dict[UUID, TenantAssertionRef] = {}
    for item in items:
        previous = unique.get(item.assertion_id)
        if previous is not None and previous.content_hash != item.content_hash:
            raise ConflictingSemanticInputError(
                "Conflicting tenant assertion content for the same assertion_id."
            )
        unique[item.assertion_id] = item
    return _sorted_assertions(tuple(unique.values()))


def _sorted_sources(
    items: Sequence[SemanticSourceIdentity],
) -> tuple[SemanticSourceIdentity, ...]:
    return tuple(
        sorted(
            items,
            key=lambda item: (item.venue.value, item.market_type.value, item.source_family.value),
        )
    )


def _canonical_sources(
    items: Sequence[SemanticSourceIdentity],
) -> tuple[SemanticSourceIdentity, ...]:
    unique: dict[tuple[VenueId, MarketType, str], SemanticSourceIdentity] = {}
    for item in items:
        unique[(item.venue, item.market_type, item.source_family.value)] = item
    return _sorted_sources(tuple(unique.values()))


def select_identity_forming_tenant_assertions(
    items: Sequence[SelectedTenantAssertion],
    *,
    required_roles: Sequence[TenantAssertionRole] = (),
    identity_roles: Sequence[TenantAssertionRole] = (),
) -> tuple[TenantAssertionRef, ...]:
    """Keep only policy-required or explicitly selected identity-forming assertions.

    Presentation and unselected roles are dropped and cannot fork candidate identity.
    Missing required roles fail closed. Exact duplicate assertion IDs collapse;
    conflicting hashes for the same ID are rejected.
    """
    if TenantAssertionRole.PRESENTATION in required_roles:
        raise TenantAssertionSelectionError(
            "PRESENTATION assertions cannot be required for identity."
        )
    if TenantAssertionRole.PRESENTATION in identity_roles:
        raise TenantAssertionSelectionError("PRESENTATION assertions cannot be identity-forming.")
    allowed = tuple(dict.fromkeys(identity_roles or required_roles))
    kept: list[SelectedTenantAssertion] = []
    for item in items:
        if item.role is TenantAssertionRole.PRESENTATION:
            continue
        if item.role not in allowed:
            continue
        kept.append(item)
    present_roles = {item.role for item in kept}
    missing = [role for role in dict.fromkeys(required_roles) if role not in present_roles]
    if missing:
        raise TenantAssertionSelectionError(
            "Required tenant assertion roles missing: "
            + ", ".join(role.value for role in missing)
            + "."
        )
    return _canonical_assertion_refs(
        tuple(
            TenantAssertionRef(assertion_id=item.assertion_id, content_hash=item.content_hash)
            for item in kept
        )
    )


def evidence_window_preimage(window: CanonicalEvidenceWindowV1) -> dict[str, Any]:
    """Architecture §26 semantic preimage. Keys are stable; lists are ordered."""
    manual = window.manual_level_revision
    return {
        "compiled_setup_content_hash": window.compiled_setup_content_hash,
        "compiled_setup_definition_id": window.compiled_setup_definition_id,
        "correction_selection_policy": window.correction_selection_policy,
        "direction": window.direction,
        "evidence_instrument": window.evidence_instrument,
        "evidence_market": window.evidence_market,
        "evidence_venue": window.evidence_venue,
        "finality_policy_version": window.finality_policy_version,
        "freshness_policy_version": window.freshness_policy_version,
        "fusion_policy_version": window.fusion_policy_version,
        "hash_algorithm_version": window.hash_algorithm_version,
        "interval_end": window.interval.end,
        "interval_start": window.interval.start,
        "manual_level_revision": (
            None
            if manual is None
            else {
                "content_hash": manual.content_hash,
                "level_id": manual.level_id,
                "revision_number": manual.revision_number,
            }
        ),
        "mandatory_evidence_roles": [role.value for role in window.mandatory_evidence_roles],
        "organization_id": window.organization_id,
        "schema_version": window.schema_version,
        "selected_public_observation_content_hashes": [
            {"content_hash": item.content_hash, "role": item.role.value}
            for item in window.selected_public_observations
        ],
        "source_set": [
            {
                "market_type": item.market_type.value,
                "source_family": item.source_family.value,
                "venue": item.venue.value,
            }
            for item in window.source_set
        ],
        "strategy_version_id": window.strategy_version_id,
        "tenant_assertions": [
            {"assertion_id": item.assertion_id, "content_hash": item.content_hash}
            for item in window.tenant_assertions
        ],
        "timeframe": window.timeframe,
        "trigger_natural_event_id": window.trigger.natural_event_id,
        "trigger_revision": window.trigger.revision,
    }


def hash_canonical_evidence_window(window: CanonicalEvidenceWindowV1) -> str:
    """SHA-256 over the §26 preimage with canonical Decimal/datetime serialization."""
    return canonical_sha256(evidence_window_preimage(window))


def build_canonical_evidence_window_v1(
    *,
    organization_id: UUID,
    strategy_version_id: UUID,
    compiled_setup_definition_id: UUID,
    compiled_setup_content_hash: str,
    fusion_policy_version: str,
    finality_policy_version: str,
    freshness_policy_version: str,
    direction: TradeDirection,
    evidence_identity: EvidenceMarketIdentity,
    interval: HalfOpenInterval,
    trigger: TriggerIdentity,
    mandatory_evidence_roles: Sequence[EvidenceRole],
    selected_public_observations: Sequence[SelectedPublicObservation],
    source_set: Sequence[SemanticSourceIdentity],
    tenant_assertions: Sequence[SelectedTenantAssertion] = (),
    required_assertion_roles: Sequence[TenantAssertionRole] = (),
    identity_assertion_roles: Sequence[TenantAssertionRole] = (),
    role_timeframes: Sequence[RoleTimeframeBinding] = (),
    manual_level_revision: ManualLevelRevisionRef | None = None,
    correction_selection_policy: str = DEFAULT_CORRECTION_SELECTION_POLICY,
    # Excluded from the hash preimage. Accepted so callers cannot accidentally
    # fork identity by passing transport/presentation fields.
    receive_time: datetime | None = None,
    recorded_at: datetime | None = None,
    scan_id: UUID | None = None,
    action_id: UUID | None = None,
    correlation_id: UUID | None = None,
    presentation_evidence: Sequence[PresentationEvidenceRef] = (),
    adapter_kind: str | None = None,
) -> CanonicalEvidenceWindowV1:
    """Build a normalized, hashed CanonicalEvidenceWindowV1.

    ``evidence_identity.timeframe`` must match ``timeframe`` when present.
    Selected observation *content hashes* enter the preimage; observation IDs,
    receive/record times, scan/action/correlation IDs, adapter kind, and
    presentation evidence do not. Tenant assertions enter only when required or
    explicitly selected by semantic policy. Duplicate set members are
    canonicalized; conflicting duplicates fail closed.
    """
    del receive_time, recorded_at, scan_id, action_id, correlation_id
    del presentation_evidence, adapter_kind

    if evidence_identity.timeframe is None:
        raise EvidenceWindowContractError("Evidence identity must carry a timeframe.")
    timeframe = evidence_identity.timeframe
    bindings = tuple(role_timeframes)
    for item in selected_public_observations:
        require_observation_matches_evidence(
            item,
            evidence_identity=evidence_identity,
            role=item.role,
            role_timeframes=bindings,
        )
    normalized_roles = _unique_sorted_roles(mandatory_evidence_roles)
    normalized_selected = _canonical_observations(selected_public_observations)
    normalized_assertions = select_identity_forming_tenant_assertions(
        tenant_assertions,
        required_roles=required_assertion_roles,
        identity_roles=identity_assertion_roles,
    )
    normalized_sources = _canonical_sources(source_set)

    draft = CanonicalEvidenceWindowV1(
        schema_version=EVIDENCE_WINDOW_SCHEMA_VERSION,
        hash_algorithm_version=HASH_ALGORITHM_VERSION,
        organization_id=organization_id,
        strategy_version_id=strategy_version_id,
        compiled_setup_definition_id=compiled_setup_definition_id,
        compiled_setup_content_hash=compiled_setup_content_hash,
        fusion_policy_version=fusion_policy_version,
        finality_policy_version=finality_policy_version,
        freshness_policy_version=freshness_policy_version,
        direction=direction,
        evidence_venue=evidence_identity.venue,
        evidence_market=evidence_identity.market_type,
        evidence_instrument=evidence_identity.instrument.instrument_id,
        timeframe=timeframe,
        interval=interval,
        trigger=trigger,
        mandatory_evidence_roles=normalized_roles,
        selected_public_observations=normalized_selected,
        tenant_assertions=normalized_assertions,
        manual_level_revision=manual_level_revision,
        source_set=normalized_sources,
        correction_selection_policy=correction_selection_policy,
        content_hash="0" * 64,
    )
    digest = hash_canonical_evidence_window(draft)
    return draft.model_copy(update={"content_hash": digest})


def assert_excluded_from_preimage(preimage: Mapping[str, Any]) -> None:
    """Guard used by tests: excluded transport keys must not appear."""
    leaked = EVIDENCE_WINDOW_EXCLUDED_INPUTS.intersection(preimage)
    if leaked:
        raise EvidenceWindowContractError(
            "CanonicalEvidenceWindowV1 preimage leaked excluded keys: "
            + ", ".join(sorted(leaked))
            + "."
        )
