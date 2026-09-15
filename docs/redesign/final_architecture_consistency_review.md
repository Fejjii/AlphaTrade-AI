# AlphaTrade Agentic Redesign — Final Architecture & Consistency Review

**Review target:** PR #64 exact commit
`8511ea15dbd6f036a873a049b1adce84a89104cb`

**Reference review:** PR #65 exact commit
`3a1a80ff7c980b3fcfbb3d239e3bcdc11f161403`,
`docs/redesign/agentic_redesign_architecture_review.md`

**Scope:** architecture/repository review only. No product code, migration, deployment
configuration, feature flag, worker, watcher, Telegram, BloFin demo or live-trading capability
was changed or enabled.

## 1. Final verdict

**NOT APPROVED**

The redesign has the right overall direction, but it is not coherent enough to authorize Phase
1. The decisive blocker is approval integrity: the immutable plan and authorization do not
bind the complete executable order, while `ExecutionCommand` independently supplies material
fields. An explicitly approved revision can therefore accompany a first-time command whose
account, order type, price behavior or execution instrument was not approved.

Independent comparison with PR #65 finds:

- CRITICAL: 5/7 fully resolved; CRITICAL-03 and CRITICAL-05 partially resolved;
- HIGH: 11/20 fully resolved; 9 partially resolved;
- mandatory corrections: 11/18 fully resolved; 7 partially resolved.

The report records 1 BLOCKER, 12 HIGH, 9 MEDIUM and 1 LOW finding. Several are omissions in the
revised architecture rather than failures of its broad safety direction. They nevertheless
must be corrected in the canonical architecture before implementation begins.

## 2. Review method

The review was pinned to the exact commits above. It compared PR #65 findings and corrections
to the revised contracts, diagrams, migration order, current repository models and first-slice
acceptance trace. The Phase 0 resolution matrices were treated as claims, not evidence.

“Resolved” means the normative architecture fully defines the correction. It does not mean the
current product implements it. “Partial” means the correction is stated but contradicted,
under-specified or absent from the architecture flow.

## 3. PR #65 CRITICAL closure

| Finding | Verdict | Independent evidence |
|---|---|---|
| CRITICAL-01 — analytical wording can persist proposal/approval | RESOLVED | Target lines 201–258 and 294–318 separate read-only intent and repeat enforcement at service/persistence boundaries. FINAL-HIGH-03 addresses observability writes, not proposal/approval creation. |
| CRITICAL-02 — executable placeholder plans | RESOLVED | Target lines 242–244 and 729–770 require complete fresh evidence and prohibit executable-shaped output on missing/degraded input. |
| CRITICAL-03 — approval/execution contradiction | PARTIAL | Approval and execution are separate at lines 168–177 and 772–798, but the plan/authorization do not bind the complete order supplied at lines 803–823; see FINAL-BLOCKER-01. |
| CRITICAL-04 — successful no-op execution tool | RESOLVED | Target lines 252–258 and Phase 1 lines 1220–1237 require fail-closed stubs and sole `ExecutionService` authority. |
| CRITICAL-05 — tenant-unsafe idempotency | PARTIAL | Tenant/principal/account lookup is corrected, but lines 803–826 hash volatile command ID/correlation/time fields, contradicting semantic replay at lines 832–838; see FINAL-HIGH-02. |
| CRITICAL-06 — missing perpetual CVD provider contract | RESOLVED | Target lines 404–474 define trade/cursor/CVD contracts; Phase 5 precedes CVD/fusion and requires regional contract testing. |
| CRITICAL-07 — fallback/forming watcher evidence | RESOLVED | Target lines 399–402, 529–548 and 879–884 reject fallback, non-live, forming, stale, gapped and wrong-market evidence. |

**CRITICAL resolution verdict: 5 fully resolved, 2 partially resolved.**

## 4. PR #65 HIGH closure

| Finding | Verdict | Independent evidence |
|---|---|---|
| HIGH-01 — watchlist capability overstated | RESOLVED | Phase 0 lines 402–405 and target lines 848–870 preserve existing curation and add only versioned watcher policy. |
| HIGH-02 — Pattern Card ignores `SetupDefinition` | PARTIAL | The target selects one identity chain, but does not migrate global legacy `SetupDefinition` rows into tenant-owned compiled artifacts; see FINAL-HIGH-05. |
| HIGH-03 — mutable strategy versions | PARTIAL | Semantic edits create new versions, but `promotion_state` is embedded in the supposedly immutable Pattern spec while later lifecycle transitions change it; see FINAL-HIGH-06. |
| HIGH-04 — generic tenant-bound evidence | PARTIAL | The global envelope is strong, but includes tenant-private TradingView payloads and leaves most payload schemas undefined; see FINAL-HIGH-04. |
| HIGH-05 — setup truth mixed with action eligibility | RESOLVED | Target lines 476–557 separate objective assessment from tenant/account risk and prohibit account state from rewriting setup truth. |
| HIGH-06 — third candidate state machine | PARTIAL | Compatibility adapters are declared, but actionable candidate versus downstream validation queue mappings remain unspecified; see FINAL-HIGH-07. |
| HIGH-07 — candidate uniqueness undefined | PARTIAL | A database key exists, but omits direction/fusion-policy identity and does not define the evidence-window hash algorithm; see FINAL-HIGH-07. |
| HIGH-08 — worker/manual watcher divergence | RESOLVED | Target lines 874–900 require one tenant-aware evaluation pipeline and honest scan lineage/outcomes. |
| HIGH-09 — non-local lock fails open | RESOLVED | Target lines 874–876 require renewable distributed lease/fencing and fail-closed unhealthy state. |
| HIGH-10 — Telegram enrollment absent | RESOLVED | Target lines 927–952 define private-chat challenge, tenant/user/bot binding, ownership and replay checks. |
| HIGH-11 — exactly-once external claim | RESOLVED | Target lines 196–199 and 954–956 use at-least-once delivery with idempotent internal effects. |
| HIGH-12 — ambiguous BloFin submit recovery | PARTIAL | Lookup/proof-of-absence prose exists, but the state diagram has no proven-absent resubmit transition; see FINAL-HIGH-08. |
| HIGH-13 — venue order/fill uniqueness | RESOLVED | Target lines 1022–1029 require account/venue-scoped client/order IDs, fill uniqueness and optimistic transitions. |
| HIGH-14 — cancel/partial-fill lifecycle gap | PARTIAL | Prose mentions partial cancellation, but the state flow has only `CANCEL_PENDING → CANCELLED` and no ambiguous-cancel reconciliation edge; see FINAL-HIGH-08. |
| HIGH-15 — reduce-only versus hedge mode | RESOLVED | Target lines 1038–1041 select NET MODE ONLY and reject hedge/unknown mode. |
| HIGH-16 — authoritative PnL reconciliation | PARTIAL | Sources are listed, but actual sign, settlement-currency, contract-size and precedence rules are only asserted to be versioned; see FINAL-HIGH-08. |
| HIGH-17 — question-shaped mutations | RESOLVED | Target lines 237–255 and 318–335 define restrictive classification and repeat policy at domain boundaries. |
| HIGH-18 — tenant-unbound BloFin permissions | RESOLVED | Target lines 1016–1023 bind credentials/records to tenant account/principal and fail closed on uncertain attestation. |
| HIGH-19 — no exact predicate system | PARTIAL | The allowlist is described, but no concrete versioned AST grammar or sequence evaluator semantics are defined; see FINAL-HIGH-06. |
| HIGH-20 — lossy behavioral backfill | RESOLVED | Target lines 1098–1112 require typed behavior mapping and row/link/discipline/coaching/RAG parity. |

**HIGH resolution verdict: 11 fully resolved, 9 partially resolved.**

## 5. Mandatory correction closure

| # | Verdict | Evidence |
|---:|---|---|
| 1 | RESOLVED | Watchlist and worker environment facts are corrected in Phase 0 lines 402–405 and 620–625. |
| 2 | PARTIAL | Tenant/principal binding is fixed, but the canonical command fingerprint includes volatile envelope fields; FINAL-HIGH-02. |
| 3 | PARTIAL | Approval is separate and single-use, but it is not bound to the full executable order/account; FINAL-BLOCKER-01. |
| 4 | RESOLVED | Read-only/question paths cannot create the listed domain resources; observability-write ambiguity is separately tracked in FINAL-HIGH-03. |
| 5 | RESOLVED | Executable placeholders are prohibited. |
| 6 | RESOLVED | Successful no-op mutation/execution tools must fail closed. |
| 7 | RESOLVED | Setup assessment and action eligibility are separate. |
| 8 | PARTIAL | Global/tenant separation is stated but contradicted by global tenant-private TradingView payloads; FINAL-HIGH-04. |
| 9 | PARTIAL | One identity chain is selected, but legacy ownership, promotion immutability and exact AST semantics remain incomplete; FINAL-HIGH-05/06. |
| 10 | RESOLVED | Model routing is Phase 2, actual-call telemetry replaces metering-only completions and data classification is present. |
| 11 | PARTIAL | One canonical lineage is intended, but adapter/validation-queue ownership is not mapped; FINAL-HIGH-07. |
| 12 | PARTIAL | Watcher unification is strong, but candidate uniqueness is not complete; FINAL-HIGH-07. |
| 13 | RESOLVED | Telegram enrollment, nonce, receipt and at-least-once/idempotent semantics are described. |
| 14 | PARTIAL | BloFin lifecycle lacks complete ambiguous submit/cancel and reconciliation semantics; FINAL-HIGH-08. |
| 15 | RESOLVED | NET MODE ONLY is selected. |
| 16 | RESOLVED | Journal adapters move early, behavioral parity is typed and automatic strategy self-modification is prohibited. |
| 17 | RESOLVED | Perpetual source contract precedes CVD/fusion. |
| 18 | RESOLVED | All automation and live-trading enablement remain outside implementation authorization. |

**Mandatory correction verdict: 11 fully resolved, 7 partially resolved.**

## 6. PR #65 MEDIUM and LOW closure

| Finding | Verdict | Evidence |
|---|---|---|
| MEDIUM-01 — metering-only LLM call | RESOLVED | Target lines 680–691 prohibit completion calls made only for metering. |
| MEDIUM-02 — Tier A candidate authority | PARTIAL | Tier A is constrained, but the reuse map still calls for “candidate synthesis”; FINAL-MEDIUM-07. |
| MEDIUM-03 — journal canonicalization too late | RESOLVED | Canonical adapters move to Phase 4 before market automation/projection. |
| MEDIUM-04 — close hook is not a projector | PARTIAL | Outbox projection is introduced, but canonical trade uniqueness and retry states remain incomplete; FINAL-HIGH-12 and FINAL-MEDIUM-08. |
| MEDIUM-05 — four mega-pages | PARTIAL | Compatibility routes remain, but Agent and Safety & Settings still lack composition boundaries; FINAL-MEDIUM-05. |
| MEDIUM-06 — slice before source contract | RESOLVED | Phase 5 source contract precedes CVD/fusion. |
| MEDIUM-07 — stale Phase 0 facts | RESOLVED | Facts and inventory wording are corrected. |
| MEDIUM-08 — router absent from migration | RESOLVED | Router is Phase 2 with classification, policy and attempt/result telemetry. |
| LOW-01 — dead `MessageClass.COMMAND` | UNRESOLVED | The target neither removes nor defines the dead branch; FINAL-LOW-01. |
| LOW-02 — attempt/result telemetry | RESOLVED | `ModelCallAttempt` and `ModelTaskResult` are distinct. |
| LOW-03 — unsupported SOL priority | RESOLVED | BTC is selected for repository reuse and no unsupported product preference is claimed. |

## 7. Required findings

### FINAL-BLOCKER-01 — Approval does not bind the complete executable order

- **Severity:** BLOCKER
- **Exact affected contract:** `TradePlanRevision` → `ApprovalAuthorization` →
  `ExecutionCommand` approval integrity.
- **Repository/document evidence:** target lines 730–758 omit account ID, order type,
  time-in-force, exact limit/market behavior and distinct evidence/execution instrument
  identities; lines 775–798 authorize only revision/hash; lines 803–823 independently accept
  account, side, order type, quantity and price; lines 1465–1468 claim separate evidence and
  execution instruments despite the contracts carrying one `instrument_id`.
- **Reason:** idempotency protects retries, not first-command approval integrity. A command can
  pair an approved hash with execution fields the user did not approve. Final risk checks may
  block unsafe facts but cannot supply missing consent or exact resource binding.
- **Required correction:** make the executable revision account-specific and include side,
  quantity, order type, exact price/zone derivation, time-in-force, slippage policy, evidence
  instrument, execution instrument/mapping, contract multiplier, tick/lot rules and basis
  policy in its hash. `ExecutionService` must lock/load the revision and derive those fields or
  reject every mismatch before gates or authorization consumption. Add altered-field tests.

### FINAL-HIGH-01 — `REJECT` and `SKIP` route to authorization creation

- **Severity:** HIGH
- **Exact affected contract:** operation routing for `APPROVE`, `REJECT` and `SKIP`.
- **Repository/document evidence:** target lines 212–220 route all `APPROVAL` operations through
  unconditional `ApprovalAuthorization` persistence, contradicting lines 313–315 and 965–967.
- **Reason:** a reject/skip action can mint an execution authorization.
- **Required correction:** dispatch by exact intent/action. Only `APPROVE` may authorize;
  `REJECT`/`SKIP` must perform their exact idempotent transition and make authorization
  impossible.

### FINAL-HIGH-02 — The idempotency fingerprint includes volatile envelope fields

- **Severity:** HIGH
- **Exact affected contract:** canonical `ExecutionCommand` replay identity.
- **Repository/document evidence:** lines 803–823 include command ID, correlation ID and
  creation time; lines 825–826 hash every identity/payload field; lines 832–838 promise
  semantically identical replay.
- **Reason:** a retry with a new server-generated ID/time hashes differently and cannot
  converge as promised.
- **Required correction:** define a versioned executable-payload fingerprint that excludes
  volatile/server-generated envelope fields and explicitly lists all included fields.

### FINAL-HIGH-03 — Literal `READ_ONLY` non-persistence is not defined

- **Severity:** HIGH
- **Exact affected contract:** the required “no other persistent mutation” invariant.
- **Repository/document evidence:** lines 239–241 prohibit domain writes, but lines 262–265
  preserve memory/quota/usage nodes and lines 667–676 persist model-call attempts. Tests at
  lines 1308–1314 enumerate domain rows but not audit/usage/memory persistence.
- **Reason:** the architecture alternates between “no domain mutation” and literal no
  persistence. Implementations/tests cannot know whether audit, quota, usage, conversation
  memory and model telemetry are permitted for a read-only request.
- **Required correction:** choose one explicit contract. Prefer an exhaustive allowlist of
  non-domain operational records that cannot trigger workflow/domain state, with all other
  writes denied and tested at service/persistence boundaries.

### FINAL-HIGH-04 — The observation domain is not fully typed or ownership-safe

- **Severity:** HIGH
- **Exact affected contract:** global `MarketObservation` discriminated union.
- **Repository/document evidence:** lines 350–389 place `TradingViewPayload` in a global
  ownerless store, while current `TradingViewSignal` is organization-scoped and can carry
  private strategy/level/backtest/journal links. Only `TradeEvent` and `CvdWindow` payloads are
  concretely defined; OHLCV, order book, TradingView, structure and volume are names only.
- **Reason:** tenant-private evidence can leak/dedupe globally, and undefined payload units,
  correction/hash and sequence/finality semantics prevent deterministic replay.
- **Required correction:** split public market observations from tenant-owned external
  assertions; define each payload schema, units, ownership, canonical hash exclusions,
  correction behavior and applicable sequence/finality rules.

### FINAL-HIGH-05 — Legacy `SetupDefinition` ownership migration is unspecified

- **Severity:** HIGH
- **Exact affected contract:** `UserStrategy` → `UserStrategyVersion` → compiled
  `SetupDefinition` identity/reuse.
- **Repository/document evidence:** target lines 563–603 require a tenant-authored one-to-one
  artifact; current `SetupDefinition` at `backend/src/app/db/models.py:261–271` is a global
  name/version record keyed to built-in `StrategyId`; Phase 3 only says “map.”
- **Reason:** existing global rows cannot directly become tenant-owned compiled artifacts
  without breaking references or recreating parallel identity.
- **Required correction:** define global-template compatibility, tenant artifact creation,
  foreign-key/backfill/alias behavior, collision handling and retirement criteria.

### FINAL-HIGH-06 — Pattern immutability and AST semantics remain contradictory

- **Severity:** HIGH
- **Exact affected contract:** immutable `UserStrategyVersion` and deterministic
  predicate/sequence AST.
- **Repository/document evidence:** lines 589–617 embed mutable promotion lifecycle state in an
  immutable Pattern spec; lines 573–603 name `PredicateAst`/`PatternStep` but omit node grammar,
  missing-data behavior, window/alignment bounds, sequence reset/overlap and Decimal semantics.
- **Reason:** promotion can mutate supposedly immutable content, while independent evaluators
  cannot be proven equivalent from the current AST description.
- **Required correction:** put promotion/activation in append-only lifecycle records; publish a
  versioned AST grammar and evaluator contract covering operands, units, rounding, missing
  data, windows, alignment and ordered-sequence transitions.

### FINAL-HIGH-07 — Candidate identity and adapter ownership are incomplete

- **Severity:** HIGH
- **Exact affected contract:** source-agnostic candidate uniqueness and compatibility mapping.
- **Repository/document evidence:** lines 491–514 omit direction and fusion-policy/setup hash
  from the unique key and do not define canonical `evidence_window_hash` fields; they call
  `PaperValidationCandidate` both an adapter and part of the same lineage although it is a
  downstream validation queue.
- **Reason:** changed policy or opposite-direction setups can collide, while source adapters
  can duplicate or conflate actionable occurrences and validation work.
- **Required correction:** define a versioned setup-occurrence identity including exact
  strategy/setup/fusion policy, direction, instrument, timeframe and semantic bounds; keep
  source IDs outside the source-agnostic hash. Map each legacy source/queue role and transition
  explicitly.

### FINAL-HIGH-08 — Demo execution/reconciliation state semantics are incomplete

- **Severity:** HIGH
- **Exact affected contract:** ambiguous submit, partial cancel and authoritative PnL
  reconciliation.
- **Repository/document evidence:** lines 991–1012 lack a proven-absent resubmit edge;
  `CANCEL_PENDING` reaches only `CANCELLED`; lines 1033–1037 name an undefined
  partially-cancelled outcome; sign/currency/contract-size/precedence are only said to be
  versioned.
- **Reason:** unknown submit/cancel outcomes and partial fill plus cancelled remainder cannot
  follow a complete deterministic path, and two implementations can compute different
  authoritative PnL.
- **Required correction:** define absent/resubmit/reject/expiry/operator states, ambiguous
  cancel reconciliation, filled/remaining quantities and the terminal partial-cancel
  representation. Specify Decimal sign, settlement currency, contract multiplier, fee/funding
  precedence and source conflict rules.

### FINAL-HIGH-09 — First-slice resistance is not immutable evidence

- **Severity:** HIGH
- **Exact affected contract:** versioned active 4h resistance used by the slice.
- **Repository/document evidence:** lines 1369–1395 require versioned resistance, but
  `SetupAssessment` has no level revision/hash; current `ManualChartLevel` is mutable and
  records only current values/timestamps.
- **Reason:** later edits can change historical setup interpretation or introduce look-ahead
  bias.
- **Required correction:** define immutable `ManualLevelRevision` or embed the level in the
  exact strategy version. Persist identity/hash, author, effective time, evidence venue and
  require creation before the trigger cutoff.

### FINAL-HIGH-10 — Phase 1 plan persistence precedes identity dependencies

- **Severity:** HIGH
- **Exact affected contract:** migration ordering for executable `TradePlanRevision`.
- **Repository/document evidence:** Phase 1 lines 1220–1237 persists plans requiring candidate
  and evidence IDs, while canonical observations/candidates arrive in Phases 5–6 at lines
  1257–1268.
- **Reason:** implementation must either invent transitional optional provenance or rework the
  plan schema after evidence/candidate migration.
- **Required correction:** separate Phase 1 contract/fail-closed scaffolding from executable
  storage rollout, or move canonical identity prerequisites earlier. No executable revision may
  use optional/transitional provenance.

### FINAL-HIGH-11 — First-slice Telegram persistence contracts are missing and `CLOSE` is early

- **Severity:** HIGH
- **Exact affected contract:** enrollment, delivery, callback/action receipt and remote close.
- **Repository/document evidence:** lines 925–955 give strong prose, but the first-slice domain
  table at lines 1486–1501 omits typed Telegram entities despite the acceptance trace requiring
  their IDs. Phase 8 includes `CLOSE` before Phase 9 reconciliation, contrary to lines 971–975.
- **Reason:** persisted ownership, nonce/hash/expiry, claim lease and replay transitions are not
  implementable from the slice contract, and remote close depends on unavailable reconciled
  position truth.
- **Required correction:** add typed enrollment, outbox attempt, callback nonce and action
  receipt contracts with ownership/hash/expiry/claim/replay states. Defer `CLOSE` until Phase 9
  NET-mode reconciliation and partial-fill/cancel tests pass.

### FINAL-HIGH-12 — Canonical journal uniqueness is not enforced

- **Severity:** HIGH
- **Exact affected contract:** one execution lifecycle → one `JournalTrade`.
- **Repository/document evidence:** lines 1075–1091 allow optional candidate-stage creation;
  line 1500 makes projection events unique but not the canonical trade. Current
  `JournalTrade` uniqueness covers only non-null external references.
- **Reason:** concurrent plan/fill projection events can create duplicate journal rows, and
  candidate-stage rows can pollute trade statistics.
- **Required correction:** keep candidate/reject/skip in lifecycle events; create the trade at
  approved-plan or first-fill boundary and enforce database uniqueness on canonical
  execution/plan/position lifecycle identity.

### FINAL-MEDIUM-01 — Agent plan persistence remains implicit

- **Severity:** MEDIUM
- **Exact affected contract:** `PLAN_TRADE` graph result.
- **Repository/document evidence:** the component model has a builder, but lines 210 and 228
  route the agent plan node directly to synthesis without naming revision persistence or the
  analysis-only terminal result.
- **Reason:** optional narrative can be confused with authoritative plan creation.
- **Required correction:** show the deterministic plan-service result explicitly and allow
  synthesis only over that frozen result.

### FINAL-MEDIUM-02 — Configuration/journal confirmation and execution result enums conflict

- **Severity:** MEDIUM
- **Exact affected contract:** confirmed configuration/journal writes and final gate outcomes.
- **Repository/document evidence:** lines 211–230 give explicit confirmation only to generic
  mutation; configuration/journal nodes combine reads and updates. Lines 91–94 and 222–225 use
  `BLOCK|ALLOW`, while line 175 adds `WARN` as a stopping result.
- **Reason:** graph structure does not prove confirmation for these writes and gate consumers
  have inconsistent enums.
- **Required correction:** draw separate read/preview/confirm/write branches with service
  rechecks; normalize execution to `BLOCK|ALLOW` and deterministically map warnings.

### FINAL-MEDIUM-03 — Outbox scope contradicts journal projection

- **Severity:** MEDIUM
- **Exact affected contract:** transactional outbox ownership.
- **Repository/document evidence:** lines 196–199 say the outbox is needed only for Telegram
  and demo venue calls; lines 1090–1093 require it for critical journal projection.
- **Reason:** “only” creates contradictory transaction/failure-boundary guidance.
- **Required correction:** define the outbox by failure boundary and explicitly include
  asynchronous journal projection.

### FINAL-MEDIUM-04 — Model routing omits account/resource scope

- **Severity:** MEDIUM
- **Exact affected contract:** `ModelTaskRequest` private-data scope.
- **Repository/document evidence:** lines 659–676 include organization/user but no account or
  typed resource references.
- **Reason:** portfolio/journal tasks cannot express least-privilege account/resource context.
- **Required correction:** add optional account and typed resource IDs plus purpose/retention
  binding.

### FINAL-MEDIUM-05 — Four-surface composition still risks mega-pages

- **Severity:** MEDIUM
- **Exact affected contract:** Agent and Safety & Settings information architecture.
- **Repository/document evidence:** lines 1155–1205 merge strategy authoring and broad account,
  billing, provider, audit and safety workflows without subroute/tab ownership boundaries.
- **Reason:** four navigation labels alone do not reduce workflow complexity.
- **Required correction:** define focused route shells/tabs; keep Strategy Lab/validation and
  account/team/billing as secondary expert workflows. Delete no Phase 1 route.

### FINAL-MEDIUM-06 — First-slice CVD/exhaustion predicate is incomplete

- **Severity:** MEDIUM
- **Exact affected contract:** deterministic first-slice CVD window and exhaustion label.
- **Repository/document evidence:** lines 1388–1405 set the CVD baseline at the 32nd bar before
  `T`, but unrestricted swing `S` can predate it; the negative signed-flow ratio proves
  aggressive-flow reversal, not necessarily exhaustion.
- **Reason:** CVD at `S` can be undefined and the label overstates the measured feature.
- **Required correction:** constrain `S` to the complete CVD window or backfill through `S`;
  define a deterministic exhaustion feature or label the existing predicate accurately.

### FINAL-MEDIUM-07 — “Candidate synthesis” reintroduces model authority ambiguity

- **Severity:** MEDIUM
- **Exact affected contract:** sole deterministic candidate authority.
- **Repository/document evidence:** lines 516–557 make fusion authoritative, but line 1441 asks
  for an explicit candidate “synthesis” intent/tool.
- **Reason:** synthesis can be implemented as a second model-controlled creation gate.
- **Required correction:** rename it candidate presentation/explanation; only deterministic
  fusion may create or transition candidates.

### FINAL-MEDIUM-08 — Journal retry and analytics evaluation contracts are incomplete

- **Severity:** MEDIUM
- **Exact affected contract:** `JournalProjectionEvent` failure states and reproducible
  analytics.
- **Repository/document evidence:** line 1500 lists only
  `PENDING → CLAIMED → APPLIED` while claiming retry/dead-letter; analytics in lines 1455–1459
  has no immutable evaluation snapshot contract.
- **Reason:** retry ownership and analytics reproducibility are undefined.
- **Required correction:** add retryable-failure/scheduled/dead-letter states with lease and
  attempt metadata; define immutable metric/evaluation snapshots with sample hash, assumptions,
  definitions, completeness and provenance.

### FINAL-MEDIUM-09 — Duplicate strategy identity remains in plans

- **Severity:** MEDIUM
- **Exact affected contract:** `strategy_version_id` versus `pattern_version_id`.
- **Repository/document evidence:** lines 730–763 persist both names for the same identity.
- **Reason:** two persisted fields can diverge despite the declared single identity chain.
- **Required correction:** persist one canonical field; expose the compatibility name only as
  a validated API alias.

### FINAL-LOW-01 — Dead `MessageClass.COMMAND` has no disposition

- **Severity:** LOW
- **Exact affected contract:** migration from current message classes to `IntentDecision`.
- **Repository/document evidence:** PR #65 lines 652–659 identifies the dead branch; target
  lines 322–335 do not remove or define it.
- **Reason:** dead routing obscures which classifier is authoritative during migration.
- **Required correction:** explicitly remove it or define bounded emitted behavior under the
  new operation policy.

## 8. Intent and operation contract

**Verdict:** read-only domain routing is sound, but the literal persistence contract and
non-read action routing are not closed.

`MARKET_ANALYSIS`, `SETUP_ANALYSIS` and `EXPLAIN` have no domain-mutation edge. `PLAN_TRADE`,
`MANAGE_POSITION`, `JOURNAL`, `CONFIGURE`, `APPROVE`, `REJECT`, `SKIP` and
`EXECUTE_PAPER_PLAN` are classified, but FINAL-HIGH-01/03 and FINAL-MEDIUM-02 must be corrected.

## 9. Plan, approval and execution contract

**Verdict:** not approved.

Approval alone correctly does not submit, `EXECUTE_PAPER_PLAN` is separate and
`ExecutionService` remains the sole authority. Final deterministic gates precede authorization
consumption and submission. However, FINAL-BLOCKER-01 means the authorization is not bound to
the full executable command. FINAL-HIGH-02/08 and FINAL-MEDIUM-02 also prevent deterministic
replay and complete terminal-state handling.

## 10. Domain ownership and duplication

**Verdict:** directionally correct, incomplete.

The modular monolith, one execution authority, one strategy identity and one candidate/journal
target are appropriate. Legacy setup ownership, candidate/validation adapters, promotion
lifecycle and journal uniqueness remain insufficiently mapped.

## 11. Evidence and fusion

**Verdict:** setup truth/action eligibility separation passes; evidence/candidate contracts
require revision.

Venue, market type, instrument, event/receive/record times, source, finality, freshness,
fallback, cursor, content hash and adapter version are present in the envelope. TradingView
ownership, payload typing, candidate policy/direction identity and exact evidence-window
canonicalization remain open.

## 12. Pattern system

**Verdict:** not implementation-ready.

Pattern Card is correctly a representation and models/screenshots/RAG/lessons cannot directly
mutate executable rules. The legacy `SetupDefinition` migration, immutable promotion state,
concrete AST/evaluator and immutable resistance input must be defined.

## 13. Model routing

**Verdict:** Tier separation and migration placement pass with one scope correction.

No model controls risk, freshness, fusion, idempotency, permissions, sizing arithmetic or
execution. Actual provider attempts replace metering-only calls. Add account/resource scope and
remove the residual candidate-synthesis wording.

## 14. Journal and learning

**Verdict:** canonicalization order and no-self-modification pass; projection identity does not.

Phase 4 correctly moves main reads, human-vs-system, RAG, attachments and discipline data before
automation. Learning proposes immutable drafts only. Canonical trade uniqueness, projection
retry states and reproducible analytics still require contracts.

## 15. Frontend

**Verdict:** navigation direction passes; page composition remains partial.

Four primary shells can reduce navigation complexity and expert routes remain deep-linked.
Phase 1 deletes no route. Strategy authoring and account/team/billing must remain focused
secondary workflows rather than full mega-page contents.

## 16. Migration order

**Verdict:** safety-first direction passes, but dependency ordering is not implementation-ready.

Phase 1 correctly starts with intent, idempotency, plans, approvals and fail-closed tools before
CVD or automation. It must separate plan contract scaffolding from storage that depends on
Phase 5–6 evidence/candidates. Telegram `CLOSE` must follow Phase 9 reconciliation.

## 17. First vertical slice

**Verdict:** valid architectural/evaluation pattern, incomplete proof contract.

BTCUSDT 15m Bearish Liquidity-Sweep Exhaustion at 4h Resistance is explicitly not a
profitability claim. It exercises the required loop, but executable plan binding, instrument
mapping, immutable resistance, Telegram entities, CVD window semantics, journal uniqueness and
analytics snapshots must be corrected. Trading thresholds are not optimized by this review.

## 18. Reuse

**Verdict:** reuse direction passes.

The architecture appropriately reuses/wraps the modular monolith, worker, providers, watchlist,
strategy/version services, planning, approvals, risk, `ExecutionService`, alerts, exchange
adapters, journal, analytics, RAG and frontend components. Typed evidence/fusion, outbox,
inbound Telegram and reconciliation are justified additions. No rewrite or deletion is
authorized.

## 19. CI and safety

GitHub reports backend, deployment-safety, frontend, docker-build, evaluation, e2e-smoke,
Vercel and Vercel Preview Comments successful for exact target commit
`8511ea15dbd6f036a873a049b1adce84a89104cb`.

Passing documentation CI does not implement the target contracts. Checked-in blueprint/default
safety remains paper-only with worker, watcher, TradingView, Telegram, BloFin demo and live
trading disabled. Live deployment control planes were not queried.

## 20. Required next step

Correct FINAL-BLOCKER-01 before any Phase 1 authorization. Then correct FINAL-HIGH-01 through
FINAL-HIGH-12 and the remaining findings in the canonical architecture documents without
product implementation. Repeat this independent exact-head review and require successful CI.
