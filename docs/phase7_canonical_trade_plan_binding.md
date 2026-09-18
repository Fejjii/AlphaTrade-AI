# Phase 7 canonical TradePlanRevision — remaining database binding

This slice implements the application layer:

`ACTIVE Candidate` → `ELIGIBLE ActionEligibility` → immutable `TradePlanRevision`
→ approval (hash-bound, no semantic mutation) → paper execution (out of scope).

It does **not** mutate SQLAlchemy models or Alembic. Agent 1 owns schema.

Canonical plan authority is `CanonicalTradePlanService` with
`CanonicalTradePlanStore` (in-memory). The SQLAlchemy adapter
`UnboundSqlAlchemyCanonicalTradePlanAdapter.persist` fails closed.

## Exact remaining PostgreSQL binding

These artifacts are encoded in
`REQUIRED_CANONICAL_TRADE_PLAN_DATABASE_BINDINGS` and must not be weakened.

### 1. Canonical Candidate persistence

**Current:** `CandidateLifecycleService` + `InMemoryCandidateRepository` only.

**Required:** Durable `Candidate` + append-only `CandidateTransition` with unique
`CandidateUniquenessTuple`, tenant isolation, and creation/transition
idempotency. `PaperValidationCandidate` stays a downstream queue and cannot
become this identity.

### 2. ActionEligibility persistence

**Current:** `ActionEligibilityService` + `InMemoryActionEligibilityStore` only.

**Required:** Immutable `ActionEligibilityEvaluation` rows keyed by
`uniqueness_hash`, bound to canonical `candidate_id` + `candidate_revision` +
`account_id` + `user_id`. Identical evaluations converge; changed risk/safety
identity appends.

### 3. `trade_plan_revisions.candidate_id`

**Current:** `NOT NULL` `ForeignKey(paper_validation_candidates.id)` from Phase 1
Wave 1B (`3e4e11598fa9`).

**Required:** Remap the FK to canonical Candidate identity (or a compatibility
view). Do **not** backfill PVC ids as canonical Candidate ids. Do **not** write
UUID5 canonical candidate ids into `paper_validation_candidates`.

Existing PVC-backed plan rows are ambiguous relative to
`CanonicalEvidenceWindowV1` and must not be auto-converted.

### 4. `trade_plan_revisions.setup_definition_id`

**Current:** `ForeignKey(setup_definitions.id)` (global templates).

**Required:** Bind executable plans to tenant-owned `CompiledSetupDefinition`.
Global `SetupDefinition` remains compatibility-only.

### 5. Canonical lineage columns (or side table)

**Current:** ORM stores `candidate_id` plus `semantic_payload` JSON. No
`candidate_content_hash`, `candidate_revision`, `eligibility_id`,
`eligibility_content_hash`, `eligibility_uniqueness_hash`,
`evidence_window_hash`, or `compiled_setup_content_hash` columns.

**Required:** Persist `CanonicalTradePlanLineage` beside the existing
`semantic_payload` **without changing** `CanonicalTradePlanContentV1` field
names (Phase 1 content hashes must keep verifying). Add unique
`uniqueness_hash` and organization-scoped unique `idempotency_key`.

### 6. Plan root (`plan_id` / `trade_proposals`)

**Current:** `plan_id` is a composite FK to `trade_proposals`.

**Required:** Canonical `plan_id` is
`UUID5(org, user, account, candidate_id)` and is not a `TradeProposal`. Either
add a canonical plan-root or map that UUID5 onto a compatibility proposal
**without** restoring `ProposalService.create_revision` as plan authority.

### 7. Approval and execution

Approval already binds `revision_id` + `plan_content_hash` and rejects
`modified_fields` on `APPROVE`. After ORM persist of canonical revisions,
existing issuance can consume them. Execution dispatch stays a later slice.

## What this PR already enforces without schema

- Only `ACTIVE` canonical `Candidate` may insert a plan.
- `ActionEligibility` must be `ELIGIBLE` and currently paper-actionable.
- Candidate and eligibility lineage must match exactly (org/user/account,
  candidate id/revision, assessment, evidence window, strategy/setup, venue,
  market, instrument, timeframe, side).
- Plan `candidate_id` is the canonical Candidate id, not a PVC id.
- Semantic content is immutable; identical requests converge; conflicting
  idempotency fails closed.
- `PLAN_CREATED` is applied only after a successful in-memory insert.
- `PaperValidationCandidate` cannot mint canonical plan authority.
- `live_executable` is always false. No execution methods exist on the service.
