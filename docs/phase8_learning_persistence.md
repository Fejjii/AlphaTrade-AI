# Phase 8 learning persistence

Durable PostgreSQL binding for Phase 7 learning attribution. Canonical trade
outcomes become queryable strategy and pattern intelligence without a second
trading authority.

See also: [phase7_learning_attribution.md](./phase7_learning_attribution.md) ·
[journal_intelligence_foundation.md](./journal_intelligence_foundation.md) ·
[journal_learning.md](./journal_learning.md) ·
[lesson_workflow.md](./lesson_workflow.md)

## Authority

`JournalLifecycleProjector` remains the only `JournalTrade` writer. Learning
persistence copies lineage and facts; it does not evaluate setups, create
candidates, authorize plans, or dispatch execution.

Quality axes stay separate:

- planned setup quality
- execution quality
- risk adherence
- trader behavior
- outcome

REJECT and SKIP remain funnel/behavior facts. They never set
`executed_trade_outcome=true` and never mint a `JournalTrade`.

## Persistence

Alembic revision `d4f7a2c8e901` (after `c9e2b4a1d078`) adds:

- `learning_attribution_records` — one aggregate per `(organization_id, candidate_id)`
- `learning_attribution_events` — append-only source-identity evidence
- optional `journal_trades` query helpers: `candidate_id`, `assessment_id`,
  `evidence_window_hash`, `trade_plan_revision_id` (stamped by the projector
  from sticky `payload.lineage`)

`PostgresAttributionStore` implements `AttributionStore`. Duplicate source
identity converges. Conflicting identity, lifecycle/candidate mismatch, and
cross-tenant reads/writes fail closed. LLM `narrative_explanation` is stored
beside facts and is excluded from `facts_hash`.

## Query and analytics

`LearningQueryService` reads persisted records and produces:

- deterministic strategy/pattern rollups
- human-versus-system comparison (approvals vs reject/skip vs paper execution)
- separate `paper_internal` and `paper_exchange_demo` cohorts for future demo
  trade learning
- lesson *suggestions* (`persist=false`) using the existing lesson review shape
- RAG evidence documents that are explicitly **not market truth**

Slice 84 `/learning-analytics` over the older paper-validation funnel is
unchanged and is not the canonical Phase 7/8 authority.

## RAG fact boundaries

`learning_evidence_document` / `render_learning_facts_text` reuse journal RAG
sanitization. Narrative is labeled `NARRATIVE_NOT_FACT`. This layer does not
call `RagService` and does not ingest vectors. Learning never updates
`HistoricalCandle` or SetupAssessment hashes.

## Safety

Paper only. `ENABLE_REAL_TRADING=false`. Watcher, Telegram, execution dispatch,
frontend, and live trading are out of scope. Not wired into FastAPI or workers.
