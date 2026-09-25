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
identity plus an idempotency key. Executable fields are forbidden. Exact replay
converges, does not double-meter usage, and still commits the request session
so any healing journal/attribution writes persist.

## ProposalService firewall

Compatibility `TradeProposal` rows with `plan_root_kind=canonical_plan_root`
satisfy the existing `plan_id` FK. They are **not** ProposalService trading
authority:

- `create` always writes `analysis_proposal`
- list endpoints omit canonical roots
- get/update/revision paths apply tenant scope first, then raise
  `TradingPolicyError` for same-tenant `canonical_plan_root`. Cross-tenant
  lookups return NotFound and do not reveal that a canonical root exists.

## Journal

`ALLOW` projects `approved_plan` and fills project `fill` through
`JournalLifecycleProjector` with `source_system=canonical_paper_execution`.
A filled plan is closed with `POST /execution/paper-plan/close`. The caller
supplies the exit price, fees, funding, slippage, exit reason, and close time.
Gross and net PnL are computed from the recorded entry and size. The close
projects `close`, attributes learning facts, and does not read market data or
call an exchange. Exact replay of the same idempotency key converges. A second
close key on an already closed trade is refused. Journal is record-only.

## Learning

After journal projection, `attribute_canonical_paper_event` writes durable
facts through `PostgresAttributionStore` and
`LearningAttributionService.apply_projected`. Missing Candidate,
ActionEligibility, or required assessment lineage fails closed with
`LearningAttributionIncompleteError` and rolls back the ALLOW unit of work.
It does not skip learning evidence and is not a second JournalTrade writer.

## Out of scope

Watcher enablement, Telegram enablement, live trading, and a new Alembic
revision (schema already landed in Phase 7 plus PR97 `d4f7a2c8e901`).
