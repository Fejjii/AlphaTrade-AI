# Journal Intelligence Foundation (AT-030)

Status: first vertical slice implemented (canonical journal trades). Paper-only; record-only;
no execution authority. This document contains the repository audit, the canonical domain
design, what the first slice ships, and the roadmap for the remaining slices.

## 1. Repository audit (what already existed)

The journal foundation **reuses and links** the following existing records instead of
duplicating them:

| Domain | Existing record(s) | Location | Reused how |
|---|---|---|---|
| Orders | `Order` (paper, idempotent), `ExchangeOrder`/`ExchangeFill` (demo venue) | `db/models.py` | `journal_trades.linked_order_id` |
| Positions | `Position` (proposal-flow paper portfolio) | `db/models.py` | `linked_position_id`; prefill endpoint |
| Proposals / plans | `TradeProposal` (entry, stop, TPs, runner, leverage, invalidation, planned loss) | `db/models.py` | `linked_proposal_id`; plan prefill from position |
| Paper validation | `PaperValidationRun`, `PaperSignal`, `PaperTrade` (+ events, metrics, drafts/candidates/plans/sessions, session observations/results) | `db/models.py` | `linked_paper_trade_id`, `linked_paper_validation_run_id`; prefill endpoint |
| Backtesting | `BacktestRun`, `BacktestTrade`, `HistoricalCandle` | `db/models.py` | `linked_backtest_trade_id` (org check via `BacktestRun`) |
| Setups | `SetupDefinition` (unique `name`+`version` → immutable per version), `SetupPerformance`, `SetupDetectionRecord` | `db/models.py` | `setup_id` |
| Strategies | `UserStrategy` + `UserStrategyVersion` (immutable versioned cards) | `db/models.py` | `user_strategy_id`, `strategy_version_id` (consistency validated) |
| Legacy journal | `TradeJournal` (`journals`): rationale, emotions, mistakes, lessons, tags, screenshots, links | `db/models.py`, `services/journal_service.py` | `linked_journal_entry_id` bridge; legacy API unchanged |
| Human vs system | `HumanVsSystemService` (plan adherence, runner/missed-profit, stop-refusal analyzers) | `services/human_vs_system_service.py` | consumed later via proposal/position links (roadmap) |
| Unified analytics | `UnifiedTradeLoader` (positions + paper trades → `UnifiedTradeRecord`) | `services/performance/unified_trade.py` | pattern for statistics slice (roadmap) |
| Analytics | discipline score, trade review, setup statistics, risk behavior | `services/analytics/*` | unchanged; future consumers of journal trades |
| Audit | `AuditLog` + `AuditService` (`record` in-UoW, `record_durable_isolated`) | `services/audit_service.py` | every journal-trade mutation audited |
| Market context | `MarketSnapshot`, `IndicatorSnapshot`, `HistoricalCandle`, `MarketWatcherObservation` | `db/models.py` | future regime/replay inputs (roadmap) |

Audit conclusions that shaped the design:

1. Trade data is fragmented across four execution lanes (proposal-flow positions,
   paper-validation trades, backtest trades, manual session records) with no canonical
   trade identity; `TradeJournal` is reflection-only and typed to the legacy built-in
   `StrategyId` enum, not to `UserStrategy` versions.
2. Plan data (thesis/trigger/invalidation/stop/targets/runner) exists only on
   `TradeProposal` (proposal lane) and partially on `PaperSignal`/`PaperTrade`.
3. MFE/MAE and available-vs-realized profit exist nowhere as first-class columns; the
   runner analyzer computes missed-profit estimates transiently.
4. Rule compliance and behavioral observations exist only as free-text lists
   (`TradeJournal.mistakes`, `emotions`) or as paper-validation session results.
5. Immutable versioning already exists (`SetupDefinition` name+version,
   `UserStrategyVersion`) — the journal must link to it, not reinvent it.

## 2. Canonical domain design

Canonical entity: **`journal_trades`** — one row per trade (any source), tenant-scoped
(`organization_id`, `user_id`), with three child tables. Record-only: never read by the
execution engine, scheduler, or risk gates; no route from journal data to order placement.

```
journal_trades
├── identity: source (manual|paper_execution|paper_validation|backtest|imported|system),
│             status (planned|open|closed|cancelled), external_ref
├── context:  symbol, exchange, timeframe, market_regime (+ regime_notes)
├── setup/strategy: setup_id → setup_definitions (immutable per name+version)
│             user_strategy_id → user_strategies
│             strategy_version_id → user_strategy_versions (immutable; consistency checked)
│             strategy_label (free text for imported/manual)
├── plan:     direction, thesis, trigger, entry_plan, invalidation,
│             planned_entry_price, planned_stop_price, planned_targets (JSON),
│             runner_enabled, runner_plan, planned_risk_amount
├── execution: entry/exit price+time, exit_reason, size, leverage,
│             fees, funding, slippage, gross_pnl, net_pnl, result
├── excursions: mfe_price/mae_price, mfe_amount/mae_amount,
│             available_profit, realized_vs_available_pct (derived deterministically),
│             excursion_source (who computed it: manual | replay | system)
├── reflection: notes, tags (JSON)
└── links:    linked_position_id, linked_paper_trade_id, linked_proposal_id,
              linked_order_id, linked_backtest_trade_id, linked_journal_entry_id,
              linked_paper_validation_run_id   (all tenant-validated, fail closed)

journal_trade_evidence      — kind (screenshot|chart|note|link|file), ref, caption, recorded_by
journal_trade_rule_checks   — rule_key, rule_source, status (followed|violated|partial|
                              not_applicable|unassessed), notes, assessed_by/at
journal_trade_observations  — category (behavioral|emotional|execution|market|risk|process),
                              observation, emotion_tags, recorded_by, observed_at
```

Design decisions (recorded as AT-ADR-012 in `.ai/DECISIONS.md`):

- **Link, don't copy.** Existing records stay the source of truth for their lane; the
  journal row is the canonical *intelligence* record that unifies them. Cross-tenant link
  attempts return 404 (fail closed, no existence leak).
- **Human-vs-system comparison** is expressed by the plan-vs-execution split plus the
  proposal/position links already consumed by `HumanVsSystemService`; a dedicated
  journal-trade comparison endpoint is a roadmap slice, not duplicated logic now.
- **MFE/MAE are stored, not fetched.** Values must come from deterministic inputs
  (manual entry today; candle replay in a later slice). `realized_vs_available_pct` is
  derived arithmetic (`net_pnl / available_profit * 100`) unless explicitly provided.
- **Sources**: `manual`, `paper_execution` (positions lane), `paper_validation` (paper
  trades lane), `backtest`, `imported` (external history via `external_ref`), `system`.
- **Legacy `TradeJournal` stays.** Existing `/journal/entries` API and RAG sync are
  untouched; `linked_journal_entry_id` bridges old entries to canonical trades.

## 3. First vertical slice (implemented)

| Layer | Artifact |
|---|---|
| Migration | `i5d6e7f8a9b0_at030_journal_trades.py` (head after `h4c5d6e7f8a9`); validated on Postgres 16: upgrade → downgrade → upgrade |
| ORM | `JournalTrade`, `JournalTradeEvidence`, `JournalTradeRuleCheck`, `JournalTradeObservation` (`db/models.py`) |
| Enums | `JournalTradeSource`, `JournalTradeStatus`, `MarketRegime`, `JournalEvidenceKind`, `RuleComplianceStatus`, `JournalObservationCategory` + 6 audit event types (`schemas/common.py`) |
| Schemas | `schemas/journal_trades.py` (strict create/update, ORM reads, paginated list, detail aggregate) |
| Repository | `repositories/journal_trades.py` (scoped queries, filtered listing, link lookup) |
| Service | `services/journal_trade_service.py` (CRUD, tenant-validated links, prefill from position/paper trade, evidence/rule-check/observation, audit on every mutation, UoW: flush-only) |
| API | `/journal/trades*` on the existing journal router — RBAC (`TraderDep` writes, `ReaderDep` reads), route-level commit |
| DI | `JournalTradeServiceDep` (`core/dependencies.py`) |
| Tests | `tests/test_at030_journal_trades.py` — 13 tests: auth, RBAC, CRUD, derived metrics, filters/pagination, tenant isolation, link validation, strategy-version consistency, prefill idempotency, children + audit |

Endpoints (all authorized, tenant-scoped, audited):

- `POST /journal/trades` — create (manual/imported/system or fully specified)
- `POST /journal/trades/from-position/{position_id}` — prefill from paper position
  (+ plan fields from its linked proposal); idempotent per position
- `POST /journal/trades/from-paper-trade/{paper_trade_id}` — prefill from
  paper-validation trade; idempotent per paper trade
- `GET /journal/trades` — filters: source, status, symbol, user_strategy_id, setup_id;
  paginated
- `GET /journal/trades/{id}` — detail with evidence, rule checks, observations
- `PATCH /journal/trades/{id}` — update/close; derives `realized_vs_available_pct`
- `DELETE /journal/trades/{id}` — delete with children
- `POST /journal/trades/{id}/evidence | /rule-checks | /observations`

Safety posture: no execution-path changes; no new config; paper-only invariants
untouched (`EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, non-live
`EXCHANGE_MODE`); no provider I/O; no secrets.

## 4. Roadmap — remaining slices

1. **Journal completion slice.** Bulk import (`imported` source with `external_ref`
   dedup), auto-journal hooks (opt-in) when positions close or paper trades close,
   `TradeJournal` → `journal_trades` backfill command, evidence upload storage strategy.
2. **Statistics slice.** Extend `UnifiedTradeLoader` with a journal-trades lane; setup- and
   strategy-version-level expectancy, MFE/MAE efficiency (realized vs available), rule
   compliance rates, regime breakdowns; feed `SetupPerformance` and
   `StrategyPerformanceDaily` rollups from canonical trades.
3. **Replay slice.** Deterministic excursion computation from `HistoricalCandle`
   (`excursion_source="replay"`), post-exit runner replay reusing
   `RunnerAndMissedProfitAnalyzer`, market-regime auto-labelling from indicator
   snapshots; strictly read-only market data with freshness provenance.
4. **Human-vs-system slice.** Journal-trade-native comparison endpoint reusing
   `HumanVsSystemService` analyzers over `linked_proposal_id`/`linked_position_id`;
   rule-check auto-suggestions from `UserStrategyVersion.structured_rules`; lesson
   candidate generation from violated rule checks.
5. **Backtesting integration slice.** Journal backtest trades in bulk per
   `BacktestRun`, compare live/paper cohort vs backtest cohort per strategy version.

Each slice follows this one's pattern: migration → models → strict schemas → repository →
audited service → RBAC routes → tests → docs, with `REVIEW_REQUIRED` before any commit.
