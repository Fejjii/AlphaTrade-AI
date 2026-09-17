"""Immutable SetupAssessment contracts.

Setup truth answers only “is this setup present?” from public market observations
and the exact fusion/pattern policy. Account, risk, and venue-action state are
forbidden on this contract.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.signal_fusion.enums import AssessmentReasonCode, SetupAssessmentState
from app.signal_fusion.errors import IllegalAssessmentTransitionError
from app.signal_fusion.types import (
    SCHEMA_VERSION_1_0,
    ExecutableSetupRef,
    HalfOpenInterval,
    PolicyVersion,
    PresentationEvidenceRef,
    RuleResult,
    Sha256Hex,
    hashed_model,
)

ASSESSMENT_SCHEMA = "SetupAssessment/v1"

ALLOWED_ASSESSMENT_TRANSITIONS: dict[SetupAssessmentState, frozenset[SetupAssessmentState]] = {
    SetupAssessmentState.NO_SETUP: frozenset({SetupAssessmentState.WATCH}),
    SetupAssessmentState.WATCH: frozenset(
        {
            SetupAssessmentState.PARTIAL_MATCH,
            SetupAssessmentState.INVALIDATED,
            SetupAssessmentState.EXPIRED,
        }
    ),
    SetupAssessmentState.PARTIAL_MATCH: frozenset(
        {
            SetupAssessmentState.CONFIRMED_SETUP,
            SetupAssessmentState.INVALIDATED,
            SetupAssessmentState.EXPIRED,
        }
    ),
    SetupAssessmentState.CONFIRMED_SETUP: frozenset(
        {
            SetupAssessmentState.INVALIDATED,
            SetupAssessmentState.EXPIRED,
        }
    ),
    SetupAssessmentState.INVALIDATED: frozenset({SetupAssessmentState.NO_SETUP}),
    SetupAssessmentState.EXPIRED: frozenset({SetupAssessmentState.NO_SETUP}),
}

_ACCOUNT_RISK_FIELDS = frozenset(
    {
        "user_id",
        "account_id",
        "risk_snapshot_id",
        "venue_state_id",
        "eligibility_id",
    }
)


class SetupAssessmentTransition(CanonicalModel):
    """Append-only assessment transition with immutable evidence references."""

    previous_assessment_id: UUID | None
    previous_state: SetupAssessmentState | None
    previous_evidence_window_hash: Sha256Hex | None = None
    new_state: SetupAssessmentState
    evidence_window_hash: Sha256Hex
    evidence_observation_hashes: tuple[Sha256Hex, ...]
    rule_results: tuple[RuleResult, ...]
    weights: tuple[CanonicalDecimal, ...] = ()
    threshold: CanonicalDecimal
    reason_codes: tuple[AssessmentReasonCode, ...]
    assessed_at: AwareDatetime
    valid_until: AwareDatetime
    correlation_id: UUID
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _architecture_transition(self) -> SetupAssessmentTransition:
        previous = (
            SetupAssessmentState.NO_SETUP if self.previous_state is None else self.previous_state
        )
        if self.previous_state is None and self.new_state is SetupAssessmentState.NO_SETUP:
            return self
        allowed = ALLOWED_ASSESSMENT_TRANSITIONS[previous]
        if self.new_state not in allowed:
            raise IllegalAssessmentTransitionError(
                f"Illegal setup assessment transition {previous.value} -> {self.new_state.value}."
            )
        restarting = (
            previous
            in {
                SetupAssessmentState.INVALIDATED,
                SetupAssessmentState.EXPIRED,
            }
            and self.new_state is SetupAssessmentState.NO_SETUP
        )
        same_window = (
            self.previous_evidence_window_hash is None
            or self.previous_evidence_window_hash == self.evidence_window_hash
        )
        if restarting and same_window:
            raise IllegalAssessmentTransitionError(
                "INVALIDATED/EXPIRED -> NO_SETUP requires a distinct evidence window."
            )
        if self.valid_until <= self.assessed_at:
            raise ValueError("valid_until must be after assessed_at.")
        return self


class SetupAssessment(CanonicalModel):
    """Organization-owned immutable setup-truth record."""

    schema_version: str = ASSESSMENT_SCHEMA
    assessment_id: UUID
    organization_id: UUID
    strategy_version_id: UUID
    executable_setup: ExecutableSetupRef
    fusion_policy_version: PolicyVersion
    observation_ids: tuple[UUID, ...]
    assessment_window: HalfOpenInterval
    state: SetupAssessmentState
    previous_assessment_id: UUID | None = None
    previous_state: SetupAssessmentState | None = None
    rule_results: tuple[RuleResult, ...]
    threshold: CanonicalDecimal
    reason_codes: tuple[AssessmentReasonCode, ...]
    explanation: str = Field(min_length=1, max_length=500)
    evidence_window_hash: Sha256Hex
    assessed_at: AwareDatetime
    valid_until: AwareDatetime
    correlation_id: UUID
    presentation_evidence: tuple[PresentationEvidenceRef, ...] = ()
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _validity_order(self) -> SetupAssessment:
        if self.valid_until <= self.assessed_at:
            raise ValueError("valid_until must be after assessed_at.")
        leaked = set(type(self).model_fields) & _ACCOUNT_RISK_FIELDS
        if leaked:
            raise ValueError("SetupAssessment must not carry account/risk fields.")
        return self

    @property
    def setup_definition_id(self) -> UUID:
        return self.executable_setup.setup_definition_id


def build_setup_assessment_transition(**kwargs: object) -> SetupAssessmentTransition:
    draft = SetupAssessmentTransition.model_validate({**kwargs, "content_hash": "0" * 64})
    return hashed_model(draft)


def build_setup_assessment(**kwargs: object) -> SetupAssessment:
    payload = {**kwargs, "schema_version": ASSESSMENT_SCHEMA, "content_hash": "0" * 64}
    draft = SetupAssessment.model_validate(payload)
    return hashed_model(draft)


__all__ = [
    "ALLOWED_ASSESSMENT_TRANSITIONS",
    "ASSESSMENT_SCHEMA",
    "SCHEMA_VERSION_1_0",
    "SetupAssessment",
    "SetupAssessmentTransition",
    "build_setup_assessment",
    "build_setup_assessment_transition",
]
