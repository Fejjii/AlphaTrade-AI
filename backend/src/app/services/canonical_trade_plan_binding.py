"""Fail-closed compatibility adapter: never write canonical plans through this path.

Durable binding is ``PostgresCanonicalTradePlanStore``. This adapter stays as a
guard so callers cannot persist canonical Candidate IDs through an unbound
SQLAlchemy helper.
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
            "PostgresCandidateRepository persists canonical Candidate + append-only "
            "transitions (Alembic 4fd8c1a90b27). In-memory remains the unit-test default."
        ),
        required_change=(
            "Keep CandidateLifecycleService as the only Candidate authority. Do not treat "
            "PaperValidationCandidate as this identity."
        ),
        owner="Phase 7 integration (completed)",
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="action_eligibility table (or equivalent)",
        current_state=(
            "PostgresActionEligibilityStore persists immutable evaluations keyed by "
            "uniqueness_hash with append-safe revision history (Alembic c9e2b4a1d078)."
        ),
        required_change=(
            "Keep ActionEligibilityService as the only eligibility authority. Identical "
            "evaluations converge; changed risk/safety identity appends a new revision."
        ),
        owner="Phase 7 integration (completed)",
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="trade_plan_revisions.candidate_id",
        current_state=(
            "PVC foreign key dropped. Discriminator plan_authority keeps legacy PVC-backed "
            "rows as paper_validation with canonical_candidate_id NULL. Canonical rows set "
            "canonical_candidate_id = candidate_id and FK canonical_candidates."
        ),
        required_change=(
            "Do not backfill PVC ids as canonical Candidate ids. Do not write UUID5 "
            "canonical candidate ids into the PVC table."
        ),
        owner="Phase 7 integration (completed)",
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="trade_plan_revisions.setup_definition_id",
        current_state=(
            "Global SetupDefinition FK dropped. Canonical rows bind "
            "compiled_setup_definition_id to compiled_setup_definitions."
        ),
        required_change=(
            "Global SetupDefinition remains compatibility-only and cannot occupy Candidate "
            "setup_definition_id."
        ),
        owner="Phase 7 integration (completed)",
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="trade_plan_revisions lineage columns or side table",
        current_state=(
            "canonical_trade_plan_lineage stores Candidate/eligibility hashes beside "
            "semantic_payload. uniqueness_hash is unique; idempotency keys are "
            "organization-scoped."
        ),
        required_change=(
            "Do not mutate CanonicalTradePlanContentV1 field names. Phase 1 hashes stay valid."
        ),
        owner="Phase 7 integration (completed)",
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="trade_plan_revisions.plan_id / trade_proposals",
        current_state=(
            "Canonical plan_id remains UUID5(org, user, account, candidate_id). A "
            "compatibility TradeProposal with plan_root_kind=canonical_plan_root satisfies "
            "the existing composite FK without granting proposal-path plan authority."
        ),
        required_change=(
            "ProposalService.create_revision stays fail-closed. CanonicalTradePlanService "
            "is the only first-slice plan authority."
        ),
        owner="Phase 7 integration (completed)",
    ),
    CanonicalTradePlanDatabaseRequirement(
        artifact="approval/execution claim rows",
        current_state=(
            "ApprovalAuthorization already binds revision_id + plan_content_hash and cannot "
            "modify executable semantics. Execution remains a later slice."
        ),
        required_change=(
            "Existing approval issuance can consume persisted canonical revisions. Do not "
            "persist canonical plans by copying them onto PaperValidationCandidate ids. "
            "Do not add execution in this wave."
        ),
        owner="approval/execution integration",
    ),
)


class UnboundSqlAlchemyCanonicalTradePlanAdapter:
    """Fail-closed PostgreSQL adapter until Agent 1 completes schema work."""

    def persist(self, revision: CanonicalTradePlanRevision) -> NoReturn:
        del revision
        raise CanonicalTradePlanPersistenceNotBoundError(
            "UnboundSqlAlchemyCanonicalTradePlanAdapter never writes; persist canonical "
            "TradePlanRevision rows through PostgresCanonicalTradePlanStore."
        )

    def required_bindings(self) -> tuple[CanonicalTradePlanDatabaseRequirement, ...]:
        return REQUIRED_CANONICAL_TRADE_PLAN_DATABASE_BINDINGS
