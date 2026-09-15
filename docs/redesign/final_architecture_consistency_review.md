# AlphaTrade Agentic Redesign — Final Architecture & Consistency Review

**Review target:** PR #64 exact commit
`8511ea15dbd6f036a873a049b1adce84a89104cb`

**Reference review:** PR #65 exact commit
`3a1a80ff7c980b3fcfbb3d239e3bcdc11f161403`,
`docs/redesign/agentic_redesign_architecture_review.md`

**Review scope:** architecture and repository consistency only. No product code, migration,
deployment configuration, feature flag, external delivery, worker, watcher, Telegram, BloFin
demo execution or live-trading capability was changed or enabled.

## 1. Final verdict

**APPROVED WITH REQUIRED PRE-IMPLEMENTATION CORRECTIONS**

The revised architecture resolves the substance of all 7 CRITICAL findings, all 20 HIGH
findings and all 18 mandatory corrections from PR #65. This conclusion is based on the revised
contracts and flows, not the resolution matrices in either Phase 0 document.

The architecture is coherent in its main safety boundaries:

- read-only requests have no path to mutation and the policy is rechecked at service and
  persistence boundaries;
- approval and execution are separate;
- `ExecutionService` is the sole execution authority;
- objective setup truth is separate from account action eligibility;
- strategy, pattern and compiled setup ownership form one identity chain;
- models cannot control Tier C decisions;
- the canonical journal migrates before automatic lifecycle projection;
- source contracts precede CVD, fusion and watcher automation;
- all automation and live-trading capabilities remain disabled.

Two HIGH architecture-flow corrections are still required before Phase 1 implementation:

1. route `APPROVE`, `REJECT` and `SKIP` to distinct effects instead of sending the entire
   `APPROVAL` class to `ApprovalAuthorization` creation; and
2. show the `PLAN_TRADE` branch creating the immutable `TradePlanRevision` that approval and
   execution consume, rather than ending at model synthesis.

Four MEDIUM corrections remove ambiguity in journal ownership, frontend composition, Telegram
ordering and the first-slice acceptance trace. These corrections are documentation/contract
work; they do not justify product implementation before the architecture is made internally
consistent.

### Finding count

| Severity | Count |
|---|---:|
| BLOCKER | 0 |
| HIGH | 2 |
| MEDIUM | 4 |
| LOW | 0 |

## 2. Review method and evidence boundary

The review compared:

- PR #65 findings at lines 79–545 and mandatory corrections at lines 1037–1068;
- the revised target architecture at the pinned PR #64 commit;
- the revised Phase 0 current-state audit at the pinned PR #64 commit;
- graph edges, sequence diagrams, typed contracts, ownership tables and migration order;
- exact-head CI reported by GitHub for the pinned commit.

“Resolved” below means the architecture now defines the required target contract. It does not
mean that the current product code already implements that contract. Most original findings
describe current behavior that remains intentionally scheduled for later implementation.

## 3. PR #65 CRITICAL finding closure

| ID | Independent verdict | Revised architecture evidence | Reason |
|---|---|---|---|
| CRITICAL-01 — analysis can persist proposal/approval | RESOLVED | Target lines 204–234, 239–257, 272–318; Phase 1 lines 1221–1237 | `MARKET_ANALYSIS`, `SETUP_ANALYSIS` and `EXPLAIN` are `READ_ONLY`; that graph branch has no mutation edge, and service/persistence boundaries recheck the authoritative intent/class pair. |
| CRITICAL-02 — placeholder executable plan | RESOLVED | Target lines 241–244, 399–402, 700–769 | An executable `TradePlanRevision` requires complete fresh, non-fallback, sequence-complete, market-correct provenance. Missing or degraded input returns the exact analysis-only result and creates no executable-shaped resource. |
| CRITICAL-03 — approval/execution contradiction | RESOLVED IN SUBSTANCE; see FINAL-01 and FINAL-02 | Target lines 168–179, 244–250, 770–841, 991–999 | `APPROVE` creates a one-time exact-revision authorization and stops. A separate `EXECUTE_PAPER_PLAN` reaches `ExecutionService`; authorization is consumed only after final deterministic `ALLOW`. The remaining findings concern graph completeness, not a return to approval-triggered execution. |
| CRITICAL-04 — successful no-op execution tool | RESOLVED | Target lines 110–119, 252–258, 840–842; Phase 1 line 1234 | Stubs must fail closed. Agent, API and Telegram facades must use the same command, and only `ExecutionService` may consume authorization, submit or create an execution receipt. |
| CRITICAL-05 — tenant-unsafe idempotency | RESOLVED | Target lines 800–839; Phase 1 lines 1225–1229 | The canonical command hash includes identity and payload, and replay is validated by organization, principal/account and exact payload before any tenant-scoped receipt/order lookup. |
| CRITICAL-06 — no perpetual CVD source contract | RESOLVED ARCHITECTURALLY | Target lines 405–468, 1257–1267, 1380–1427 | Typed perpetual trade, cursor and CVD contracts precede implementation; gaps, unknown aggressor semantics, stale/fallback data and wrong market fail closed. Phase 5 must contract-test a reachable source first. |
| CRITICAL-07 — watcher accepts fallback/forming evidence | RESOLVED ARCHITECTURALLY | Target lines 397–402, 873–902, 1324–1337 | The watcher must reject non-live, fallback, stale, forming/unknown-finality, wrong-market, incomplete and gapped evidence before confirmation, candidate creation or alerting. |

**CRITICAL closure verdict: 7/7 resolved architecturally.**

The qualification on CRITICAL-03 is explicit because the core approval-versus-execution
contract is resolved, while the consolidated graph still needs the routing corrections in
FINAL-01 and FINAL-02.

## 4. PR #65 HIGH finding closure

| ID | Independent verdict | Revised architecture evidence | Reason |
|---|---|---|---|
| HIGH-01 — watchlist capability overstated | RESOLVED | Target lines 111–114, 846–872; Phase 0 lines 400–405 | `WatchlistItem` remains symbol/exchange/timeframe/strategy curation; only minimal immutable policy association/versioning is added. |
| HIGH-02 — Pattern Card ignores `SetupDefinition` | RESOLVED | Target lines 114–116, 560–599 | `UserStrategy` → immutable `UserStrategyVersion` → one compiled `SetupDefinition` is explicit; Pattern Card is a representation, not another identity. |
| HIGH-03 — mutable strategy versions | RESOLVED ARCHITECTURALLY | Target lines 600–618, 1132–1151, 1245–1249 | Every semantic change creates a new immutable draft version; accepted lessons cannot patch active logic. |
| HIGH-04 — tenant-coupled generic evidence | RESOLVED | Target lines 350–402, 477–514 | Global typed public observations are separated from tenant assessments and tenant/account eligibility. Payloads are discriminated and provenance is explicit. |
| HIGH-05 — setup truth mixed with risk | RESOLVED | Target lines 477–514, 517–557, 1407–1413 | `SetupAssessment` answers market-pattern truth; `ActionEligibility` answers whether an account may act. Risk cannot rewrite setup truth. |
| HIGH-06 — third orchestration lifecycle | RESOLVED | Target lines 114–118, 510–514, 894–902 | Existing paper orchestration, watcher, TradingView and validation records are compatibility adapters into one assessment/candidate lineage. |
| HIGH-07 — candidate uniqueness undefined | RESOLVED | Target lines 490–514, 1489–1497 | A source-agnostic evidence-window key is database-enforced; transactional upsert, optimistic transitions and separate delivery dedupe are required. |
| HIGH-08 — worker/manual watcher divergence | RESOLVED ARCHITECTURALLY | Target lines 873–902, 1269–1274 | Worker and manual dry runs use one tenant-aware evaluation pipeline; scan attempts and honest attempted/succeeded/failed health are recorded. |
| HIGH-09 — non-local lock fails open | RESOLVED ARCHITECTURALLY | Target lines 873–878, 1271–1274 | Non-local distributed locking, renewable leases and fencing are mandatory; loss blocks the cycle and marks health unhealthy. |
| HIGH-10 — insecure Telegram enrollment | RESOLVED ARCHITECTURALLY | Target lines 925–955 | Enrollment binds organization, AlphaTrade user, Telegram user/private chat and bot through an expiring web-originated challenge; groups are rejected by default. |
| HIGH-11 — exactly-once external claim | RESOLVED | Target lines 195–199, 931–955 | The design promises at-least-once delivery with durable claims and idempotent internal effects, not exactly-once external delivery. |
| HIGH-12 — ambiguous BloFin submit recovery | RESOLVED ARCHITECTURALLY | Target lines 1021–1028 | Mutation POSTs receive no blind retry; uncertain submission enters reconciliation and is queried by exactly one venue or deterministic client order ID. |
| HIGH-13 — exchange/fill uniqueness | RESOLVED ARCHITECTURALLY | Target lines 1021–1030, 1496–1499 | Client/order IDs are scoped by account/venue, fill IDs are unique per exchange order, and transitions are append-only and optimistic. |
| HIGH-14 — cancel/partial-fill lifecycle gap | RESOLVED ARCHITECTURALLY | Target lines 999–1011, 1030–1034 | Cancel routes through `ExecutionService`, enters `CANCEL_PENDING`, ingests late fills and resolves reconciled state. |
| HIGH-15 — reduce-only versus hedge mode | RESOLVED | Target lines 1037–1041 | The first slice is NET MODE ONLY; hedge or unknown mode is rejected before approval/execution. |
| HIGH-16 — insufficient PnL reconciliation | RESOLVED ARCHITECTURALLY | Target lines 1034–1058 | Order detail, fills, positions, bills/funding, fees and realized PnL are reconciled with versioned sign/currency/contract semantics; unresolved totals remain explicit. |
| HIGH-17 — question-shaped mutations | RESOLVED IN SUBSTANCE; see FINAL-01 | Target lines 293–299, 318–335; Phase 1 lines 1228–1234 | Ambiguity defaults to read-only, every sub-intent declares a class, and graph plus domain boundary enforce intent/class pairs. The consolidated graph still needs distinct non-read operation routes. |
| HIGH-18 — tenant-unbound BloFin permissions | RESOLVED ARCHITECTURALLY | Target lines 1015–1023 | Credentials and all exchange records bind non-null account/organization/principal; stale, unknown or failed permission attestation fails closed. |
| HIGH-19 — no exact predicate system | RESOLVED ARCHITECTURALLY | Target lines 572–613, 1245–1249 | The allowlisted typed predicate/sequence AST rejects unknown, ambiguous, approximate or unsupported constructs. |
| HIGH-20 — lossy journal backfill | RESOLVED ARCHITECTURALLY | Target lines 1098–1112, 1251–1255 | The dry-run-first typed migration preserves structured behavior, attachments, links, comparison behavior and RAG lineage with parity fixtures. |

**HIGH closure verdict: 20/20 resolved architecturally.**

FINAL-01 is a new cross-document routing defect exposed by combining the revised intent table
with the revised graph. It does not reinstate the current product's question-shaped mutation
behavior, but it must be corrected before that graph is implemented.

## 5. Mandatory correction closure

| # | Independent verdict | Evidence |
|---:|---|---|
| 1 | RESOLVED | Phase 0 lines 400–405 and 620–625 accurately preserve watchlist fields and identify only the worker `CORS_ORIGINS` gap. |
| 2 | RESOLVED | Target lines 800–839 bind idempotency to tenant, principal/account, revision and canonical payload. |
| 3 | RESOLVED IN SUBSTANCE | Target lines 168–179 and 770–841 separate approval from execution and define one-time authorization; FINAL-01/02 must complete the graph. |
| 4 | RESOLVED | Target lines 204–257 and 320–335 prohibit read-only/question paths to all listed mutations and workloads. |
| 5 | RESOLVED | Target lines 700–769 prohibit executable placeholders and require immutable fresh provenance. |
| 6 | RESOLVED | Target lines 252–258 and 840–842 make no-op mutation/execution tools fail closed. |
| 7 | RESOLVED | Target lines 477–557 separate setup truth from account action eligibility. |
| 8 | RESOLVED | Target lines 350–402 and 477–514 separate global typed market observations from tenant assessments. |
| 9 | RESOLVED | Target lines 560–618 define one strategy/version/setup chain and an exact compiler. |
| 10 | RESOLVED | Target lines 638–697 and 1239–1244 place model routing before consumers and remove metering-only calls conceptually. |
| 11 | RESOLVED | Target lines 510–514 and 894–902 adapt existing orchestration into one lineage. |
| 12 | RESOLVED | Target lines 846–902 define minimal watcher policy, shared scans, evidence rejection, lineage, health, locking and uniqueness. |
| 13 | RESOLVED | Target lines 925–955 define verified Telegram enrollment, nonce/receipt state and at-least-once/idempotent semantics. |
| 14 | RESOLVED | Target lines 980–1058 define tenant-bound BloFin demo permission, submit, lookup, fill, cancel, uniqueness and reconciliation contracts. |
| 15 | RESOLVED | Target lines 1037–1041 select NET MODE ONLY. |
| 16 | RESOLVED | Target lines 1067–1112 and 1251–1255 move canonical journal adapters early, preserve behavior and forbid self-modification. |
| 17 | RESOLVED | Target lines 1257–1267 and 1380–1427 require source contracts before CVD/fusion implementation. |
| 18 | RESOLVED | Target lines 1215–1223, 1470–1475 and 1510–1533 keep all automation off until separate review. |

**Mandatory correction verdict: 18/18 resolved architecturally, subject to the two graph
consistency corrections required before implementation.**

## 6. Required pre-implementation findings

### FINAL-01 — Approval-class routing contradicts `REJECT` and `SKIP`

- **Severity:** HIGH
- **Exact affected contract:** `IntentDecision` operation-class routing for `APPROVE`, `REJECT`,
  `SKIP`, `CONFIGURE` and confirmed journal writes.
- **Repository/document evidence:**
  - target lines 212–219 route the entire `APPROVAL` class through one node and then
    unconditionally persist an `ApprovalAuthorization`;
  - target lines 313–316 specify different effects: `APPROVE` creates authorization,
    `REJECT` rejects an exact object and `SKIP` records dismissal;
  - target lines 214–215 label configuration/journal branches as “read or confirmed update,”
    but lines 229–230 route both only to synthesis.
- **Reason:** operation classes are not sufficient to choose a domain command. As drawn, a
  `REJECT` or `SKIP` reaches authorization creation, while confirmed configuration and journal
  writes have no persistence route. This contradicts the intent table and makes the graph
  unsafe to implement literally even though the `READ_ONLY` branch itself remains
  non-mutating.
- **Required correction:** add an intent/requested-action dispatch inside each non-read class.
  `APPROVE` alone may create `ApprovalAuthorization`; `REJECT` and `SKIP` must call their exact
  idempotent decision commands and cannot mint authorization. Configuration and journal
  branches must distinguish read from confirmed writes and route only confirmed writes through
  the same preview/command/service-boundary policy. Add graph and persistence tests for every
  intent/effect pair.

### FINAL-02 — The plan graph does not create the revision approval requires

- **Severity:** HIGH
- **Exact affected contract:** explicit `PLAN_TRADE` → immutable `TradePlanRevision` →
  exact-revision approval.
- **Repository/document evidence:**
  - target lines 168–172 require an explicit plan request, exact immutable revision and later
    approval;
  - target lines 210 and 228 route `PLAN` to “Build inspectable plan draft” and then directly to
    optional model synthesis;
  - target lines 242–244 say only in prose that `PLAN_TRADE` “may create” a
    `TradePlanRevision`;
  - target lines 730–769 define the immutable revision required by approval.
- **Reason:** the primary agent graph contains no deterministic plan-builder/service node, no
  revision persistence edge and no analysis-only terminal branch. The exact resource required
  by `APPROVE` therefore exists in the schema and prose but not in the architecture flow. This
  is the kind of prose-only resolution the final review was required to detect.
- **Required correction:** show `PLAN_TRADE` invoking the existing planning stack through one
  authoritative service. Complete eligible input must atomically persist and return one
  immutable `TradePlanRevision`; incomplete/degraded input must return the distinct
  non-executable analysis-only result and persist no executable resource. Route later approval
  by exact revision ID and content hash.

### FINAL-03 — Optional candidate-stage `JournalTrade` overlaps candidate ownership

- **Severity:** MEDIUM
- **Exact affected contract:** boundary between `Candidate` lifecycle events and canonical
  `JournalTrade` creation.
- **Repository/document evidence:**
  - target lines 1080–1081 allow a confirmed candidate to create an “optional planned draft,”
    while skipped/rejected decisions remain lifecycle events;
  - PR #65 lines 855–858 require candidate/reject/skip history to remain lifecycle events and
    place canonical planned-trade creation at approved-plan or first-fill boundary;
  - target lines 1493–1500 already define separate candidate and journal projection identities.
- **Reason:** an optional candidate-stage journal row can duplicate the candidate aggregate,
  create journal records for trades that were never planned and make statistics depend on an
  unspecified optional projection policy. It weakens the otherwise clear “one execution
  lifecycle → one canonical trade” rule.
- **Required correction:** keep pre-plan candidate/reject/skip facts in candidate/decision
  events. Create the canonical `JournalTrade` at exact plan approval or first fill. If a
  pre-plan notebook artifact is required, define it as a distinct non-trade record excluded
  from trade statistics and specify its one-way promotion/linkage semantics.

### FINAL-04 — Four surfaces are named, but page-composition boundaries remain incomplete

- **Severity:** MEDIUM
- **Exact affected contract:** frontend information architecture for Agent and Safety &
  Settings.
- **Repository/document evidence:**
  - target lines 1165–1169 still merge dashboard, proposals, approvals, pre-trade, manual
    levels, coaching and strategy create/edit into Agent;
  - target lines 1204–1205 place risk, notifications, exchange diagnostics, audit, usage,
    billing and team components under Safety & Settings;
  - target lines 1301–1302 call the surfaces “focused” but define no tab/subroute/loading or
    ownership boundaries;
  - PR #65 MEDIUM-05 at lines 599–614 warned that this produces oversized screens.
- **Reason:** preserving deep links prevents route loss, but it does not itself prevent two
  mega-pages. Strategy authoring and account/team/billing are distinct mental models from the
  immediate trading conversation and safety control plane.
- **Required correction:** specify each primary surface as a shell over focused modules/tabs and
  deep links. Keep strategy authoring/validation in secondary Strategy Lab workflows; keep
  account/team/billing/usage in distinct secondary settings sections. Phase 1 must delete no
  route, and Phase 12 may hide primary navigation only after compatibility tests.

### FINAL-05 — Telegram `CLOSE` is ordered before its reconciliation dependency

- **Severity:** MEDIUM
- **Exact affected contract:** migration dependency order for remote close.
- **Repository/document evidence:**
  - target lines 971–975 require `CLOSE` to bind and freshly reconcile the exact position before
    delegating to `ExecutionService`;
  - Phase 8 at lines 1276–1280 includes `CLOSE`;
  - Phase 9 at lines 1282–1287 adds the NET-mode reduce-only close and position/order/PnL
    reconciliation on which that action depends;
  - the explicit sequence repeats Phase 8 before Phase 9 at lines 1522–1525.
- **Reason:** implementing the remote close action before authoritative demo position and close
  semantics either creates an unusable adapter or couples Telegram to temporary execution
  behavior that Phase 9 must replace.
- **Required correction:** keep Phase 8 to outbox/enrollment/read-only actions, `REJECT`,
  `SKIP`, exact-plan `APPROVE` and other actions whose domain commands already exist.
  Implement/enable Telegram `CLOSE` only after Phase 9 reconciliation and reduce-only close
  contracts pass. Flags remain off throughout.

### FINAL-06 — The first-slice trace omits the explicit planning action

- **Severity:** MEDIUM
- **Exact affected contract:** first vertical-slice acceptance lineage.
- **Repository/document evidence:**
  - target lines 168–172 explicitly require a new `PLAN_TRADE` request after a candidate action;
  - target lines 1455–1459 jump from an authenticated Telegram callback receipt directly to an
    immutable plan revision;
  - the Telegram rollout at lines 960–978 has no `PLAN_TRADE` callback action.
- **Reason:** the acceptance trace can be read as if an unspecified Telegram callback creates a
  plan, contradicting the explicit-intent invariant and leaving the callback action and channel
  transition untestable.
- **Required correction:** name the callback action, then insert an explicit authenticated
  `PLAN_TRADE` request and resulting immutable revision before `APPROVE`. If planning moves from
  Telegram to Agent/web, preserve the same principal, candidate ID and correlation ID in the
  trace.

## 7. Intent and operation contract verdict

**Verdict: READ_ONLY invariant approved; non-read graph requires FINAL-01 and FINAL-02.**

The final intent table covers all required intents:

| Intent | Contract verdict |
|---|---|
| `MARKET_ANALYSIS` | `READ_ONLY`; facts/evidence summary only |
| `SETUP_ANALYSIS` | `READ_ONLY`; pattern progress/invalidation only |
| `PLAN_TRADE` | `PLAN`; immutable revision only, never approval/execution |
| `REVIEW_TRADE` | read by default; confirmed reflective journal write only |
| `MANAGE_POSITION` | preview then exact confirmed idempotent mutation |
| `JOURNAL` | read by default; explicit confirmed write |
| `EXPLAIN` | `READ_ONLY`; explanation over existing/frozen facts |
| `CONFIGURE` | current-config read or previewed confirmed update |
| `APPROVE` | exact revision/hash authorization only |
| `REJECT` | exact object rejection; never execution |
| `SKIP` | exact evidence/object dismissal; never execution |
| `EXECUTE_PAPER_PLAN` | sole execution intent |

The required read-only invariant is explicit at target lines 239–257 and is also enforced at
each service/persistence mutation boundary. There is no read-only edge to proposal, approval,
execution, strategy, backtest, validation, watcher, configuration, journal or other
persistence mutation. Ambiguity takes the most restrictive result and defaults to read-only.

## 8. Plan, approval and execution contract verdict

**Verdict: lifecycle semantics approved; plan graph correction required.**

The coherent target lifecycle is:

`explicit PLAN_TRADE`
→ immutable `TradePlanRevision`
→ `APPROVE` exact revision/hash
→ available `ApprovalAuthorization`
→ separate `EXECUTE_PAPER_PLAN`
→ `ExecutionService`
→ fresh deterministic authorization/eligibility/risk/freshness/kill-switch gates
→ `BLOCK` with no submit, or `ALLOW`
→ atomic one-time authorization consumption
→ demo/internal-paper submission
→ authoritative `ExecutionReceipt`
→ reconciliation.

Approval alone stops before execution. Replay, wrong tenant/principal/account, wrong revision,
wrong hash, expiry and revocation fail closed. Agent, API and Telegram are facades; only
`ExecutionService` may consume authorization, submit, cancel/close or create the authoritative
receipt. `BloFinSyncService` is a reconciliation input, and `AUTO_PAPER` remains a separate
validation simulator with no path to BloFin or remote approval.

## 9. Domain ownership and duplication verdict

**Verdict: approved with the journal boundary correction in FINAL-03.**

- Strategy/pattern ownership is singular:
  `UserStrategy` → immutable `UserStrategyVersion` → one compiled `SetupDefinition`.
  `StructuredRules` are authored input and Pattern Card is a representation.
- Surveillance ownership is singular:
  immutable global `MarketObservation` → tenant `SetupAssessment` → tenant/account
  `ActionEligibility` plus one canonical `Candidate`.
- Existing `PaperSignalOrchestrationDecision`, watcher, TradingView and
  `PaperValidationCandidate` records are migration adapters, not independent authorities.
- `JournalTrade` is the target canonical intelligence record; legacy `TradeJournal` remains
  only behind compatibility reads/backfill until behavior parity.
- `ExecutionService` owns execution; the BloFin coordinator and sync/reconciliation components
  are internal collaborators, not public execution authorities.

No unnecessary microservice or parallel strategy, candidate, execution or journal system is
required by the target design.

## 10. Evidence and fusion contract verdict

**Verdict: approved.**

The architecture correctly separates:

1. global public market observations with no tenant owner;
2. tenant-scoped setup assessments using exact strategy/setup policy; and
3. tenant/user/account action eligibility using private risk and venue state.

`MarketObservation` carries venue, market type, canonical instrument, provider symbol, event
time, receive time, source clock, interval bounds, source/provider, source event identity,
sequence/cursor, freshness, finality and finality policy, fallback/live state, supersession,
adapter version, content hash and recorded time. Perpetual trade/CVD contracts add aggressor
semantics, reconnect/gap/warm-up state and cursor lineage.

The same market evidence and policy reproduce the same setup state across accounts. Kill
switch, daily loss, cooldown, exposure, portfolio conflict and cross-venue basis affect
`ActionEligibility` only. Candidate identity uses organization, strategy version, instrument,
timeframe and canonical evidence-window hash, allowing watcher, TradingView and detector
evidence for the same semantic window to converge while retaining source and venue lineage.

## 11. Pattern system verdict

**Verdict: approved.**

The identity chain is coherent and has one owner. The allowlisted deterministic AST supports
typed operands/units, bounded windows, boolean composition, cross-series alignment and ordered
sequence steps. Unknown fields, ambiguous units, unsupported constructs and approximate
mappings are rejected.

Screenshots, RAG, lessons and model output can supply evidence or a draft only. Executable
rules require schema validation, exact AST compilation, user review, linked historical/paper
evidence and explicit promotion of a new immutable strategy version. Existing versions are
never patched.

## 12. Model-routing verdict

**Verdict: approved.**

Tier A is limited to explanation of frozen conflicts, strategy drafting and post-trade review;
Tier B handles bounded classification, extraction and summaries; Tier C owns all deterministic
calculations, freshness, fusion transitions, pattern math, risk, permissions, idempotency,
sizing and execution authority.

Phase 2 introduces the router before any new Tier A/B consumer. The request contract includes
data classification, tenant/user scope, prompt-policy version, provider/retention policy,
budgets, fallback and validation. `ModelCallAttempt` records actual provider calls, retries,
tokens, latency, validation and cost; no model call may be made solely for metering.

## 13. Journal and learning verdict

**Verdict: approved with FINAL-03.**

Phase 4 moves main journal reads, canonical detail/attachments, human-versus-system behavior,
behavioral tags/discipline and RAG to `JournalTrade` before market automation and automatic
projection. Legacy reads remain during typed, idempotent, dry-run-first backfill, with row,
link, attachment, behavior, coaching and RAG parity tests.

Reconciled fills, prices, fees, funding and PnL retain provenance and append-only correction
history. Learning produces pending lessons and may propose a new immutable draft strategy
version only. It cannot patch, activate or promote strategy logic automatically.

## 14. Frontend verdict

**Verdict: direction approved; FINAL-04 required before Phase 12 implementation.**

Agent, Live Watcher, Trades & Journal and Safety & Settings are valid primary navigation
surfaces if they are shells over focused workflows. Existing components and API clients are
reused. Strategy Lab, paper-validation, backtest, knowledge, import, audit, exchange,
billing/usage and other expert/compatibility routes remain reachable and deep-linkable.

No route deletion is required or authorized for Phase 1. Navigation hiding occurs only in
Phase 12 after compatibility tests; deletion requires a separate evidence-based task.

## 15. Migration-order verdict

**Verdict: safety-first order approved with FINAL-05.**

Phase 1 correctly freezes paper/live-host/risk invariants, repairs idempotency, introduces
operation policy at graph and persistence boundaries, removes read-to-mutation paths, fails
closed no-op tools and defines immutable plans plus consumable authorization.

Model routing, strategy immutability, canonical journal migration and perpetual source
contracts all precede new CVD/fusion/watcher automation. Telegram, BloFin demo reconciliation,
automatic journaling, analytics/learning and frontend consolidation remain later and disabled.
Only Telegram `CLOSE` is misplaced before its Phase 9 reconciliation dependency.

## 16. First vertical-slice verdict

**Verdict: approved as an architecture/evaluation pattern with FINAL-06.**

The fixed slice is correctly labelled an architectural proof, not a profitability claim.
Thresholds are deterministic fixture hypotheses and must not be presented as validated edge or
optimized during implementation.

The contracts are sufficient to prove:

- immutable perpetual 15m/4h market observations;
- versioned pattern evaluation and transition reasons;
- signed-trade CVD with continuity/gap semantics;
- source-agnostic candidate identity;
- durable Telegram delivery and authenticated action receipt;
- immutable planning, exact approval and separate explicit execution;
- final deterministic action eligibility/risk;
- BloFin demo submission, partial fill/cancel/close and reconciliation;
- exactly one canonical `JournalTrade`;
- analytics and review-only pending learning.

The intended runtime region must pass the Phase 5 perpetual source contract before CVD,
pattern/fusion or watcher implementation. Spot or fallback data cannot substitute for
perpetual evidence. Cross-venue basis can block action only and cannot rewrite setup truth.

## 17. Reuse verdict

**Verdict: approved.**

The target consistently prefers reuse, wrapping, extension, adaptation, merging and later
navigation hiding:

- existing FastAPI modular monolith and worker;
- provider factory/registry and deterministic analysis;
- watchlist, watcher, orchestration and validation records through adapters;
- strategy cards, versions, structured rules, setup definitions and manual levels;
- planning, proposal, approval, risk, kill switch and `ExecutionService`;
- alerts, notification routing and Telegram provider;
- exchange adapters, order/fill persistence and BloFin snapshots;
- canonical journal, analytics, lessons, RAG and frontend components.

New modules—operation policy, typed evidence/fusion, model router, outbox/action receipts and
demo reconciliation coordinator—fill verified ownership gaps inside the modular monolith.
They do not justify a rewrite or new independently deployed service.

## 18. CI and safety verdict

At the end of this review, GitHub reports all checks for exact commit
`8511ea15dbd6f036a873a049b1adce84a89104cb` completed successfully:

- backend;
- deployment-safety;
- docker-build;
- frontend;
- evaluation;
- e2e-smoke;
- Vercel;
- Vercel Preview Comments.

Exact-head CI is therefore not an outstanding gate for this architecture revision. Passing
documentation-branch CI does not prove that target contracts are implemented.

Safety posture is unchanged. No product code, migration, deployment configuration or feature
flag was modified. Worker, watcher, TradingView, paper-signal orchestration, Telegram delivery
or inbound actions, BloFin demo execution and live trading remain disabled. The permanent
paper-only, production-host denial and `ENABLE_REAL_TRADING=false` boundaries are preserved.

## 19. Required next step

Correct FINAL-01 through FINAL-06 in the canonical target architecture without implementing
product code. Re-run a narrow consistency review of those corrections. Phase 1 implementation
may begin only after the two HIGH graph defects are corrected and the resulting exact-head CI
is successful. Runtime features and deployment flags remain outside that authorization.
