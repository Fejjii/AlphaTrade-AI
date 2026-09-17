"""Candidate identity, uniqueness tuple, and append-only transitions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.enums import MarketType, VenueId
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.models import CanonicalModel
from app.schemas.common import Timeframe, TradeDirection
from app.services.canonical_serialization import canonical_json_bytes, canonical_sha256
from app.signal_fusion.enums import CandidateReasonCode, CandidateState
from app.signal_fusion.errors import IllegalCandidateTransitionError
from app.signal_fusion.types import (
    SCHEMA_VERSION_1_0,
    ExecutableSetupRef,
    PolicyVersion,
    Sha256Hex,
    hashed_model,
)

CANDIDATE_SCHEMA = "Candidate/v1"
TERMINAL_CANDIDATE_STATES = frozenset(
    {
        CandidateState.REJECTED,
        CandidateState.SKIPPED,
        CandidateState.EXPIRED,
        CandidateState.INVALIDATED,
    }
)
DESCENDANT_CANDIDATE_STATES = frozenset({CandidateState.PLAN_CREATED}) | TERMINAL_CANDIDATE_STATES

ALLOWED_CANDIDATE_TRANSITIONS: dict[CandidateState, frozenset[CandidateState]] = {
    CandidateState.ACTIVE: frozenset(DESCENDANT_CANDIDATE_STATES),
    CandidateState.PLAN_CREATED: frozenset(TERMINAL_CANDIDATE_STATES),
}


class CandidateUniquenessTuple(CanonicalModel):
    """Canonical candidate uniqueness key from architecture §5 / §26."""

    organization_id: UUID
    strategy_version_id: UUID
    setup_definition_id: UUID
    fusion_policy_version: PolicyVersion
    direction: TradeDirection
    evidence_venue: VenueId
    evidence_market: MarketType
    evidence_instrument: str = Field(min_length=8, max_length=80)
    timeframe: Timeframe
    evidence_window_hash: Sha256Hex

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(uniqueness_preimage(self))

    def canonical_hash(self) -> str:
        return canonical_sha256(uniqueness_preimage(self))


def uniqueness_preimage(key: CandidateUniquenessTuple) -> dict[str, Any]:
    return {
        "direction": key.direction,
        "evidence_instrument": key.evidence_instrument,
        "evidence_market": key.evidence_market,
        "evidence_venue": key.evidence_venue,
        "evidence_window_hash": key.evidence_window_hash,
        "fusion_policy_version": key.fusion_policy_version,
        "organization_id": key.organization_id,
        "setup_definition_id": key.setup_definition_id,
        "strategy_version_id": key.strategy_version_id,
        "timeframe": key.timeframe,
    }


class CandidateTransition(CanonicalModel):
    """Append-only candidate transition. Terminal states cannot return to ACTIVE."""

    previous_state: CandidateState
    new_state: CandidateState
    transition_version: int = Field(ge=1)
    reason_codes: tuple[CandidateReasonCode, ...]
    occurred_at: AwareDatetime
    correlation_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=120)
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _architecture_transition(self) -> CandidateTransition:
        if self.previous_state in TERMINAL_CANDIDATE_STATES:
            raise IllegalCandidateTransitionError(
                f"Terminal candidate state {self.previous_state.value} cannot be resurrected "
                f"to {self.new_state.value}."
            )
        allowed = ALLOWED_CANDIDATE_TRANSITIONS.get(self.previous_state, frozenset())
        if self.new_state not in allowed:
            raise IllegalCandidateTransitionError(
                f"Illegal candidate transition {self.previous_state.value} -> "
                f"{self.new_state.value}."
            )
        if self.new_state is CandidateState.ACTIVE:
            raise IllegalCandidateTransitionError(
                "Candidate ACTIVE is the initial confirmed state and cannot be a resurrection."
            )
        return self


class Candidate(CanonicalModel):
    """Organization-owned confirmed-setup candidate. Initial state is ACTIVE."""

    schema_version: str = CANDIDATE_SCHEMA
    candidate_id: UUID
    organization_id: UUID
    strategy_version_id: UUID
    executable_setup: ExecutableSetupRef
    fusion_policy_version: PolicyVersion
    direction: TradeDirection
    assessment_id: UUID
    evidence_window_hash: Sha256Hex
    evidence_identity: EvidenceMarketIdentity
    evidence_venue: VenueId
    evidence_market: MarketType
    evidence_instrument: str = Field(min_length=8, max_length=80)
    timeframe: Timeframe
    state: CandidateState
    created_at: AwareDatetime
    valid_until: AwareDatetime
    transition_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=120)
    correlation_id: UUID
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _identity_matches_tuple(self) -> Candidate:
        identity = self.evidence_identity
        if identity.venue is not self.evidence_venue:
            raise ValueError("evidence_venue does not match evidence_identity.venue.")
        if identity.market_type is not self.evidence_market:
            raise ValueError("evidence_market does not match evidence_identity.market_type.")
        if identity.instrument.instrument_id != self.evidence_instrument:
            raise ValueError("evidence_instrument does not match evidence_identity.instrument.")
        if identity.timeframe is not None and identity.timeframe is not self.timeframe:
            raise ValueError("timeframe does not match evidence_identity.timeframe.")
        if self.valid_until <= self.created_at:
            raise ValueError("valid_until must be after created_at.")
        return self

    @property
    def setup_definition_id(self) -> UUID:
        return self.executable_setup.setup_definition_id

    def uniqueness_tuple(self) -> CandidateUniquenessTuple:
        return CandidateUniquenessTuple(
            organization_id=self.organization_id,
            strategy_version_id=self.strategy_version_id,
            setup_definition_id=self.setup_definition_id,
            fusion_policy_version=self.fusion_policy_version,
            direction=self.direction,
            evidence_venue=self.evidence_venue,
            evidence_market=self.evidence_market,
            evidence_instrument=self.evidence_instrument,
            timeframe=self.timeframe,
            evidence_window_hash=self.evidence_window_hash,
        )


def build_candidate_transition(**kwargs: object) -> CandidateTransition:
    draft = CandidateTransition.model_validate({**kwargs, "content_hash": "0" * 64})
    return hashed_model(draft)


def build_candidate(**kwargs: object) -> Candidate:
    payload = {**kwargs, "schema_version": CANDIDATE_SCHEMA, "content_hash": "0" * 64}
    draft = Candidate.model_validate(payload)
    return hashed_model(draft)


def build_confirmed_candidate(**kwargs: object) -> Candidate:
    """Initial confirmed candidate is always ACTIVE."""
    return build_candidate(**{**kwargs, "state": CandidateState.ACTIVE, "transition_version": 1})


__all__ = [
    "ALLOWED_CANDIDATE_TRANSITIONS",
    "CANDIDATE_SCHEMA",
    "DESCENDANT_CANDIDATE_STATES",
    "SCHEMA_VERSION_1_0",
    "TERMINAL_CANDIDATE_STATES",
    "Candidate",
    "CandidateTransition",
    "CandidateUniquenessTuple",
    "build_candidate",
    "build_candidate_transition",
    "build_confirmed_candidate",
    "uniqueness_preimage",
]
