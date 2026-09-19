# Phase 7 learning attribution

Connects the canonical trading lifecycle to AlphaTrade learning **without a
second trading authority**.

`JournalLifecycleProjector` remains the only `JournalTrade` writer. One
`execution_lifecycle_id` still converges to one canonical `JournalTrade`.
Candidate, REJECT, and SKIP still never create `JournalTrade`. This slice adds
a record-only attribution layer on top of that projector.

See also: [journal_intelligence_foundation.md](./journal_intelligence_foundation.md) ·
[journal_learning.md](./journal_learning.md) ·
[phase6_candidate_telegram_alerts.md](./phase6_candidate_telegram_alerts.md)

## Authority

| Layer | Authority | This slice |
|---|---|---|
| Setup truth | `SetupAssessment` | read-only copy |
| Candidate | `CandidateLifecycleService` | read-only copy |
| Trade plan | existing TradePlan aggregate | identity ref only |
| Journal trade | `JournalLifecycleProjector` | reused, not redesigned |
| Learning facts | `LearningAttributionService` | new, record-only |

Attribution cannot place orders, evaluate setups, create candidates, mutate
TradePlan terms, or rewrite evidence-window hashes.

## Lineage

Identity is preserved from:

`SetupAssessment` → `Candidate` → `TradePlanLineageRef` → paper execution
lifecycle → `JournalTrade` → trade outcome → strategy/pattern stats →
learning evidence.

Durable lineage for this wave is nested on append-only journal events as
`payload.lineage` (typed `JournalLineagePayload`). First-seen values are sticky
for an execution lifecycle. Conflicting source identity and conflicting lineage
fail closed. Cross-tenant organization mismatch fails closed.

## Outcomes

- `REJECT` and `SKIP` write lifecycle/audit evidence and trader-behavior facts.
  They never set `executed_trade_outcome=true` and never mint a `JournalTrade`.
- Approved-plan / fill / close / reconcile remain append-only projector
  evidence. Duplicate events converge.
- Quality axes are separate:
  - **planned setup quality** from `SetupAssessment` (unchanged by PnL)
  - **execution quality** from plan vs fill/close
  - **trader behavior** from REJECT/SKIP/APPROVE
- LLMs may attach `narrative_explanation`. Narrative is excluded from
  `facts_hash` and cannot override deterministic facts.

## Persistence

No Alembic and no ORM model changes in this wave (Agent 1 owns shared schema).

Reuse now:

- `journal_lifecycle_events` + `payload.lineage`
- `journal_projection_receipts`
- `journal_trades.execution_lifecycle_id` uniqueness

In-memory `InMemoryAttributionStore` holds computed `AttributionRecord`s.
The exact later PostgreSQL contract is
`app.learning_attribution.persistence.AGENT_1_ATTRIBUTION_INTEGRATION`.

Optional later `journal_trades` columns (Agent 1 only): `candidate_id`,
`assessment_id`, `evidence_window_hash`, `trade_plan_revision_id`.

## Adapters

- Lessons: suggestions only (`persist=false`). No auto-created lesson rows.
- Analytics: in-memory strategy/pattern and human-vs-system rollups. REJECT/SKIP
  are funnel counts, never executed-outcome rates.
- RAG: deterministic text renderer. Does not call `RagService`. Narrative is
  labeled `NARRATIVE_NOT_FACT`.

## Safety

Paper only. `ENABLE_REAL_TRADING=false`. Watcher, Telegram, execution dispatch,
frontend, and live trading are out of scope.
