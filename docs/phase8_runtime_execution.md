# Phase 8 canonical PAPER runtime execution

Phase 7 persisted Candidate, ActionEligibility, and canonical TradePlanRevision
in PostgreSQL without FastAPI or worker composition. This wave attaches those
adapters to the application runtime and completes the paper execution path.

Canonical flow:

`Evidence → SetupAssessment → Candidate → ActionEligibility → TradePlanRevision
→ approval → PAPER EXECUTE_PAPER_PLAN → journal lifecycle`

## Composition

`ProductionCanonicalRuntime` (`app.runtime.canonical`) is the process-level
bundle:

- `PostgresCandidateRepository` + `CandidateLifecycleService` (sole Candidate
  authority)
- `PostgresActionEligibilityStore` + `ActionEligibilityService`
- `PostgresCanonicalTradePlanStore` + `CanonicalTradePlanService`

FastAPI lifespan stores the runtime on `app.state.canonical_runtime`. Request
handlers bind the caller's SQLAlchemy session (`bind_session`) so canonical
reads share the unit of work. The worker entrypoint constructs the same runtime
and does **not** start Watcher or Telegram loops. Feature flags default false.

## Execution

`ExecutionService.execute_paper_plan` routes on `plan_authority`:

| `plan_authority` | Path |
|---|---|
| `paper_validation` | existing Phase 1 `PaperPlanClaimService` |
| `canonical` | `CanonicalPaperExecutionService` |

Canonical execution:

1. Requires the bound production runtime.
2. Loads the exact immutable `TradePlanRevision` and hash-bound
   `ApprovalAuthorization`.
3. Re-verifies Candidate, ActionEligibility, plan, approval, and account
   lineage immediately before the claim transaction. Failures return `BLOCKED`
   and do **not** consume the authorization.
4. Kill switch and deterministic risk remain final inside `PaperPlanClaimService`
   (`evaluate_claim_predicate`).
5. Duplicate idempotency keys converge to the same command identities, including
   after process restart.
6. `live_executable` stays false. No exchange mutation.

HTTP: `POST /execution/paper-plan` accepts only account/authorization/revision
identity plus an idempotency key. Executable fields are forbidden.

## ProposalService firewall

Compatibility `TradeProposal` rows with `plan_root_kind=canonical_plan_root`
satisfy the existing `plan_id` FK. They are **not** ProposalService trading
authority:

- `create` always writes `analysis_proposal`
- list endpoints omit canonical roots
- get/update/revision paths raise `TradingPolicyError`

## Journal

`ALLOW` projects `approved_plan` and fills project `fill` through
`JournalLifecycleProjector` with `source_system=canonical_paper_execution`.
Exact replay converges. Journal is record-only.

## Learning

After journal projection, `attribute_canonical_paper_event` writes durable
facts through `PostgresAttributionStore` and
`LearningAttributionService.apply_projected`. It does not become a second
JournalTrade writer.

## Out of scope

Watcher enablement, Telegram enablement, live trading, and a new Alembic
revision (schema already landed in Phase 7 plus PR97 `d4f7a2c8e901`).
