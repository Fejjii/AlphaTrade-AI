# Journal Intelligence Foundation (AT-030, AT-031, AT-032, AT-033)

Status: slices 1 (canonical journal trades, AT-030), 2 (journal statistics & setup
analytics v1, AT-031), 3 (deterministic excursion replay, AT-032), and 4 (journal
completion — import/backfill/auto-journal/attachments, AT-033) implemented.
Paper-only; record-only; no execution authority. This document contains the repository
audit, the canonical domain design, what each slice ships, and the roadmap for the
remaining slices.

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
  (manual entry or AT-032 HistoricalCandle replay). `realized_vs_available_pct` is
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

## 4. Statistics slice (AT-031 — implemented)

Journal Statistics & Setup Analytics v1: deterministic, tenant-scoped, grouped/filterable
aggregates over canonical `journal_trades`. Extends the AT-030 architecture — no separate
analytics system.

| Layer | Artifact |
|---|---|
| Migration | `j6e7f8a9b0c1_at031_journal_stats_indexes.py` (head after `i5d6e7f8a9b0`); composite indexes on `journal_trades` (org+user+status+exit_time; org+setup; org+strategy; org+strategy-version) and `journal_trade_rule_checks` (org+status); validated on Postgres 16: upgrade → downgrade → upgrade |
| Schemas | `schemas/journal_statistics.py` — `JournalStatsGroupBy`, `TradeRuleCompliance`, `ExecutionActor`, `SampleConfidence`, warning codes, `JournalTradeStatsMetrics`, `JournalStatsBucket`, `JournalStatsResponse` |
| Repository | `repositories/journal_trades.py` — `fetch_stats_rows` (bounded projection of closed trades, stable ordering, `max_rows + 1` truncation detection), `fetch_rule_check_status_pairs` (SQL-grouped per-trade rule statuses); shared filter builder |
| Service | `services/journal_statistics_service.py` — pure `Decimal` metric computation, grouping, label resolution (setup name+version, strategy name+version), derived dimensions, confidence + warnings |
| API | `GET /journal/statistics` on the journal router — `ReaderDep` (viewer can read), tenant-scoped (org + user), bucket pagination (`limit`/`offset`), 422 on invalid date range |
| Config | `journal_stats_max_rows` (default 5000) bounds every statistics scan |
| Frontend | `/journal/statistics` page — group-by + filters (source, symbol, timeframe, regime, compliance, execution, date range), overall card, bucket cards with confidence badges and warnings, truncation banner, bucket pagination |
| Tests | `tests/test_at031_journal_statistics.py` — 19 tests: auth/RBAC, exact metric values, result fallback, profit-factor edge, excursion/capture coverage, grouping (setup/setup-version/strategy/strategy-version/symbol/regime/source), all filters, date range, rule-compliance classification, execution-actor mapping, tenant isolation, empty samples, truncation |

Semantics (deterministic, conservative — see AT-ADR-013):

- **Closed trades only.** Outcome metrics are undefined for planned/open/cancelled rows.
  The date-range filter applies to `coalesce(exit_time, entry_time, created_at)`.
- **Win/loss/breakeven** uses the recorded `result`; a closed trade left at `result=open`
  falls back to the sign of its recorded `net_pnl` (same arithmetic AT-030 applies at
  close); otherwise the trade stays undecided. Win rate = wins / (wins + losses).
- **Metric families carry their own sample counts** (PnL, R-multiple, costs, MFE/MAE,
  available-vs-realized). `None` means "not computable from recorded data" — never a
  silent zero. MFE/MAE aggregates exist only where deterministic recorded values exist.
- **Rule compliance per trade** is the worst recorded assessment: `violated` > `partial` >
  `compliant` (any `followed`) > `unassessed`. No checks ⇒ `unassessed`, never compliant.
- **Human vs system execution** is derived from `source` by decision authority: `manual`,
  `imported`, `paper_execution` (human-approved proposal flow) ⇒ `human`;
  `paper_validation`, `backtest`, `system` ⇒ `system`.
- **Confidence labels**: `insufficient` (<5 closed trades), `low` (<20), `moderate` (<50),
  `high` (≥50), plus explicit warnings (low sample, missing PnL/risk, no losing trades,
  partial excursion/capture coverage, truncation).
- **Bounded scans.** Every computation reads at most `journal_stats_max_rows` closed
  trades (stable oldest-first window); truncation is flagged in the response and as a
  warning. Reads are not audited (consistent with existing journal reads); all
  journal-trade mutations remain audited via AT-030.

## 5. Excursion replay slice (AT-032 — implemented)

Deterministic MFE/MAE, available profit, and profit-capture from stored
`HistoricalCandle` rows. Extends AT-030/031 — no live market I/O, no execution path.

| Layer | Artifact |
|---|---|
| Migration | `k7f8a9b0c1d2_at032_journal_excursion_replay.py` (head after `j6e7f8a9b0c1`); provenance columns + org/user/excursion_source index |
| Calculator | `services/journal_excursion_calculator.py` — pure long/short MFE/MAE / available-profit arithmetic |
| Service | `services/journal_excursion_replay_service.py` — read-only candle load, overwrite policy, audit, optional post-exit `RunnerAndMissedProfitAnalyzer` |
| Schemas | `schemas/journal_excursion_replay.py` — request/result/provenance; `overwrite_policy=skip_protected\|force` |
| Repository | `JournalTradeRepository.list_replay_candidates` — bounded eligible closed trades |
| API | `POST /journal/trades/{id}/replay-excursions`, `POST /journal/trades/replay-excursions` (`TraderDep`) |
| Config | `journal_replay_max_candles` (default 5000), `journal_replay_batch_max` (default 100) |
| Tests | `tests/test_at032_journal_excursion_replay.py` — calculator, edge cases, overwrite policy, tenant isolation, stats feed |

Semantics (deterministic, conservative — see AT-ADR-014):

- **Read-only candles.** Replay never calls market-data providers; missing candles skip
  safely (`skipped_reason=missing_candles`). Gaps / incomplete coverage set
  `excursion_is_stale` + freshness notes but still persist best-effort metrics when bars
  exist.
- **Window.** Bars overlapping `[entry_time, exit_time)` (exit exclusive) so post-exit
  runner lookahead is separate.
- **Long / short.** LONG: MFE=`max(high)`, MAE=`min(low)`; SHORT: MFE=`min(low)`,
  MAE=`max(high)`. Amounts use recorded size; MAE amount is typically ≤ 0.
- **available_profit** = `max(mfe_amount, 0)`; **realized_vs_available_pct** =
  `net_pnl / available_profit * 100` when both set and available ≠ 0.
- **Overwrite policy.** Default `skip_protected`: write when empty or
  `excursion_source=replay`; never replace `manual`/`system` without
  `overwrite_policy=force`.
- **Provenance.** `excursion_source="replay"` plus data source, staleness, gap count,
  window completeness, computed_at. Mutations audited as
  `JOURNAL_TRADE_EXCURSION_REPLAYED`.
- **AT-031 feed.** Persisted amounts are recorded values — statistics aggregates pick
  them up automatically (raising excursion coverage).

## 6. Journal completion slice (AT-033 — implemented)

Bulk import, legacy backfill, opt-in auto-journal hooks, and DB-backed evidence
attachments. Record-only — nothing here places orders or feeds execution/risk gates.

| Layer | Artifact |
|---|---|
| Migration | `l8a9b0c1d2e3_at033_journal_completion.py` (head after `k7f8a9b0c1d2`); partial unique index, `entry_method`, `journal_import_batches`, `journal_trade_attachments` |
| Import | `services/journal_import_service.py`, `schemas/journal_import.py` |
| Backfill | `services/journal_backfill_service.py`, `scripts/backfill_journal_entries.py` |
| Attachments | `services/journal_attachment_service.py`, `services/journal_attachment_storage.py`, `schemas/journal_attachments.py` |
| Auto-journal | Hooks in `services/position_service.py` (`close_paper`) and `services/paper_validation_runtime_service.py` (tick close loop) |
| API | `POST /journal/trades/import`, `GET /journal/imports[/{id}]`, `POST/GET /journal/trades/{id}/attachments`, `GET /journal/attachments/{id}/content`, `DELETE /journal/attachments/{id}` |
| Config | `journal_auto_from_position_close`, `journal_auto_from_paper_validation` (both default **false**); `journal_attachment_max_bytes` (5 MiB), `journal_attachment_allowed_types` (png/jpeg/webp/pdf), `journal_attachment_max_per_trade` (20) |
| Frontend | `/journal/import` — CSV parse + column mapping + dry-run reconciliation + all-or-nothing commit + batch history |
| Tests | `tests/test_at033_journal_import.py`, `test_at033_journal_backfill.py`, `test_at033_journal_attachments.py`, `test_at033_auto_journal.py`, `test_at033_integration.py` |

### 6.1 Deduplication & idempotency (`external_ref`)

- Partial unique index `uq_journal_trades_org_external_ref` on
  `(organization_id, external_ref) WHERE external_ref IS NOT NULL` — the database
  backstop for all import/backfill dedup. NULL refs remain unconstrained.
- Import rows without an explicit `external_ref` get a deterministic fingerprint
  `fp-sha256:<hex>` over normalized `(symbol, direction, entry_time, entry_price,
  size)`, so re-importing the same file is idempotent either way.
- Backfilled rows use `external_ref='legacy-journal:<id>'` plus
  `linked_journal_entry_id`; entries already linked manually are skipped.

### 6.2 Import API contract

`POST /journal/trades/import` (`TraderDep`), max **500** raw row objects per request:

- `mode=dry_run` (default) validates each row individually and previews per-row
  outcomes without persisting anything.
- `mode=commit` is **all-or-nothing in one unit of work**: any invalid row downgrades
  the request to a validation report (`committed=false`, nothing written). Duplicate
  rows (existing or repeated within the batch) are skipped idempotently.
- Per-row outcomes: `created` / `would_create` / `duplicate` (with the existing trade
  id) / `invalid` (readable field errors). Rows become `journal_trades` with
  `source=imported`, `entry_method=import`; `result` falls back to the net-PnL sign
  for closed rows. Internal record links are intentionally not importable.
- Committed batches persist to `journal_import_batches` (counts + row report) —
  reconciliation history via `GET /journal/imports` and `GET /journal/imports/{id}`
  (`ReaderDep`, org+user scoped).
- **Recovery model:** a failed commit persists nothing; fixing the input and
  re-running is always safe because dedup skips already-imported rows.

### 6.3 Backfill command

```bash
cd backend
uv run python scripts/backfill_journal_entries.py            # dry-run (default)
uv run python scripts/backfill_journal_entries.py --commit   # apply
uv run python scripts/backfill_journal_entries.py --org <uuid>
```

Maps legacy `TradeJournal` (`journals`) rows to canonical trades
(`source=imported`, `entry_method=backfill`): thesis ← entry rationale; notes fold
exit rationale/lessons/improvement rule/emotions/mistakes; `screenshot_refs` become
`screenshot` evidence rows; proposal/position links copied. Legacy rows are never
modified or deleted. Commit records a `JOURNAL_BACKFILL_COMPLETED` audit event per
organization.

### 6.4 Auto-journal hooks (opt-in, default off)

- `journal_auto_from_position_close=true`: `PositionService.close_paper` also calls
  the idempotent `create_from_position` with `entry_method=auto`.
- `journal_auto_from_paper_validation=true`: the paper-validation tick journals each
  closed trade via `create_from_paper_trade`, attributed to the **run owner**.
- **Failure isolation guarantee:** each hook runs in a savepoint and swallows every
  error after a warning log — journaling can never block, fail, or roll back the
  close itself. Link-based idempotency prevents duplicates when a trade was already
  journaled manually.

### 6.5 Attachment storage strategy

Bytes live in Postgres (`journal_trade_attachments.content`) behind the
`AttachmentStorage` interface (`storage_backend='db'`). Rationale: the platform has
no durable object store and Render disks are ephemeral, so DB storage is the only
backend covered by existing backups; strict caps keep it safe (5 MiB/file, MIME
whitelist png/jpeg/webp/pdf, 20 attachments/trade, filename sanitized to a
basename). An S3-style backend can replace it later by adding an implementation and
switching the factory — no schema change. Uploads auto-create a linked
`JournalTradeEvidence` row (`ref='attachment:<id>'`) so attachments appear in the
existing evidence timeline; downloads stream with `X-Content-Type-Options: nosniff`.

### 6.6 Human-vs-system analytics readiness

New `entry_method` column (`manual` / `auto` / `import` / `backfill`) is orthogonal
to `source` and is a first-class statistics filter and `group_by=entry_method`
dimension (AT-031 service). This distinguishes human-created from system-created
journal records even when both share `source=paper_execution`.

### 6.7 RBAC, tenancy, audit

Mutations (`import`, attachments upload/delete) require `TraderDep`; reads
(`imports`, attachment list/content) require `ReaderDep`. All lookups are
organization-scoped and fail closed (404, no existence leak); import batches are
additionally user-scoped. New audit events: `JOURNAL_IMPORT_COMPLETED`,
`JOURNAL_BACKFILL_COMPLETED`, `JOURNAL_ATTACHMENT_ADDED`,
`JOURNAL_ATTACHMENT_DELETED`; auto-journal reuses `JOURNAL_TRADE_CREATED` with
`action=auto_journal_position_close|auto_journal_paper_validation`.

### 6.8 Deferred work

- Attachment upload **UI** (needs a canonical trades detail page first — not built).
- Per-user/per-org auto-journal preference (flags are global `Settings` today; no
  preferences model exists).
- Persisting failed/dry-run import batches (`journal_import_batches.status` already
  supports `dry_run`/`failed` for forward compatibility; only `committed` rows are
  written today).

## 7. Roadmap — remaining slices

1. **Human-vs-system slice.** Journal-trade-native comparison endpoint reusing
   `HumanVsSystemService` analyzers over `linked_proposal_id`/`linked_position_id`;
   rule-check auto-suggestions from `UserStrategyVersion.structured_rules`; lesson
   candidate generation from violated rule checks.
2. **Backtesting integration slice (delivered — AT-034).** Deterministic backtest v2
   (`ENGINE_VERSION=at034-2.0.0`) with frozen `config_snapshot`/`config_hash`,
   immutable `backtest_datasets`, walk-forward holdout/rolling splits, long+short
   structured-rule entries, bulk journal-from-backtest (`source=backtest`,
   dedup via `external_ref`), `GET /journal/comparison` three-cohort analytics,
   and advisory `GET /journal/setup-evidence` tiers. Record-only — never feeds
   execution or risk. See [backtesting.md](backtesting.md).
3. **Rollup feeds (optional).** Feed `SetupPerformance` and `StrategyPerformanceDaily`
   rollups from canonical trades once auto-journaling ensures coverage.
4. **Journal completion follow-ups.** See §6.8 (attachment upload UI, per-user
   auto-journal preference, failed/dry-run batch persistence).

Each slice follows the established pattern: migration → models → strict schemas →
repository → audited service → RBAC routes → tests → docs, with `REVIEW_REQUIRED` before
any commit.
