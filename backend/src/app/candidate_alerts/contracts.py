"""Immutable contracts for CandidateAlertIntent identity and structured alert data.

Authoritative facts come from canonical Phase 6 Candidate / SetupAssessment /
CanonicalEvidenceWindowV1. This module does not generate setup truth with an LLM
and does not claim profitability.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.market_contracts.enums import MarketType, VenueId
from app.market_contracts.models import CanonicalModel
from app.schemas.common import Timeframe, TradeDirection
from app.signal_fusion.enums import CandidateState, SetupAssessmentState
from app.signal_fusion.types import Sha256Hex
from app.telegram_security.actions import ActionEffectKind, TelegramRemoteAction
from app.telegram_security.contracts import ActionOutcome, AuthorizationIntent, OutboxRecord

CANDIDATE_ALERT_SCHEMA = "CandidateAlertIntent/v1"
CANDIDATE_RESOURCE_TYPE = "candidate"
CANDIDATE_ALERT_OUTBOX_PREFIX = "candidate-alert:"
MAX_ALERT_TEXT_BYTES_GUARD = 4096


class CandidateAlertKind(StrEnum):
    CANDIDATE_ACTIVE = "CANDIDATE_ACTIVE"


class DeliveryChannel(StrEnum):
    TELEGRAM = "TELEGRAM"


class TriggerContext(CanonicalModel):
    """Canonical trigger identity. Not a second market-identity system."""

    natural_event_id: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=1)
    timeframe: Timeframe
    interval_start: AwareDatetime
    interval_end: AwareDatetime


class InvalidationSummary(CanonicalModel):
    """Invalidation facts that already exist on canonical records. No invented price."""

    candidate_state: CandidateState
    assessment_state: SetupAssessmentState
    invalidated: bool
    bound_to_expiry: Literal[True] = True
    reason_codes: tuple[str, ...] = ()


class RuleResultSummary(CanonicalModel):
    """Deterministic rule outcome. Weights are omitted so alerts cannot imply scoring alpha."""

    rule_id: str = Field(min_length=1, max_length=80)
    passed: bool
    reason_code: str | None = Field(default=None, max_length=80)


class EvidenceFreshnessSummary(CanonicalModel):
    freshness_policy_version: str = Field(min_length=3, max_length=120)
    finality_policy_version: str = Field(min_length=3, max_length=120)
    all_selected_observations_final: bool
    freshness_rule_passed: bool | None = None


class EvidenceProvenanceSummary(CanonicalModel):
    venue: VenueId
    market_type: MarketType
    instrument: str = Field(min_length=8, max_length=80)
    source_families: tuple[str, ...]
    selected_observation_hashes: tuple[Sha256Hex, ...]
    tenant_assertion_count: int = Field(ge=0)


class CandidateAlertContent(CanonicalModel):
    """Structured alert facts. Formatting may later use an LLM; these fields must not."""

    instrument: str = Field(min_length=8, max_length=80)
    direction: TradeDirection
    setup_name: str = Field(min_length=1, max_length=200)
    setup_state: SetupAssessmentState
    candidate_state: CandidateState
    trigger_context: TriggerContext
    invalidation: InvalidationSummary
    expiry: AwareDatetime
    rule_results: tuple[RuleResultSummary, ...]
    evidence_freshness: EvidenceFreshnessSummary
    evidence_provenance: EvidenceProvenanceSummary
    candidate_id: UUID
    candidate_revision: int = Field(ge=1)


class CandidateAlertRecipient(CanonicalModel):
    """Telegram delivery recipient. Account is required for nonce/account isolation."""

    organization_id: UUID
    user_id: UUID
    account_id: UUID
    binding_id: UUID
    bot_id: str = Field(min_length=1, max_length=64)
    chat_id: str = Field(min_length=1, max_length=64)


class CandidateAlertIntent(CanonicalModel):
    """Deterministic alert identity. Duplicate semantic Candidate events converge here."""

    schema_version: str = CANDIDATE_ALERT_SCHEMA
    intent_id: UUID
    identity_hash: Sha256Hex
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    candidate_id: UUID
    candidate_content_hash: Sha256Hex
    strategy_version_id: UUID
    compiled_setup_definition_id: UUID
    compiled_setup_content_hash: Sha256Hex
    fusion_policy_version: str = Field(min_length=3, max_length=120)
    evidence_window_hash: Sha256Hex
    candidate_lifecycle_revision: int = Field(ge=1)
    telegram_revision_id: UUID
    alert_kind: CandidateAlertKind
    delivery_channel: DeliveryChannel
    content: CandidateAlertContent
    content_fingerprint: Sha256Hex
    created_at: AwareDatetime


class CandidateAlertProjection(CanonicalModel):
    intent: CandidateAlertIntent
    outbox: OutboxRecord
    converged: bool


class RiskReductionIntent(CanonicalModel):
    """Typed REDUCE_RISK intent. Does not mutate Candidate or create a plan revision."""

    intent_id: UUID
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    candidate_id: UUID
    candidate_content_hash: Sha256Hex
    candidate_revision: int = Field(ge=1)
    alert_intent_id: UUID
    receipt_id: UUID
    created_at: AwareDatetime
    action: Literal[TelegramRemoteAction.REDUCE_RISK] = TelegramRemoteAction.REDUCE_RISK
    mutates_candidate: Literal[False] = False
    creates_plan_revision: Literal[False] = False
    executes: Literal[False] = False
    execution_attempted: Literal[False] = False
    future_plan_revision_required: Literal[True] = True


class CandidateReadView(CanonicalModel):
    """Read-only EXPLAIN / SHOW_CHART / STATUS projection. No mutation fields."""

    action: TelegramRemoteAction
    candidate_id: UUID
    candidate_revision: int = Field(ge=1)
    candidate_state: CandidateState
    setup_state: SetupAssessmentState
    instrument: str
    direction: TradeDirection
    expiry: AwareDatetime
    setup_name: str
    trigger_context: TriggerContext | None = None
    rule_results: tuple[RuleResultSummary, ...] = ()
    mutates_candidate: Literal[False] = False
    executes: Literal[False] = False


class CandidateAlertActionResult(CanonicalModel):
    """Application result after a secured Telegram callback. APPROVE never executes."""

    telegram_outcome: ActionOutcome
    intent: CandidateAlertIntent | None = None
    candidate_state: CandidateState | None = None
    candidate_revision: int | None = Field(default=None, ge=1)
    authorization_intent: AuthorizationIntent | None = None
    risk_reduction_intent: RiskReductionIntent | None = None
    read_only_view: CandidateReadView | None = None
    effect_kind: ActionEffectKind = ActionEffectKind.NONE
    candidate_mutated: bool = False
    executed: Literal[False] = False
    execution_attempted: Literal[False] = False
    execution_command_id: None = None
    paper_plan_invoked: Literal[False] = False
