# AlphaTrade Agentic Redesign — Independent Architecture Review

**Review base:** draft PR #64, branch `cursor/agentic-redesign-phase0-audit-86fd`,
head `0c264365aea4cadf000d133cec71063a498b3af5`

**Documents reviewed:**

- `docs/redesign/agentic_redesign_phase0_audit.md`
- `docs/redesign/agentic_redesign_target_architecture.md`

**Scope:** repository and architecture review only. No product code, migrations, deployment
configuration, feature flags, external delivery, exchange connectivity, or trading capability
was changed or enabled.

## 1. Executive verdict

**Final implementation readiness verdict: REDESIGN REQUIRED.**

The proposal has the right high-level direction: retain the modular monolith, keep deterministic
risk and exchange safety authoritative, extend the existing strategy and journal domains, and
unify surveillance before enabling automation. The checked-in defaults and BloFin host guards
also preserve the required paper/demo-only posture.

It is not ready to implement as written. Four critical contracts are unresolved:

1. current read-only analytical wording can create and persist proposals and approval records;
2. missing market data can become an executable-shaped plan using a placeholder price;
3. the target contradicts itself about whether `APPROVE` merely records approval or causes demo
   execution, while the repository has no immutable plan version or consumable approval;
4. the agent's apparent paper-execution tool is a successful no-op, not the authoritative
   `ExecutionService`.

The target also mixes objective setup state with account-specific risk eligibility, overlooks an
existing versioned `SetupDefinition` domain, understates existing watchlist capabilities, and
does not define enough exchange identity, evidence typing, deduplication, or reconciliation
detail to make replay claims credible.

The architecture should be corrected in documentation before migrations or product
implementation begin. This verdict does not recommend a rewrite.

### Issue count

| Severity | Count |
|---|---:|
| CRITICAL | 4 |
| HIGH | 16 |
| MEDIUM | 7 |
| LOW | 3 |

## 2. Reuse verdict

**Verdict:** reuse direction is good, but the proposed ownership map is incomplete and would
still create parallel concepts.

| Proposed responsibility | Existing owner to extend | Review decision |
|---|---|---|
| Intent/operation policy | `agents/routing.py`, `agents/mutation_policy.py`, typed `AgentState` | Add one policy contract; do not add a second agent framework |
| Planning | `PreTradeAnalysisService`, `PositionSizingService`, `LossAcceptanceService`, `ProposalService` | Extend; remove executable placeholders |
| Watcher subscriptions | `WatchlistItem`, `MarketService` | Extend the existing item; a separate subscription identity is not justified |
| Normalized evidence | `MarketDataEnvelope` plus watcher/TradingView/detector adapters | Add a typed envelope and append-only observations; do not copy every source payload |
| Fusion/candidate lifecycle | `PaperSignalOrchestrationDecision`, `PaperValidationCandidate`, watcher and TradingView adapters | Generalize one assessment state machine; do not add a third candidate flow |
| Pattern Cards | `UserStrategyVersion`, `StrategyCard`, `StructuredRules`, and existing `SetupDefinition` | Define one identity mapping and immutable compiled artifact |
| Model routing | `LLMProvider`, provider factory, `NarrativeService`, `UsageService` | Add a thin task router only |
| Telegram outbound | `PaperAlertService`, delivery routing/provider | Reuse; add a separate inbound authorization adapter |
| Reliable external effects | Existing alert retry/audit patterns | New transactional outbox and action receipts are justified |
| Demo execution | `ExecutionService`, exchange providers/repositories, `BloFinSyncService` | Keep `ExecutionService` authoritative; add an internal coordinator component, not another public authority |
| Journal/learning | Canonical `JournalTrade`, excursion/statistics/lesson services | Migrate legacy consumers; do not create another lifecycle record |

The Phase 0 estimates of “approximately 78% backend” and “approximately 60% frontend” reuse are
explicitly estimates, not measurements. They should not be used as acceptance criteria.

## 3. Severity-ranked findings

### CRITICAL-01 — Analytical wording can persist a proposal and approval

- **Affected area:** agent intent, read-only safety, proposal lifecycle.
- **Repository evidence:**
  - `backend/src/app/agents/nodes.py:137-173` maps `analyze`, `setup`, `pullback`, and
    `entry` to `Intent.PLAN_TRADE`.
  - `backend/src/app/agents/routing.py:34-48` routes that intent to trading analysis.
  - `backend/src/app/agents/graph.py:117-121` always traverses
    `strategy_module_execution -> trade_proposal_generation`.
  - `backend/src/app/agents/nodes.py:1332-1353` creates a proposal for `PLAN_TRADE`.
  - `backend/src/app/services/agent_service.py:107-113` invokes workflow persistence and commits.
  - `backend/src/app/services/workflow_persistence_service.py:30-52` persists the proposal and
    can create an approval.
- **Why it matters:** “Analyze BTC” is semantically read-only but can mutate durable state. This
  directly violates the requested intent boundary and makes the current graph unsafe as the
  base for watcher or Telegram automation.
- **Recommended correction:** make a typed `IntentDecision` and operation class authoritative
  before context retrieval. Give `MARKET_ANALYSIS` and `SETUP_ANALYSIS` graph branches no edge
  to proposal or mutation nodes. Enforce the same operation class again in
  `WorkflowPersistenceService`, then test both response state and database row counts.

### CRITICAL-02 — Missing data can become an executable-shaped placeholder plan

- **Affected area:** planning, freshness, execution eligibility.
- **Repository evidence:**
  - `backend/src/app/agents/nodes.py:1339-1353` substitutes `BTCUSDT`, `4h`, and
    `Decimal("60000")` when context is missing; degraded data only lowers confidence.
  - `backend/src/app/services/proposal_service.py:76-105` can persist that proposal.
  - `backend/src/app/services/paper_execution_risk_gate.py:94-137` binds an order to proposal
    symbol/side/size/price, but does not prove that the proposal price came from fresh evidence.
  - `backend/src/app/services/execution_service.py:362-402` checks that a current ticker is
    usable but does not compare its provenance or observation window with the approved plan.
- **Why it matters:** current market availability at execution time does not repair an approved
  plan that was derived from a fabricated placeholder. A proposal must not be approval-eligible
  without immutable fresh-price provenance.
- **Recommended correction:** missing, stale, fallback, or sequence-gapped executable inputs
  must return analysis-only and create no plan/proposal. Persist evidence IDs, observation
  windows, venue/market identity, and a valid-until value on each immutable plan revision;
  execution must revalidate that exact binding.

### CRITICAL-03 — Approval and execution semantics are contradictory and not single-use

- **Affected area:** intent model, approval, Telegram, execution.
- **Repository evidence:**
  - Target architecture §2 shows approval followed by risk and execution, while §4 says
    “approval is not execution”; the required intent table has no separate `EXECUTE` intent.
  - `backend/src/app/db/models.py:317-358` and `backend/src/app/schemas/proposal.py:59-114`
    define no proposal/plan version.
  - `backend/src/app/services/approval_service.py:99-133` binds a decision to proposal ID only.
  - `backend/src/app/services/execution_service.py:120-139` accepts an approved record, but
    nothing consumes it atomically; different idempotency keys can reuse one approval.
- **Why it matters:** a Telegram `APPROVE` nonce cannot safely bind an exact immutable plan or
  guarantee one execution. The target does not say whether approval stops at `APPROVED` or
  authorizes immediate order submission.
- **Recommended correction:** choose and document one contract:
  - preferred: `APPROVE` changes only the exact plan revision to approved, and a distinct,
    explicit `EXECUTE_PAPER_PLAN` operation submits it; or
  - make the action text and nonce explicitly “approve and submit this demo order,” then treat
    that as a single execution authorization.
  In both designs, persist immutable plan revisions, bind approval to the revision/content hash,
  consume the execution authorization atomically, and reject stale/replayed versions.

### CRITICAL-04 — The agent execution path reports success without executing

- **Affected area:** agent tools, audit truthfulness, execution authority.
- **Repository evidence:**
  - `backend/src/app/tools/registry.py` registers `paper_execution` through `_stub_execute`,
    which returns successful mock output.
  - `backend/src/app/agents/nodes.py` `tool_execution_if_allowed` can dispatch that tool for
    `Intent.EXECUTE`.
  - The real path is `POST /execution/paper` through
    `backend/src/app/services/execution_service.py`.
- **Why it matters:** the graph and HTTP API currently represent two execution paths, one of
  which can claim success without an order. That breaks auditability and the proposed
  one-authority architecture.
- **Recommended correction:** remove the stub from agent reach immediately in the first safety
  phase by making it fail closed. Only after immutable plan/approval and operation policy exist
  should the agent facade delegate to the same `ExecutionService` command as the API.

### HIGH-01 — The watchlist gap is factually overstated

- **Affected area:** reuse, watcher subscription model.
- **Repository evidence:**
  - `backend/src/app/db/models.py:1195-1215` already stores one symbol/exchange plus
    `timeframes` and `strategy_ids`.
  - `backend/src/app/schemas/market.py:39-67` requires typed timeframes and strategies.
  - `backend/src/app/services/market_service.py:30-94` validates and persists those fields.
  - PR #64 states that watchlist items lack timeframe/pattern/evidence-expression subscriptions.
- **Why it matters:** the incorrect claim encourages a new `WatcherSubscription` identity when
  most of that identity already exists.
- **Recommended correction:** extend `WatchlistItem` with immutable revision/audit metadata,
  user-strategy-version references, evidence policy, threshold bounds, and delivery preference
  references. Keep one row per user/org/symbol/exchange; do not introduce a multi-symbol row.

### HIGH-02 — Pattern Card identity ignores the existing `SetupDefinition`

- **Affected area:** Pattern Cards, reuse, identity/versioning.
- **Repository evidence:**
  - `backend/src/app/db/models.py:261-271` defines versioned `SetupDefinition` with rules and
    filters.
  - `StrategySignal`, `TradingViewSignal`, `PaperSignalOrchestrationDecision`, and
    `JournalTrade` already link to setup definitions.
  - Target architecture §7 says `pattern_id` may be “the same stable identity as strategy or
    linked one-to-one,” without choosing one or migrating `SetupDefinition`.
- **Why it matters:** adding Pattern identity only to `UserStrategyVersion` would leave two
  versioned setup/pattern systems and split existing lineage.
- **Recommended correction:** make `UserStrategy` the user-facing stable identity and
  `UserStrategyVersion` the immutable authored version. Define `SetupDefinition` as the compiled
  immutable detector artifact for exactly one strategy version, or explicitly migrate it behind
  a compatibility adapter. Do not create an independent `pattern_id`.

### HIGH-03 — Existing strategy versions are mutable

- **Affected area:** Pattern Cards, learning, version safety.
- **Repository evidence:**
  - `backend/src/app/services/structured_rules_service.py:38-60` patches the latest version's
    `structured_rules` in place.
  - `backend/src/app/services/lesson_candidate_service.py:424-442` can attach a rule patch to
    the latest version in place.
  - `backend/src/app/services/lesson_candidate_service.py:444-491` already demonstrates the
    safer new-version path.
- **Why it matters:** evidence, backtests, approvals, and journal outcomes cannot be reproduced
  if executable rules change under an existing version ID.
- **Recommended correction:** prohibit semantic mutation of every strategy version before
  Pattern Card storage is added. Every card/rule/pattern change creates a draft version with
  parent version, actor, source lesson, diff, and validation lineage. Accepted lessons remain
  advisory until explicit version promotion.

### HIGH-04 — `NormalizedEvidence` is too generic and incorrectly tenant-coupled

- **Affected area:** evidence schema, lineage, replay.
- **Repository evidence:**
  - Target §5 requires `organization_id` and `timeframe` for all evidence and uses generic
    `signal_type`, `metrics`, and `raw_evidence`.
  - `backend/src/app/db/models.py:447-473` correctly treats historical candles as shared global
    market data.
  - `backend/src/app/providers/market_data.py` already distinguishes exchange, source,
    timeframe, live/stale state, provider, fallback, and retrieval time.
- **Why it matters:** public BTC market observations should not be duplicated per tenant.
  Conversely, risk/portfolio/journal evidence is tenant-private. A mandatory timeframe does not
  fit position or risk events. A bounded generic dictionary is not a genuinely strict schema
  and cannot enforce category-specific units or replay semantics.
- **Recommended correction:** separate:
  1. a global immutable `MarketObservation` identity (`venue`, `market_type`, `instrument_id`,
     event/sequence ID, interval start/end, observed/received timestamps, source clock, revision
     or supersedes ID); and
  2. a tenant-scoped `EvidenceAssessment` that references observations plus private facts.
  Use a discriminated union of typed payloads for candles, trades, CVD windows, order-book
  state, external signals, positions, risk, and behavior. Keep redacted raw payloads optional.

### HIGH-05 — Fusion mixes setup truth with execution eligibility

- **Affected area:** fusion state, safety, explainability.
- **Repository evidence:** target §6 requires no “Tier C candidate eligibility block” for
  `CONFIRMED_CANDIDATE` and moves a confirmed candidate to `INVALIDATED` for kill switch,
  exposure, position conflict, or risk policy.
- **Why it matters:** a kill switch or daily loss lock does not invalidate a market pattern.
  Mixing these domains makes replay depend on a user's account state, hides valid setups from
  research, and corrupts strategy statistics.
- **Recommended correction:** maintain two deterministic but separate states:
  - `SetupAssessment`: no setup/watch/partial/confirmed/market-invalidated/expired; and
  - `ActionEligibility`: eligible/blocked with kill-switch, daily loss, exposure, cooldown,
    duplicate-position, freshness-at-action, and approval reasons.
  An alert policy may suppress a confirmed setup when action-blocked, but must not rewrite the
  market assessment.

### HIGH-06 — The target risks a third candidate/orchestration state machine

- **Affected area:** reuse, candidate lifecycle, idempotency.
- **Repository evidence:**
  - `backend/src/app/db/models.py` `PaperSignalOrchestrationDecision` already stores eligibility
    evidence, risk evidence, transitions, reason codes, links, and an idempotency key.
  - `backend/src/app/services/paper_signal_orchestration_service.py:139-239` evaluates and
    advances TradingView signals.
  - Separate watcher alert/draft/candidate and research-promotion paths already exist.
- **Why it matters:** a greenfield `SignalFusionService` plus new candidate table would add
  another lifecycle without removing the existing three paths.
- **Recommended correction:** generalize the useful decision/transition shape into one
  source-agnostic assessment aggregate. Feed it through adapters from watcher, TradingView, and
  fixed detectors; keep `PaperValidationCandidate` as the downstream validation queue during
  migration.

### HIGH-07 — Cross-source candidate uniqueness is not defined

- **Affected area:** duplicate alert/candidate protection.
- **Repository evidence:**
  - `backend/src/app/services/paper_alert_service.py:89-140` checks a cooldown key before insert.
  - `backend/src/app/db/models.py:774-813` has an indexed but non-unique `dedup_key`.
  - TradingView and paper orchestration use source-local uniqueness; watcher dedupe uses a
    different key family.
- **Why it matters:** concurrent workers or two sources describing the same pattern window can
  create duplicate candidates and notifications. Alert delivery dedupe is not candidate
  idempotency.
- **Recommended correction:** define a database-enforced candidate key such as
  `(organization_id, strategy_version_id, instrument_id, timeframe, evidence_window_hash)`.
  Use transactional insert/upsert and optimistic transition versioning. Keep alert delivery
  dedupe separate.

### HIGH-08 — Worker and manual watcher are different pipelines and scopes

- **Affected area:** continuous watcher, tenant isolation, reuse.
- **Repository evidence:**
  - `backend/src/app/workers/scanner.py:25-60` scans settings symbols at fixed `1h`, calls
    `analyze()`, and creates `SetupDetectionRecord` without organization ID.
  - `backend/src/app/services/market_watcher_service.py` runs per-organization request scans,
    stores observations, and can create in-app alerts.
  - `backend/src/app/services/market_watcher_scanner.py:17-18` separately hard-codes
    BTC/ETH/SOL and 15m/1h.
- **Why it matters:** simply adding subscriptions to the worker will not make behavior,
  dedupe, or tenant lineage match manual scans.
- **Recommended correction:** create one organization-aware surveillance application service
  used by both worker and dry-run API. Batch shared market fetches, then evaluate each tenant's
  strategy version and alert policy separately.

### HIGH-09 — Worker locking fails open outside local development

- **Affected area:** watcher concurrency.
- **Repository evidence:** `backend/src/app/workers/lock.py:89-109` falls back to
  `InMemoryWorkerLock` when Redis is disabled or unavailable, regardless of environment.
- **Why it matters:** multiple non-local instances can scan and emit concurrently.
- **Recommended correction:** allow in-memory locking only in local/test. In staging or
  production, an unavailable distributed lock must block the cycle and produce a visible
  unhealthy heartbeat. Add lock renewal/fencing checks for cycles that can exceed the TTL.

### HIGH-10 — Telegram account binding has no secure enrollment contract

- **Affected area:** Telegram authentication and tenant binding.
- **Repository evidence:**
  - `backend/src/app/db/models.py:1369-1398` and
    `backend/src/app/schemas/notifications.py` store only a user-editable Telegram chat ID.
  - Current Telegram code is outbound-only; there is no Telegram user ID, chat type, verified
    binding, callback, nonce, update receipt, or webhook route.
- **Why it matters:** possession or entry of a chat ID is not proof that the Telegram user is
  the authenticated AlphaTrade user. Group chats also create confused-deputy risk.
- **Recommended correction:** define an authenticated enrollment challenge initiated in the
  web app and completed by the same Telegram user in a private chat. Persist organization,
  AlphaTrade user, Telegram user, chat, bot identity, chat type, verified-at/revoked-at, and
  allowed actions. Reject groups by default and recheck role/ownership on every action.

### HIGH-11 — “Exactly-once-effect” is not a valid external-delivery guarantee

- **Affected area:** Telegram/outbox semantics.
- **Repository evidence:** target migration Phase 4 promises “exactly-once-effect action
  receipts,” while current delivery performs direct calls and status checks without a durable
  atomic claim.
- **Why it matters:** Telegram and exchange APIs cannot participate in the database
  transaction. A crash after external success and before local commit always permits duplicate
  delivery.
- **Recommended correction:** specify at-least-once delivery with idempotent internal effects,
  durable claim leases, unique update/callback receipts, and replay returning the original
  result. Never claim exactly-once external delivery.

### HIGH-12 — BloFin order lookup cannot recover an ambiguous submit

- **Affected area:** BloFin demo reconciliation and idempotency.
- **Repository evidence:**
  - `backend/src/app/providers/exchange/base.py:150-166` exposes `get_order` only by exchange
    order ID.
  - `backend/src/app/providers/exchange/blofin_execution.py:115-125` calls
    `/api/v1/trade/order` with `orderId`.
  - Current BloFin documentation defines `GET /api/v1/trade/order-detail` and allows either
    `orderId` or `clientOrderId`.
- **Why it matters:** after a submit timeout, the system may have only its client order ID.
  Current code cannot perform the target's mandatory lookup-before-retry and appears to call a
  different query endpoint.
- **Recommended correction:** update the provider contract to query order detail by exactly one
  of venue order ID or client order ID, then make ambiguous submit transition to
  `RECONCILIATION_REQUIRED`. Contract-test the current demo API before enabling it.

### HIGH-13 — Exchange-order and fill persistence lacks natural uniqueness

- **Affected area:** BloFin duplicate-order/fill protection.
- **Repository evidence:**
  - `backend/src/app/db/models.py:1986-2028` has no unique constraint for
    `(exchange, venue_client_order_id)`, venue order ID, or `(exchange_order_id, fill_id)`.
  - `backend/src/app/repositories/exchange_orders.py` provides only generic CRUD.
- **Why it matters:** reconciliation retries can duplicate orders or fills even though the
  internal paper order has an idempotency key.
- **Recommended correction:** define venue-scoped unique client-order and order IDs, unique
  non-null fill IDs per exchange order, optimistic state versioning, and append-only transition
  records.

### HIGH-14 — Cancel and partial-fill handling is disconnected from lifecycle state

- **Affected area:** BloFin order state.
- **Repository evidence:**
  - `ExchangeExecutionProvider.cancel_order` returns `None`.
  - `backend/src/app/api/routes/exchange.py` cancels directly at the provider and audits it,
    without updating `Order`, `ExchangeOrder`, or position state.
  - `BloFinDemoExecutionProvider` parses fill aggregates, but `ExecutionService` persists only
    the initial response and has no polling lifecycle.
- **Why it matters:** cancellation can race with fills, leaving internal position and remaining
  size wrong.
- **Recommended correction:** route cancel through `ExecutionService`; persist
  `CANCEL_PENDING`, query final order detail, ingest any late fills idempotently, and only then
  transition to cancelled or partially-cancelled.

### HIGH-15 — Reduce-only close conflicts with hedge mode

- **Affected area:** BloFin demo close, position mode.
- **Repository evidence:** `backend/src/app/providers/exchange/position_side.py:29-49` rejects
  every reduce-only request in `long_short_mode`, while the target requires reduce-only close.
- **Why it matters:** the target acceptance trace is impossible for the account mode shown in
  existing exchange diagnostics tests unless mode policy is decided.
- **Recommended correction:** for the first slice, require and verify BloFin `net_mode`, or
  implement explicit hedge-side close semantics verified against demo documentation and
  black-box tests. Unknown/mismatched mode must fail closed before approval.

### HIGH-16 — Reconciliation inputs do not yet support authoritative PnL

- **Affected area:** BloFin reconciliation, journal.
- **Repository evidence:**
  - `backend/src/app/services/blofin_sync_service.py` stores bounded read-only snapshots and
    does not match them to internal orders/positions.
  - `ExchangePositionData` lacks realized PnL and funding history.
  - `ExchangeFill` stores fees, but current internal close PnL is price-difference based and does
    not project venue fees/funding.
- **Why it matters:** the target cannot claim reconciled PnL, fees, funding, or a complete
  journal from account snapshots alone.
- **Recommended correction:** specify order detail, fills/trade history, account bills/funding,
  and position snapshot adapters; define Decimal sign/currency/contract-size semantics and
  reconciliation precedence. Keep unresolved differences visible and block journal
  finalization rather than fabricating totals.

### MEDIUM-01 — Model metering makes an unnecessary LLM call

- **Affected area:** model routing, cost/latency observability.
- **Repository evidence:** `backend/src/app/agents/nodes.py:1563-1588` calls
  `llm.complete()` in `usage_tracking`; `narrative_enhancement` may make another call, and
  narrative generation is enabled by default.
- **Why it matters:** a routine request can pay for two model calls although only one produces
  user value; placeholder usage can be mistaken for actual generation metadata.
- **Recommended correction:** propagate provider usage from the actual routed call. If no model
  ran, use a labelled deterministic token estimate and zero provider latency; never invoke a
  model solely to meter it.

### MEDIUM-02 — Tier A “candidate synthesis” is too close to deterministic authority

- **Affected area:** model routing and fusion.
- **Repository evidence:** target §8 includes “high-impact candidate synthesis” in Tier A while
  target §6 says deterministic fusion emits confirmed candidates.
- **Why it matters:** the term can be implemented as a second, model-controlled promotion gate.
- **Recommended correction:** rename Tier A work to candidate explanation/conflict summary and
  strategy-draft assistance. Its input is a frozen deterministic assessment; its output cannot
  create, promote, invalidate, or reprioritize a candidate.

### MEDIUM-03 — Journal canonicalization is sequenced too late

- **Affected area:** journal/learning, migration order.
- **Repository evidence:**
  - `backend/src/app/db/models.py:1420-1587` contains legacy `TradeJournal` and canonical
    `JournalTrade`.
  - `frontend/src/app/(app)/journal/page.tsx` uses legacy `api.journal.list`.
  - `backend/src/app/services/human_vs_system_service.py:430-520` resolves legacy journal or
    proposal IDs.
  - `backend/src/app/services/journal_rag_sync_service.py` ingests legacy entries.
  - Canonical statistics, excursions, detail, and attachments already exist.
- **Why it matters:** enabling lifecycle projection late would write records that the main
  journal, per-trade comparison, and RAG do not consume.
- **Recommended correction:** move canonical read adapters, per-trade comparison, RAG, and a
  minimal canonical list/detail UI before enabling automatic projection. Keep legacy reads and
  parity checks during migration.

### MEDIUM-04 — Close-only auto-journal hooks are not a lifecycle projector

- **Affected area:** journal reliability and observability.
- **Repository evidence:** `PositionService` invokes `JournalTradeService.create_from_position`
  only after close and catches all exceptions in a nested savepoint; the feature is opt-in.
- **Why it matters:** this neither projects candidate/plan/fill transitions nor provides visible
  retry when journal creation fails.
- **Recommended correction:** distinguish existing close backfill hooks from the new projector.
  Use idempotent outbox events for fill/close projection, visible retry state, one canonical
  trade per execution lifecycle, and append-only corrections for reconciled facts.

### MEDIUM-05 — The four-surface frontend still overloads Agent and Settings

- **Affected area:** frontend information architecture.
- **Repository evidence:**
  - `frontend/src/components/layout/navigation-config.ts` currently has eight coherent primary
    destinations and extensive secondary routes.
  - Target §14 moves dashboard, proposals, approvals, pre-trade, manual levels, coaching, and
    strategy create/edit into Agent; it moves risk, providers, watcher, Telegram, exchange,
    audit, usage, billing, and team into Safety & Settings.
- **Why it matters:** replacing route fragmentation with two oversized screens does not simplify
  mental models. Strategy authoring and account/billing are not conversational trading tasks.
- **Recommended correction:** keep Agent focused on analysis, plan preview, proposal/approval
  context, and explanations. Keep Strategy Lab and validation as secondary expert workflows.
  Use tabs/deep links for watcher operations and trade analytics. Keep account/team/billing as
  secondary Settings sections distinct from the safety control plane. Hide navigation only;
  delete no routes in this phase.

### MEDIUM-06 — The first slice is selected before its evidence contract

- **Affected area:** first vertical slice and migration order.
- **Repository evidence:** target §17 fixes SOLUSDT 15m while acknowledging that CVD/trade-flow
  source and sequence semantics are unknown. Existing worker defaults to BTCUSDT and 1h;
  manual watcher supports both BTC/SOL and 15m.
- **Why it matters:** symbol choice should follow the feed/venue contract, not precede it.
- **Recommended correction:** adopt the BTCUSDT 15m slice in §16 of this review and decide the
  read-only futures feed contract before fusion or Pattern Card acceptance tests.

### MEDIUM-07 — Some Phase 0 facts and validation counts are stale or imprecise

- **Affected area:** documentation truthfulness.
- **Repository evidence:**
  - The audit says watchlists lack timeframes, but they do not.
  - It says the worker blueprint omits `QDRANT_URL` and `CORS_ORIGINS`; the checked-in worker
    block includes `QDRANT_URL` but not `CORS_ORIGINS`.
  - The current branch contains 113 backend test files, while the PR body reports 112 at the
    audited base.
- **Why it matters:** architecture decisions should not be justified by stale inventory.
- **Recommended correction:** correct the watchlist and worker statements. Keep counts explicitly
  tied to the audited commit and avoid treating file counts as behavioral validation.

### LOW-01 — `MessageClass.COMMAND` is routed but never assigned

- **Affected area:** agent taxonomy.
- **Repository evidence:** `routing.py` includes `MessageClass.COMMAND`, while
  `message_classification` never emits it.
- **Why it matters:** it is a dead semantic branch and obscures the target mapping.
- **Recommended correction:** remove it or define bounded command classification as part of the
  new operation contract.

### LOW-02 — Model-routing observability needs explicit attempt versus result records

- **Affected area:** model routing.
- **Repository evidence:** existing usage schemas can store provider/model/tokens/latency and
  fallback, but the target result contract does not state how retries and failed validation
  attempts are represented.
- **Why it matters:** one final result can hide cost and latency from multiple attempts.
- **Recommended correction:** emit one call-attempt record per provider invocation and one
  task-result record, both tied to prompt version and correlation ID. Label estimated cost as
  non-billing-grade.

### LOW-03 — User priorities for SOL versus BTC are not repository evidence

- **Affected area:** first vertical slice.
- **Repository evidence:** repository defaults and tests favor BTC, but no durable product
  decision or user-research artifact establishes SOL as the user's priority.
- **Why it matters:** product preference should not be inferred from the Phase 0 choice.
- **Recommended correction:** treat user preference as **UNKNOWN**. Select BTC for architectural
  proof, then validate whether SOL should be the next slice.

## 4. Agent and intent verdict

**Verdict:** target taxonomy is directionally correct but incomplete until approval execution
semantics are resolved.

Required mapping:

| Intent | Operation class | Allowed effect |
|---|---|---|
| `MARKET_ANALYSIS` | READ_ONLY | Read facts/evidence only |
| `SETUP_ANALYSIS` | READ_ONLY | Evaluate progress/invalidation only |
| `PLAN_TRADE` | PLAN | Create immutable non-executable plan revision |
| `REVIEW_TRADE` | READ_ONLY/JOURNAL | Read by default; confirmed reflective write only |
| `MANAGE_POSITION` | MUTATION | Exact position preview and confirmed idempotent command |
| `JOURNAL` | JOURNAL | Read by default; confirmed note/evidence write |
| `EXPLAIN` | READ_ONLY | Explain frozen facts |
| `CONFIGURE` | CONFIGURATION | Read or preview; confirmed versioned update |
| `APPROVE` | APPROVAL | Approve exact immutable revision only |
| `REJECT` | APPROVAL | Reject exact object; never execute |
| `SKIP` | APPROVAL | Dismiss exact evidence window; never execute |

Ambiguous commands must set `requires_clarification=true` and have an effective operation class
of `READ_ONLY`. The deterministic policy must take the more restrictive result when classifier,
role, channel, or object state disagree. Tool metadata is defense in depth, not authority.

## 5. Safety verdict

**Verdict:** existing deterministic safeguards are strong and should remain authoritative, but
the agent/proposal boundary prevents approval of implementation today.

Verified reusable controls:

- `Settings` defaults to `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, and
  `EXCHANGE_MODE=paper_internal` (`backend/src/app/core/config.py:95-110`).
- `Settings.real_trading_enabled` requires both trade mode and the explicit flag.
- `core/exchange_safety.py` permanently rejects `trade_live`, production BloFin hosts, missing
  demo credentials, and any demo/live-axis conflict.
- `ExecutionService` binds proposal and approval, enforces unique internal idempotency key,
  checks kill switch twice, re-evaluates daily risk/overtrading/green-day controls, and rejects
  stale/fallback market data.
- paper-signal orchestration has deterministic age, cooldown, daily-loss, kill-switch, and
  conflict checks.
- audit records exist across proposal, approval, execution, watcher, delivery, and sync paths.

Required preservation:

1. the LLM cannot change risk inputs, thresholds, freshness, position size, or eligibility;
2. execution-time Tier C remains a fresh server-side check and `BLOCK` is final;
3. mock/fallback evidence may be displayed but never confirms a candidate or executable plan;
4. candidate dedupe, approval consumption, venue client IDs, fills, and outbox receipts receive
   database constraints;
5. all watcher, Telegram, and BloFin flags stay off until separate test and deployment review;
6. no live-money path is introduced.

## 6. Evidence and fusion verdict

**Verdict:** normalized evidence and deterministic fusion are justified, but the proposed schema
and state machine need redesign.

Use a typed observation envelope plus discriminated payloads; do not use one tenant-bound table
for both public market events and private account facts. Add venue, market type, instrument,
event/sequence identity, interval boundaries, timestamp semantics, correction lineage, units,
and source-specific freshness.

Keep market-pattern progression independent from action eligibility. A replay of the same
evidence and policy version must reproduce the same setup assessment. Account risk is evaluated
separately at alert, plan, approval, and execution time.

Adapt current sources rather than replacing them:

- OHLCV/provider metadata from `MarketDataEnvelope`;
- setup detectors and watcher observations;
- signed/idempotent TradingView signals;
- paper-orchestration transition/reason-code shape;
- strategy and setup version IDs;
- portfolio/risk snapshots as private evidence references.

## 7. Pattern Card verdict

**Verdict:** extend the strategy system, but first resolve `SetupDefinition` ownership and enforce
immutability.

Recommended identity:

- `UserStrategy`: stable user-owned strategy/pattern identity;
- `UserStrategyVersion`: immutable authored card, structured rules, sequence, evidence
  requirements, and promotion state;
- `SetupDefinition`: immutable compiled detector artifact tied one-to-one to a strategy version;
- backtest/paper statistics: immutable evaluation records referenced by ID, not mutable fields on
  the card;
- examples/counterexamples: references to canonical journal/evidence/attachments;
- screenshot input: non-executable evidence from which a reviewed draft may be produced.

No screenshot, RAG result, lesson, or model output may directly modify executable rules.

## 8. Model-routing verdict

**Verdict:** a thin Tier A/B router is appropriate after removing the metering-only LLM call.

- **Tier A:** strategy/pattern draft assistance, complex post-trade review, and explanation of
  frozen multi-source conflicts. No state transition or mutation.
- **Tier B:** bounded intent extraction, routine summaries, journal field extraction, and alert
  wording with strict structured outputs.
- **Tier C:** all calculations, fusion, freshness, risk, permissions, idempotency, state
  transitions, sizing, and execution.

Record task type, prompt version, tier, provider/model, every attempt, input/output tokens,
latency, validation, fallback reason, and estimated/provider cost. A model outage returns
deterministic facts or human review; it never relaxes safety.

## 9. Continuous watcher verdict

**Verdict:** the current worker, heartbeat, watcher, watchlist, and observations are reusable,
but they do not yet form a safe always-on system.

`WatcherSubscription` behavior is necessary; a new top-level identity is not. Extend
`WatchlistItem`, use one row per symbol/exchange, and add revisioned strategy-version/evidence
policy. Unify manual and worker evaluation through one tenant-aware application service. Require
distributed locking outside local, lease renewal, source batching, closed-candle boundaries,
trade/depth sequence-gap detection, candidate TTL, database uniqueness, retry-safe transitions,
and degraded heartbeat state.

## 10. Telegram verdict

**Verdict:** outbound components are reusable; inbound mutation is a new security boundary and
must not be built as an extension of the delivery provider.

Required order:

1. verified private-chat enrollment and revocation;
2. webhook secret-token validation, body bounds, rate limiting, bot identity, update-type
   allowlist, and durable `update_id` receipt;
3. read-only `STATUS`, `EXPLAIN`, and `SHOW_CHART`;
4. idempotent `REJECT` and `SKIP`;
5. exact-revision `APPROVE` only after approval semantics are fixed;
6. `REDUCE_RISK` creates a new plan revision and invalidates old tokens;
7. `CLOSE` requires a position-bound preview and a second short-lived nonce.

Each nonce binds organization, AlphaTrade user, Telegram user/chat/bot, resource ID, immutable
revision/content hash, allowed action, expiry, and one-time compare-and-set state. Delivery is
at least once; internal effects are idempotent.

## 11. BloFin demo verdict

**Verdict:** keep `ExecutionService` as authority, but refactor demo mode from internal-first
mirroring into an explicit venue-coordinated lifecycle.

Current demo-host controls are strong. Current order semantics are not sufficient:

- internal order/position is marked filled before demo submission;
- submit failure is swallowed as best-effort;
- client-order lookup is missing;
- cancel is disconnected;
- partial fills do not drive position state;
- hedge-mode reduce-only close is rejected;
- account snapshots are not reconciliation;
- fees/funding/realized PnL are not projected end to end.

The coordinator should remain an internal component of `ExecutionService`; it does not justify a
second execution service. Internal paper mode can keep its current clearly labelled simulator.
Demo mode must use venue acknowledgement/fills as truth and expose uncertainty rather than
pretend a fill. BloFin production hosts and live trading remain permanently out of scope.

## 12. Journal and learning verdict

**Verdict:** `JournalTrade` is the correct canonical record, but migration adapters must move
earlier.

One execution lifecycle should project to one canonical trade. Candidate/reject/skip history
belongs in lifecycle events, not fake executed journal rows. Create the canonical planned trade
at approved-plan or first-fill boundary, then idempotently project order/fill/position/close
facts. Reflective notes remain editable; reconciled venue facts are append-only corrections with
actor and reason.

Move the main journal UI, per-trade human-versus-system analysis, and journal RAG to canonical
IDs before enabling automatic projection. Reuse existing MFE/MAE replay, missed-profit analysis,
statistics, attachments, rule checks, and lessons. Learning can propose a new draft strategy
version only; it cannot edit or activate strategy logic.

## 13. Frontend verdict

**Verdict:** four primary destinations can simplify navigation, but they should be shells over
focused workflows, not four monolithic pages.

- **Agent:** analysis, setup progress, plan preview, proposal/approval context, explanations.
- **Live Watcher:** candidates and freshness first; scanner/worker/source diagnostics as expert
  tabs or deep links.
- **Trades & Journal:** open/reconciling/closed positions, canonical journal, performance, and
  learning tabs.
- **Safety & Settings:** safety control plane first; provider/demo diagnostics and audit as
  secondary. Account, team, billing, and usage remain distinct secondary settings.

Keep `/strategy-lab`, `/paper-validation/*`, `/backtests/*`, `/knowledge`, import, audit,
exchange diagnostics, billing, usage, and compatibility routes reachable. Hide from primary
navigation only after links and tests migrate. Delete no route in this phase.

## 14. Migration-order verdict

**Verdict:** intent safety remains first and frontend remains last, but identity, immutability,
correlation, canonical-journal adapters, and evidence-source contracts must move earlier.

Recommended dependency order:

1. Freeze paper/live-host/kill-switch/risk/idempotency invariants and characterize current
   agent persistence/stub defects.
2. Implement `IntentDecision`, operation classes, clarification, and graph/persistence
   non-interference tests.
3. Make agent execution fail closed; remove every successful no-op mutation tool from reach.
4. Define immutable plan revision, consumable approval, lifecycle correlation, and event/outbox
   identity contracts.
5. Enforce immutable strategy versions and map `SetupDefinition` to `UserStrategyVersion`.
6. Move canonical `JournalTrade` read adapters, per-trade comparison, RAG, and minimal list/detail
   UI; keep legacy compatibility.
7. Select the read-only trades/depth source and define instrument, aggressor, sequence, gap,
   timestamp, and freshness semantics.
8. Implement typed normalized observation contracts and adapters for existing OHLCV,
   TradingView, watcher, detector, portfolio, and risk records.
9. Add the deterministic Pattern evaluator and separate setup-assessment/action-eligibility
   state machines.
10. Extend `WatchlistItem`; unify worker/manual surveillance; add database candidate uniqueness
    and fail-closed distributed locking.
11. Add transactional outbox and Telegram outbound consumer; then verified inbound read-only
    actions, reject/skip, and exact-plan approval.
12. Extend `ExecutionService` with demo order lookup, partial-fill/cancel/reduce-only close, and
    reconciliation; keep all flags off.
13. Add idempotent fill/close journal projection, excursions, analytics, and review-only lesson
    generation.
14. Run the complete vertical-slice replay/failure matrix and an independent safety/security
    review.
15. Assemble four frontend surfaces and hide old primary links only after compatibility tests.
16. Enable any staging/demo feature only in a separately authorized deployment task.

## 15. First vertical-slice verdict

**Verdict:** use **BTCUSDT 15m**, not SOLUSDT 15m, for the first complete architectural proof.

Repository reasons:

- BTCUSDT is the worker's default symbol (`Settings.market_watcher_default_symbols`);
- the manual watcher already supports BTCUSDT and 15m;
- agent, market, backtest, seed, and exchange tests are BTC-heavy;
- BloFin mapping/execution tests exercise BTC-USDT;
- BTC generally gives denser trade flow for deterministic fixtures, while no repository
  evidence establishes SOL as a product priority.

The CVD gap exists for both symbols. The choice does not remove the need for a source contract.

### Exact first custom pattern

**BTCUSDT 15m Bearish Liquidity-Sweep Exhaustion at 4h Resistance**

Deterministic draft rules:

1. The latest closed 15m candle trades above a confirmed prior 15m swing high that lies within a
   bounded ATR distance of a versioned 4h resistance/manual level.
2. Excursion above the swing is at least `0.25 * ATR(14)` and the candle closes back below the
   prior swing high, reusing the current liquidity-sweep detector semantics.
3. Trigger-window 15m volume is at least `1.5 *` the median/mean of the preceding 20 closed
   15m bars; the exact statistic is fixed in the Pattern version.
4. Price makes a higher high while cumulative aggressor delta over the matched swing window
   makes a lower high.
5. Aggressive-buy efficiency deteriorates in the final push: positive taker-buy delta produces
   less upward price movement than the preceding push, then signed delta turns negative before
   or during the trigger close.
6. Entry trigger is the first closed 15m candle below the swept swing level after rules 1-5.
7. Invalidation is the exhausted high plus a versioned ATR/tick buffer. TTL is a fixed number of
   closed 15m bars. Any trade-sequence gap, stale source, fallback, or new high invalidates the
   assessment.

Thresholds above are a starting specification for fixtures, not validated trading claims.
Historical and paper evidence must determine whether the Pattern is promotable.

### Exact evidence sources

Preferred evidence venue:

1. **Binance USD-M Futures 15m and 4h klines** for structure, ATR, closed-candle volume, and
   resistance context. Extend the existing Binance provider's already configured futures base
   rather than mixing spot OHLCV with perpetual execution.
2. **Binance USD-M Futures aggregate trades** (`/fapi/v1/aggTrades` for bounded backfill and
   `<symbol>@aggTrade` for streaming) for aggressor-signed CVD and buy-efficiency/exhaustion.
   Persist aggregate trade ID and buyer-maker classification semantics.
3. **Optional Binance USD-M diff-depth stream plus REST snapshot** for sequence-complete L2
   imbalance as supporting evidence only in v1; resting liquidity is not CVD and should not be
   required until spoofing/sequence limitations are evaluated.
4. Existing versioned 4h manual levels or deterministic swing levels for resistance.
5. Existing portfolio/risk/kill-switch state only for separate action eligibility.
6. **BloFin demo ticker/order detail/fills/positions** only for execution-time venue price,
   contract sizing, basis check, and reconciliation—not as a substitute for the Binance
   evidence feed.

Because evidence and execution are cross-venue, every plan must record both instruments and
block when the BloFin demo price basis versus the evidence venue exceeds a conservative,
versioned tolerance. Alternatively, use BloFin demo public trades/books/candles consistently
after a dedicated provider contract is implemented and validated; its current repository
provider lacks trades and is coupled to demo configuration.

Official API references used only to assess source feasibility:

- Binance USD-M aggregate trades:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Compressed-Aggregate-Trades-List>
- Binance USD-M aggregate-trade stream:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams>
- Binance USD-M diff depth:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Diff-Book-Depth-Streams>
- BloFin API and demo endpoints: <https://docs.blofin.com/index.html>

### Why this slice is best

It exercises the complete architecture with the least repository divergence: existing watcher
symbol/timeframe support, existing liquidity-sweep semantics, a deterministic custom Pattern,
two typed market evidence classes from one public futures venue, explicit CVD/order-flow
semantics, agent read-versus-plan separation, Telegram version binding, current Tier C risk,
BloFin demo reconciliation, and canonical journal projection. It also avoids presenting an
untested SOL preference as architecture evidence.

## 16. Mandatory corrections before implementation

1. Correct Phase 0's watchlist and worker-environment facts.
2. Resolve `APPROVE` versus execution semantics and define immutable, single-use plan approval.
3. Make read-only analysis structurally unable to create in-memory or durable proposals.
4. Remove executable placeholders and bind plans to immutable fresh evidence.
5. Remove successful no-op mutation/execution tools from agent reach.
6. Separate deterministic setup assessment from account/action eligibility.
7. Replace the generic tenant-bound evidence design with global typed market observations plus
   tenant-scoped assessments.
8. Define one Pattern identity across `UserStrategyVersion` and `SetupDefinition`; enforce
   immutable versions.
9. Generalize existing orchestration rather than create a parallel fusion/candidate flow.
10. Extend `WatchlistItem`; unify worker/manual scans; enforce fail-closed distributed locking
    and database candidate uniqueness.
11. Define verified Telegram enrollment, private-chat/user binding, nonce/receipt state, and
    at-least-once/idempotent semantics.
12. Extend BloFin provider contracts for client-order lookup, partial fill, cancel, position
    mode, and reconciliation; add venue/fill uniqueness.
13. Decide net-mode versus hedge-mode close policy.
14. Move canonical journal adapters earlier and prohibit automatic strategy self-modification.
15. Adopt and record the first-slice feed/instrument/freshness/sequence contract before fusion
    implementation.
16. Keep worker, watcher, Telegram, BloFin demo execution, and live trading disabled throughout
    implementation and tests until separately reviewed.

## 17. Optional improvements

- Replace imprecise reuse percentages with a responsibility-by-responsibility migration matrix.
- Version every model prompt and store task-level plus call-attempt telemetry.
- Add deterministic evidence fixture bundles that replay gaps, reordering, source corrections,
  and cross-source conflicts.
- Add role-aware deployment validation so non-HTTP workers do not inherit irrelevant CORS
  requirements.
- Keep advanced route telemetry before any future deprecation proposal.
- Add a visible “no state change” result to every read-only agent and Telegram response.

## 18. Final implementation readiness

**REDESIGN REQUIRED**

PR #64 is a useful current-state inventory and a strong starting point, but the mandatory
corrections above must be incorporated into the architecture before implementation begins.
After correction, repeat an independent review of the revised documents. Do not merge this
review verdict into an authorization to enable runtime features.
