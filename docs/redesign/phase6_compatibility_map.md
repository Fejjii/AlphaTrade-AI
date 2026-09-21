# Phase 6 legacy compatibility map

**Audit base:** `main@2570a84768137cfae93475ae0905d26d1cb6b991`  
(merge of PR #81, watcher orchestration foundation PR #78 + Telegram security protocol PR #79)

**Scope:** implementation map only. No runtime behavior, migrations, configuration, or
architecture-document edits.

**Target architecture used (not invented):**
`docs/redesign/agentic_redesign_target_architecture.md` sections 5, 6, 15, 25, 26
(and the first-slice contract table in §18 that restates those identities).

**Safety posture observed, not changed:** `EXECUTION_MODE=paper`,
`ENABLE_REAL_TRADING=false`. Watcher, TradingView webhook, paper-signal orchestration,
bridge, scheduler, and external alert delivery remain flag-gated off in checked-in defaults
(`backend/src/app/core/config.py`).

This document maps **current repository objects** onto the Phase 6 lineage:

- global `PublicMarketObservation`
- tenant `TenantExternalAssertion`
- tenant `SetupAssessment`
- tenant `Candidate` whose uniqueness key is the §5 tuple with
  `evidence_window_hash = CanonicalEvidenceWindowV1`
- downstream `PaperValidationCandidate` as a **validation/evaluation queue**, not candidate
  authority (§26)

Classification vocabulary (exclusive primary mapping per legacy entity):

| Token | Meaning |
|---|---|
| `PUBLIC OBSERVATION ADAPTER` | Persist or project a public venue fact into `PublicMarketObservation`. |
| `TENANT ASSERTION ADAPTER` | Persist a private/proprietary/manual claim as `TenantExternalAssertion`. |
| `SETUP ASSESSMENT ADAPTER` | Feed the source-agnostic assessment command that emits `SetupAssessment`. |
| `CANDIDATE ADAPTER` | Upsert the canonical tenant `Candidate` after `CONFIRMED_SETUP`. |
| `DOWNSTREAM PAPER VALIDATION CONSUMER` | Queue, plan, or evaluate against a canonical candidate; never mint one. |
| `DEPRECATED COMPATIBILITY READ` | Keep readable; stop treating as truth; do not backfill as canonical. |
| `UNCHANGED` | Already matches its target role, or is out of Phase 6 write authority. |

---

## 1. Target identities this map must not violate

Quoted from the target architecture; restated here so the mapping cannot drift.

**§5 candidate database key**

`(organization_id, strategy_version_id, setup_definition_id, fusion_policy_version,
direction, evidence_venue, evidence_market, evidence_instrument, timeframe,
evidence_window_hash)`

where `setup_definition_id` is the tenant-owned `CompiledSetupDefinition` for the exact
strategy version, and `evidence_window_hash` is `CanonicalEvidenceWindowV1` over the complete
§26 preimage.

**§26 CanonicalEvidenceWindowV1 preimage includes**

organization, strategy version, `CompiledSetupDefinition` ID/hash, fusion/finality/freshness
policy versions, direction, evidence venue/market/instrument, timeframe, half-open final
interval bounds, trigger natural identity/revision, mandatory evidence roles, selected public
observation content hashes, tenant assertion IDs/content hashes where required, manual-level
revision, source set and correction-selection policy.

**Excludes:** receive/record times, scan/action/correlation IDs, optional presentation evidence.

**§25 ownership**

- `PublicMarketObservation`: privacy class `PUBLIC_MARKET_DATA`, **no tenant IDs**, global
  dedupe by natural source event.
- `TenantExternalAssertion`: privacy class `TENANT_CONFIDENTIAL`. TradingView alerts,
  proprietary signals, user strategy references, and manually asserted levels. Never enters a
  global index, hash namespace, query, cache, or deduplication decision.
- A private assertion can reference public observation IDs; it never becomes one.

**§6 / §26 write rule**

Watcher, detector and TradingView adapters feed the **same** assessment command.
`PaperValidationCandidate` remains a downstream validation/evaluation queue referencing the
canonical candidate; it is not a source adapter or competing identity.

**§15 Phase 6 work**

Implement global typed `PublicMarketObservation` adapters, perpetual
`TradeEvent` / `TradeStreamCursor` / `CvdWindow`, deterministic pattern evaluation, separate
`SetupAssessment` / `ActionEligibility`, compatibility adapters, and database candidate
uniqueness. Watcher unification is Phase 7; Telegram delivery outbox is Phase 8.

---

## 2. Master mapping table

| Legacy entity | Current SoT | PK | Tenant | Strategy/setup identity | Market identity | Evidence identity | State machine | TTL / invalidation | Idempotency / uniqueness | Downstream consumers | Phase 6 mapping |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PublicMarketObservation` (Phase 5 in-memory) | `backend/src/app/market_contracts/observation.py` | `observation_id` UUID (derived) | none (contract forbids tenant) | none | `EvidenceMarketIdentity` | payload `content_hash` + envelope hash | `FORMING` / `FINAL` / correction append | freshness evaluated at consumer time | natural key `(source, venue, market_type, instrument_id, observation_type, source_event_id)` | none persisted | `UNCHANGED` contract; Phase 6 **persists** it. Not a DB table today |
| `HistoricalCandle` | `historical_candles` | UUID PK | none (global) | none | `symbol`+`exchange`+`timeframe` strings | OHLCV values; **no** content hash, venue, market type, finality | mutable `is_stale` flag | `is_stale` / `freshness_note` | `uq_historical_candle (symbol, exchange, timeframe, open_time)` | backtest datasets | `PUBLIC OBSERVATION ADAPTER` for historical OHLCV only; **do not backfill** as executable `PublicMarketObservation` |
| `MarketWatcherObservation` | `market_watcher_observations` | UUID PK | `organization_id` required | optional `related_strategy_id` | `symbol`+`exchange`+`timeframe` | latest price/volume; `data_freshness` string; **no** content hash | `FRESH` / `STALE` / `UNAVAILABLE` | watcher stale-age setting (default 60 min) | **no DB unique** besides PK | bridge; dashboard | `PUBLIC OBSERVATION ADAPTER` **cannot** copy the row globally (tenant-owned). New writes persist global observations then tenant links |
| Phase 5 `TradeEvent` / `CvdWindow` / cursor | `backend/src/app/market_contracts/` | contract IDs | none | none | venue + `PERPETUAL` + instrument | content hashes | gap / warm-up fail-closed | freshness policy | venue natural IDs | first-slice fixtures | `UNCHANGED` contracts; Phase 6 persistence adapters |
| `TradingViewSignal` | `tradingview_signals` | UUID PK | `organization_id` required | optional `setup_definition_id` (**global** `setup_definitions` by name/version), optional `user_strategies` / versions | `symbol`+`timeframe` only; **no** venue/market | redacted payload + `payload_hash`; optional levels | `received` → `validated` / `rejected` / `duplicate` / `candidate_created` | none on row; orchestration applies 900s max age | `uq_tv_signal_org_idempotency`, `uq_tv_signal_org_alert` | inbox APIs; orchestration; optional candidate writer | `TENANT ASSERTION ADAPTER` |
| `ManualChartLevel` | `manual_chart_levels` | UUID PK | org+user | none | `symbol`+`exchange`+optional timeframe | mutable price | `enabled` bool | none | none beyond PK | chart UI; revision append | `DEPRECATED COMPATIBILITY READ` for **current** mutable level (ineligible as evidence) |
| `ManualLevelRevision` | `manual_level_revisions` | UUID PK | org+user | none | `instrument`+`exchange`+`venue`+`market_type` (defaults `unknown`/`unspecified`) | immutable `content_hash`; supersession chain | `valid` bool; append-only | none | `uq_manual_level_revision (level_id, revision_number)` | Phase 3 compiler / first-slice R | `TENANT ASSERTION ADAPTER` (already the §26 manual-level identity) |
| `SetupDetection` (analysis DTO) | `backend/src/app/analysis/types.py` | none | none | `name` string (`liquidity_sweep`, `sfp`, …) | caller-supplied symbol/tf | `metrics` dict | `detected` bool | none | none | watcher detectors; worker scanner | `SETUP ASSESSMENT ADAPTER` (in-memory detector output) |
| `SetupDetectionRecord` | `setup_detections` | UUID PK | **nullable** `organization_id` | `setup_name` string; **no** strategy version / compiled setup | `symbol`+`timeframe` | `detected_metrics` JSON; `detected_at` | append-only fire log | none | **no unique** | worker history UI | `SETUP ASSESSMENT ADAPTER`; **do not backfill** null-org rows |
| `PaperSignal` | `paper_signals` | UUID PK | org+user+run | `strategy_id` + optional `strategy_version_id`; **no** compiled setup | `symbol`+`exchange`+`timeframe` | matched blocks / limitations JSON | `detected` / `not_testable` / `blocked_filter` / `consumed` | none | **no unique**; one row **per scan** | paper trades; alerts; runtime metrics | `SETUP ASSESSMENT ADAPTER` for run-scoped scans; not a candidate |
| `PaperSignalOrchestrationDecision` | `paper_signal_orchestration_decisions` | UUID PK | `organization_id` | copies TV `setup_definition_id` (global) + optional user strategy/version | copies TV symbol/tf/direction | eligibility+**risk** JSON blobs; transition log | `eligible` / `blocked` / `awaiting_review` / `paper_candidate_created` / `paper_proposal_created` / `expired` / `rejected` | `PAPER_SIGNAL_MAX_AGE_SECONDS` (900); `expired_at` | `uq_pso_org_signal`, `uq_pso_org_idempotency` (`pso:{signal.id}`) | candidate/plan/proposal links | `SETUP ASSESSMENT ADAPTER` for market/setup checks; **split** kill-switch/daily-loss/cooldown into `ActionEligibility` (do not store risk on assessment) |
| In-memory `MarketWatcherCandidate` / `ScanCandidate` | scanner DTOs | none | implied by scan org | detector `condition` + version string | symbol+tf | trigger bucket + metrics | ephemeral | none | `dedup_key` string used only when materializing an **alert** | `PaperValidationAlert` | `SETUP ASSESSMENT ADAPTER`; today it writes alerts, not candidates |
| `MarketWatcherScanRecord` | `market_watcher_scan_records` | UUID PK | org | detector version map JSON | symbols/timeframes JSON | scan summary | `ok` / `degraded` / blocked | none | **no unique** | dashboard | `UNCHANGED` scan lineage precursor (Phase 7 durable lineage replaces it) |
| `MarketWatcherBridgeDecision` | `market_watcher_bridge_decisions` | UUID PK | org | optional `strategy_id` | symbol/exchange/tf | observation FK | `TRIGGERED_SCAN` / skip / `FAILED` | none | **no unique** | paper runtime scans; alerts | `DEPRECATED COMPATIBILITY READ` after paper-validation links sit on the common lifecycle (§9) |
| `WatcherOrchestrator` contracts | `backend/src/app/watcher/` in-memory store | lineage/attempt UUIDs | org on `ScanRequest` | optional `strategy_version_id` / `setup_definition_id` on `WatcherPolicyVersion` | watchlist item IDs | opaque freshness/validity tokens | scan attempt statuses | lease/fence | `(org, idempotency_key)` in memory; `candidate_ids` **always emptied** | tests only | `UNCHANGED` in Phase 6 (Phase 7 wires it to the Phase 6 assessment service) |
| `WatchlistItem` | `watchlist_items` | UUID PK | org+user | `strategy_ids` JSON list | `symbol`+`exchange`+`timeframes` JSON | none | `enabled` | none | `uq_watchlist_org_user_symbol_exchange` | watcher scans | `UNCHANGED` (§9 preserve) |
| `StrategySignal` ORM | `strategy_signals` | UUID PK | org | `StrategyId` enum + optional **global** `setup_id` | `symbol`+`timeframe` | `evidence` JSON list | none | none | **no unique** | `TradeProposal.signal_id` | `DEPRECATED COMPATIBILITY READ` — **no current writer** found in services |
| In-memory `schemas.strategy.StrategySignal` | strategy modules | none | implied | `StrategyId` enum | symbol/tf from eval input | module evidence | returned or `None` | none | none | agent `strategy_signals`; proposal generation | `SETUP ASSESSMENT ADAPTER` (legacy global strategy modules) |
| `SetupDefinition` / `GlobalSetupTemplate` | `setup_definitions` / `global_setup_templates` | UUID PK | **global** (`organization_id IS NULL` on template) | `(name, version)` / `StrategyId` | none | JSON rules | `enabled` | none | `uq_setup_name_version`; `uq_global_setup_template_source` | TV name lookup; `TradePlanRevision.setup_definition_id` | `DEPRECATED COMPATIBILITY READ` (§26: cannot occupy executable `CompiledSetupDefinition`) |
| `UserStrategy` | `user_strategies` | UUID PK | org+user | stable tenant strategy | none | none | `enabled` / `paper_eligible` | none | `uq_user_strategy_org_user_name` | versions, paper runs, TV optional FK | `UNCHANGED` |
| `UserStrategyVersion` | `user_strategy_versions` | UUID PK | via strategy | immutable version + `content_hash` | card JSON | `structured_rules` / `pattern_spec` | validation/backtest/paper status fields | none | `uq_user_strategy_version (strategy_id, version)` | compile; paper; plans | `UNCHANGED` |
| `CompiledSetupDefinition` | `compiled_setup_definitions` | UUID PK | org+user | 1:1 `strategy_version_id` | none | AST + `content_hash` | `compile_status` | none | `uq_compiled_setup_strategy_version` | strategy compile/migration | `UNCHANGED` — **required** Phase 6 assessment identity; **unused** by current TV/watcher/orchestration writes |
| `PaperValidationAlert` | `paper_validation_alerts` | UUID PK | org | optional `strategy_id` | via metadata JSON | `dedup_key` + message | delivery + `review_status` | cooldown windows per `PaperAlertType` (e.g. setup 3600s) | **index** `(org, dedup_key, created_at)` **not unique** | drafts; delivery; Telegram | `UNCHANGED` delivery record; **not** a candidate |
| `PaperValidationDraft` | `paper_validation_drafts` | UUID PK | org | copied condition string | symbol/tf | thesis/checklist | `draft` / `archived` / `cancelled` + prep status | none | `uq_paper_validation_drafts_org_alert_status` | candidate queue | `DOWNSTREAM PAPER VALIDATION CONSUMER` (human prep) |
| `PaperValidationCandidate` | `paper_validation_candidates` | UUID PK | org | optional strategy/version (research/TV); often **null** on alert-draft path | nullable symbol/tf | optional `evidence_snapshot` JSON; **no** window hash | `queued` / `reviewing` / `archived` | **none** | partial unique `ix_paper_validation_candidates_org_draft_active`; `uq_pvc_org_backtest_active`; **no semantic window unique** | run plans, sessions, **`TradePlanRevision.candidate_id`**, TV/PSO FKs | `DOWNSTREAM PAPER VALIDATION CONSUMER` |
| `PaperValidationRunPlan` | `paper_validation_run_plans` | UUID PK | org | copied from candidate | copied | planned rules text | `planned` / `needs_revision` / `archived` | `max_duration_minutes` planning field only | partial unique active `(org, candidate_id)` | sessions | `DOWNSTREAM PAPER VALIDATION CONSUMER` |
| `PaperValidationRunSession` + observations + result | session tables | UUID PKs | org | none (explicitly **no** strategy/engine FKs) | copied symbol/tf | manual notes/prices | running/completed/cancelled; one result/session | session clock | one **running** session per plan; one result per session | learning/coaching reads | `DOWNSTREAM PAPER VALIDATION CONSUMER` |
| `PaperValidationRun` / `PaperTrade` | paper runtime | UUID PK | org+user | strategy + optional version | symbol/exchange/tf | runtime metrics | run/trade enums | none | no semantic candidate unique | scheduler; journal opt-in | `DOWNSTREAM PAPER VALIDATION CONSUMER` (engine path, separate from Slice 80–83 queue) |
| `TradeProposal` | `trade_proposals` | UUID PK | org+user | `StrategyId` enum + optional `user_strategy_id`; optional `signal_id` → `strategy_signals` | symbol+tf | levels on the proposal | proposal status | none on proposal | `uq_trade_proposal_tenant_owner (id, org, user)` | approvals; PSO approve path | `UNCHANGED` plan root (Phase 1); must bind canonical `Candidate` later, not PVC |
| `TradePlanRevision` | `trade_plan_revisions` | UUID PK | org+user+account | **`setup_definition_id` → global `setup_definitions`**; `strategy_version_id` | evidence vs execution identities in payload | `content_hash`; `valid_from`/`valid_until` | immutable | `valid_until` | unique content hash; binding unique | approval/execution | `UNCHANGED` Phase 1 plan; **FK `candidate_id` currently points at PVC** — remap, do not backfill blindly |
| `UserNotificationPreferences` | `user_notification_preferences` | UUID PK | org+user | none | none | none | digest / quiet hours | quiet hours | `uq_user_notification_preferences_org_user` | alert delivery routing | `UNCHANGED` |
| Alert delivery payload | `AlertDeliveryService` | n/a | org | none | none | `idempotency_key=alert-deliver:{alert.id}` | pending/delivered/failed/skipped/disabled | retries | **per alert row**, not per canonical candidate | Telegram/webhook providers | `UNCHANGED` until Phase 8 outbox; must later unique **per candidate revision + delivery-policy** (§26) |
| `WorkerNotifier` | process-only | n/a | none (system) | none | none | none | one-way send | quiet hours helpers | none durable | configured channels | `UNCHANGED`; must not create candidates |
| `LessonCandidate` | `lesson_candidates` | UUID PK | org+user | optional strategy | none | journal lesson | pending_review | none | none relevant | coaching | `UNCHANGED` (not a trading candidate) |
| `BloFinDemoSyncSnapshot` | `blofin_demo_sync_snapshots` | UUID PK | org | none | market_context JSON | provenance JSON | health enum | `is_stale` | none besides PK | PSO market-context check | `UNCHANGED` (eligibility input, not setup truth) |

---

## 3. Entity detail (inspected write paths)

### 3.1 Public market facts

**Current:** Phase 5 defined `PublicMarketObservation` in
`backend/src/app/market_contracts/observation.py`. There is **no**
`public_market_observations` table (`rg` over `backend/src/app/db` is empty).

`HistoricalCandle` is the only global persisted OHLCV store. Unique
`(symbol, exchange, timeframe, open_time)`. It lacks venue/market type, canonical instrument,
finality, adapter version, and content hash required by §25.

`MarketWatcherObservation` is a **tenant copy** of a latest price/volume snapshot written by
`MarketWatcherService.scan`. Status is `FRESH|STALE|UNAVAILABLE`. No unique natural key; each
scan appends. `related_strategy_id` / `related_paper_validation_run_id` are optional tenant
links.

**Mapping:** new watcher/runtime fetches persist **global** `PublicMarketObservation` /
`TradeEvent` / `CvdWindow` first (Phase 6). Existing tenant observation rows stay
compatibility reads. Do not upsert tenant rows into the global store.

### 3.2 TradingView intake (tenant assertion)

**Source of truth:** `TradingViewSignal` via `TradingViewSignalService.intake_webhook`.

**API (compatibility surfaces):**

- `POST /webhooks/tradingview` (signed, flag-gated)
- `GET /tradingview/signals`
- `GET /tradingview/signals/{id}`
- `POST /tradingview/signals/{id}/create-candidate`

Frontend inbox: `/tradingview-signals`.

**Uniqueness:** `(organization_id, idempotency_key)` and `(organization_id, external_alert_id)`.
Default `idempotency_key = alert_id`. Same key + different `payload_hash` is rejected (not
silently merged).

**Setup identity:** if `setup_name` **and** `setup_version` are present, lookup is
`SetupDefinition.name == … AND version == …` — a **global** table, not
`CompiledSetupDefinition`, not org-scoped. Unresolved name is **not** a validation error;
`setup_definition_id` stays null. Orchestration then fails only when
`paper_signal_require_setup_when_named` is true.

**Candidate write (today, competing authority):**
`_create_candidate_internal` always creates a new `PaperValidationAlert`
(`dedup_key=tradingview_signal:{row.id}`), a ready-for-validation `PaperValidationDraft`, and a
`PaperValidationCandidate` with `promotion_source=tradingview_signal`. Then it sets
`TradingViewSignal.candidate_id`. Re-entry returns that pointer.

Flags: `tradingview_webhook_enabled=false`, `tradingview_auto_create_candidate=false`.

**§25 rule:** this payload is tenant-confidential. It must never be stored as
`PUBLIC_EXTERNAL_MARKET_SIGNAL` or participate in global observation dedupe.

**Phase 6:** persist `TenantExternalAssertion` (org, source event id, redacted hash, typed
venue/market/instrument **claim**, strategy/setup **references**, expiry). Assessment consumes
the assertion **plus** selected public observations. Stop minting PVC from this path.

### 3.3 Paper-signal orchestration (mixed assessment + eligibility)

**Source of truth:** `PaperSignalOrchestrationDecision`.

**API:**

- `GET /paper-signal-orchestration/decisions`
- `GET /paper-signal-orchestration/decisions/{id}`
- `POST /paper-signal-orchestration/signals/{id}/evaluate`
- `POST /paper-signal-orchestration/signals/{id}/orchestrate`
- `POST /paper-signal-orchestration/decisions/{id}/approve-paper-proposal`

**State machine (current):**
`eligible | blocked | awaiting_review | paper_candidate_created | paper_proposal_created | expired | rejected`.
Transitions JSON-append. Terminal set: proposal-created, rejected, expired.

**This is the closest existing *lifecycle shape* to §6**, which is why §6 says fusion
“generalizes the useful transition/reason-code shape already present in paper-signal
orchestration.” It is **not** setup truth:

- Eligibility checks mix signal quality (validated, fresh, timeframe, direction, confidence,
  setup/strategy link, level consistency, opposite TV signal in
  `PAPER_SIGNAL_CONFLICT_WINDOW_SECONDS`) with **account** gates (kill switch, daily loss,
  cooldown, paper mode, BloFin snapshot).
- Advance in `candidate_only` / `approval_required` calls
  `TradingViewSignalService._create_candidate_internal` — i.e. it treats PVC as the candidate.
- Idempotency is **one decision per TV signal**, not one candidate per
  `CanonicalEvidenceWindowV1`.
- TTL is wall-clock age of `occurred_at or received_at` vs 900s, not assessment `valid_until`
  derived from a freshness policy over selected observations.

**Phase 6 split (required by §5/§6, not optional):**

| Current check | Target object |
|---|---|
| validated / direction / named setup / compiled-setup once required / public evidence freshness / pattern rules | `SetupAssessment` |
| kill switch, daily loss, cooldown, exposure, venue snapshot, paper mode | `ActionEligibility` |
| TV payload itself | `TenantExternalAssertion` |
| PVC create | **stop**; after `CONFIRMED_SETUP` upsert canonical `Candidate`, then optionally enqueue PVC |

### 3.4 Watcher + detectors + worker

**Manual scanner:** `MarketWatcherService.scan` (`POST /market-watcher/scan`).

Flow: fetch OHLCV via `MarketDataService` → `detect_candidates` +
`detect_setup_candidates` → in-memory `ScanCandidate` → unless `dry_run`,
`PaperAlertService.create` with detector `dedup_key`:

```text
market_watcher:{symbol}:{timeframe}:{detection.name}:{direction|none}:{trigger_bucket}
```

`trigger_bucket` is `f"{level:.4f}"` or `none`. Cooldown for
`SETUP_SIGNAL_DETECTED` is **3600 seconds**, org-scoped, **application-level** (not a unique
constraint). Detector versions are hardcoded `1.0.0` in
`SETUP_DETECTOR_VERSIONS`.

`MarketWatcherCandidate` in the scan response is **not** `PaperValidationCandidate`.
Humans later: alert review → draft → `POST /paper-validation/drafts/{id}/queue`.

**Worker scanner:** `backend/src/app/workers/scanner.py` persists `SetupDetectionRecord`
with **no `organization_id`**, **no `scan_run_id`**, **no unique key**, on every fired
detection every cycle. Same semantic setup therefore appends unbounded duplicate rows.

**Bridge:** `MarketWatcherBridgeService.tick` matches tenant observations to active
`PaperValidationRun` rows and may trigger `PaperValidationRuntimeService` scans (creating
`PaperSignal` rows). Skip paths can emit `DATA_STALE` / `STRATEGY_BLOCKED` alerts.
§9: retire the bridge only after paper-validation links are represented by the common
lifecycle.

**Phase 7 orchestrator (AT-042):** `WatcherOrchestrator` is isolated, in-memory, and
**explicitly does not model candidate lifecycle**. `candidate_ids` are forced to `()`.
Phase 6 must still publish the assessment/candidate service that Phase 7 will call.

### 3.5 Paper validation candidate queue (Slice 80–83 + AT-035)

**PVC uniqueness actually enforced:**

1. Partial unique `(organization_id, draft_id)` while status ∈ `{queued, reviewing}`.
2. Partial unique `(organization_id, backtest_run_id)` while backtest_id IS NOT NULL and
   status ∈ `{queued, reviewing}` (research promotion).
3. Application `get_active_for_draft` / `get_active_for_backtest_run`.
4. TV/PSO: pointer on `TradingViewSignal.candidate_id` / decision row — **not** a PVC unique
   index on signal or window.

There is **no** unique key on `(org, symbol, timeframe, direction, strategy, evidence window)`.
Archived rows can be followed by a new queued row for the same draft after the partial unique
releases. Draft uniqueness includes `status`, so an archived draft plus a new draft for the
same alert is allowed.

**Writers of PVC (duplicate semantic candidates):**

| Writer | Service | Key it thinks is unique | Creates alert+draft too? |
|---|---|---|---|
| Alert-draft queue | `PaperValidationCandidateService.queue_from_draft` | active row per draft | no (draft exists) |
| TradingView manual | `POST .../create-candidate` | TV `candidate_id` pointer | **yes**, synthetic alert/draft |
| TradingView auto | flag `tradingview_auto_create_candidate` | same | yes |
| Orchestration advance | `PaperSignalOrchestrationService._advance_by_mode` | same TV pointer | yes (shared helper) |
| Research promotion | `ResearchValidationService._create_candidate` | active row per backtest run | yes, synthetic alert/draft |

Watcher scans **do not** write PVC; they write alerts that a human may later queue. That is a
second, delayed mint of a “candidate” for the same detector fire.

**Run plan / session:** downstream of PVC. One active plan per candidate; one running session
per plan; one result per session. Session rows **intentionally omit** strategy/engine FKs.

### 3.6 Paper runtime signals (Slice 39)

`PaperValidationRuntimeService` inserts a **new** `PaperSignal` on every scan of a
`PaperValidationRun`. Status may be `detected` / `not_testable` / `blocked_filter`; auto-paper
mode may open a `PaperTrade` and mark the signal `consumed`.

This is run-scoped **evaluation output**, not canonical candidate identity. Strategy identity
is `user_strategies` / optional version. No compiled-setup FK. No evidence-window hash.

Bridge-triggered scans and scheduler ticks both create these rows, independently of Slice 80
PVC and independently of watcher alerts.

### 3.7 Proposals and Phase 1 plan binding

`TradeProposal` remains the plan root. PSO `approve_paper_proposal` creates a proposal via
`ProposalService.create` with `signal_id=None`, `strategy_id=MANUAL_REVIEW`,
`approval_required=True`. It does **not** set `TradeProposal` to the PVC id.

`TradePlanRevision.candidate_id` is **NOT NULL** and FKs
`paper_validation_candidates.id` (migration
`3e4e11598fa9_phase_1_wave_1b_plan_authorization_`).
`setup_definition_id` FKs **global** `setup_definitions`.

Phase 6 cannot pretend PVC is the §5 `Candidate`. The plan FK must later point at the
canonical candidate (or a compatibility view). Existing PVC-backed revisions are
**ambiguous** relative to `CanonicalEvidenceWindowV1` and must not be auto-backfilled.

### 3.8 Manual levels

`ManualLevelService` keeps a mutable `ManualChartLevel` and appends `ManualLevelRevision`
with canonical `content_hash`. Unique `(level_id, revision_number)`.

§26: mutable current levels are ineligible as evidence; the first-slice resistance revision
must exist before trigger cutoff and is part of `CanonicalEvidenceWindowV1`.

`venue` defaults to `"unknown"` and `market_type` to `"unspecified"` — **incompatible** with
§25 `EvidenceMarketIdentity` until writers require explicit venue/market/instrument.

### 3.9 Notifications and delivery

`PaperAlertService.create` cooldown-dedupes by `dedup_key` within type-specific windows.
`dedup_key` is **not** unique in the database (`ix_paper_validation_alerts_dedup_key` includes
`created_at`).

Delivery idempotency is `alert-deliver:{alert.id}` — **one key per alert row**, not per
canonical candidate revision. Worker and watcher can therefore emit distinct alert rows (and
later distinct deliveries) for one semantic setup.

`UserNotificationPreferences` stays a routing config (`UNCHANGED`).
`WorkerNotifier` is outbound-only and has no candidate identity.

§26: “One delivery-intent key is unique per candidate revision and delivery-policy version.”
That key does not exist yet. Introducing it **before** candidate convergence duplicates
alerts; introducing it **after** without suppressing legacy `dedup_key` also duplicates.

### 3.10 Persistence firewall kinds (current)

`backend/src/app/core/persistence_firewall.py` already labels:

- `PaperValidationCandidate`, `TradingViewSignal`, `PaperSignalOrchestrationDecision`,
  `StrategySignal` → `PersistenceKind.CANDIDATE`
- `PaperSignal`, drafts/plans/sessions → `PAPER_VALIDATION`
- `PaperValidationAlert`, notification prefs → `NOTIFICATION`
- `MarketWatcherObservation` / scan / bridge / watchlist → `WATCHER`
- `CompiledSetupDefinition` / `SetupDefinition` / `GlobalSetupTemplate` → `SETUP`

`SetupDetectionRecord` and `MarketScanRun` are **absent** from `_MODEL_KIND` and would
classify as `OTHER`. Phase 6 adapters must be added to this map when tables land; this audit
does not change the firewall.

---

## 4. Critical questions (repository evidence)

### 4.1 Which existing object currently behaves most like setup truth?

**Semantic “is this setup present?” without account risk**

Closest: in-memory `SetupDetection` / watcher `ScanCandidate` from
`market_watcher_setup_detectors.py`, persisted loosely as `SetupDetectionRecord` (worker) or
as a `PaperValidationAlert` (manual scan). `PaperSignal` is the same question scoped to one
paper-validation run and one user strategy version.

**Lifecycle / reason-code shape**

Closest: `PaperSignalOrchestrationDecision` (explicit transitions, reason codes, expiry).
§6 already names this shape. It is contaminated with `ActionEligibility` concerns.

**None of these is `SetupAssessment`:** they lack compiled-setup identity, observation IDs,
content hash, `valid_until` from a freshness policy, and the
`NO_SETUP → WATCH → PARTIAL_MATCH → CONFIRMED_SETUP` machine.

### 4.2 Which behaves most like a candidate?

**Product currently treats `PaperValidationCandidate` as candidate authority.**
Evidence: TV/PSO write it; research promotion writes it; Slice 80 queue is named “candidate”;
`TradePlanRevision.candidate_id` FKs it; persistence firewall kind is `CANDIDATE`.

**§26 forbids that reading.** PVC is a validation queue. In-memory
`MarketWatcherCandidate` is also named “candidate” but materializes as an **alert**.

Canonical `Candidate` does not exist as a table.

### 4.3 Which records can safely map one-to-one?

Only when **all** of: non-null org, exact `UserStrategyVersion`, existing
`CompiledSetupDefinition`, typed venue/market/instrument, and a reconstructable §26
preimage.

**Practically one-to-one (after adapters, not as row copies):**

| From | To | Condition |
|---|---|---|
| `TradingViewSignal` (validated, org-scoped, stable `external_alert_id`) | `TenantExternalAssertion` | keep tenant isolation; do not copy into public observations |
| `ManualLevelRevision` with explicit venue/market/instrument and valid hash | assertion/evidence input already in §26 | default `unknown`/`unspecified` venue/market **fails** this |
| `CompiledSetupDefinition` | `setup_definition_id` on assessment/candidate | already 1:1 with strategy version |
| `UserStrategyVersion` | `strategy_version_id` | already immutable |

**Not one-to-one:** PVC, PaperSignal, SetupDetectionRecord, MarketWatcherObservation,
StrategySignal, orchestration decisions, watcher alerts, HistoricalCandle.

### 4.4 Which require many-to-one convergence?

| Many current rows | One target |
|---|---|
| Worker `SetupDetectionRecord` (unbounded per cycle) + watcher alerts (hourly dedupe) + `PaperSignal` (per scan) + TV signal + PVC | one `SetupAssessment` then one `Candidate` per §5 key |
| TV auto-candidate + TV manual create-candidate + PSO orchestrate (same helper, usually one PVC via pointer) **plus** a human-queued PVC from a watcher alert on the same symbol/tf/direction | one canonical candidate |
| Research PVC (unique per backtest run) **plus** live watcher/TV PVC for the same strategy version | one candidate (research PVC stays a **downstream evaluation** of that candidate, keyed by backtest run) |
| Opposite or adjacent bars / trigger buckets (`:.4f`) | policy-selected window; §26: optional evidence enriches assessment, new candidate only when required role/bound/direction/venue changes |
| `MarketWatcherObservation` per scan + `HistoricalCandle` + future `PublicMarketObservation` | one public observation per natural source event |

### 4.5 Which identities are incompatible with CanonicalEvidenceWindowV1?

An identity is incompatible if it cannot populate the §26 preimage without invention.

| Identity | Missing vs §26 |
|---|---|
| Watcher `dedup_key` | no org in key string (applied only as query filter); no compiled-setup hash; no observation hashes; trigger **price bucket**; no venue/market; no interval bounds; no fusion/finality/freshness policy versions |
| TV `(org, alert_id)` / `(org, idempotency_key)` | no public observation hashes; no compiled setup (global name lookup only); no venue/market/instrument; `occurred_at` optional; payload hash includes receive-path bytes (`sha256(raw_body)`), which §26 would exclude |
| PSO `pso:{signal.id}` | one-to-one with TV row, not with evidence window |
| PVC PK / draft active unique | no window hash; strategy/version often null; condition is a free string (`tradingview_signal` or detector name) |
| `PaperSignal` PK | per scan insert; no window hash |
| `SetupDetectionRecord` | org nullable; setup is a detector **name**; no compiled setup |
| `StrategySignal` | `StrategyId` enum + global setup; no compiled setup |
| `TradePlanRevision.candidate_id` | points at PVC; `setup_definition_id` is global template |
| `HistoricalCandle` unique | symbol/exchange/timeframe/open_time; no venue/market/finality/content hash |
| `ManualLevelRevision` defaults | `venue=unknown`, `market_type=unspecified` |
| Alert `dedup_key` | delivery/cooldown identity, not evidence window |
| Watcher orchestrator `idempotency_key` on `ScanRequest` | scan attempt identity; explicitly excluded from request hash; not a candidate key |

### 4.6 Which existing workflow currently creates duplicate semantic candidates?

**Confirmed duplicate minting of PVC-or-alert “candidates” for one market event:**

1. **Watcher scan → alert** (`dedup_key` hourly) **and** **worker `SetupDetectionRecord`**
   (no dedupe) **and** **paper runtime `PaperSignal`** (if a matching run exists / bridge
   ticks). Three lineages, zero shared window hash.
2. **Human queues PVC from the watcher alert** while **TV webhook** (same symbol/tf/direction,
   different `alert_id`) creates another PVC via `_create_candidate_internal`.
3. **TV create-candidate** and **PSO orchestrate** share a pointer **per TV row**, but two TV
   rows (two `alert_id`s) yield two PVCs.
4. **Research promotion** unique-per-`backtest_run_id` creates a PVC that can coexist with a
   live watcher/TV PVC for the same strategy version (different unique indexes, no window key).
5. **Alert cooldown expiry** (3600s) allows a second `SETUP_SIGNAL_DETECTED` alert, then a
   second draft/PVC, while the first PVC is still `queued`/`reviewing` if it was tied to a
   **different** draft/alert.
6. Naming collision: scan response `candidates[]` are alerts; Slice 80 rows are also
   “candidates”; Phase 1 plans FK the latter.

PSO `observe_only` does **not** mint PVC; `candidate_only` / `approval_required` do.

### 4.7 Which APIs must remain compatibility surfaces?

Keep request/response shapes until a separately approved hide/delete task (§15 Phase 12).
Phase 6 adds adapters behind them; it does not remove routes.

| Surface | Why it must remain |
|---|---|
| `POST /webhooks/tradingview` + `GET /tradingview/signals*` | tenant inbox; signed intake |
| `POST /tradingview/signals/{id}/create-candidate` | existing confirm phrase; must later enqueue validation **from canonical candidate**, not mint authority |
| `/paper-signal-orchestration/*` | existing queue/detail/evaluate/orchestrate/approve |
| `/market-watcher/*` including scan, observations, bridge | UI + e2e; manual dry-run must call the **same** evaluation pipeline (§9) once it exists |
| `/paper-validation/drafts*`, `/candidates*`, `/plans*`, `/run-sessions*` | Slice 78–83 UI |
| `/paper-validation` scheduler/runtime/signals/trades | engine path |
| `/alerts*` including setup-alert review + draft create | human review |
| `/notifications/preferences*` | delivery routing |
| `/manual-levels*` | chart levels |
| `/proposals*` | plan root |
| `/research-validation/*` | promotion into validation queue |
| Frontend routes `/tradingview-signals`, `/paper-signal-orchestration`, `/paper-validation/candidates`, market-watcher pages | listed in `phase-b-redirects.ts` as retained deep links |

### 4.8 Which writes must eventually route through the new canonical service?

All **setup-present / candidate-create** writes:

- watcher manual scan (non-dry-run persistence of assessments/candidates)
- worker market scan detections
- TradingView validated assertions (assessment command; not PVC mint)
- paper-signal orchestration evaluate/orchestrate (assessment + eligibility split)
- strategy-module in-memory signals if they remain an executable source
- **not** PVC queue, run-plan, session, research promotion, or paper-runtime **trade** opens —
  those consume a canonical candidate (or remain evaluation-only)

Public OHLCV/trade/CVD persistence from those scans must go through observation adapters
**before** assessment (§9 steps 3–6).

### 4.9 Which existing tables must not be backfilled because ownership or semantic identity is ambiguous?

Do **not** copy these rows into `PublicMarketObservation`, `SetupAssessment`, or `Candidate`:

1. `setup_detections` with `organization_id IS NULL` (worker writer).
2. `market_watcher_observations` (tenant-owned public-looking facts; no natural source event
   id, no content hash, no venue/market type).
3. `historical_candles` as executable observations (no finality/venue/market/hash contract).
4. `paper_validation_candidates` lacking `strategy_version_id` **or** compiled setup **or**
   reconstructable window (alert-draft and many TV rows).
5. `paper_signals` (per-scan, run-scoped, no window).
6. `strategy_signals` (no current writer; global `StrategyId`; optional global setup).
7. `paper_validation_alerts` (delivery/review records).
8. `paper_signal_orchestration_decisions` as assessments (mixed risk; one-per-TV-signal).
9. `trade_plan_revisions` as proof of a canonical candidate (PVC + global setup FKs).
10. `manual_chart_levels` (mutable).
11. `manual_level_revisions` with `venue=unknown` / `market_type=unspecified`.
12. `tradingview_signals` into public observation indexes (tenant confidential).

§26 migration order for setups still applies: add new tables and nullable compatibility
references **without rewriting** legacy rows; dual-read; then non-null where the owning
workflow is migrated.

### 4.10 How should PaperValidationCandidate become downstream validation rather than candidate authority?

Required sequence (adapters only; no invention):

1. Introduce canonical `Candidate` with the §5 unique key and
   `CanonicalEvidenceWindowV1`.
2. Add **nullable** `canonical_candidate_id` (and later revision) on PVC, TV signal, PSO
   decision, run plan, and `TradePlanRevision` — without rewriting old FKs in place.
3. Stop all mint paths (`_create_candidate_internal`, `queue_from_draft` as authority,
   research `_create_candidate` as authority). Replace with: require an existing canonical
   candidate in `CONFIRMED_SETUP` / `ACTIVE`, then insert PVC as a **queue row** unique on
   `(organization_id, canonical_candidate_id, validation_policy_version)` (or research:
   `(canonical_candidate_id, backtest_run_id)`).
4. Keep Slice 80–83 APIs as compatibility reads/writes against PVC, projecting canonical
   state.
5. Remap `TradePlanRevision.candidate_id` to canonical `Candidate` only after dual-read
   fixtures pass. Until then new revisions must not be created from window-less PVC rows.
6. Retire PVC as firewall `CANDIDATE` kind; it becomes `PAPER_VALIDATION`.

Research PVC stays a **promotion into the validation queue**, unique per backtest run, never
a second live candidate.

### 4.11 How should TradingView remain a tenant assertion rather than global public observation?

- Keep `organization_id` mandatory; keep webhook authz/signature/replay skew.
- Persist `TenantExternalAssertion` with tenant-scoped uniqueness on
  `(organization_id, source, source_event_id)` (today: `external_alert_id` / idempotency key).
- Hashes: semantic content hash **excluding** receive/raw transport bytes; store redacted
  raw hash separately as today (`payload_hash` currently hashes raw body — replace in the
  adapter, do not reuse as `PublicMarketObservation.content_hash`).
- Resolve strategy/setup only to **tenant** `UserStrategyVersion` +
  `CompiledSetupDefinition`. Global `SetupDefinition` name/version lookup remains a
  compatibility alias (`GlobalSetupTemplate`), never the executable field.
- Assessment command: assertion ID + selected **public** observation hashes. Missing public
  evidence → cannot `CONFIRMED_SETUP`.
- Never insert into global observation indexes, caches, or dedupe.
- `PUBLIC_EXTERNAL_MARKET_SIGNAL` stays illegal for TradingView (§5/§25).

### 4.12 What exact migration order avoids data loss and duplicate alerts?

Dependency-respecting order from §15 + §26 + the duplicate-alert constraint in §26
(“delivery uniqueness remains separate” and “one delivery-intent key per candidate
revision”):

1. **Persist public observations** (Phase 5 contracts → tables) with global natural-key
   uniqueness. Do not backfill tenant watcher rows or historical candles into executable
   observations.
2. **Persist `TenantExternalAssertion`** for new TradingView intakes. Dual-write to
   `tradingview_signals` for compatibility APIs. Do **not** auto-create PVC.
3. **Persist `SetupAssessment` + `ActionEligibility`** as separate immutable rows. Adapter:
   PSO evaluate writes assessment (market/setup) + eligibility (risk) instead of one mixed
   decision; keep PSO row as compatibility projection.
4. **Persist canonical `Candidate`** with §5 unique constraint and terminal
   non-resurrection. All source adapters (watcher detectors, TV assertion, paper-runtime
   pattern eval) call one upsert.
5. **Freeze duplicate minting** behind flags still off: disable
   `tradingview_auto_create_candidate` remains false; PSO default `observe_only` remains;
   watcher/bridge/orchestration flags remain false until dual-write is proven.
6. **Point PVC at canonical candidate** (nullable FK). New queue/research/TV-confirm writes
   require the FK. Old PVC rows stay readable, uncopied.
7. **Delivery:** add unique delivery-intent key `(canonical_candidate_revision_id,
   delivery_policy_version)` **before** enabling any path that would emit alerts from both
   legacy `dedup_key` and the new key. Until then, keep emitting **only** the legacy alert
   row for compatibility, or only the new key — never both. Worker `SetupDetectionRecord`
   must not gain a parallel notifier path.
8. **Remap `TradePlanRevision.candidate_id`** after candidate dual-read parity.
9. **Retire competing writes** (bridge as candidate/scan authority, TV PVC mint, PSO PVC
   mint, worker unowned detections) only after row/link/hash reports and zero
   unmapped-reference reports pass (§26 steps 5–7).
10. Phase 7 then unifies watcher manual/worker on this service; Phase 8 then binds Telegram
    outbox to the delivery-intent key.

**Data-loss avoidance:** no deletes; no in-place rewrite of PVC, TV, alerts, or plan
revisions; nullable compatibility FKs first; dual-read; then non-null on migrated
workflows only.

**Duplicate-alert avoidance:** do not enable watcher persistence + TV candidate mint +
bridge scans + worker notifier on the same semantic event while uniqueness is still
per-source.

---

## 5. Compatibility API inventory (must remain)

Exact current write/read routes that Phase 6 may **adapt behind**, not remove.

**TradingView** (`backend/src/app/api/routes/tradingview.py`)

- `POST /webhooks/tradingview`
- `GET /tradingview/signals`
- `GET /tradingview/signals/{signal_id}`
- `POST /tradingview/signals/{signal_id}/create-candidate`

**Paper-signal orchestration** (`paper_signal_orchestration.py`)

- `GET /paper-signal-orchestration/decisions`
- `GET /paper-signal-orchestration/decisions/{decision_id}`
- `POST /paper-signal-orchestration/signals/{signal_id}/evaluate`
- `POST /paper-signal-orchestration/signals/{signal_id}/orchestrate`
- `POST /paper-signal-orchestration/decisions/{decision_id}/approve-paper-proposal`

**Market watcher** (`market_watcher.py`)

- `GET /market-watcher/status`, `/summary`, `/monitoring`
- `POST /market-watcher/scan`
- `GET /market-watcher/scans/recent`, `/observations`, `/history`
- `GET /market-watcher/bridge/status`, `POST /bridge/tick`, `GET /bridge/history`

**Paper validation queue + engine** (`paper_validation.py`) — drafts, candidates, plans,
sessions, observations, results, scheduler, runtime scans/ticks, signals, trades.

**Alerts / notifications** (`alerts.py`, `notifications.py`) — list/summary/review/draft,
delivery pending/deliver/telegram/preview/test, preferences.

**Adjacent unchanged surfaces:** `/manual-levels`, `/proposals`, `/research-validation`.

---

## 6. Recommended Phase 6 implementation slices (map only)

These slices implement §15 Phase 6. They do not enable flags.

1. Observation persistence adapters (OHLCV/trade/CVD) + global uniqueness tests.
2. `TenantExternalAssertion` table + TV dual-write (no PVC mint).
3. `SetupAssessment` / `ActionEligibility` tables + PSO split adapter (evaluate-only).
4. Canonical `Candidate` uniqueness + watcher/detector/TV assessment command (dry-run
   default).
5. PVC `canonical_candidate_id` + stop competing mint in code paths still flag-gated.
6. Delivery-intent unique key design (implementation may wait for Phase 8 outbox, but the
   key must be specified before any dual-alert enablement).
7. Compatibility read projections for existing APIs; contract tests that one window → one
   candidate across watcher + TV + detector.

Out of Phase 6: watcher distributed lock/health (Phase 7), Telegram outbox (Phase 8),
execution (already Phase 1, Mode D still forbidden).

---

## 7. Mapping completeness

| Gate | Result |
|---|---|
| Every named legacy path in the task prompt inspected | **PASS** (see §8) |
| Every relevant persisted/in-memory entity classified | **PASS** |
| One-to-one safe backfill identified without invention | **FAIL for PVC / detections / watcher observations / mixed PSO** — classified as many-to-one or do-not-backfill rather than invented 1:1 maps |
| Canonical mappings complete | **PASS** as an implementation map; **not** a claim that identities already match `CanonicalEvidenceWindowV1` |

Ambiguous identities are listed in §4.5 and §4.9; they are mapping **outputs**, not skipped
entities.

---

## 8. Inspection proof

Audit HEAD: `2570a84768137cfae93475ae0905d26d1cb6b991`. Working tree vs that SHA before this
document: empty.

**Named paths present (all `OK`):**

`paper_signal_orchestration_service.py`, `tradingview_signal_service.py`,
`paper_validation_candidate_service.py`, `paper_validation_runtime_service.py`,
`paper_validation_draft_service.py`, `paper_validation_run_plan_service.py`,
`paper_validation_run_session_service.py`, `paper_validation_session_observation_service.py`,
`paper_validation_session_result_service.py`, `research_validation_service.py`,
`market_watcher_service.py`, `market_watcher_bridge_service.py`,
`market_watcher_scanner.py`, `market_watcher_setup_detectors.py`,
`manual_level_service.py`, `proposal_service.py`, `paper_alert_service.py`,
`alert_delivery_service.py`, `compiled_setup_service.py`, matching repositories and API
routes, `workers/scanner.py`, `workers/repository.py`, `workers/notifier.py`,
`watcher/orchestrator.py`, `watcher/contracts.py`, `market_contracts/observation.py`,
`db/models.py`, target architecture.

**Commands run during audit (re-runnable):**

```bash
git rev-parse HEAD
git diff --stat 2570a84768137cfae93475ae0905d26d1cb6b991

rg -n "class (PaperSignalOrchestrationDecision|PaperValidationCandidate|TradingViewSignal|SetupDetectionRecord|MarketWatcherObservation|ManualLevelRevision|CompiledSetupDefinition)" \
  backend/src/app/db/models.py

rg -n "_create_candidate|queue_from_draft|PaperValidationCandidate\(" backend/src/app --glob '*.py'

rg -n "CanonicalEvidenceWindowV1|class SetupAssessment|TenantExternalAssertion" backend/src/app --glob '*.py'
# expected: no SetupAssessment/TenantExternalAssertion/CanonicalEvidenceWindowV1 types

rg -n "PublicMarketObservation|public_market_observation" backend/src/app/db
# expected: empty (contract only)

rg -n "uq_pso_|uq_tv_signal_|ix_paper_validation_candidates_org_draft_active|uq_pvc_org_backtest" \
  backend/src/app/db
```

**Unique keys verified in models/migrations:**

- `uq_tv_signal_org_idempotency`, `uq_tv_signal_org_alert`
- `uq_pso_org_signal`, `uq_pso_org_idempotency`
- `uq_paper_validation_drafts_org_alert_status`
- partial unique `ix_paper_validation_candidates_org_draft_active`
- partial unique `uq_pvc_org_backtest_active`
- partial unique active run plan / running session; unique session result per session
- `uq_compiled_setup_strategy_version`, `uq_setup_name_version`
- `uq_manual_level_revision`
- `uq_historical_candle`
- `uq_watchlist_org_user_symbol_exchange`
- alert `dedup_key` **indexed, not unique**

**Negative proof:** no DB tables for `SetupAssessment`, `ActionEligibility`, canonical
`Candidate`, `TenantExternalAssertion`, or persisted `PublicMarketObservation` at this SHA.

---

## 9. Safety notes

- This map does not enable watcher, TradingView, orchestration, bridge, scheduler, or
  external delivery.
- Real trading remains disabled. No order/withdraw/leverage change is in scope.
- `LessonCandidate` is a journal/coaching object and is not part of the trading candidate
  lineage.
- Persistence-firewall kind `CANDIDATE` today includes PVC, TV, and PSO — evidence that the
  repository currently treats those as candidate authorities; Phase 6 must change that
  **classification in a later implementation task**, not in this document-only audit.
