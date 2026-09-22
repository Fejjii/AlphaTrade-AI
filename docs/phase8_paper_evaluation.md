# Continuous paper evaluation

Measurement layer over Watcher scans, SetupAssessment, Candidate,
ActionEligibility, paper decisions, paper trades, Journal outcomes, and
learning attribution. This package does **not** evaluate setups, mint
Candidates, authorize plans, dispatch execution, or activate strategy
refinements.

See also: [phase7_learning_attribution.md](./phase7_learning_attribution.md) ·
[phase8_learning_persistence.md](./phase8_learning_persistence.md) ·
[journal_intelligence_foundation.md](./journal_intelligence_foundation.md)

## Authority

`app.paper_evaluation` is a record-and-query measurement layer.

- Watcher fusion remains the setup-truth evaluator.
- CandidateLifecycleService remains the Candidate writer.
- ActionEligibility remains the account/action gate.
- JournalLifecycleProjector remains the JournalTrade writer.
- Learning attribution remains record-only.

Refinement suggestions always have `activate=false` and `auto_activate=false`.
`refuse_activation` fails closed.

## Funnel

Watcher scan → SetupAssessment → Candidate → paper decision → paper trade →
outcome → Journal → attribution → strategy statistics → learning evidence →
refinement suggestion.

Query-time merge:

- Watcher observations (`paper_evaluation_observations`)
- ActionEligibility evaluations already stored for the tenant
- Learning attribution records
- Journal MFE / MAE / capture / rule-compliance copies (read-only)

Watcher orchestration stays disabled. Empty scan metrics are honest zeros with
`watcher_not_activated`, not a RUNNING status.

## Facts vs narrative

Deterministic facts are hashed without LLM wording. Observation
`narrative_explanation` and query-time `PaperEvaluationNarrative` are siblings
of facts. Narrative cannot rewrite `content_hash`.

Missed-opportunity counts are funnel misses only. Counterfactual PnL is never
invented (`counterfactual_pnl=null`).

## Persistence

Alembic revision `e3f4a5b6c7d8` (after `c8d9e0f1a2b3`) adds
`paper_evaluation_observations`. The linear head continues through `d9e0f1a2b3c4`
(paper Telegram identity) to `e0f1a2b3c4d5` (activation cursor and send ledger) to `f1a2b3c4d5e6` (controlled runtime status).
Duplicate source identity converges.
Identity columns cannot be rewritten. Narrative may be attached later.

## HTTP

`GET /canonical/paper-evaluation/summary` — operator-visible measurement
summary. `watcher_activated` and `live_executable` stay false. Refinements
cannot be activated through this API.

## Safety

Paper only. `ENABLE_REAL_TRADING=false`. Watcher, Telegram, and live trading
stay off. This layer does not start Watcher, send Telegram, or place orders.
