# AlphaTrade Agentic Redesign — Final Phase 1 Architecture GO/NO-GO Gate

**Review target:** PR #70, branch `cursor/final-architecture-alignment-c5d7`, exact commit
`d8f684f7c7a945986951c01aaed10bb3261eff4f`

**Canonical documents on that commit:**

- `docs/redesign/agentic_redesign_phase0_audit.md`
  SHA-256 `91e016f00d65e8f89d78ded5c447fd06f4fef2c09d7c7989346f67ef74d55991`
- `docs/redesign/agentic_redesign_target_architecture.md`
  SHA-256 `ff73880441d1b3bc6227bdec65c9983b6b38d0544a6bb1ab1788c68d236d5b5d`

**Reference reviews (not merged by this task):**

- PR #69 exact head `25d4f8d9ae3dd00261a7eaafed9904a67c9b7a5f`
  (`docs/redesign/final_architecture_rereview.md`)
- PR #68 exact head `e050d743837c75694044a1fd6808315b7aca605f`
  (`docs/redesign/final_safety_data_execution_rereview.md`)

**Base at review time:** `origin/main` = `549e42a42fb16765ec0947ef3ba08550459dd1f5`

**Scope:** narrow final GO/NO-GO architecture review only. No redesign, no product
implementation, no canonical-architecture edit, no deployment, no feature enablement, no
merge of PR #70, and no live trading.

**Method:** the two canonical documents were read on the exact PR #70 head. PR #68 and PR #69
were read in full. Earlier still-presented schemas, diagrams and tables were compared with
§§21–30. Only issues that could materially affect implementation correctness are in scope.
Stylistic preference is out of scope.

---

## 1. Final verdict

**APPROVED FOR PHASE 1 IMPLEMENTATION**

PR #70 closes the remaining pre-implementation HIGH findings from PR #69
(`REREVIEW-HIGH-01`) and PR #68 (`HIGH-14`, `HIGH-16`). No BLOCKER and no HIGH finding
remains on exact head `d8f684f`.

This verdict authorizes Phase 1 coding against the ten safety-foundation slices in target
§§15/29 only. It does not merge PR #70, enable workers, watchers, Telegram delivery, BloFin
demo submission, or live trading, and it does not authorize Phase 2+.

---

## 2. Exact-head verification

| Check | Result |
|---|---|
| Requested branch | `cursor/final-architecture-alignment-c5d7` |
| Requested exact head | `d8f684f7c7a945986951c01aaed10bb3261eff4f` |
| `git rev-parse` of that ref | same commit |
| PR #70 files vs `origin/main` | only the two redesign documents |
| Product code / config / deployment in PR #70 | unchanged |
| PR #69 / PR #68 heads | `25d4f8d` / `e050d74` as specified; both remain OPEN |

---

## 3. Closure of remaining pre-implementation findings

### PR #69 — architecture re-review

| Finding | Prior severity | Verdict on `d8f684f` | Controlling evidence |
|---|---|---|---|
| REREVIEW-HIGH-01 earlier copyable schemas | HIGH | **RESOLVED** | §8 `TradePlanRevision` / `ApprovalAuthorization` now bind account, mode, attestation and `AVAILABLE\|CONSUMED\|EXPIRED\|REVOKED` with no durable `CONSUMING` (`:783-872`). §11 mermaid includes absence/resubmit, `PARTIALLY_FILLED_CANCELLED`, `CLOSE_PENDING` and `BLOCKED_BEFORE_DISPATCH` (`:1069-1105`). §12 candidate/reject/skip create no `JournalTrade` (`:1192-1202`). §18 table matches those contracts (`:1638-1646`). §21 requires every repeated representation to stay identical (`:1729-1735`). |
| REREVIEW-MEDIUM-01 exhaustion naming | MEDIUM | **RESOLVED** (not a Phase 1 HIGH) | §17 names CVD divergence and aggressive sell imbalance; §26 forbids labelling either “exhaustion” (`:1501-1542`, `:2342-2348`). |
| REREVIEW-MEDIUM-02 venue-submit vs local exits | MEDIUM | **RESOLVED** (not a Phase 1 HIGH) | V1 entry POST is entry-only; attached TP/SL/OCO unsupported; policy-versioned (`:1155-1157`, `:1955-1963`). |
| REREVIEW-MEDIUM-03 ATR / AST | MEDIUM | **RESOLVED** (not a Phase 1 HIGH) | `WilderAtrFeatureV1` plus first-slice field allowlist (`:2276-2315`). |
| REREVIEW-MEDIUM-04 claim-time BLOCK persistence | MEDIUM | **RESOLVED** (not a Phase 1 HIGH) | Evaluated BLOCK after idempotency insert commits a terminal blocked receipt and leaves the key unusable (`:1975-1980`). |
| REREVIEW-LOW-01 / LOW-02 | LOW | **RESOLVED** | PlanService persist node before synthesis (`:245-247`); missing approval action cannot mint authorization (`:325-326`). |

### PR #68 — safety/data/execution re-review

| Finding | Prior severity | Verdict on `d8f684f` | Controlling evidence |
|---|---|---|---|
| HIGH-14 kill switch after claim before dispatch | HIGH | **RESOLVED** | Four barriers; pre-POST `DISPATCH_AUTHORIZED` commit is the linearization point; later activation cannot pretend a possible send disappeared (`:2027-2058`, `:1117-1127`). |
| HIGH-16 close uniqueness and fill race | HIGH | **RESOLVED** | Channel-neutral `CloseClaim` unique on account/position/projection version; atomic `POSITION_OPEN(version) -> CLOSE_PENDING`; pre-POST revalidation; `reduce_only` forbids side flip; residual recovery is a new authorized action (`:2417-2481`). |

Prior PR #66 / PR #67 blockers and HIGHs remain closed in §§21–27; this gate did not reopen
them.

---

## 4. Required GO/NO-GO checks

### 4.1 Earlier schemas and diagrams agree with canonical contracts

**Result: PASS**

§21 states that §§21–30 and the earlier overview schemas/diagrams/tables are the same
contract, and that implementation must never select a less restrictive reading
(`:1729-1735`). Independent comparison of the previously contradictory copyable blocks:

| Resource | Earlier still-presented contract | §§21–30 |
|---|---|---|
| `TradePlanRevision` | §8 hashes account, both market identities, full order, rules, basis, risk/exits and calculations (`:783-827`) | Same complete `CanonicalTradePlanContentV1` set (`:1805-1844`) |
| `ApprovalAuthorization` | §8 binds `account_id` / `exchange_account_id?`, venue/instrument, NET mode, attestation; `AVAILABLE -> CONSUMED`; no `CONSUMING` (`:840-872`) | Same field set and unique issuance (`:1851-1868`) |
| `ExecutionCommand` | §8 is a transport envelope; no independent side/qty/price (`:876-897`) | Service derives venue payload only from the revision (`:1872-1876`); `CanonicalExecutionPayloadV1` (`:1896-1920`) |
| Execution lifecycle | §1/§2/§3 claim then lease then dispatch (`:97-102`, `:181-186`, `:238-243`) | Same first-writer transaction then leased send (`:1982-2008`, `:2027-2040`) |
| Journal creation | §12/§13: candidate/reject/skip never create a trade (`:1192-1202`, `:1244-1246`) | Same uniqueness and start boundary (`:2506-2513`) |

`CONSUMING` remains only as an explicit prohibition (`:872`, `:1639`). The previous optional
candidate-stage `JournalTrade` row is gone.

### 4.2 TradePlanRevision / ApprovalAuthorization / execution lifecycle remain coherent

**Result: PASS**

Lifecycle on this head:

```text
immutable TradePlanRevision
  -> APPROVE issues unique available ApprovalAuthorization (no submit)
  -> explicit EXECUTE_PAPER_PLAN / SubmitEntryCommand
  -> pre-submit gates; evaluated BLOCK commits terminal receipt; grant stays AVAILABLE
  -> one PostgreSQL transaction:
       lock idempotency + CanonicalExecutionPayloadV1
       unique revision/account ENTRY claim
       CAS-consume authorization
       lock safety epoch / risk
       atomic RiskReservation
       stable ExecutionReceipt (SUBMITTING)
       one VenueSubmitEffect + deterministic client order ID
       COMMIT
  -> lease, dispatch-authorization, then venue POST
```

Callers cannot introduce executable semantics (`:1872-1876`). One revision + one account has
at most one entry claim (`:1883-1892`). Split execution remains unsupported without numbered
immutable child slices.

### 4.3 APPROVE does not execute

**Result: PASS**

- Graph: `APPROVE` persists authorization and returns; there is no edge to
  `ExecutionService` (`:222-233`).
- Rule text: approval records an authorization and does not submit (`:265-267`, `:869-872`).
- Routing table: `APPROVE` may create one authorization only (`:1769`).
- Telegram rollout: `APPROVE` never submits (`:1041`).
- Sequence: approval is recorded, then a separate `EXECUTE_PAPER_PLAN` is required
  (`:177-180`).

### 4.4 REJECT / SKIP cannot authorize

**Result: PASS**

Separate graph paths “never authorize” (`:223-224`, `:268-270`). §21 issuance accepts only
the `APPROVE` discriminator and rejects every other intent before write (`:1770-1775`).
§4: `operation_class=APPROVAL` with a missing or non-`APPROVE`/`REJECT`/`SKIP` action cannot
mint an authorization (`:325-326`). §27 revokes unconsumed descendants and creates no
command (`:2397-2398`).

### 4.5 READ_ONLY cannot perform domain mutation

**Result: PASS**

No graph path from `READ_ONLY` to proposal, approval, execution, strategy, backtest,
validation, watcher, configuration or other domain writes (`:258-261`). Exhaustive
allowlist is audit/security events, quota counters, usage/model-call telemetry, and
`NON_DOMAIN_MEMORY` that cannot trigger a workflow or authorize action (`:1777-1794`).
Everything else is deny-by-default, including journal and risk/configuration mutation.
Ambiguity defaults to `READ_ONLY` (`:323`).

### 4.6 Kill-switch dispatch-time semantics are coherent

**Result: PASS**

Four mandatory barriers (`:2027-2039`):

1. claim-transaction safety-epoch lock;
2. effect-lease epoch recheck;
3. immediate pre-POST epoch lock and CAS `LEASED -> DISPATCH_AUTHORIZED` (linearization
   point);
4. post-ambiguous-send epoch record.

If a newer blocking epoch commits first, `BLOCKED_BEFORE_DISPATCH` is appended, no POST
occurs, and identities remain historical truth (`:2041-2049`, `:1117-1123`). After
linearization, the worker must POST without unrelated work; a later kill switch cannot erase
a possible send (`:2051-2058`). Claim-time evaluated BLOCK commits a terminal blocked
receipt; the same key cannot later submit (`:1975-1980`). Entry/increase remains blocked;
authenticated exact cancel and reduce-only recovery follow the no-increase matrix
(`:2022-2025`, `:2410-2415`).

### 4.7 Unique channel-neutral close claim is defined

**Result: PASS**

`CloseClaim` is database-unique for
`(organization_id, account_id, exchange_account_id-or-null, position_id,
position_projection_version)` (`:2436-2440`, `:1645`). Web, agent and Telegram are adapters
to one service (`:2418-2419`, `:1047-1051`). The claim transaction compare-and-sets
`POSITION_OPEN(expected_version) -> CLOSE_PENDING`, inserts one receipt/effect, and includes
that pending effect in the working-order hash (`:2451-2454`). A competing same-hash caller
resolves the existing result; a different hash conflicts without a second effect
(`:2440-2441`). Channel-specific idempotency cannot bypass the claim (`:2456-2457`).

### 4.8 Fill-versus-close race cannot reverse exposure

**Result: PASS**

Before POST, dispatcher revalidates remaining NET position and working-order hash against
the claim; changed state suppresses stale-quantity POST unless a `close_policy_version`
bound reduce-only primitive is contract-tested never to reverse exposure (`:2460-2466`,
`:1149-1154`). Fills during/after send remain authoritative. `reduce_only=true` must prevent
side flip and over-close becoming reverse exposure (`:2468-2471`). Zero quantity is
`CLOSED`; a residual returns to truthful `POSITION_OPEN` or stays `RECONCILIATION_REQUIRED`;
further reduce-only recovery is a new authorized action on a new projection version
(`:2472-2475`). Required races are enumerated (`:2477-2481`).

### 4.9 Execution state diagrams agree on partial fill / cancel / uncertainty / close

**Result: PASS**

§11 mermaid and §24 protocol both include:

`SUBMITTING`, `BLOCKED_BEFORE_DISPATCH`, `ACKNOWLEDGED`, `PARTIALLY_FILLED`, `FILLED`,
`CANCEL_PENDING`, `CANCEL_RECONCILIATION_REQUIRED`, `CANCELLED`,
`PARTIALLY_FILLED_CANCELLED`, `POSITION_OPEN`, `CLOSE_PENDING`,
`RECONCILIATION_REQUIRED`, `ABSENCE_PENDING`, `ABSENCE_PROVEN`, `RESUBMIT_AUTHORIZED`,
`OPERATOR_HOLD`, `CLOSED`.

Partial fill immediately updates position/exposure (`:2109-2110`, `:1138`). Cancel affects
remainder only; filled-plus-cancelled remainder is `PARTIALLY_FILLED_CANCELLED` with an open
position (`:2095-2096`, `:1085-1089`). Uncertain submit uses
`RECONCILIATION_REQUIRED -> ABSENCE_PENDING -> ABSENCE_PROVEN -> RESUBMIT_AUTHORIZED ->
SUBMITTING` and never a second authorization (`:2086-2092`, `:1099-1102`). Close is a
separate `ClosePositionCommand` / `CloseClaim` aggregate (`:1943-1948`, `:2417-2454`), not a
second entry authorization.

### 4.10 JournalTrade creation timing is consistent

**Result: PASS**

Candidate confirmation, `REJECT` and `SKIP` never create `JournalTrade` (`:1192-1202`,
`:2508`). The aggregate starts only at the approved-plan/execution boundary: either when an
approved plan has a non-null execution-claim identity, or on first authoritative fill, under
a versioned §12 policy selector. Both resolve the same database-unique
`(organization_id, execution_lifecycle_id)` row (`:1193-1196`, `:2508-2513`). Planned-never-
executed rows are excluded from executed statistics. Projector-owned venue facts cannot be
overwritten (`:2515-2521`).

This is one uniqueness rule with a versioned start selector, not two trade authorities.

### 4.11 Strategy / evidence / candidate ownership has no duplicate authority

**Result: PASS**

- Strategy: `UserStrategy` → immutable `UserStrategyVersion` → one tenant-owned
  `CompiledSetupDefinition`; Pattern Card is not a fourth identity (`:609-617`, `:2193-2200`).
  Legacy global rows remain `GlobalSetupTemplate` and are never relabelled tenant-owned
  (`:2214-2218`).
- Evidence: `PublicMarketObservation` has no tenant IDs; `TenantExternalAssertion` cannot
  enter public indexes (`:2128-2136`, `:430-433`).
- Candidate: one database key including `CanonicalEvidenceWindowV1`
  (`:548-562`, `:2322-2340`). Watcher / TradingView / detector adapters feed one assessment
  command. `PaperValidationCandidate` is a downstream queue, not a source identity.
- Execution: only `ExecutionService` may consume authorization and submit (`:914-916`).
  `AUTO_PAPER` cannot mint demo execution (`:1177-1182`).
- Fusion, not models, creates/transitions candidates (`:2550-2552`).

### 4.12 BTC first-slice terminology and ATR / AST path are implementable

**Result: PASS**

Slice name is **Bearish Liquidity Sweep with CVD Divergence and Aggressive Sell Imbalance
at 4h Resistance** (`:1503-1507`). Required predicates are named:

- `bearish_cvd_divergence` (`:1539-1540`, `:2344-2345`);
- `trigger_bar_aggressive_sell_imbalance` (`:1541-1542`, `:2343-2344`).

No first-slice exhaustion / absorption / deceleration predicate is defined (`:2345-2348`).

ATR path is implementable without a generic indicator operator: precomputed
`WilderAtrFeatureV1` (Wilder seed/recurrence, Decimal, contiguous final bars, `MISSING` on
gap/warm-up failure) is referenced through allowlisted `Field` nodes (`:2276-2315`,
`:1524-1533`). Remaining slice arithmetic uses existing AST operators and
`WindowAggregate(MEAN, ...)`. This is sufficient to compile the slice; it is not a
profitability claim.

### 4.13 Permanent paper / demo-only safety remains unchanged

**Result: PASS**

Permanent invariant (`:1743-1761`):

```text
EXECUTION_MODE == PAPER
ENABLE_REAL_TRADING == false
EXCHANGE_MODE in {paper_internal, paper_exchange_demo}
trade_live == tombstoned and rejected
execution-capable process + READ_ONLY mode == invalid configuration
```

Settings, services, providers, APIs, Telegram and models cannot alter those constants.
Real-money hosts remain unreachable. PR #70 is documentation-only; it does not enable any
runtime capability. Phase 1 **replaces** unsafe current local `trade + true` semantics; it
does not freeze them (`:1739-1740`, `:2571-2576`).

---

## 5. Phase 1 authorization boundary

Approved work, in order (`:2578-2589`):

1. permanent paper-mode invariant;
2. exhaustive `READ_ONLY` non-interference;
3. fail-closed fake mutation/execution tools;
4. complete account-specific `TradePlanRevision`;
5. account/order-bound unique `ApprovalAuthorization`;
6. `CanonicalExecutionPayloadV1` and serializer;
7. scoped idempotency and unique entry claim;
8. serializable `RiskReservation`, claim-time ordering and dispatch-time barriers;
9. append-only receipt/transition and versioned projection;
10. PostgreSQL concurrency/crash/fencing tests.

Not authorized by this verdict: CVD/watcher/Telegram/BloFin automation, journal projection,
analytics learning, frontend consolidation, flag changes, deployment, or Mode D.

Phase 1 may use fail-closed scaffolding and must not persist executable plans with
optional/transitional provenance (`:2591-2595`).

---

## 6. Safety verdict

Paper/demo-only posture is unchanged and is the Phase 1 *target* invariant. This review
changed no runtime code. Current local `Settings` can still accept unsafe combinations; that
is a known CURRENT defect that Phase 1.1 must replace, not preserve.

No live trading, Telegram delivery, BloFin submit, worker, or watcher enablement is
authorized.

---

## 7. CI status

CI is not an architecture-correctness input. PR #70 is documentation-only relative to
`main`. Passing documentation CI would not implement the contracts; failing it would not
reopen a closed architecture finding.

---

## 8. Remaining BLOCKER / HIGH findings

**BLOCKERS:** none

**HIGH:** none

No other material implementation-correctness defect was found in the thirteen required
checks.

---

## 9. Required next step

1. Human-merge PR #70 (documentation-only architecture alignment) if this gate is accepted.
   This review does not merge it.
2. Do not merge PR #68 or PR #69; they review the pre-alignment head `549e42a`.
3. Start Phase 1.1 on the merged/aligned architecture: replace unsafe local/test/staging
   composition-root semantics with exact `PAPER` / `ENABLE_REAL_TRADING=false` /
   non-live `EXCHANGE_MODE`, with a negative matrix across settings, API, worker, service
   and provider roots.
4. Keep every automation flag off. Do not call exchanges, send Telegram, or enable workers.

**Exact next Cursor prompt:**

```text
Phase 1.1 — permanent paper-mode invariant only.

Implement against merged PR #70 / exact architecture head d8f684f (or the merge commit
that contains it). Follow target §§21 and 29 slice 1 only.

Replace unsafe legacy Settings/service/provider/API/worker/test composition-root
semantics with:
  EXECUTION_MODE == PAPER
  ENABLE_REAL_TRADING == false
  EXCHANGE_MODE in {paper_internal, paper_exchange_demo}
  trade_live tombstoned
  execution-capable process + READ_ONLY == invalid

Do not implement slices 2–10 yet. Do not enable workers, watchers, Telegram, BloFin
demo submission, or live trading. Do not weaken deployment_safety / exchange_safety.
Add the negative matrix tests required by §31 BLOCKER-06.
```
