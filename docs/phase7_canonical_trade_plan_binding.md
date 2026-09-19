# Phase 7 canonical TradePlanRevision — database binding

Canonical plan authority is `CanonicalTradePlanService`. Persistence is the
typed `CanonicalTradePlanStore` port:

- in-memory default for unit tests
- `PostgresCanonicalTradePlanStore` for durable PostgreSQL

The fail-closed `UnboundSqlAlchemyCanonicalTradePlanAdapter` never writes.

Flow:

`ACTIVE Candidate` → `ELIGIBLE ActionEligibility` → immutable `TradePlanRevision`
→ approval (hash-bound, no semantic mutation) → paper execution (out of scope).

## Database authority model

| Artifact | Authority | Notes |
|---|---|---|
| Canonical Candidate | `CandidateLifecycleService` + `PostgresCandidateRepository` | Alembic `4fd8c1a90b27`. PVC is not this identity. |
| ActionEligibility | `ActionEligibilityService` + `PostgresActionEligibilityStore` | Alembic `c9e2b4a1d078`. Append-safe revisions keyed by uniqueness hash. |
| Canonical TradePlanRevision | `CanonicalTradePlanService` + `PostgresCanonicalTradePlanStore` | Discriminator `plan_authority='canonical'`. Lineage is a side table. |
| Compatibility TradeProposal | FK only | `plan_root_kind='canonical_plan_root'`. Not plan authority. |
| Legacy PVC-backed plan | `plan_authority='paper_validation'` | `canonical_candidate_id` NULL. Existing rows are not remapped. |
| Approval | existing `ApprovalAuthorization` | Binds exact revision id + plan content hash. Execution is a later slice. |

Canonical `plan_id` remains deterministic UUID5(org, user, account, candidate_id).

`PLAN_CREATED` runs in the same PostgreSQL transaction as the plan insert after
locking the canonical Candidate. Failed creates do not transition.

## Binding completed in Phase 7 integration

1. Canonical Candidate persistence (`4fd8c1a90b27`).
2. ActionEligibility persistence with deterministic identity bindings.
3. Dropped `trade_plan_revisions.candidate_id` FK to `paper_validation_candidates`.
   Canonical rows set `canonical_candidate_id = candidate_id`.
4. Dropped global `setup_definitions` FK. Canonical rows bind
   `compiled_setup_definition_id` to tenant-owned `compiled_setup_definitions`.
5. `canonical_trade_plan_lineage` stores Candidate/eligibility hashes beside
   unchanged `semantic_payload` (`CanonicalTradePlanContentV1`).
6. Compatibility TradeProposal satisfies the existing `plan_id` composite FK.

Do **not** backfill PVC ids as canonical Candidate ids. Do **not** write UUID5
canonical candidate ids into `paper_validation_candidates`.

## Still later

Approval issuance can consume persisted canonical revisions. Execution dispatch
stays a later slice. Adapters are not wired into FastAPI, workers, Watcher,
Telegram, or live trading.

## Application invariants (unchanged)

- Only `ACTIVE` canonical `Candidate` may insert a plan.
- `ActionEligibility` must be `ELIGIBLE` and currently paper-actionable.
- Lineage must match exactly (org/user/account, candidate id/revision, assessment,
  evidence window, strategy/setup, venue/market/instrument/timeframe/side).
- Plan `candidate_id` is the canonical Candidate id, not a PVC id.
- Semantic content is immutable; identical requests converge; conflicting
  idempotency fails closed.
- `PaperValidationCandidate` cannot mint canonical plan authority.
- `live_executable` is always false. No execution methods exist on the service.
