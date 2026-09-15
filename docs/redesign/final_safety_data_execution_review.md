# AlphaTrade Agentic Redesign — Final Safety, Data, and Execution Review

**Review target:** PR #64  
**Exact head:** `8511ea15dbd6f036a873a049b1adce84a89104cb`  
**Reference:** PR #65 independent architecture review at
`3a1a80ff7c980b3fcfbb3d239e3bcdc11f161403`  
**Scope:** final adversarial architecture review only; no implementation, migrations,
deployment, external API action, delivery, exchange call, or feature enablement  
**Final verdict:** **NOT APPROVED**

## 1. Executive safety decision

PR #64 now states the correct non-negotiable posture: paper/internal simulation and BloFin
demo only; deterministic risk and kill-switch authority; no production exchange host; no
model override; no execution implied by approval; no fallback, stale, forming, wrong-market,
or gapped evidence in an executable path. It also incorporates the 18 mandatory corrections
from PR #65 at the architecture level.

The architecture is nevertheless not ready to start Phase 1 implementation. Six blocking
contracts remain ambiguous or incomplete:

1. `ApprovalAuthorization` is user-bound but not account/exchange-account-bound, so it is not
   bound to the complete principal that will bear the risk and venue mutation.
2. `canonical_command_hash` is said to hash every `ExecutionCommand` field, including
   retry-variant identifiers and timestamps, which contradicts same-payload convergence.
3. The first-writer transaction, authorization consumption, durable submit claim, and external
   call boundary are not ordered precisely enough to prove that concurrent/crash recovery
   cannot duplicate a demo order.
4. Distinct concurrent commands have no account-level risk reservation or serialization, so
   each can independently pass a limit that their combined exposure breaches.
5. Multiple authorizations can be issued for one plan revision and executed under different
   keys; one-time use per authorization is not one execution per plan.
6. Phase 1 says to freeze existing paper invariants even though current local settings accept
   `trade + ENABLE_REAL_TRADING=true` and `read_only` does not block internal paper mutation.

Twenty high and seven medium findings additionally require architecture corrections. The most
material concern is not the current disabled runtime; it is that implementing the present
wording permits multiple incompatible implementations, including cross-account authorization,
stale-worker writes, duplicate candidates, wrong-unit cross-venue sizing, unrepresented
partial-fill exposure, and duplicate canonical journal trades.

### Finding count

| Severity | Count |
|---|---:|
| BLOCKER | 6 |
| HIGH | 20 |
| MEDIUM | 7 |
| LOW | 0 |

## 2. Confirmed paper/demo safety invariants

The following controls are explicit and must be preserved unchanged:

- `Settings` defaults to `EXECUTION_MODE=paper`,
  `ENABLE_REAL_TRADING=false`, and `EXCHANGE_MODE=paper_internal`
  (`backend/src/app/core/config.py:40-55, 94-105`).
- Staging/production reject real trading, and production rejects demo exchange mode
  (`backend/src/app/core/deployment_safety.py:36-53`).
- `trade_live` is a startup tombstone; demo mode requires paper execution and
  `enable_real_trading=false`; only the TLS demo host is allowlisted and production hosts are
  denied (`backend/src/app/core/exchange_safety.py:21-41, 48-67, 69-119`).
- The current `ExecutionService` rejects `real_trading_enabled`, checks the kill switch before
  risk and again immediately before fill, and invokes the deterministic execution-time risk
  gate (`backend/src/app/services/execution_service.py:110-194`).
- The deterministic gate blocks current or stored risk `BLOCK` decisions
  (`backend/src/app/services/paper_execution_risk_gate.py:140-218`).
- The target keeps models outside risk, freshness, fusion, permissions, idempotency, sizing,
  and execution authority (`docs/redesign/agentic_redesign_target_architecture.md:17-28,
  650-697`).
- The target repeats paper mode, real-trading denial, demo-host checks, production-host denial,
  and the `trade_live` tombstone at startup and execution
  (`docs/redesign/agentic_redesign_target_architecture.md:1017-1047, 1470-1475,
  1531-1535`).

No agent, model tier, Telegram action, worker, provider fallback, or remote channel is granted
an override path. This review did not change or exercise any of those controls.

Production-host denial, `trade_live` startup rejection, deterministic risk authority, and
kill-switch authority are confirmed. The stronger requested permanence of
`EXECUTION_MODE=paper` and `ENABLE_REAL_TRADING=false` is **not yet confirmed** because current
local settings intentionally accept `trade + true` and Phase 1 says to freeze existing
invariants; BLOCKER-06 requires an explicit global tombstone/replacement contract.

## 3. Severity-ranked findings

### BLOCKER-01 — Approval authorization omits the execution account principal

- **Severity:** BLOCKER
- **Exact evidence:**
  - `ApprovalAuthorization` binds `organization_id`, `user_id`, plan/revision/hash, resource
    state, channel, and actor, but has no `account_id` or `exchange_account_id`
    (`docs/redesign/agentic_redesign_target_architecture.md:773-791`).
  - `TradePlanRevision` has organization/user and evidence/execution venues but no intended
    execution account (`docs/redesign/agentic_redesign_target_architecture.md:728-759`).
  - `ExecutionCommand` chooses `account_id` only after authorization, while
    `ActionEligibility` is account-scoped
    (`docs/redesign/agentic_redesign_target_architecture.md:483-490, 803-823`).
  - Existing demo execution is globally configured and does not yet use tenant-bound
    `ExchangeAccount`; PR #65 identified that current gap
    (`docs/redesign/agentic_redesign_phase0_audit.md:714-719`;
    reference review `agentic_redesign_architecture_review.md:501-516`).
- **Failure scenario:** one organization/user has two demo accounts with different balances,
  permissions, position modes, or existing exposure. An authorization previewed against
  account A is supplied in an `ExecutionCommand` for account B. Revision/hash checks pass
  because neither the plan nor authorization commits to A. A fresh risk check on B does not
  repair the authorization defect: the user did not approve that account mutation.
- **Required correction:** bind `TradePlanRevision` and `ApprovalAuthorization` to the exact
  typed account principal, including non-null internal account ID and exchange-account ID when
  demo execution is selected. Bind the operation, execution venue, execution instrument, and
  account mode/permission-attestation identity into the approved resource hash. Reject any
  account substitution before authorization consumption.
- **Required test:** create two accounts for one user and prove that an authorization for A
  cannot execute, close, cancel, or reconcile B; assert no consumption, order, venue call, or
  position mutation and a tenant/principal-safe audit conflict.

### BLOCKER-02 — The command hash includes retry-variant fields

- **Severity:** BLOCKER
- **Exact evidence:**
  - `ExecutionCommand` includes `execution_command_id`, opaque idempotency key,
    `correlation_id`, and `created_at` as well as semantic order fields
    (`docs/redesign/agentic_redesign_target_architecture.md:803-823`).
  - The next sentence says the canonical hash is calculated from **every** identity and
    payload field above (`docs/redesign/agentic_redesign_target_architecture.md:825-826`).
  - The required replay behavior says the same principal/key/canonical payload returns the
    original receipt (`docs/redesign/agentic_redesign_target_architecture.md:831-838`).
- **Failure scenario:** a client safely retries the same key and semantic payload after losing
  the response. A new command ID, correlation ID, or creation timestamp changes the hash, so a
  literal implementation rejects rather than converges. An implementer who informally excludes
  fields can choose a different field set and accidentally omit a semantic discriminator.
- **Required correction:** define a versioned `CanonicalExecutionPayloadV1` with an exhaustive
  field list. It must include organization, typed user/account principal, operation,
  immutable plan/revision, authorization identity, plan content hash, execution venue,
  execution instrument, side, order type, quantity plus unit, price plus unit/null marker,
  reduce-only semantics, and account/position binding where applicable. It must exclude the
  opaque key itself and server/transport metadata such as command ID, correlation ID,
  receipt ID, received/created timestamps, and retry-attempt metadata. Specify canonical
  Decimal, enum, UUID, null, and serializer-version encoding.
- **Required test:** retry the same semantic payload with different transport request IDs,
  correlation IDs, timestamps, JSON field order, and canonically equivalent Decimals and
  assert the original receipt; mutate each semantic field one at a time and assert audited
  conflict before any state or venue action.

### BLOCKER-03 — First-writer, authorization, and venue-submit ordering is not atomic enough

- **Severity:** BLOCKER
- **Exact evidence:**
  - The target says the service first locks an idempotency record, but does not define how an
    absent record is atomically reserved or which uniqueness key arbitrates two first writers
    (`docs/redesign/agentic_redesign_target_architecture.md:825-838`).
  - Authorization consumption is a compare-and-set in the transaction that “claims the
    command,” but the commit boundary relative to the external submit is unspecified
    (`docs/redesign/agentic_redesign_target_architecture.md:793-799`).
  - External demo calls are named as an outbox use case, but the execution lifecycle does not
    define the outbox/submit-effect claim, lease, or crash recovery transaction
    (`docs/redesign/agentic_redesign_target_architecture.md:195-199, 990-1058`).
  - The current implementation demonstrates why the boundary matters: replay is looked up
    before tenant validation and concurrent convergence relies only on a globally unique order
    key (`backend/src/app/services/execution_service.py:135-146, 203-246`;
    `backend/src/app/db/models.py:1244-1266`).
- **Failure scenario:** two first requests observe no idempotency row, both pass risk and
  authorization checks, and a venue POST occurs before the losing transaction is rejected.
  Separately, a process can consume authorization and crash before durably recording
  `SUBMITTING`, or send the order and crash before recording enough identity for client-order
  lookup. Each ordering can strand authorization or duplicate/lose venue truth.
- **Required correction:** specify the exact transaction protocol:
  1. evaluate deterministic pre-submit gates without consuming authorization;
  2. atomically insert-or-lock the scoped key binding, compare its canonical payload, claim the
     command, consume authorization by CAS, create receipt state `SUBMITTING`, and persist one
     venue-submit effect with deterministic client order ID;
  3. commit that transaction before network I/O;
  4. claim the effect with a renewable lease/fence;
  5. after any ambiguous send or crash, reconcile by client order ID and never issue a second
     semantic submit unless the venue contract supplies authoritative, final absence plus
     duplicate-safe client-ID behavior.
  No database transaction may remain open across the network call.
- **Required test:** PostgreSQL barrier tests with 2 and 5 first writers, plus crash injection
  before claim commit, after claim commit, before send, after bytes are sent, after venue
  acceptance, and before receipt update. Every case must yield at most one venue order, one
  consumed authorization, one command/receipt, and a recoverable truthful state.

### BLOCKER-04 — Distinct concurrent commands can oversubscribe deterministic risk

- **Severity:** BLOCKER
- **Exact evidence:**
  - The target defines concurrency convergence only for identical idempotent commands; it has
    no account-level execution/risk reservation before submission
    (`docs/redesign/agentic_redesign_target_architecture.md:800-840, 980-1031`).
  - Current daily risk recomputes committed orders/positions, flushes a snapshot, and does not
    lock or reserve pending capacity (`backend/src/app/services/risk/daily_risk_accounting.py:
    69-140`).
  - Current execution evaluates risk before it persists new exposure
    (`backend/src/app/services/execution_service.py:163-200, 203-299`).
- **Failure scenario:** two distinct approved commands each request 3% exposure under a 5%
  cap. Both read zero pending exposure, both receive deterministic `ALLOW`, and both reach
  `SUBMITTING`, creating 6% combined exposure. The risk engine is deterministic but its inputs
  are not serializable.
- **Required correction:** serialize execution eligibility per organization/account or
  atomically reserve risk capacity. Reservations must cover pending and ambiguous orders,
  open-order notional, daily trade slots, and exposure, and remain charged while execution is
  `SUBMITTING` or `RECONCILIATION_REQUIRED`. Release only from authoritative terminal facts.
- **Required test:** PostgreSQL races between distinct commands where only one fits the
  exposure or max-trade limit. Exactly one may reach `SUBMITTING`; the other must receive an
  authoritative `BLOCK`, with one venue call. Race kill-switch activation against the claim
  transaction as well.

### BLOCKER-05 — One-time authorization does not mean one execution per plan revision

- **Severity:** BLOCKER
- **Exact evidence:**
  - `ApprovalAuthorization` is single-use, but the target specifies no uniqueness or idempotent
    issuance for available authorizations on the same principal/plan revision/hash/operation
    (`docs/redesign/agentic_redesign_target_architecture.md:773-799`).
  - The plan lifecycle has no unique execution claim, while different idempotency keys are
    independent (`docs/redesign/agentic_redesign_target_architecture.md:831-838,
    1495-1498`).
- **Failure scenario:** two tabs or duplicate approval actions concurrently mint two available
  authorizations for one revision. Two explicit commands use different keys and consume one
  authorization each, creating two orders that are both individually valid and single-use.
- **Required correction:** make approval issuance idempotent and database-unique for the active
  `(organization, account principal, plan revision, plan hash, operation)`. Add a database
  unique execution claim for that plan revision/account. If intentional split execution is
  later needed, encode immutable authorized child slices and counts in the approved plan.
- **Required test:** sequential and concurrent duplicate approval issuance followed by
  distinct execution keys must produce one available authorization, one execution claim, one
  receipt, and at most one provider submit.

### BLOCKER-06 — “Freeze existing” does not permanently enforce paper mode

- **Severity:** BLOCKER
- **Exact evidence:**
  - The target calls `EXECUTION_MODE=paper` and `ENABLE_REAL_TRADING=false` permanent, but
    Phase 1 says to freeze existing invariants
    (`docs/redesign/agentic_redesign_target_architecture.md:1220-1228, 1470-1475`).
  - Current settings accept `execution_mode=trade` with `enable_real_trading=true` and expose
    `real_trading_enabled=True` outside staging/production
    (`backend/src/app/core/config.py:26-55, 435-450, 503-507`;
    `backend/tests/test_config.py:47-55`).
  - Current `ExecutionService` rejects only `real_trading_enabled`; it does not require exact
    paper mode, so `read_only` can still mutate internal paper state
    (`backend/src/app/services/execution_service.py:110-118`).
- **Failure scenario:** Phase 1 characterization preserves the current local `trade + true`
  contract as an invariant, leaving a latent live-mode switch for a future adapter. Separately,
  a process configured `read_only` can create an internal order because real trading is false.
- **Required correction:** state that Phase 1 **replaces**, not freezes, these behaviors:
  globally reject `ENABLE_REAL_TRADING=true` and non-paper execution at settings construction,
  or tombstone/remove `ExecutionMode.TRADE`; require exact paper mode and false real-trading
  flag at every execution boundary. No model/channel/configuration operation may alter them.
- **Required test:** local/staging/production matrix through settings, API, worker, direct
  service, and provider construction. `trade`, `read_only` execution, and
  `ENABLE_REAL_TRADING=true` must fail before any database or network side effect.

### HIGH-01 — Risk-BLOCK authorization and retry semantics are incomplete

- **Severity:** HIGH
- **Exact evidence:**
  - The diagrams correctly say risk `BLOCK/WARN` stops and authorization is consumed only after
    `ALLOW` (`docs/redesign/agentic_redesign_target_architecture.md:171-177, 219-225`).
  - Replay returns the original receipt for the same key/payload, but the target does not define
    whether a blocked command is terminal, whether its key may be retried after conditions
    change, or which new command may use the still-available authorization
    (`docs/redesign/agentic_redesign_target_architecture.md:831-838, 1496-1498`).
- **Failure scenario:** daily loss or kill switch blocks an attempt. Reusing the key can replay
  a stale block forever; using a new key can be treated as unauthorized reuse; or an
  implementation can silently re-run the same claimed command after the block clears. The last
  option changes a previously final response into an order without a new explicit execution
  action.
- **Required correction:** make a risk-blocked command terminal with an immutable blocked
  receipt and leave authorization `AVAILABLE` (or revoke it if the exact plan is no longer
  valid). A later retry must be a new explicit command/key, revalidate plan validity, account,
  eligibility, market facts, kill switch, and risk, and consume the authorization only on its
  own `ALLOW`. State whether `WARN` is a block or requires a separate explicit policy; do not
  make it an implicit allow.
- **Required test:** block on kill switch and daily loss, replay the old key, then clear the
  condition and submit a new explicit command. Assert old receipt stability, zero consumption
  on block, exactly one later consumption/order, and complete audit lineage.

### HIGH-02 — Immutable `FRESH` observations can remain fresh forever

- **Severity:** HIGH
- **Exact evidence:**
  - `MarketObservation` persists a categorical `freshness` value and timestamps but no
    freshness policy version, evaluation time, maximum age, or freshness expiry
    (`docs/redesign/agentic_redesign_target_architecture.md:357-390`).
  - Executable use tests only for `freshness=FRESH`
    (`docs/redesign/agentic_redesign_target_architecture.md:397-402`).
  - Assessment and action records have `valid_until`, but the architecture does not require
    age recomputation from event/receive time at every confirmation, planning, approval, and
    execution boundary (`docs/redesign/agentic_redesign_target_architecture.md:479-501`).
- **Failure scenario:** the feed stops after an observation was stored as `FRESH`. No later
  event arrives to mark it stale. A delayed evaluator reads the immutable label and confirms a
  candidate or plan from old data.
- **Required correction:** treat observation freshness as measured fact plus a versioned
  evaluation, not a permanent truth label. Record source/event/receive times and, where useful,
  ingestion-time classification, but require each consumer to calculate age against an
  immutable `FreshnessPolicy` and `evaluated_at`, producing `valid_until`. Expiry without a new
  event must fail closed.
- **Required test:** freeze time, ingest a fresh final event, advance beyond every relevant
  threshold without adding an event, and prove setup confirmation, plan creation, approval,
  and execution are blocked. Include event-clock skew and delayed receive-time boundaries.

### HIGH-03 — Reconnect recovery is not deterministic for CVD windows

- **Severity:** HIGH
- **Exact evidence:**
  - `TradeStreamCursor` has connection identity, reconnect state, gap state, and warm-up state;
    `CvdWindow` has only one `source_connection_id` plus start/end cursor IDs
    (`docs/redesign/agentic_redesign_target_architecture.md:426-467`).
  - The text rejects unresolved gaps and incomplete warm-up, while the cursor permits
    `RECOVERED`; it does not specify whether a recovered window may span connections, what
    backfill proves continuity, or when warm-up restarts
    (`docs/redesign/agentic_redesign_target_architecture.md:470-474`).
  - The first-slice fixture requires no “gap/reconnect discontinuity” but does not define the
    recovery transition (`docs/redesign/agentic_redesign_target_architecture.md:1402-1405`).
- **Failure scenario:** the stream reconnects, REST backfill overlaps some trades, and a window
  is built partly before and partly after the reconnect. Depending on implementation it can
  double-count overlap, omit unseen trades, or mark the single-connection window complete.
- **Required correction:** choose one deterministic policy. Safest v1: every reconnect makes
  current CVD unusable, starts a new connection epoch, deduplicates a bounded authoritative
  backfill by venue trade ID, proves contiguous cursor coverage, and completes a fresh warm-up
  before any new usable window. If cross-connection windows are allowed later, store all
  connection/backfill segments and a continuity proof.
- **Required test:** deterministic fixtures for disconnect before/after an event, overlap,
  reordering, duplicate backfill, irrecoverable gap, cursor reset, and complete recovery.
  CVD output must replay byte-for-byte and remain unusable until continuity and warm-up pass.

### HIGH-04 — The fencing token is recorded but no storage-level fence is defined

- **Severity:** HIGH
- **Exact evidence:**
  - The target requires a renewable lease and monotonically increasing fencing token, and says
    stale-holder writes are rejected (`docs/redesign/agentic_redesign_target_architecture.md:
    872-876`).
  - Runtime steps record the token but do not define a transactional predicate on observations,
    scan lineage, assessments, candidates, transitions, or outbox rows
    (`docs/redesign/agentic_redesign_target_architecture.md:877-897`).
  - Current `WorkerLock` has no renewal method and uses random UUID ownership tokens; on Redis
    failure it falls back to process-local locking
    (`backend/src/app/workers/lock.py:23-32, 64-87, 89-109`).
- **Failure scenario:** worker A pauses beyond TTL, worker B acquires a newer lease and writes,
  then A resumes. A check performed before its pause does not prevent its transaction from
  writing a candidate/outbox after B unless the database write itself compares a monotonic
  fence.
- **Required correction:** define a persisted worker/scan epoch with a database-enforced
  monotonically increasing token. Every worker-caused write or transition must include a
  transactional `incoming_fence == current_active_fence` (or stronger monotonic CAS)
  predicate. Lease renewal must fail closed, and loss must cancel work and mark the scan and
  heartbeat unhealthy. Process-local fallback remains local/test only.
- **Required test:** pause A after evaluation but before commit, expire its lease, let B acquire
  and commit, then resume A. Assert every A write and outbox enqueue is rejected and only B's
  lineage can transition the candidate.

### HIGH-05 — Candidate deduplication claims semantic convergence without defining it

- **Severity:** HIGH
- **Exact evidence:**
  - Candidate uniqueness is
    `(organization_id, strategy_version_id, instrument_id, timeframe,
    evidence_window_hash)` (`docs/redesign/agentic_redesign_target_architecture.md:504-510`).
  - The key omits the independently versioned setup/fusion/finality policy identities and
    explicit venue/source set, and no outbox uniqueness key or expired-candidate
    non-resurrection rule is specified
    (`docs/redesign/agentic_redesign_target_architecture.md:518-550, 887-890`).
  - The hash is said to represent the same semantic window across watcher, TradingView, and
    detector sources, but no canonical field set, source-equivalence rule, time bucketing,
    correction rule, or algorithm version is defined (`docs/redesign/agentic_redesign_target_architecture.md:
    505-514`).
- **Failure scenario:** watcher and TradingView identify the same trigger candle but carry
  different source IDs, receive times, or optional evidence. If raw observation identities
  enter the hash, each creates a candidate; if too much is omitted, distinct setup windows
  collide.
- **Required correction:** define and version `CanonicalEvidenceWindowV1`: exact
  strategy/setup/fusion/finality policy versions, market identity and venue/source set, final
  interval bounds, trigger identity, mandatory evidence roles, correction/supersession
  handling, and explicit exclusion/inclusion of optional source IDs. Define when two sources
  enrich one candidate versus create a distinct assessment. Terminal candidates cannot be
  resurrected; enforce one delivery-intent key per candidate revision/delivery policy.
- **Required test:** concurrent watcher/TradingView/detector fixtures for semantically equal,
  enriched, corrected, adjacent, policy-changed, venue-changed, expired, and genuinely distinct
  windows. Equal inputs must produce one candidate and one eligible delivery; changed policy or
  venue must not collide; retry cannot reactivate or renotify an expired candidate.

### HIGH-06 — Cross-venue contracts store two venues but only one instrument identity

- **Severity:** HIGH
- **Exact evidence:**
  - `TradePlanRevision` stores `evidence_venue` and `execution_venue`, but only one `symbol`,
    `instrument_id`, `market_type`, position size, and unit context
    (`docs/redesign/agentic_redesign_target_architecture.md:728-759`).
  - `ExecutionCommand` likewise has one venue and one instrument, while the acceptance text
    claims both identities are present on plan, command, and receipt
    (`docs/redesign/agentic_redesign_target_architecture.md:803-823, 1462-1467`).
  - The first slice explicitly combines Binance USD-M perpetual evidence with BloFin DEMO
    execution and warns that BloFin contract specifications determine sizing
    (`docs/redesign/agentic_redesign_target_architecture.md:1415-1427, 1462-1467`).
- **Failure scenario:** Binance `BTCUSDT` base quantity/tick semantics are interpreted as
  BloFin `BTC-USDT` contract count, lot size, tick size, multiplier, or settlement amount.
  Basis can appear acceptable while the submitted exposure is wrong.
- **Required correction:** use separate typed `EvidenceMarketIdentity` and
  `ExecutionInstrumentIdentity` on plan, eligibility, command, receipt, reconciliation, and
  journal. Persist provider symbols, venue IDs, market/product type, base/quote/settlement
  currencies, linear/inverse type, contract multiplier, quantity unit, tick/lot/minimum rules,
  mapping version, and source timestamps. Store the basis snapshot, formula, policy/tolerance
  version, and both prices. A breach blocks `ActionEligibility` only.
- **Required test:** fixtures where symbols look equivalent but contract multiplier, lot size,
  quote currency, inverse/linear type, or tick size differs. Assert deterministic conversion,
  round-down, conservative risk, basis block without `SetupAssessment` mutation, and no use of
  evidence-venue tick/quantity rules for the venue order.

### HIGH-07 — Partial fills do not have an explicit position/exposure transition

- **Severity:** HIGH
- **Exact evidence:**
  - The state diagram transitions `ACKNOWLEDGED -> PARTIALLY_FILLED -> FILLED ->
    POSITION_OPEN`; a partially filled then cancelled order has no transition to an open
    position (`docs/redesign/agentic_redesign_target_architecture.md:990-1011`).
  - The prose updates average price, fees, and remaining size, but does not require the
    position size and risk exposure to update on every fill
    (`docs/redesign/agentic_redesign_target_architecture.md:1030-1041`).
  - Current demo mirroring creates an internal full-size paper position before venue truth,
    illustrating the state that Phase 9 must replace
    (`backend/src/app/services/execution_service.py:410-525, 529-559`).
- **Failure scenario:** 20% of an entry fills and the remainder is cancelled. The order is
  `CANCELLED`, but no `POSITION_OPEN` transition exists, so the system can show no exposure or
  the requested full exposure rather than the actual 20%. A later close can use the wrong size.
- **Required correction:** every unique fill must atomically update cumulative filled
  quantity, weighted price, fees, and the reconciled/open position exposure. A partially
  filled order opens/updates a position immediately. Cancel affects only remaining quantity;
  partial-cancel and late-fill transitions must preserve actual exposure. Close quantity is
  derived from a fresh reconciled position, never requested entry size.
- **Required test:** zero fill, one partial fill, multiple partial fills, duplicate fill,
  partial-fill/cancel race, late fill after cancel request, and partial reduce-only close.
  Position size and risk exposure must equal unique net fills after every transition.

### HIGH-08 — Fill identity and reconciliation finality leave a duplicate-accounting path

- **Severity:** HIGH
- **Exact evidence:**
  - The target makes only **non-null** fill IDs unique and permits resubmit after
    “authoritative proof of absence,” without defining venue finality/settling semantics
    (`docs/redesign/agentic_redesign_target_architecture.md:1023-1036`).
  - `ReconciliationState` can end `FAILED`, but the allowed operational behavior and account
    quarantine after timeout are not specified
    (`docs/redesign/agentic_redesign_target_architecture.md:1051-1058, 1499-1504`).
  - Current storage permits null fill IDs and has no fill uniqueness constraint
    (`backend/src/app/db/models.py:1985-2028`).
- **Failure scenario:** the venue returns a fill without a usable trade ID, or a trade-history
  page repeats it. Retry inserts it twice, doubling position/PnL/fees. Separately, an eventually
  consistent order lookup briefly returns absent after an ambiguous submit, allowing resubmit.
  A reconciliation timeout then becomes `FAILED` without explicitly blocking new entries.
- **Required correction:** require a stable venue trade/fill ID; if the venue cannot provide
  one, define a documented, versioned immutable composite identity with collision analysis or
  treat the feed as unsupported and keep reconciliation unresolved. Define bounded
  finality/overlap cursors and never infer final absence from one negative lookup. A failed or
  timed-out reconciliation must quarantine new exposure for that account/instrument, keep
  uncertainty visible, and permit only safe reconciliation/cancel/reduce-only recovery actions
  under fresh checks.
- **Required test:** missing/repeated fill ID, overlapping pages, out-of-order and corrected
  fills, delayed order visibility, negative-then-positive client-ID lookup, and reconciliation
  timeout. Assert one accounting effect per fill, no resubmit during uncertainty, and
  account/instrument action block until consistent.

### HIGH-09 — Authorization is not explicitly compared to the complete order payload

- **Severity:** HIGH
- **Exact evidence:**
  - Authorization binds revision/hash, while `ExecutionCommand` independently accepts venue,
    instrument, side, type, quantity, and price
    (`docs/redesign/agentic_redesign_target_architecture.md:773-823`).
  - The target does not explicitly require `ExecutionService` to load the scoped revision,
    recompute its hash, and derive/compare every venue field. The command also omits
    `reduce_only`, time-in-force, margin mode, position side, and instrument-spec identity.
  - Current risk binding does compare proposal symbol, side, size, and price
    (`backend/src/app/services/paper_execution_risk_gate.py:94-138`).
- **Failure scenario:** a valid authorization for quantity 1 is paired with quantity 2 or a
  different order type while retaining the approved plan hash. Idempotency faithfully binds
  the unsafe command but does not prove that it is the approved command.
- **Required correction:** `ExecutionService` must tenant-load and hash-verify the revision,
  then derive the complete venue payload server-side. Bind every safety-relevant order
  attribute, including reduce-only, time-in-force, account/margin/position mode, trigger/limit
  fields, instrument specification, and conversion/rounding result.
- **Required test:** retain one authorization and independently mutate every executable field.
  Each mismatch must fail before authorization consumption, risk reservation, order creation,
  or venue effect enqueue.

### HIGH-10 — Candle finality is labelled but not deterministically derived

- **Severity:** HIGH
- **Exact evidence:**
  - `MarketObservation` names interval bounds, finality, a policy version, and grace, but the
    architecture never defines `OHLCVPayload` or the exact finality predicate
    (`docs/redesign/agentic_redesign_target_architecture.md:357-390`).
  - Runtime prose says provider finality plus grace, while the first slice requires final
    perpetual bars (`docs/redesign/agentic_redesign_target_architecture.md:877-884,
    1367-1397`).
  - Current `OHLCVBar` has only one timestamp and no close/finality field
    (`backend/src/app/providers/market_data.py:66-74`).
- **Failure scenario:** an intrabar liquidity sweep on the currently forming 15-minute candle
  is labelled final based on opening timestamp or local interval math, confirms a candidate,
  and disappears by venue close.
- **Required correction:** define OHLCV open/close times, provider-final/completion semantics,
  source event/revision identity, and the exact rule:
  `FINAL iff provider_complete AND evaluated_at >= interval_end + versioned_grace`.
  Unknown provider semantics remain `UNKNOWN`; a correction or final form appends a new
  observation rather than mutating the forming one.
- **Required test:** the same source candle immediately before close, at close, during grace,
  after grace, and after correction. Only the appended final observation may confirm.

### HIGH-11 — Trade/CVD natural identity and arithmetic are underdefined

- **Severity:** HIGH
- **Exact evidence:**
  - `TradeEvent.quantity` may be base or contract units while `quote_quantity` is supplied
    independently; `CvdWindow` lacks explicit unit, currency, multiplier/formula, rounding,
    half-open interval, and included event-range fields
    (`docs/redesign/agentic_redesign_target_architecture.md:407-467`).
  - Observation uniqueness includes `adapter_version`, allowing the same venue event to be
    inserted again after an adapter upgrade
    (`docs/redesign/agentic_redesign_target_architecture.md:392-397`).
  - CVD sums ordered signed quote quantity and first-slice windows can cross reconnect recovery
    (`docs/redesign/agentic_redesign_target_architecture.md:1396-1405`).
- **Failure scenario:** adapter v2 reprocesses an aggregate trade stored by v1 and both
  normalization revisions enter CVD. Another adapter interprets quantity as contracts rather
  than base units or assigns a boundary trade to the adjacent bar, producing a different
  divergence from the same venue facts.
- **Required correction:** make venue/event natural identity independent of adapter version;
  store versioned normalization revisions beneath it and pin one adapter policy for replay.
  Define quantity unit, quote/settlement currency, contract formula, precision/rounding,
  half-open event-time windows with event-ID tie-break, first/last included IDs, event-set hash,
  baseline/reset policy, and correction selection.
- **Required test:** adapter v1/v2 ingestion of the same trade, base and contract quantities,
  inverse/linear formula vectors, boundary timestamps, duplicates, reordering, corrections,
  and exact CVD at swing/trigger closes. A natural trade is counted once.

### HIGH-12 — Tenant-owned TradingView signals cannot be global market observations

- **Severity:** HIGH
- **Exact evidence:**
  - The target says public `MarketObservation` facts are global, yet includes `TRADINGVIEW` as
    a global observation type/payload
    (`docs/redesign/agentic_redesign_target_architecture.md:348-388`).
  - Current TradingView signals are organization-owned and can carry strategy/setup linkage
    and private redacted payload metadata (`backend/src/app/db/models.py:2098-2164`).
- **Failure scenario:** a proprietary tenant alert or strategy-linked TradingView payload is
  normalized into the global store and deduped, queried, or reused by another organization.
- **Required correction:** limit global observations to public venue facts. Represent
  TradingView as a tenant-scoped external signal/assessment referencing public observations,
  or define an ownership-discriminated envelope whose tenant-private variants can never enter
  global indexes or queries.
- **Required test:** ingest the same external alert ID and similar payload for two
  organizations; assert no cross-tenant payload, strategy linkage, normalized signal, dedupe
  decision, or candidate reference.

### HIGH-13 — Scan lineage and crash recovery lack a first-slice domain contract

- **Severity:** HIGH
- **Exact evidence:**
  - Runtime prose requires a scan attempt before work, detailed source/subscription counts,
    fencing token, and honest outcomes
    (`docs/redesign/agentic_redesign_target_architecture.md:877-897`).
  - The first-slice domain-contract table defines no scan/source/subscription attempt, and
    `Candidate` has no direct attempt lineage
    (`docs/redesign/agentic_redesign_target_architecture.md:1477-1503`).
  - Current worker records/heartbeat behavior does not prove durable in-progress recovery; the
    Phase 0 audit confirms the worker/manual pipeline split
    (`docs/redesign/agentic_redesign_phase0_audit.md:375-414`).
- **Failure scenario:** a process commits candidate/outbox data and crashes before finishing
  the scan record. Health shows the previous cycle, the candidate cannot be attributed to an
  exact source/subscription attempt, and replacement logic cannot distinguish unfinished work
  from a completed attempt.
- **Required correction:** define separately committed `ScanAttempt`, `SourceFetchAttempt`,
  and `SubscriptionEvaluationAttempt` contracts with worker instance, lease epoch, policy
  versions, started/heartbeat/finished times, attempt counts, status, error, and recovery
  disposition. Link observations, assessments, candidates, and outbox rows to those attempts.
- **Required test:** crash after attempt creation, fetch, observation persistence, candidate
  insert, and outbox insert. Assert honest health, attributable lineage, orphan recovery, and
  no duplicate candidate/delivery.

### HIGH-14 — Risk actions need an operation-specific `BLOCK`/`WARN` matrix

- **Severity:** HIGH
- **Exact evidence:**
  - Target diagrams disagree: the sequence says `BLOCK/WARN` stops, while other diagrams expose
    only `BLOCK` and `ALLOW`
    (`docs/redesign/agentic_redesign_target_architecture.md:90-94, 173-177, 220-225`).
  - Kill switch and daily risk are general action-eligibility blockers, while `CLOSE` requires
    fresh kill-switch checks but must reduce an existing position
    (`docs/redesign/agentic_redesign_target_architecture.md:497-501, 967-976`).
  - Current execution blocks only `RiskAction.BLOCK`
    (`backend/src/app/services/paper_execution_risk_gate.py:199-218`).
- **Failure scenario:** a uniform kill-switch/daily-loss block traps an open position by
  preventing cancel or reduce-only close. An indiscriminate bypass lets a mislabeled close
  flip/increase exposure. Separately, one implementation submits on `WARN` while another stops.
- **Required correction:** define a deterministic operation matrix: opening/increasing exposure
  is blocked; authenticated cancel and exact reconciled reduce-only decrease/close follow an
  explicit conservative emergency policy. Define each WARN-producing rule as either stop plus
  revised plan/reapproval or explicitly bounded allow. `BLOCK` is never overrideable.
- **Required test:** activate kill switch/daily loss before entry, after submit, during partial
  fill, before cancel, and before close. Assert no exposure increase, declared cancel/reduce
  behavior, no side flip, and exact authorization state for every WARN.

### HIGH-15 — Telegram enrollment and receipt identity are not durable domain contracts

- **Severity:** HIGH
- **Exact evidence:**
  - Enrollment/binding and receipts are described in prose, but §18 defines no enrollment
    challenge, binding, bot installation, update receipt, callback receipt, or action receipt
    contract (`docs/redesign/agentic_redesign_target_architecture.md:925-955,
    1477-1503`).
  - `update_id` and `callback_query_id` uniqueness is not scoped to immutable bot-installation
    identity; enrollment has no token hash, CAS lifecycle, active-binding uniqueness,
    revocation/replacement, or bot-rotation rule.
- **Failure scenario:** a consumed/leaked enrollment link is reused to bind another chat, two
  concurrent completions create active bindings, or a rotated/second bot emits an update ID
  colliding with an old bot's receipt and receives the wrong outcome.
- **Required correction:** define `BotInstallation`, `TelegramEnrollmentChallenge`,
  `TelegramBinding`, update/callback receipt, and action-receipt contracts. Store challenge
  tokens hashed; bind org/user/bot; use expiry and one-time CAS; enforce one active private
  binding per policy; scope secrets and receipt uniqueness to bot installation/credential
  version; define revocation, replacement, and rotation.
- **Required test:** replay/concurrent enrollment, wrong Telegram user, group chat, expiry,
  revoked challenge, duplicate active binding, bot rotation, retired bot, wrong endpoint
  secret, and identical update IDs from two bot installations.

### HIGH-16 — Telegram `CLOSE` lacks working-order serialization and a durable close command

- **Severity:** HIGH
- **Exact evidence:**
  - `CLOSE` requires preview, second nonce, fresh position reconciliation, and delegation to
    `ExecutionService`, but the only command contract is `EXECUTE_PAPER_PLAN`
    (`docs/redesign/agentic_redesign_target_architecture.md:803-823, 967-976`).
  - The architecture does not bind live competing orders or serialize the
    reconciliation-to-submit interval; it only says close has an independent idempotency key
    (`docs/redesign/agentic_redesign_target_architecture.md:1032-1045`).
- **Failure scenario:** a take-profit fills after the position snapshot but before a Telegram
  close POST, or duplicate second callbacks race. The close is oversized, duplicated, rejected,
  or flips exposure, and replay has no stable close receipt to return.
- **Required correction:** add a first-class close command/receipt bound to organization,
  user, exchange account, action receipt and second nonce, position ID/version/hash, all working
  orders, venue instrument, exact current side/contract quantity, reduce-only, deterministic
  client ID, and canonical hash. Claim nonce, create command/receipt, and enqueue one durable
  close effect atomically. Serialize close preparation per account/instrument and re-reconcile
  competing exits.
- **Required test:** duplicate callbacks and crashes at each claim/send boundary; TP fill
  between preview/confirmation and reconciliation/submit; concurrent web/Telegram close;
  partial close and active kill switch. At most one close command may reduce the exact current
  exposure.

### HIGH-17 — Record ownership does not guarantee account-scoped credentials or fresh NET mode

- **Severity:** HIGH
- **Exact evidence:**
  - Target prose binds credentials/records to `ExchangeAccount`, but it does not explicitly
    replace global provider resolution or require a fresh mode probe immediately before every
    effect (`docs/redesign/agentic_redesign_target_architecture.md:1017-1041`).
  - Current provider construction reads one global credential set from `Settings`
    (`backend/src/app/providers/exchange/factory.py:39-119`).
  - Current provider probes position mode during placement and passes size directly
    (`backend/src/app/providers/exchange/blofin_execution.py:57-91`).
- **Failure scenario:** organization A's command is labelled with A's account ID but a cached
  singleton submits with B/global credentials; or the venue changes from net to hedge mode
  after approval and before dispatch.
- **Required correction:** account-scoped provider resolution must require the authorized
  `ExchangeAccount` and secret reference; forbid global credential fallback. Bind permission
  attestation to venue account UID, demo host, credential fingerprint/version, and probe time.
  Probe and bind NET mode immediately before each entry/close effect; mismatch rejects before
  POST and remains reconcilable.
- **Required test:** two tenants/accounts concurrently, provider-cache cross-wiring, stale or
  rotated credential, venue-account UID mismatch, and mode changes after plan, approval,
  command claim, and close preview. Every mismatch fails before submit.

### HIGH-18 — `ExecutionReceipt` is both mutable current state and immutable content

- **Severity:** HIGH
- **Exact evidence:**
  - The receipt contains current state and fill aggregates
    (`docs/redesign/agentic_redesign_target_architecture.md:1051-1055`).
  - The domain table describes immutable accepted/submitted/updated transition facts and a
    content hash, while replay returns “the same receipt”
    (`docs/redesign/agentic_redesign_target_architecture.md:1497-1498`).
- **Failure scenario:** a replay returns the original `ACKNOWLEDGED` snapshot after the order is
  partially filled/closed, or a mutable receipt changes underneath its prior content hash.
- **Required correction:** use a stable `receipt_id`, append-only `ExecutionTransition` events,
  and an explicitly versioned current projection. Define that replay returns the stable
  identity plus latest authorized projection and event watermark; historical hashes remain
  immutable.
- **Required test:** replay before acknowledgement and after partial fill, cancel, close, late
  fill, and reconciliation correction. Identity remains stable, versions advance
  monotonically, and prior events/hashes do not change.

### HIGH-19 — Current journal APIs can overwrite or delete venue truth

- **Severity:** HIGH
- **Exact evidence:**
  - The target says reconciled prices/fills/PnL retain provenance and cannot be silently
    overwritten (`docs/redesign/agentic_redesign_target_architecture.md:1090-1097`).
  - Current `JournalTradeUpdate` exposes entry/exit, size, leverage, fees, funding, gross/net
    PnL, and result (`backend/src/app/schemas/journal_trades.py:96-139`).
  - Current service assigns every provided field directly and permits deletion
    (`backend/src/app/services/journal_trade_service.py:355-387`).
- **Failure scenario:** a user edit replaces venue-derived fees or net PnL, or deletes a
  projected trade while immutable fills remain. Analytics then report editable assertions as
  reconciled venue facts.
- **Required correction:** separate reflective user-owned fields from projector-owned facts.
  Venue facts derive from immutable fill/bill/reconciliation links; corrections append with
  actor/reason/supersession. Manual overrides are separate labelled assertions. Restrict hard
  deletion to unexecuted drafts or use tombstones.
- **Required test:** attempt edits/deletion after first fill and after final reconciliation.
  Authoritative facts and source links remain unchanged; corrections preserve prior values and
  actor/reason.

### HIGH-20 — `REJECT`, `SKIP`, and `REDUCE_RISK` do not define descendant invalidation

- **Severity:** HIGH
- **Exact evidence:**
  - The action table states the immediate effect of `REJECT`, `SKIP`, and `REDUCE_RISK`, but
    does not define their transaction across candidate, plan, authorization, and already
    claimed execution descendants
    (`docs/redesign/agentic_redesign_target_architecture.md:960-969`).
  - Candidate, plan, and authorization transitions are listed separately without a cascade
    matrix (`docs/redesign/agentic_redesign_target_architecture.md:1494-1498`).
- **Failure scenario:** Telegram rejects a candidate while an approved descendant remains
  executable over web/API; or merely requesting a lower-risk preview revokes the current
  authorization before the new revision is explicitly confirmed.
- **Required correction:** define an atomic action/state matrix: whether reject/skip revokes
  descendant plans/authorizations, behavior for claimed commands, non-mutating
  `REDUCE_RISK` preview versus confirmed revision creation, and atomic supersession plus prior
  authorization revocation. A claimed/submitted command cannot be erased by a parent action.
- **Required test:** cross every candidate/plan/authorization/execution state with `REJECT`,
  `SKIP`, and preview/confirmed `REDUCE_RISK`, including races with execution claim. Assert
  exact descendant state, no implicit mutation on preview, and no stale executable path.

### MEDIUM-01 — Cancel and close lack complete operation-specific command contracts

- **Severity:** MEDIUM
- **Exact evidence:**
  - The only specified `ExecutionCommand.operation` is `EXECUTE_PAPER_PLAN`
    (`docs/redesign/agentic_redesign_target_architecture.md:803-823`).
  - Cancel and close are later assigned independent idempotency keys, but no canonical command
    payload, principal/resource binding, or operation namespace is defined for them
    (`docs/redesign/agentic_redesign_target_architecture.md:1032-1045`).
  - Telegram `CLOSE` correctly requires a position-bound second confirmation
    (`docs/redesign/agentic_redesign_target_architecture.md:967-976`).
- **Failure scenario:** entry, cancel, and close handlers hash different ad hoc fields or reuse
  an opaque key namespace. A repeated close can resolve an entry receipt, or a changed
  position size can replay an old close result instead of rejecting.
- **Required correction:** define separate typed `SubmitEntryCommand`, `CancelOrderCommand`,
  and `ClosePositionCommand` (or one discriminated union). Each includes operation in the
  canonical hash and exact tenant/account/resource revision. Close binds reconciled position
  ID/version, side, current size, reduce-only flag, and second authorization/nonce.
- **Required test:** reuse one key across entry/cancel/close and assert conflicts; replay each
  identical command and assert convergence; change order/position version, side, quantity, or
  account and assert rejection before mutation.

### MEDIUM-02 — Telegram receipt state is not mechanically bound to domain idempotency

- **Severity:** MEDIUM
- **Exact evidence:**
  - The gateway defines unique `update_id`, `callback_query_id`, nonce, and action receipts and
    claims that repeated delivery returns the original outcome
    (`docs/redesign/agentic_redesign_target_architecture.md:931-955`).
  - It does not state that every delegated mutating domain command uses the durable action
    execution ID/nonce as its idempotency identity in the same transaction that changes
    `CLAIMED -> APPLIED`.
- **Failure scenario:** a callback is claimed and the domain mutation commits, but the process
  crashes before the Telegram receipt becomes `APPLIED`. Lease recovery delegates the action
  again; a service that has only local/ad hoc idempotency creates a second rejection, revision,
  approval, or close.
- **Required correction:** persist a unique action-execution record before delegation and pass
  its immutable ID plus canonical action hash into every domain command. Domain mutation and
  action result linkage must be atomic where local; recovery must query/return the authoritative
  domain result rather than invoke an unbound mutation again.
- **Required test:** inject a crash after each domain mutation commit but before callback result
  update for `REJECT`, `SKIP`, `APPROVE`, `REDUCE_RISK`, and both `CLOSE` steps. Re-delivery
  must return the original outcome with exactly one internal mutation.

### MEDIUM-03 — Journal projection event dedupe does not guarantee one `JournalTrade`

- **Severity:** MEDIUM
- **Exact evidence:**
  - Projection-event idempotency is
    `(correlation_id, projection_event_type, source_event_id)`
    (`docs/redesign/agentic_redesign_target_architecture.md:1077-1096`).
  - The domain table says one lifecycle maps to one `JournalTrade`, but it does not define a
    database uniqueness key for the lifecycle-to-trade mapping or transactional get-or-create
    (`docs/redesign/agentic_redesign_target_architecture.md:1498-1504`).
- **Failure scenario:** plan-approved and first-fill projectors run concurrently. Their event
  keys differ, so each can create a different canonical trade before either sees the other's
  row. All projection events are unique while the journal contains two trades.
- **Required correction:** define one non-null canonical trade aggregate identity and database
  uniqueness constraint, for example organization plus execution lifecycle/position ID (with
  explicit policy for planned-but-never-executed records). Every event resolves that mapping in
  a transaction before applying append-only facts. Venue fact corrections retain source,
  actor, reason, and supersession lineage; reflective fields remain separately editable.
- **Required test:** concurrently deliver plan, first-fill, duplicate fill, close, and
  reconciliation events in every order. Assert one `JournalTrade`, one effect per source event,
  immutable venue-fact provenance, retryable journal failure without venue rollback, and
  correct reconciled PnL/fees/funding only after finality.

### MEDIUM-04 — The reuse map still labels order-book features as “order flow”

- **Severity:** MEDIUM
- **Exact evidence:**
  - Required CVD/exhaustion is correctly derived from signed perpetual trades, and book data is
    optional supporting evidence
    (`docs/redesign/agentic_redesign_target_architecture.md:1367-1377, 1396-1405`).
  - The reuse table nevertheless maps “Order flow” to order-book contract and
    imbalance/exhaustion features
    (`docs/redesign/agentic_redesign_target_architecture.md:1434-1439`).
- **Failure scenario:** an implementer treats complete L2 imbalance as satisfying required
  aggressive-flow exhaustion when signed trades are unavailable.
- **Required correction:** rename the row to optional resting-liquidity/L2 evidence. Assign
  required CVD and aggressive-flow exhaustion exclusively to explicit signed perpetual
  executions; missing trade flow blocks confirmation even when book continuity is complete.
- **Required test:** hold trades fixed while changing the book and prove CVD is unchanged;
  remove signed trades while supplying a complete book and prove confirmation fails.

### MEDIUM-05 — Replay requirements do not define canonical fixture bundles

- **Severity:** MEDIUM
- **Exact evidence:**
  - Testing requests CVD, gap, reordering, replay, and end-to-end convergence, but no fixture
    manifest, clock, arrival ordering, adapter/policy versions, or expected hashes are defined
    (`docs/redesign/agentic_redesign_target_architecture.md:1306-1321, 1451-1468`).
- **Failure scenario:** tests start from already-normalized events and miss adapter timestamp,
  aggressor inversion, event-dedupe, reconnect, and correction defects. Incompatible
  implementations can each claim deterministic replay.
- **Required correction:** define immutable sanitized fixture bundles with raw REST/stream
  payloads, arrival order, event/wall clocks, reconnect markers, instrument and
  adapter/finality/freshness/fusion versions, and expected observation hashes, cursor/gap
  ledger, CVD windows, transitions, candidate key, and reason codes.
- **Required test:** replay from empty and partially ingested databases, shuffled delivery,
  restart, and adapter revision; require identical selected normalized hashes and logically
  identical transition/output sets.

### MEDIUM-06 — Manual and worker “same pipeline” omits persistence-mode concurrency

- **Severity:** MEDIUM
- **Exact evidence:**
  - Manual scans use the same evaluator with `dry_run=true`, while scheduling and persistence
    policy may differ (`docs/redesign/agentic_redesign_target_architecture.md:895-900`).
  - The target does not define authorized manual persistence racing worker persistence or how
    it participates in fence-compatible repositories.
- **Failure scenario:** worker and non-dry manual evaluation process one window concurrently.
  Detector outputs match, but distinct persistence modes create competing assessment
  transitions or delivery intents.
- **Required correction:** define one typed evaluation command with explicit `PREVIEW`,
  `PERSIST_EVIDENCE`, and `PERSIST_AND_NOTIFY` modes. All use the same source adapter, clock,
  policy, finality, fusion, candidate key, and transactional repositories. Preview creates no
  durable state; persistent modes converge even if only scheduler work owns a lease.
- **Required test:** race worker persistence, manual preview, and authorized manual persistence
  over one fixture. Preview writes nothing; persistent callers converge on one assessment,
  candidate transition, and delivery intent.

### MEDIUM-07 — Journal source identity and candidate-draft boundary are ambiguous

- **Severity:** MEDIUM
- **Exact evidence:**
  - The proposed event key omits source system, account/aggregate identity, and correction
    version (`docs/redesign/agentic_redesign_target_architecture.md:1090-1093, 1500`).
  - The projection table permits an optional `JournalTrade` draft at candidate confirmation,
    while the target also says one execution lifecycle maps to one canonical trade
    (`docs/redesign/agentic_redesign_target_architecture.md:1077-1089, 1498-1504`).
- **Failure scenario:** two sources reuse a textual event ID, or a corrected event is discarded
  as duplicate. Separately, skipped/expired candidates inflate planned-trade counts and
  complicate one-execution/one-trade uniqueness.
- **Required correction:** namespace projection identity by source system, account/aggregate,
  event type/version, and supersession. Keep candidate/reject/skip in candidate lifecycle
  events; create canonical `JournalTrade` only at approved-plan or first-fill boundary, with
  earlier lineage linked but not represented as a trade row.
- **Required test:** same source-event ID across account/provider, correction with reused ID,
  and confirmed candidate followed by skip/reject/expiry. Corrections append correctly and no
  unexecuted candidate creates a canonical trade.

## 4. Market data and CVD/order-flow decision

Subject to HIGH-02, HIGH-03, HIGH-10, HIGH-11, and HIGH-12, the architecture correctly requires:

- explicit perpetual venue, market type, canonical instrument, provider symbol, source event
  ID, aggressor semantics/version, event/receive times, cursor/connection, gap state, warm-up,
  finality, live/fallback, and content hash
  (`docs/redesign/agentic_redesign_target_architecture.md:357-474`);
- buyer-aggressor positive and seller-aggressor negative quote-volume CVD only when provider
  semantics are known and versioned (`docs/redesign/agentic_redesign_target_architecture.md:
  470-474, 1396-1405`);
- rejection of spot/perpetual substitution, fallback, stale, unknown aggressor, unresolved gap,
  and incomplete warm-up (`docs/redesign/agentic_redesign_target_architecture.md:470-474`);
- final candles plus versioned post-close grace, with forming/unknown-finality evidence
  ineligible (`docs/redesign/agentic_redesign_target_architecture.md:877-885`);
- order book as optional supporting evidence only after snapshot/stream continuity; resting
  liquidity is not CVD (`docs/redesign/agentic_redesign_target_architecture.md:1371-1377,
  1415-1421`).

The design remains valid without order book in v1 because the required exhaustion metric is
derived from signed perpetual trades, while depth is optional supporting evidence.

## 5. Watcher/worker decision

The intended common worker/manual evaluator, candidate TTL, transactional upsert, optimistic
transition versioning, scan lineage, degraded/failed counts, and disabled-until-review posture
are sound (`docs/redesign/agentic_redesign_target_architecture.md:872-900`).

Implementation cannot rely on the current lock, current separate scan pipelines, or current
freshness behavior. HIGH-04, HIGH-05, HIGH-13, and MEDIUM-06 must define the enforceable
fence, semantic candidate key, durable attempt lineage, and persistence-mode behavior first.
Once corrected, retries or duplicate sources can converge without stale workers producing
candidate/outbox writes.

## 6. Telegram security decision

The proposed policy boundary is directionally acceptable, but HIGH-15, HIGH-16, MEDIUM-01, and
MEDIUM-02 must supply the durable enrollment, bot, receipt, and close-command contracts:

- enrollment starts in authenticated AlphaTrade web and completes with the same Telegram user
  in a private chat;
- binding includes organization, AlphaTrade user, Telegram user, private chat/type, bot
  identity, verification/revocation, and allowed actions;
- webhook secret, bounded body, rate limits, update-type allowlist, unique update/callback
  receipts, opaque nonce, exact resource/revision/hash/action, expiry, and single-use CAS are
  required;
- server-side role, ownership, object state, risk, and expiry are rechecked;
- `STATUS`, `EXPLAIN`, and `SHOW_CHART` are read-only; `REJECT` and `SKIP` cannot execute;
  `APPROVE` creates authorization only; `REDUCE_RISK` creates a new revision and invalidates
  old authorization;
- `CLOSE` binds a fresh reconciled position/account/side/size/state, requires a second
  short-lived nonce, re-reconciles and rechecks safety, and uses reduce-only execution;
- Telegram plan execution is not included in this rollout.

These contracts are at
`docs/redesign/agentic_redesign_target_architecture.md:925-976`.

## 7. BloFin DEMO decision

The target correctly keeps `ExecutionService` as sole authority, retains demo-host-only and
paper-only gates, requires tenant account credentials and fresh permissions, chooses NET MODE
ONLY, prohibits blind POST retry, uses deterministic client order IDs, makes uncertainty
visible, and refuses to claim `FILLED` from request transmission alone
(`docs/redesign/agentic_redesign_target_architecture.md:979-1064`).

BLOCKER-01 through BLOCKER-05, HIGH-06 through HIGH-09, HIGH-14, HIGH-16 through HIGH-18, and
MEDIUM-01 are required before that lifecycle can be implemented safely. In particular, an
acknowledged or partially filled order is venue exposure even if the requested quantity did
not fully fill, and reconciliation uncertainty must conservatively constrain subsequent
actions.

## 8. Cross-venue decision

The architecture correctly separates setup truth from action eligibility and states that a
basis breach blocks `ActionEligibility` without rewriting `SetupAssessment`
(`docs/redesign/agentic_redesign_target_architecture.md:497-501, 1462-1467`).

HIGH-06 prevents approval because two venue IDs plus one instrument field do not establish two
complete market identities or safe contract conversion. The basis and instrument-rule
snapshot must be explicit and provenance-bound before cross-venue planning or execution;
HIGH-17 must also ensure the selected account credential and current NET mode belong to that
execution identity.

## 9. Journal integrity decision

The target correctly selects canonical `JournalTrade`, preserves venue execution when journal
projection fails, makes projection retryable, keeps venue facts provenance-bound and
append-only, blocks final PnL while reconciliation is unresolved, and moves behavioral
migration/parity before automation
(`docs/redesign/agentic_redesign_target_architecture.md:1066-1113, 1250-1256`).

MEDIUM-03 must add aggregate uniqueness; HIGH-19 must separate editable reflection from
projector-owned venue truth; MEDIUM-07 must namespace source events and keep candidates outside
trade rows. With those corrections, fill retries, close corrections, and journal recovery can
preserve one lifecycle without erasing venue truth or behavioral data.

## 10. Deterministic failure matrix

| Failure | Required safe state in the target | Review result |
|---|---|---|
| Provider unavailable | Observation/source unavailable; assessment/cycle degraded or failed; no confirmed setup/plan/order | Defined |
| Fallback data | Display-only degraded evidence; no candidate confirmation, executable plan, or execution | Defined |
| Forming candle | `FORMING`; no final-evidence use | Defined |
| Sequence gap | CVD/window unusable; setup invalidated/blocked | Defined |
| Reconnect | Fail closed until continuity and warm-up | Correction required: HIGH-03 and HIGH-11 |
| Stale trade flow | No confirmation/plan/execution | Correction required: HIGH-02 makes time expiry deterministic |
| Duplicate/adapter-revised trade | One natural venue event selected for CVD | Correction required: HIGH-11 |
| Tenant TradingView signal | Tenant-scoped assessment; no global leakage | Correction required: HIGH-12 |
| Duplicate candidate | One database candidate and separate delivery dedupe | Correction required: HIGH-05 and HIGH-13 |
| Duplicate Telegram delivery | At-least-once delivery; internal action returns original outcome | Defined |
| Duplicate callback | Unique bot-scoped update/callback/action receipts and nonce CAS | Correction required: HIGH-15, HIGH-16, and MEDIUM-02 |
| Expired/enrollment nonce | Reject and audit; no state change | Correction required: HIGH-15 for durable lifecycle |
| Wrong plan revision/hash | Reject and audit; no authorization/order | Defined |
| Kill-switch activation | Final entry/increase block; explicit cancel/reduce policy | Correction required: HIGH-01 and HIGH-14 |
| Daily-loss block | Final entry/increase block; explicit cancel/reduce policy | Correction required: HIGH-01 and HIGH-14 |
| Concurrent distinct commands | One serializable risk reservation per account | Unsafe/undefined: BLOCKER-04 |
| Duplicate authorization | One active authorization/execution claim per plan/account | Unsafe/undefined: BLOCKER-05 |
| Authorization replay | Reject consumed/expired/revoked/wrong binding | Correction required: BLOCKER-01, BLOCKER-05, and HIGH-09 |
| Ambiguous demo submit | `RECONCILIATION_REQUIRED`; client-ID lookup; no blind retry | Correction required: BLOCKER-03 and HIGH-08 |
| Partial fill | Fill/remaining quantity/fees updated | Unsafe/undefined position exposure: HIGH-07 |
| Late fill | Idempotently ingest before final state | Correction required: HIGH-07 and HIGH-08 |
| Cancel | `CANCEL_PENDING`, reconcile detail and late fills, then final state | Correction required: HIGH-07, HIGH-14, and MEDIUM-01 |
| Telegram close replay/race | One position-bound reduce-only command/receipt | Unsafe/undefined: HIGH-16 |
| Position-mode mismatch | Reject hedge/unknown; no reinterpretation or submit | Correction required: HIGH-17 for immediate account-scoped recheck |
| Basis breach | `ActionEligibility=BLOCKED`; `SetupAssessment` unchanged | Defined; identity correction HIGH-06 |
| Reconciliation timeout | Visible unresolved/failed state; no fabricated final truth | Correction required: HIGH-08 for quarantine/recovery authority |
| Duplicate journal projection | One event effect and one canonical trade | Correction required: MEDIUM-03 and MEDIUM-07 |
| Journal venue-fact edit/delete | Immutable projector facts; append-only correction | Unsafe under current API: HIGH-19 |

No failure may produce a success receipt, confirmed candidate, executable plan, fill, closed
position, finalized PnL, or journal fact without the corresponding authoritative evidence.

## 11. Phase 1 safety foundation decision

The migration order correctly begins with:

1. characterization of paper-only, live-host denial, kill switch, and deterministic risk;
2. tenant/principal/payload/revision-bound idempotency;
3. authoritative intent and operation-class isolation at graph and service/persistence
   boundaries;
4. removal of analysis/question-to-mutation paths;
5. fail-closed replacement of successful no-op mutation/execution tools;
6. immutable `TradePlanRevision` with no executable placeholders;
7. expiring, exact-revision, content-hash-bound, consumable authorization for a separate
   explicit execution operation.

Evidence:
`docs/redesign/agentic_redesign_target_architecture.md:1220-1238, 1508-1535`.

However, Phase 1 must not begin until BLOCKER-01 through BLOCKER-06 and direct Phase 1 contract
findings HIGH-01, HIGH-09, and HIGH-14 are corrected in the canonical architecture. Item 1
must explicitly characterize the known analysis-to-proposal write, successful execution stub,
global key-only replay, internal-first demo mirror, and cancel-status behavior before replacing
them; “freeze existing” must not preserve unsafe semantics. The account, hash, transaction,
risk reservation, execution uniqueness, paper-mode, payload-binding, and blocked-operation
definitions are the foundation Phase 1 would otherwise implement incorrectly. All automation
flags remain off throughout implementation and testing; enabling any staging/demo capability
remains a separate authorization and review.

## 12. CI and scope gate

At review completion, GitHub reported the following successful checks on exact PR #64 head
`8511ea15dbd6f036a873a049b1adce84a89104cb`:

- backend
- deployment-safety
- frontend
- docker-build
- evaluation
- e2e-smoke
- Vercel
- Vercel Preview Comments

Exact-head CI is therefore green for the reviewed commit. This review is documentation-only;
green CI does not resolve the architecture findings above.

No canonical Phase 0 document was modified by this review. No worker/watcher, Telegram
delivery, BloFin demo execution, deployment, migration, production host, or real-trading path
was enabled or invoked.

## 13. Final verdict

**NOT APPROVED**

Correct all BLOCKER findings in the canonical target architecture and close the associated
HIGH/MEDIUM contract gaps before Phase 1 coding. Then repeat this safety/data/execution gate
against a new exact head. This verdict does not authorize implementation, merge, deployment,
remote delivery, exchange connectivity, demo execution, or live trading.
