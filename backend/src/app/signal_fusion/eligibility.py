"""ActionEligibility contract.

Separate from SetupAssessment. This freeze binds identity and state only;
it does not evaluate account risk, kill switch, or venue decisions.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.models import CanonicalModel
from app.signal_fusion.enums import ActionEligibilityState, EligibilityReasonCode
from app.signal_fusion.types import SCHEMA_VERSION_1_0, Sha256Hex, hashed_model

ELIGIBILITY_SCHEMA = "ActionEligibility/v1"


class ActionEligibility(CanonicalModel):
    """Organization + user + account permission to act on a candidate revision."""

    schema_version: str = ELIGIBILITY_SCHEMA
    eligibility_id: UUID
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    candidate_id: UUID
    candidate_revision: int = Field(ge=1)
    assessment_id: UUID
    risk_snapshot_id: UUID
    venue_state_id: UUID
    state: ActionEligibilityState
    reason_codes: tuple[EligibilityReasonCode, ...]
    checked_at: AwareDatetime
    valid_until: AwareDatetime
    correlation_id: UUID
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _validity_order(self) -> ActionEligibility:
        if self.valid_until <= self.checked_at:
            raise ValueError("valid_until must be after checked_at.")
        return self


def build_action_eligibility(**kwargs: object) -> ActionEligibility:
    payload = {**kwargs, "schema_version": ELIGIBILITY_SCHEMA, "content_hash": "0" * 64}
    draft = ActionEligibility.model_validate(payload)
    return hashed_model(draft)


__all__ = [
    "ELIGIBILITY_SCHEMA",
    "SCHEMA_VERSION_1_0",
    "ActionEligibility",
    "build_action_eligibility",
]
