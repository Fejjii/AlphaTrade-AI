"""Compatibility adapter: canonical plans cannot occupy the PVC-backed ORM row.

Agent 1 owns database schema. This adapter documents the exact remaining binding
and refuses to write canonical Candidate IDs into
``trade_plan_revisions.candidate_id`` (FK ``paper_validation_candidates.id``).
"""

from __future__ import annotations

from typing import NoReturn

from app.schemas.canonical_trade_plan import (
    CanonicalTradePlanDatabaseRequirement,
    CanonicalTradePlanRevision,
)
from app.services.canonical_trade_plan_errors import CanonicalTradePlanPersistenceNotBoundError

REQUIRED_CANONICAL_TRADE_PLAN_DATABASE_BINDINGS: tuple[
    CanonicalTradePlanDatabaseRequirement, ...
] = (
    CanonicalTradePlanDatabaseRequirement(
        artifact="canonical candidates table (or equivalent)",
        current_state=(
            "CandidateLifecycleService is in-memory only. No SQLAlchemy Candidate model "
            "and no Alembic table for CandidateUniquenessTuple."
        ),
        required_change=(
            "Persist canonical Candidate + append-only CandidateTransition with unique "
            "CandidateUniquenessTuple, tenant isolation, and creation/transition idempotency. "
            "Do not treat PaperValidationCandidate as this identity."
        ),
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="action_eligibility table (or equivalent)",
        current_state="ActionEligibilityService is in-memory only. No eligibility ORM table.",
        required_change=(
            "Persist immutable ActionEligibilityEvaluation keyed by uniqueness_hash, bound to "
            "canonical candidate_id + candidate_revision + account_id + user_id. Identical "
            "evaluations converge; changed risk/safety identity appends a new revision."
        ),
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="trade_plan_revisions.candidate_id",
        current_state=(
            "NOT NULL ForeignKey(paper_validation_candidates.id) from Phase 1 Wave 1B. "
            "Existing PVC-backed rows are ambiguous relative to CanonicalEvidenceWindowV1."
        ),
        required_change=(
            "Remap the FK to canonical Candidate identity (or a compatibility view). "
            "Do not backfill PVC ids as canonical Candidate ids. Do not write UUID5 "
            "canonical candidate ids into the PVC table."
        ),
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="trade_plan_revisions.setup_definition_id",
        current_state="ForeignKey(setup_definitions.id) — global SetupDefinition templates.",
        required_change=(
            "Bind executable plans to tenant-owned CompiledSetupDefinition. Global "
            "SetupDefinition remains compatibility-only and cannot occupy Candidate "
            "setup_definition_id."
        ),
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="trade_plan_revisions lineage columns or side table",
        current_state=(
            "ORM stores candidate_id plus semantic_payload JSON. No candidate_content_hash, "
            "candidate_revision, eligibility_id, eligibility_content_hash, "
            "eligibility_uniqueness_hash, evidence_window_hash, or compiled_setup_content_hash "
            "columns. Phase 1 TradePlanRevisionSemantic hash set must stay unchanged."
        ),
        required_change=(
            "Persist CanonicalTradePlanLineage beside the existing semantic_payload without "
            "mutating CanonicalTradePlanContentV1 field names. Unique constraint on "
            "application uniqueness_hash. Organization-scoped unique idempotency_key."
        ),
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="trade_plan_revisions.plan_id / trade_proposals",
        current_state=(
            "plan_id is a composite FK to trade_proposals (id, organization_id, user_id). "
            "Canonical plan_id is UUID5(org, user, account, candidate_id) and is not a "
            "TradeProposal."
        ),
        required_change=(
            "Either introduce a canonical plan-root row or explicitly map UUID5 plan_id to a "
            "compatibility TradeProposal without granting the proposal path plan authority."
        ),
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="approval/execution claim rows",
        current_state=(
            "ApprovalAuthorization already binds revision_id + plan_content_hash and cannot "
            "modify executable semantics. Execution remains a later slice."
        ),
        required_change=(
            "After ORM persist of canonical revisions, existing approval issuance can consume "
            "them. No approval semantic change is required. Do not persist canonical plans by "
            "copying them onto PaperValidationCandidate ids."
        ),
        owner="Agent 1, then approval/execution integration",
    ),
)


class UnboundSqlAlchemyCanonicalTradePlanAdapter:
    """Fail-closed PostgreSQL adapter until Agent 1 completes schema work."""

    def persist(self, revision: CanonicalTradePlanRevision) -> NoReturn:
        del revision
        raise CanonicalTradePlanPersistenceNotBoundError(
            "trade_plan_revisions.candidate_id still foreign-keys paper_validation_candidates; "
            "canonical Candidate identity cannot be written to PostgreSQL until Agent 1 remaps "
            "that FK and persists Candidate / ActionEligibility lineage."
        )

    def required_bindings(self) -> tuple[CanonicalTradePlanDatabaseRequirement, ...]:
        return REQUIRED_CANONICAL_TRADE_PLAN_DATABASE_BINDINGS
