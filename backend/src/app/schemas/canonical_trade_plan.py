"""Application-layer canonical TradePlanRevision identity.

Phase 1 ``TradePlanRevisionSemantic`` remains the hash-stable executable-order
preimage. This module adds the Candidate + ActionEligibility lineage envelope
without changing that semantic field set (existing persisted hashes stay valid).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.trade_plan import CanonicalModel, TradePlanRevision, TradePlanRevisionCreate
from app.signal_fusion.enums import ActionEligibilityState


class CanonicalTradePlanLineage(CanonicalModel):
    """Exact Candidate and ActionEligibility identity bound into a plan revision."""

    candidate_id: UUID
    candidate_revision: int = Field(ge=1)
    candidate_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    assessment_id: UUID
    eligibility_id: UUID
    eligibility_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligibility_uniqueness_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligibility_state: Literal[ActionEligibilityState.ELIGIBLE] = ActionEligibilityState.ELIGIBLE
    evidence_window_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy_version_id: UUID
    setup_definition_id: UUID
    compiled_setup_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    fusion_policy_version: str = Field(min_length=3, max_length=120)


class CanonicalTradePlanCommand(CanonicalModel):
    """Untrusted create boundary. Authority is loaded from Candidate and eligibility ports."""

    organization_id: UUID
    user_id: UUID
    account_id: UUID
    candidate_id: UUID
    eligibility_id: UUID
    terms: TradePlanRevisionCreate
    idempotency_key: str = Field(min_length=8, max_length=120)
    correlation_id: UUID


class CanonicalTradePlanRevision(CanonicalModel):
    """Immutable executable revision plus canonical lineage. Not an ORM row."""

    plan: TradePlanRevision
    lineage: CanonicalTradePlanLineage
    uniqueness_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    paper_actionable: Literal[True] = True
    live_executable: Literal[False] = False
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CanonicalTradePlanDatabaseRequirement(CanonicalModel):
    """One remaining PostgreSQL binding Agent 1 (or later integration) must own."""

    artifact: str = Field(min_length=3, max_length=200)
    current_state: str = Field(min_length=3, max_length=500)
    required_change: str = Field(min_length=3, max_length=800)
    owner: str = Field(default="Agent 1", min_length=3, max_length=80)


__all__ = [
    "CanonicalTradePlanCommand",
    "CanonicalTradePlanDatabaseRequirement",
    "CanonicalTradePlanLineage",
    "CanonicalTradePlanRevision",
]
