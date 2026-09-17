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
from app.signal_fusion.enums import EvidenceRole
from app.signal_fusion.errors import EvidenceWindowContractError
from app.signal_fusion.policy import DEFAULT_CORRECTION_SELECTION_POLICY
from app.signal_fusion.types import (
    HalfOpenInterval,
    ManualLevelRevisionRef,
    PresentationEvidenceRef,
    SelectedPublicObservation,
    SemanticSourceIdentity,
    Sha256Hex,
    TenantAssertionRef,
    TriggerIdentity,
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
        selected_roles = {item.role for item in self.selected_public_observations}
        missing = [role for role in self.mandatory_evidence_roles if role not in selected_roles]
        if missing:
            raise EvidenceWindowContractError(
                "Mandatory evidence roles missing from selected observations: "
                + ", ".join(role.value for role in missing)
                + "."
            )
        return self


def _sorted_roles(roles: Sequence[EvidenceRole]) -> tuple[EvidenceRole, ...]:
    return tuple(sorted(roles, key=lambda role: role.value))


def _sorted_observations(
    items: Sequence[SelectedPublicObservation],
) -> tuple[SelectedPublicObservation, ...]:
    return tuple(sorted(items, key=lambda item: (item.role.value, item.content_hash)))


def _sorted_assertions(
    items: Sequence[TenantAssertionRef],
) -> tuple[TenantAssertionRef, ...]:
    return tuple(sorted(items, key=lambda item: (str(item.assertion_id), item.content_hash)))


def _sorted_sources(
    items: Sequence[SemanticSourceIdentity],
) -> tuple[SemanticSourceIdentity, ...]:
    return tuple(
        sorted(
            items,
            key=lambda item: (item.venue.value, item.market_type.value, item.source_family.value),
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
    tenant_assertions: Sequence[TenantAssertionRef] = (),
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
    presentation evidence do not.
    """
    del receive_time, recorded_at, scan_id, action_id, correlation_id
    del presentation_evidence, adapter_kind

    if evidence_identity.timeframe is None:
        raise EvidenceWindowContractError("Evidence identity must carry a timeframe.")
    timeframe = evidence_identity.timeframe
    normalized_roles = _sorted_roles(mandatory_evidence_roles)
    normalized_selected = _sorted_observations(selected_public_observations)
    normalized_assertions = _sorted_assertions(tenant_assertions)
    normalized_sources = _sorted_sources(source_set)

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
