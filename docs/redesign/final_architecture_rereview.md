# AlphaTrade Agentic Redesign — Final Exact-Head Architecture Re-Review

**Review target:** `main` exact commit `549e42a42fb16765ec0947ef3ba08550459dd1f5`
(merged PR #64: `docs: revise agentic redesign architecture after independent review`)

**Canonical documents on that commit:**

- `docs/redesign/agentic_redesign_phase0_audit.md`
  SHA-256 `f21d30e991e1dacb126097c98767dc3dd02263640ffba758952bc4191e8513b4`
- `docs/redesign/agentic_redesign_target_architecture.md`
  SHA-256 `90f9f651f8db36e64de3c56d574f68ced75d2beca1643f836b5780eb6f347a7f`

**Source review A:** PR #66, branch `cursor/final-architecture-consistency-review-b91f`,
commit `4c4a66b9ca5276e7a7e7dd07c7715d8eecb70160`,
`docs/redesign/final_architecture_consistency_review.md`

**Source review B:** PR #67, branch `cursor/final-safety-review-6b1a`,
commit `a13c60c045e3454456a926ca726e77793ba269b2`,
`docs/redesign/final_safety_data_execution_review.md`

**Scope:** independent architecture and consistency re-review only. No product code,
migrations, canonical-architecture edits, deployment, feature enablement, worker/watcher
enablement, Telegram delivery, BloFin external execution, or live trading. PR #66 and
PR #67 were not merged by this task.

**Method:** the two canonical documents were read in full on the exact head above. PR #66
and PR #67 were read in full. The §31 resolution matrix was treated as a claim, not evidence.
Earlier illustrative schemas were compared against the declared controlling layer in
target §§21–30.

---

## 1. Final verdict

**APPROVED WITH REQUIRED PRE-IMPLEMENTATION CORRECTIONS**

The previous decisive blocker is closed in the controlling contracts: `TradePlanRevision`
now hashes the complete executable order, `ApprovalAuthorization` is account-bound, and
`ExecutionCommand` is a transport envelope. `ExecutionService` must derive venue fields from
the locked revision and must reject caller-introduced executable semantics before
authorization consumption, risk reservation, domain mutation, durable effect, or venue I/O.

PR #67’s six blockers are likewise closed in target §§21–24. Permanent paper mode, unique
entry claim, semantic retry hashing, first-writer commit-before-network, serializable
`RiskReservation`, and exact-`PAPER` replacement of unsafe local settings are specified.

The architecture is **not** yet copy-safe for Phase 1 implementation. Earlier still-presented
schemas and tables in §§8, 11, 12 and 18 omit account binding, retain `CONSUMING`, describe an
incomplete BloFin state machine, and still allow an optional candidate-stage `JournalTrade`.
Target §21 says §§21–30 control when earlier prose differs, but those earlier blocks remain
implementable contracts. Phase 1 must not start until those earlier schemas are aligned or
explicitly marked non-normative. Additional medium gaps remain in first-slice exhaustion
labelling, venue-submit versus locally managed exits, AST operator coverage, and in-transaction
`BLOCK` persistence.

No remaining finding re-opens an unapproved execution path in the controlling layer. This
verdict does not authorize Phase 1 coding, automation, demo venue use, or live trading.

---

## 2. Exact-head verification

| Check | Result |
|---|---|
| Requested canonical head | `549e42a42fb16765ec0947ef3ba08550459dd1f5` |
| `git rev-parse HEAD` on this review branch | `549e42a42fb16765ec0947ef3ba08550459dd1f5` |
| `origin/main` at review time | same commit |
| PR #64 | MERGED; merge commit equals the target |
| PR #66 / PR #67 heads | `4c4a66b` / `a13c60c` as specified; both remain OPEN |
| Source-review base | both source PRs target `8511ea15…`, the pre-correction PR #64 head |
| Product code in this task | unchanged |

PR #64 is the canonical correction. Older PR #64 heads and the source-review bases are not
the review target.

---

## 3. PR #66 closure

Counts from source review A: **1 BLOCKER, 12 HIGH, 9 MEDIUM, 1 LOW**.

| Finding | Source severity | Verdict | Controlling contract on `549e42a` |
|---|---|---|---|
| FINAL-BLOCKER-01 | BLOCKER | **RESOLVED** | Target §22 complete hashed plan; §22 derives venue payload from revision; §8 `ExecutionCommand` is a transport envelope pointing at §§22–24 |
| FINAL-HIGH-01 | HIGH | **RESOLVED** | §3 separate `REJECT`/`SKIP` graph paths; §21 dispatch by `(intent, requested_action)`; authorization issuance accepts only `APPROVE` |
| FINAL-HIGH-02 | HIGH | **RESOLVED** | §23 `CanonicalExecutionPayloadV1` with exhaustive include/exclude lists and canonical serializer |
| FINAL-HIGH-03 | HIGH | **RESOLVED** | §21 exhaustive `READ_ONLY` operational-write allowlist; deny-by-default repositories |
| FINAL-HIGH-04 | HIGH | **RESOLVED** | §25 `PublicMarketObservation` vs `TenantExternalAssertion`; typed payloads with hash/finality/sequence |
| FINAL-HIGH-05 | HIGH | **RESOLVED** | §26 `GlobalSetupTemplate` compatibility; tenant `UserStrategy` → version → `CompiledSetupDefinition`; no silent relabel |
| FINAL-HIGH-06 | HIGH | **RESOLVED** | §26 append-only `StrategyLifecycleEvent`; AST grammar V1, three-valued logic, windows, alignment, sequence reset/overlap, Decimal |
| FINAL-HIGH-07 | HIGH | **RESOLVED** | §5 full candidate key; §26 `CanonicalEvidenceWindowV1`; `PaperValidationCandidate` is downstream |
| FINAL-HIGH-08 | HIGH | **RESOLVED** | §24 absence/resubmit, `PARTIALLY_FILLED_CANCELLED`, Decimal/source/precedence in §27 |
| FINAL-HIGH-09 | HIGH | **RESOLVED** | §26 `ManualLevelRevision` cutoff-bound and hashed into the evidence window |
| FINAL-HIGH-10 | HIGH | **RESOLVED** | §29 Phase 1 scaffolding; executable storage waits for exact identities; no optional provenance |
| FINAL-HIGH-11 | HIGH | **RESOLVED** | §27 Telegram identity contracts; §15/§29 `CLOSE` after Phase 9 |
| FINAL-HIGH-12 | HIGH | **RESOLVED** | §27 unique `(organization_id, execution_lifecycle_id)`; candidate/reject/skip never create `JournalTrade` |
| FINAL-MEDIUM-01 | MEDIUM | **RESOLVED** | §22 `PLAN_TRADE` → `PlanService` → frozen persist or analysis-only, then optional synthesis |
| FINAL-MEDIUM-02 | MEDIUM | **RESOLVED** | §21 separate read/preview/confirm/write; execution `ALLOW\|BLOCK` only; no implicit `WARN → ALLOW` |
| FINAL-MEDIUM-03 | MEDIUM | **RESOLVED** | §2 and §28 outbox = every cross-transaction failure boundary, including journal projection |
| FINAL-MEDIUM-04 | MEDIUM | **RESOLVED** | §28 `ModelTaskRequest` adds typed account/resource/purpose/retention |
| FINAL-MEDIUM-05 | MEDIUM | **RESOLVED** | §28 four route shells with focused tabs; expert/account/billing remain secondary |
| FINAL-MEDIUM-06 | MEDIUM | **PARTIALLY RESOLVED** | §26 constrains CVD through `S` and `T` and renames the ratio; §17 still labels that ratio “exhaustion”; the extra exhaustion predicate is unnamed |
| FINAL-MEDIUM-07 | MEDIUM | **RESOLVED** | §28 synthesis is presentation only; fusion alone creates/transitions candidates |
| FINAL-MEDIUM-08 | MEDIUM | **RESOLVED** | §27 projection retry/dead-letter; §28 `MetricEvaluationSnapshot` |
| FINAL-MEDIUM-09 | MEDIUM | **RESOLVED** | §8/§22 persist only `strategy_version_id`; alias must equal it |
| FINAL-LOW-01 | LOW | **RESOLVED** | §21 removes `MessageClass.COMMAND` during `IntentDecision` migration |

**PR #66 resolution: 1/1 BLOCKER, 12/12 HIGH, 8/9 MEDIUM, 1/1 LOW.**
**Unresolved original finding: FINAL-MEDIUM-06 (partial).** Residual earlier-schema
contradictions are recorded as new findings in §16; they do not reopen FINAL-BLOCKER-01 in
the controlling layer.

### 3.1 Decisive blocker — complete executable-order binding

Original defect: `TradePlanRevision` / `ApprovalAuthorization` did not bind the complete
executable order, while `ExecutionCommand` independently supplied account, side, order type,
quantity and price.

Current controlling contract:

1. `TradePlanRevision` is the sole immutable executable-order source. Its
   `CanonicalTradePlanContentV1` hash covers identity (including `account_id` and optional
   `exchange_account_id`), account safety (NET mode and permission attestation), distinct
   evidence and execution instruments, full order fields (side, quantity/unit, order type,
   TIF, limit-or-MARKET, entry zone, slippage, `reduce_only`, margin/position mode), instrument
   rules, basis policy, risk/exits, validity and every calculation input/result
   (target §22, `TradePlanRevision`).
2. `ApprovalAuthorization` binds organization, user, `account_id`,
   `exchange_account_id?`, operation, plan/revision, `plan_content_hash`, execution
   venue/instrument, verified account mode and permission attestation. Issuance is unique for
   `(organization_id, account_id, exchange_account_id-or-null, revision_id,
   plan_content_hash, operation)` while available (target §22, `ApprovalAuthorization`).
3. `ExecutionService` tenant-loads and locks authorization and revision, recomputes the
   plan hash, and **derives the venue payload only from the revision**. Callers may supply
   transport IDs and redundant assertions; they **cannot introduce an executable field**.
   Mismatch is rejected before authorization consumption, risk reservation, execution-domain
   writes, durable venue effect or venue call (target §22).
4. `ExecutionCommand` in §8 is labelled a transport envelope. Semantic retry identity is
   `CanonicalExecutionPayloadV1` (target §23), which excludes opaque keys, command IDs,
   correlation/request/receipt IDs and transport timestamps.

This closes the original blocker in the controlling layer. It does not make the earlier §8
authorization schema safe to copy; that residual is REREVIEW-HIGH-01.

Required remaining validation (already demanded by the target, still required before Phase 1
coding): mutate each executable plan field and each redundant caller assertion; reject before
consumption, reservation, write or effect; two accounts for one user cannot share an
authorization.

---

## 4. PR #67 cross-check

Source review B recorded **6 BLOCKER, 20 HIGH, 7 MEDIUM**. All are accepted in target §31.
Independent verification of the controlling contracts:

| Finding | Verdict | Why the correction does not reopen PR #66 |
|---|---|---|
| BLOCKER-01 account principal | **RESOLVED** | Plan and authorization bind internal and exchange account, mode and attestation (§22) |
| BLOCKER-02 retry-variant hash | **RESOLVED** | Shared `CanonicalExecutionPayloadV1` with PR #66 HIGH-02 (§23) |
| BLOCKER-03 first-writer ordering | **RESOLVED** | One PostgreSQL transaction claims key, payload, entry claim, authorization, reservation, receipt and `VenueSubmitEffect`, then commits before network I/O (§24) |
| BLOCKER-04 serializable risk | **RESOLVED** | Account serialization plus atomic `RiskReservation` covering pending/ambiguous capacity (§24) |
| BLOCKER-05 one execution per plan | **RESOLVED** | Unique approval issuance plus unique `(organization, account, exchange-account-or-null, revision, ENTRY)` claim (§22, §24) |
| BLOCKER-06 permanent paper | **RESOLVED** | Phase 1 **replaces** unsafe local `trade` / `READ_ONLY` mutation semantics; exact `PAPER` everywhere (§21, §29) |
| HIGH-01 blocked-command retry | **RESOLVED** | Terminal blocked receipt; grant remains `AVAILABLE` unless invalidated; new key required (§24). Residual claim-time rollback is REREVIEW-MEDIUM-04 |
| HIGH-02 consumer freshness | **RESOLVED** | `FreshnessEvaluation` at every boundary; persisted `ingestion_freshness` is not permanent truth (§25) |
| HIGH-03 reconnect/CVD | **RESOLVED** | V1 new connection epoch, no cross-epoch CVD, contiguous backfill and fresh warm-up (§25) |
| HIGH-04 storage fence | **RESOLVED** | `WorkerLeaseEpoch` predicates on every worker-caused write (§28) |
| HIGH-05 candidate convergence | **RESOLVED** | `CanonicalEvidenceWindowV1`; terminal non-resurrection (§26) |
| HIGH-06 cross-venue identity | **RESOLVED** | Separate `EvidenceMarketIdentity` / `ExecutionInstrumentIdentity` plus `BasisSnapshot` (§25) |
| HIGH-07 partial-fill exposure | **RESOLVED** | Every unique fill updates position/exposure immediately; cancel remainder only (§24) |
| HIGH-08 fill identity / absence | **RESOLVED** | Stable fill identity; bounded finality; no single-negative absence; quarantine (§27) |
| HIGH-09 approved payload compare | **RESOLVED** | Same derive-or-reject rule as FINAL-BLOCKER-01 (§22) |
| HIGH-10 candle finality | **RESOLVED** | `FINAL iff provider complete AND evaluated_at >= interval_end + grace` (§25) |
| HIGH-11 trade/CVD identity | **RESOLVED** | Natural identity excludes adapter version; explicit units, windows, event-set hash (§25) |
| HIGH-12 TradingView privacy | **RESOLVED** | Tenant assertions never enter public observation indexes (§25) |
| HIGH-13 scan lineage | **RESOLVED** | `ScanAttempt` / `SourceFetchAttempt` / `SubscriptionEvaluationAttempt` (§28) |
| HIGH-14 operation risk matrix | **RESOLVED** | Entry blocked; authenticated cancel and reduce-only decrease permitted; no `WARN` allow (§21, §27) |
| HIGH-15 Telegram identities | **RESOLVED** | Bot/enrollment/binding/nonce/`ActionExecution` (§27) |
| HIGH-16 durable close | **RESOLVED** | `ClosePositionCommand` with working-order hash, second nonce, atomic effect (§23, §27) |
| HIGH-17 account credentials/NET | **RESOLVED** | Exact `ExchangeAccount` secret resolution; no global fallback; NET probe before POST (§27) |
| HIGH-18 receipt identity | **RESOLVED** | Stable receipt, append-only transitions, versioned projection (§24) |
| HIGH-19 journal truth | **RESOLVED** | Reflective vs projector-owned fields; append-only corrections (§27) |
| HIGH-20 descendant cascade | **RESOLVED** | Atomic reject/skip/reduce-risk matrix; submitted truth preserved (§27) |
| MEDIUM-01..07 | **RESOLVED** | Discriminated commands; Telegram domain idempotency; unique journal aggregate; L2 terminology; replay bundles; evaluation modes; namespaced journal sources (§23, §27, §28) |

PR #67’s added contracts (account binding, canonical payload, first-writer, reservation,
unique claim, paper-mode replacement) **compose** with PR #66 rather than forking a second
execution authority. No new parallel strategy, candidate, journal, or risk authority is
introduced.

---

## 5. Intent / operation safety

Dispatch is `(intent, requested_action)`, never operation class alone (target §21).

| Intent | Default class | Verified routing |
|---|---|---|
| `MARKET_ANALYSIS` | `READ_ONLY` | Market/evidence summary only |
| `SETUP_ANALYSIS` | `READ_ONLY` | Pattern/evidence; no proposal |
| `PLAN_TRADE` | `PLAN` | Immutable revision or analysis-only; never approve/execute |
| `REVIEW_TRADE` | `READ_ONLY` or `JOURNAL` | Write requires confirmation |
| `MANAGE_POSITION` | `MUTATION` | Preview then confirmed update/close only |
| `JOURNAL` | `JOURNAL` | Read by default; confirmed write |
| `EXPLAIN` | `READ_ONLY` | Existing facts only |
| `CONFIGURE` | `CONFIGURATION` | Read or confirmed change; cannot alter paper-mode constants |
| `APPROVE` | `APPROVAL` | One `ApprovalAuthorization`; no submit |
| `REJECT` | `APPROVAL` | Reject transition; cannot create authorization; revokes unconsumed descendants |
| `SKIP` | `APPROVAL` | Skip transition; cannot create authorization; revokes unconsumed descendants |
| `EXECUTE_PAPER_PLAN` | `EXECUTION` | Sole explicit execution intent; `ExecutionService` only |

Confirmed:

- `READ_ONLY` has no graph path to listed domain mutations. Allowed persistence is exhaustive:
  append-only audit/security, atomic quota counters, usage/model-call telemetry, and optional
  `NON_DOMAIN_MEMORY` that cannot trigger a workflow or authorize action (target §21).
- `APPROVE` alone cannot execute (target §3, §8, §21, §22).
- `REJECT` and `SKIP` cannot create authorization (target §21, §27).
- `EXECUTE_PAPER_PLAN` is never inferred from analysis, approval, emoji or generic labels
  (target §3). All channels delegate success to `ExecutionService`.

`IntentDecision.requested_action` remains optional in the §4 schema. Ambiguity is specified
to default to `READ_ONLY` / clarification, and issuance rejects non-`APPROVE` before write.
That combination is sufficient; an explicit negative test for `APPROVAL` with a null action
should still be required (see REREVIEW-LOW-02).

---

## 6. Approval / execution consistency

Controlling lifecycle:

```text
TradePlanRevision
  → ApprovalAuthorization (APPROVE only; unique while available)
  → explicit EXECUTE_PAPER_PLAN / SubmitEntryCommand
  → deterministic pre-submit gates (no consumption on BLOCK)
  → one PostgreSQL transaction:
       lock/bind idempotency + CanonicalExecutionPayloadV1
       unique revision/account ENTRY claim
       CAS-consume authorization
       lock risk state / safety epoch
       atomic RiskReservation
       stable ExecutionReceipt (SUBMITTING)
       one VenueSubmitEffect + deterministic client order ID
       COMMIT
  → leased venue send (no open DB transaction over network I/O)
  → append-only ExecutionTransition + versioned ExecutionProjection
  → reconciliation
```

Ordering and transaction boundary match the required protocol. No caller may alter approved
executable semantics. One revision + one account has at most one entry claim. Split
execution is unsupported without numbered immutable child slices in the parent hash.

`CancelOrderCommand` and `ClosePositionCommand` have distinct hash namespaces
(`alphatrade/submit-entry/v1`, `alphatrade/cancel-order/v1`,
`alphatrade/close-position/v1`). Cross-operation opaque-key reuse is a conflict.

---

## 7. Domain ownership

| Domain | Owner | Parallel authority? |
|---|---|---|
| Strategy/pattern/setup | `UserStrategy` → immutable `UserStrategyVersion` → tenant `CompiledSetupDefinition` | No. Legacy global `SetupDefinition` becomes `GlobalSetupTemplate`; never relabelled tenant-owned |
| Candidate | One assessment/candidate lineage; adapters from watcher, TradingView, orchestration | `PaperValidationCandidate` is a downstream queue, not a source identity |
| Execution | `ExecutionService` only | `AUTO_PAPER` remains a validation simulator and cannot mint demo execution |
| Journal | Canonical `JournalTrade` | Legacy `TradeJournal` is compatibility until parity; not a second target truth |
| Public market observations | Global `PublicMarketObservation` | No tenant IDs |
| Tenant external signals | `TenantExternalAssertion` | Cannot enter public indexes |
| Risk / action eligibility | Deterministic `ActionEligibility` / `RiskReservation` / kill switch | Account state cannot rewrite `SetupAssessment` |
| Models | Tier A/B explanation only | Tier C cannot be overridden |

Legacy global `SetupDefinition` migration is explicit in target §26, including aliasing,
collision `COLLISION_REVIEW_REQUIRED`, dual-read, and retirement only after parity/rollback
reports.

---

## 8. Evidence / candidate contract

Ownership-safe and replayable as specified:

- public observations globally dedupe by natural source event, excluding adapter version;
- tenant assertions are tenant-unique and may reference public IDs;
- `SetupAssessment` is objective and tenant-owned;
- `ActionEligibility` is tenant/account/resource scoped;
- candidate uniqueness is
  `(organization_id, strategy_version_id, setup_definition_id, fusion_policy_version,
  direction, evidence_venue, evidence_market, evidence_instrument, timeframe,
  evidence_window_hash)`;
- `CanonicalEvidenceWindowV1` includes strategy/setup/fusion/finality/freshness versions,
  direction, venue/market/instrument, timeframe, half-open bounds, trigger identity, mandatory
  roles, selected public hashes, tenant assertion hashes, manual-level revision, source set
  and correction policy; it excludes receive/record times and optional presentation evidence.

Equivalent watcher / TradingView / detector evidence is required to converge on one
candidate. Optional evidence enriches an assessment revision; it creates a new candidate
only when a required role or semantic bound changes. Terminal candidates cannot be resurrected.

---

## 9. Pattern / AST

Specified sufficiently for compiler/evaluator design:

- authored content is immutable; promotion lives in append-only `StrategyLifecycleEvent`;
- AST grammar V1 covers literals/fields, arithmetic, comparison, boolean, window
  aggregates, crosses, `IsMissing`, ordered `PatternStep` with min/max offset, `reset_on`,
  `invalidate_on`, and `DISALLOW | RESTART_AT_CURRENT | ALLOW_DISTINCT_START`;
- Decimal arbitrary precision with grammar-declared scale/rounding only at named
  boundaries; default rounding forbidden;
- `AND`/`OR` three-valued logic; required `MISSING` fails closed;
- windows are half-open event-time or exact final-bar counts; alignment is exact /
  previous-final / bounded as-of; interpolation forbidden unless a versioned operator
  permits it;
- higher-timeframe values must be final before lower-timeframe cutoff;
- corrections replay from the earliest affected event and append a superseding assessment.

Not yet sufficient to compile the first-slice fixture as AST V1: Wilder ATR(14) is required
by §17 but is not an AST operator, and no first-slice field catalog is published. That is
REREVIEW-MEDIUM-03, not a Phase 1 blocker.

---

## 10. Execution state model

Stable `ExecutionReceipt` identity, append-only `ExecutionTransition`, and rebuildable
`ExecutionProjection` are distinct (target §18, §24).

Uncertainty, partial fill, cancel, late fill and terminal states in the controlling protocol:

- ambiguous submit: `RECONCILIATION_REQUIRED → ABSENCE_PENDING → ABSENCE_PROVEN →
  RESUBMIT_AUTHORIZED → SUBMITTING`, reusing the same command, reservation, effect and client
  ID; never a second authorization;
- every unique fill immediately updates quantity, price, fees, open position and exposure;
- cancel affects unfilled remainder only; filled quantity plus cancelled remainder is
  `PARTIALLY_FILLED_CANCELLED` with an open position;
- late fills append and update that position;
- unresolved conflict is `OPERATOR_HOLD` with quarantine;
- replay returns stable identity, latest projection and event watermark; historical hashes
  never change.

The §11 mermaid state diagram still ends `CANCEL_PENDING → CANCELLED` and lacks the absence
and partial-cancel terminals. That is superseded by §24 but remains a copy hazard
(REREVIEW-HIGH-01).

---

## 11. Journal / learning

Canonical migration is coherent in the controlling layer:

- `JournalTrade` is the lifecycle aggregate, unique per `(organization_id,
  execution_lifecycle_id)`;
- candidate/reject/skip remain lifecycle events and never create a trade row;
- projector-owned venue facts vs user reflective fields;
- append-only factual corrections with actor/reason/supersession;
- typed behavioral backfill parity including emotions, mistakes, tags, attachments,
  discipline, human-versus-system and RAG lineage (Phase 4 before automation);
- lessons stay `PENDING_REVIEW`; accepting a lesson does not mutate an active strategy;
- automatic learning may propose a new immutable draft version only.

§12’s projection table still says “Candidate confirmed → Optional planned draft”. That
contradicts §27 and is part of REREVIEW-HIGH-01. No learning path in §§13/27/29 may mutate
active executable strategy logic automatically.

---

## 12. Migration order

Phase 1 is the safety foundation, in order (target §15, §29):

1. permanent paper mode
2. `READ_ONLY` non-interference
3. fake mutation/execution tool removal / fail-closed
4. complete plan binding
5. account-bound unique `ApprovalAuthorization`
6. `CanonicalExecutionPayloadV1`
7. scoped idempotency and unique execution claim
8. serializable `RiskReservation`
9. append-only execution state
10. PostgreSQL concurrency/crash tests

CVD, watcher, Telegram mutation, BloFin automation, journal projection, analytics learning and
frontend consolidation remain later. Automation flags stay off. This matches the required
order.

Phase 1 may use fail-closed scaffolding and must not persist executable plans with
optional/transitional provenance.

---

## 13. First vertical slice

Scope: BTCUSDT, 15m, Bearish Liquidity-Sweep Exhaustion at 4h Resistance. This review does not
evaluate profitability. Thresholds remain evaluation hypotheses.

The slice is internally coherent as an architectural proof and exercises:

| Required loop element | Contract |
|---|---|
| Market evidence | Binance USD-M perpetual 15m/4h final klines; spot adapter must not be reused |
| CVD | Signed perpetual quote-volume CVD; window must cover `S` and `T` |
| Pattern assessment | Versioned resistance/`ManualLevelRevision`; sequence/volume/CVD predicates |
| Candidate | Canonical window key; one occurrence |
| Plan | Account-specific immutable revision; no placeholders |
| Approval | Authorization only |
| Risk | Fresh `ActionEligibility` and final gates; basis blocks eligibility only |
| Telegram | Enrollment/binding/nonce/receipts; `CLOSE` after Phase 9; no Telegram plan execution in this rollout |
| BloFin DEMO | Separate execution venue; NET only; account-scoped credentials |
| Reconciliation | Orders, fills, positions, fees, funding, PnL |
| Journal | One `JournalTrade` after approved-plan or first-fill |
| Analytics | Snapshot-bound; pending lesson only |

Cross-venue basis is explicit. The slice is blocked from implementation until Phase 5 source
contracts pass. Remaining slice-definition gaps are REREVIEW-MEDIUM-01 and
REREVIEW-MEDIUM-02/03.

---

## 14. Remaining problems

### REREVIEW-HIGH-01 — Earlier schemas remain copyable and contradict §§21–30

- **Severity:** HIGH
- **Source finding:** residual of FINAL-BLOCKER-01, PR #67 BLOCKER-01, FINAL-HIGH-08,
  FINAL-HIGH-12, PR #67 HIGH-18 / MEDIUM-07
- **Exact canonical contract evidence:**
  - Controlling: target §21 (“If earlier illustrative schemas, diagrams, phase labels or
    prose differ, these sections control”), §22 account-bound authorization, §24 complete
    execution protocol, §27 journal uniqueness.
  - Contradictory still-presented contracts:
    - §8 `ApprovalAuthorization` omits `account_id`, `exchange_account_id`, mode and
      permission attestation, and uses `CONSUMING`.
    - §18 first-slice table binds authorization to organization/user/revision/hash/channel/
      actor only, and still specifies `AVAILABLE → CONSUMING → CONSUMED`.
    - §11 mermaid lifecycle has `CANCEL_PENDING → CANCELLED` only and has no
      absence-proof/resubmit or `PARTIALLY_FILLED_CANCELLED` path.
    - §12 journal table still creates an optional `JournalTrade` at candidate confirmation.
- **Why it remains unresolved:** Phase 1 implementers can copy the first schema they see.
  A control clause several hundred lines later does not delete those schemas. This is how
  incomplete order binding survived the previous revision.
- **Required correction:** replace the §8/§11/§12/§18 schemas with the §22–§27 field sets, or
  mark each earlier block `NON-NORMATIVE / superseded by §§21–30` adjacent to the schema, not
  only in §21. Do not leave two implementable authorization or journal-creation contracts.
- **Required deterministic validation:** a documentation consistency checklist that every
  named resource (`TradePlanRevision`, `ApprovalAuthorization`, `ExecutionReceipt`,
  `JournalTrade` creation boundary, execution state enum) has exactly one field list and
  state machine in the target document.

This is a documentation correction. This re-review is not authorized to edit the canonical
architecture documents.

### REREVIEW-MEDIUM-01 — First-slice “exhaustion” remains two different predicates

- **Severity:** MEDIUM
- **Source finding:** FINAL-MEDIUM-06
- **Exact canonical contract evidence:**
  - §17 step 9 still requires “trigger-bar exhaustion” as
    `signed_quote_delta_T / total_quote_volume_T <= -0.10`.
  - §26 says that ratio is `trigger_bar_aggressive_sell_imbalance` and that “exhaustion”
    additionally requires a versioned price-response/declining-aggression predicate, which
    is not defined.
- **Why it remains unresolved:** two implementations can both claim first-slice compliance
  with different confirmation conditions.
- **Required correction:** either define the additional predicate with exact inputs, window,
  Decimal formula and finality, or change §17 to use the imbalance name only and stop calling
  the ratio exhaustion.
- **Required deterministic validation:** golden fixtures where the ratio passes and the
  additional predicate fails (and the reverse); only one confirmation result is legal.

### REREVIEW-MEDIUM-02 — Venue-submit field set versus locally managed exits is unspecified

- **Severity:** MEDIUM
- **Source finding:** related to FINAL-BLOCKER-01 / PR #67 HIGH-09 (complete approved
  order), not reopened as a blocker because `plan_content_hash` covers stops/targets/runner
- **Exact canonical contract evidence:** §22 hashes stop, ordered targets, runner, slippage,
  margin mode and position mode. `CanonicalExecutionPayloadV1` (§23) lists side, order type,
  TIF, quantity, price/`MARKET`, `reduce_only`, bindings and policy versions, but not stop,
  targets, runner or slippage. No sentence states whether BloFin receives an entry-only order
  or attached working exits.
- **Why it remains unresolved:** the same approved revision can produce different venue orders
  (entry only vs attached TP/SL/OCO). Risk reservation and close working-order hashes cannot
  be implemented uniformly.
- **Required correction:** enumerate the exact venue-submitted field set for
  `SubmitEntryCommand`. State that stop/target/runner are locally managed, attached working
  orders, or unsupported in v1. Bind that choice into `execution_policy_version`.
- **Required deterministic validation:** from one frozen revision, two independent builders
  emit byte-identical venue client payloads; attaching or omitting exits is a hash change.

### REREVIEW-MEDIUM-03 — AST V1 cannot express first-slice ATR / indicator fields

- **Severity:** MEDIUM
- **Source finding:** residual of FINAL-HIGH-06 (original AST gap is otherwise closed)
- **Exact canonical contract evidence:** §17 requires Wilder ATR(14) matching existing
  indicator semantics. §26 `WindowAggregate` operators are `MIN|MAX|SUM|MEAN|COUNT|FIRST|LAST`
  only. No field allowlist maps `T.high`, volume-mean, or CVD series.
- **Why it remains unresolved:** a Pattern Card for the slice cannot compile to AST V1 as
  specified. A hardcoded evaluator can implement §17, but then Pattern Card compilation is
  not the slice’s executable source.
- **Required correction:** add versioned indicator operators (or an explicit first-slice
  exception: hardcoded evaluator with golden parity, AST operators in a later grammar
  version) and publish the field catalog used by the slice.
- **Required deterministic validation:** compile or explicitly exempt the slice predicates;
  independent evaluators produce byte-identical rule results on the §17 fixture.

### REREVIEW-MEDIUM-04 — Claim-transaction `BLOCK` versus terminal blocked-receipt persistence

- **Severity:** MEDIUM
- **Source finding:** residual of PR #67 HIGH-01
- **Exact canonical contract evidence:** §24 pre-submit `BLOCK` creates an immutable blocked
  receipt and leaves authorization `AVAILABLE`; replay of that key returns the same block. For
  kill-switch versus claim races, “a stale epoch causes `BLOCK`, reservation rollback and no
  effect.” Crash-before-commit also rolls back with no receipt.
- **Why it remains unresolved:** if a claim-time capacity/kill-switch failure rolls back the
  idempotency row, the same opaque key can later submit after the condition clears, without a
  new user action. If it instead commits a blocked receipt, the key is terminal. Both readings
  are available.
- **Required correction:** state that any evaluated `BLOCK` after the idempotency row is
  inserted commits a terminal blocked receipt in that transaction; only failures before the
  insert roll back with an unused key. Alternatively, state unused-key rollback explicitly
  and require a new key only after a committed block.
- **Required deterministic validation:** kill-switch activation during the claim transaction;
  assert either a stable blocked receipt on replay or a documented unused-key retry, never
  both.

### REREVIEW-LOW-01 — Agent graph still omits the PlanService persist node

- **Severity:** LOW
- **Source finding:** FINAL-MEDIUM-01 residual
- **Exact canonical contract evidence:** §22 names
  `EXECUTABLE_REVISION_PERSISTED | ANALYSIS_ONLY_CANNOT_CREATE_EXECUTABLE_PLAN` before
  synthesis. The §3 graph still has `PLAN → SYN` without that result.
- **Why it remains unresolved:** narrative synthesis can still be mistaken for plan
  creation if implementers follow the diagram.
- **Required correction:** add the PlanService result node on the graph.
- **Required deterministic validation:** already required by §22 (synthesis cannot
  create/alter a revision).

### REREVIEW-LOW-02 — `APPROVAL` with null `requested_action`

- **Severity:** LOW
- **Source finding:** related to FINAL-HIGH-01
- **Exact canonical contract evidence:** §4 `requested_action` is optional; §21 dispatches
  on exact action; issuance rejects non-`APPROVE`.
- **Why it remains unresolved:** the fail-closed path for `operation_class=APPROVAL` and
  `requested_action=null` is implied by ambiguity→`READ_ONLY`, not stated as a negative case.
- **Required correction:** one sentence plus a test that this input cannot mint authorization.
- **Required deterministic validation:** classifier/graph/repository fixtures with missing
  action.

No remaining **BLOCKER**.

---

## 15. Safety verdict

Paper/demo posture in the target is stronger than the current runtime and is acceptable as a
Phase 1 *design*:

- exact `EXECUTION_MODE == PAPER`, `ENABLE_REAL_TRADING == false`,
  `EXCHANGE_MODE in {paper_internal, paper_exchange_demo}`;
- `trade_live` remains tombstoned;
- execution-capable process plus `READ_ONLY` is an invalid configuration;
- settings, services, providers, APIs, Telegram and models cannot enable live trading;
- real-money hosts remain unreachable by allowlist and network policy.

This review did not change runtime code. Current local `Settings` can still accept `trade +
true`; that is a known CURRENT defect that Phase 1 is required to replace, not freeze.

No live trading, Telegram delivery, BloFin submit, worker, or watcher enablement is
authorized.

---

## 16. CI status

CI is **not** an architecture-correctness input. It is recorded separately.

GitHub Actions run `34956824132` for exact head
`549e42a42fb16765ec0947ef3ba08550459dd1f5` completed **success**:

| Check | Status |
|---|---|
| deployment-safety | success |
| frontend | success |
| docker-build | success |
| backend | success |
| evaluation | success |
| e2e-smoke | success |
| workflow `CI` | success |
| Vercel commit status | success |

Passing documentation CI does not implement the target contracts and does not reopen or
close architecture findings. This re-review PR is a later commit and has its own CI, which
is also not an architecture-correctness input.

---

## 17. Required next step

1. Do **not** start Phase 1 product implementation.
2. Do **not** merge PR #66 or PR #67; they review the pre-correction head `8511ea15`.
3. Apply documentation-only corrections to the canonical architecture for REREVIEW-HIGH-01
   and the medium items that affect later phases (especially MEDIUM-01 and MEDIUM-04 before
   Phase 1.8).
4. Repeat an independent exact-head review after those documentation corrections.
5. Only then authorize Phase 1 coding against the ten-slice order in target §29, with
   automation remaining disabled.

**Exact next Cursor prompt:**

```text
Documentation-only canonical architecture alignment after final re-review.

Target main exact head 549e42a42fb16765ec0947ef3ba08550459dd1f5
plus docs/redesign/final_architecture_rereview.md.

Do not implement product code, migrations, flags, workers, Telegram, BloFin, or live trading.
Do not merge PR #66 or PR #67.

Edit only the canonical architecture documents to close REREVIEW-HIGH-01 and the listed
MEDIUM/LOW findings: replace or mark non-normative the earlier §8/§11/§12/§18 schemas;
resolve first-slice exhaustion naming; define venue-submit vs local exits; specify
claim-transaction BLOCK persistence; add AST/slice operator exception or operators.

Keep §§21–30 as the controlling layer and make earlier schemas identical to them.
```
