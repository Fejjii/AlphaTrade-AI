# AlphaTrade Agentic Redesign — Final Safety, Data, and Execution Re-review

**Canonical target:** `main`

**Exact canonical head:** `549e42a42fb16765ec0947ef3ba08550459dd1f5`

**Source safety review:** PR #67 at
`a13c60c045e3454456a926ca726e77793ba269b2`,
`docs/redesign/final_safety_data_execution_review.md`

**Source architecture review:** PR #66 at
`4c4a66b9ca5276e7a7e7dd07c7715d8eecb70160`

**Scope:** adversarial architecture re-review only. No product implementation, migration,
deployment, worker/watcher activation, Telegram action, exchange API call, BloFin demo
execution, live trading, or review-PR merge was performed or authorized.

**Final verdict:** **APPROVED FOR PHASE 1 IMPLEMENTATION**

## 1. Review method and decision

The complete 2,419-line canonical target was read at the exact head. Each PR #67 finding was
then checked against the underlying normative contract, not against the target's resolution
matrix. Earlier diagrams and illustrative schemas were also checked for conflict. The target
explicitly makes §§21–30 the controlling correction layer when earlier text differs
(`agentic_redesign_target_architecture.md:1604-1608`).

“Resolved” below means the architecture now defines an implementable deterministic contract
and corresponding test obligation. It does not mean the current product implements that
contract. Phase 1 approval is limited to the ten safety-foundation slices in §§29–30, with all
automation and external execution disabled.

| PR #67 severity | Resolved | Partial | Unresolved |
|---|---:|---:|---:|
| BLOCKER | 6 / 6 | 0 | 0 |
| HIGH | 20 / 20 | 0 | 0 |
| MEDIUM | 7 / 7 | 0 | 0 |

No new blocker or high-severity architecture gap was found.

## 2. Previous blocker re-review

| Finding | Status | Independent canonical evidence and determination |
|---|---|---|
| BLOCKER-01 — account-bound approval authorization | RESOLVED | The immutable plan binds internal and applicable exchange-account IDs, operation, NET mode, permission attestation, both market identities, instrument mapping/rules and the complete order (`:1676-1722`). Authorization repeats account, operation, execution venue/instrument, mode and attestation identity (`:1724-1749`). Provider resolution is exact-account-only with no global fallback (`:2120-2137`). Account substitution is rejected before consumption or execution-domain mutation (`:1744-1749`). |
| BLOCKER-02 — stable semantic canonical execution hash | RESOLVED | `CanonicalExecutionPayloadV1` exhaustively identifies the semantic principal, operation, immutable plan/authorization, venue/instrument and order semantics (`:1769-1789`). Transport/retry fields are explicitly excluded and exact UTF-8 JSON, UUID, enum, Unicode, null, Decimal, array, set and map rules are defined (`:1790-1807`). |
| BLOCKER-03 — atomic first-writer/authorization/submit-effect protocol | RESOLVED | One PostgreSQL transaction insert-locks idempotency, binds payload, enforces the unique entry claim, consumes authorization by CAS, locks risk, reserves capacity, creates the stable receipt and creates one durable venue effect, then commits before network I/O (`:1836-1859`). Leased/fenced effect handling and query-first ambiguity recovery forbid blind semantic resubmit (`:1878-1912`). |
| BLOCKER-04 — serializable concurrent risk capacity | RESOLVED | The claim transaction serializes account risk and safety epoch (`:1836-1859`). `RiskReservation` charges pending/ambiguous exposure, open-order notional, daily trade slots/loss allocation, total and symbol exposure, and keeps capacity charged through uncertainty (`:1861-1875`). |
| BLOCKER-05 — one execution per plan revision/account | RESOLVED | Available approval issuance is database-unique for the complete account/revision/hash/operation identity (`:1739-1743`). A separate database uniqueness rule permits at most one entry claim for a plan revision/account, including different keys/channels (`:1757-1765`), and the claim is enforced in the first-writer transaction (`:1841-1848`). |
| BLOCKER-06 — globally permanent paper mode | RESOLVED | Phase 1 replaces, rather than freezes, unsafe legacy semantics. Settings, service, provider, API, worker, task runner and test roots require exact `PAPER`, false real-trading, non-live exchange mode and a rejected `trade_live` tombstone (`:1610-1634`). `READ_ONLY` cannot execute, production hosts/latent live switches are rejected, and models, Telegram, APIs and environment combinations cannot alter the invariant. |

Because all six blockers are resolved and none is partial or unresolved, the blocker gate does
not prevent Phase 1.

## 3. Complete approved order

`TradePlanRevision` is the sole executable-order source and its
`CanonicalTradePlanContentV1` hash covers all execution-affecting fields
(`:1674-1722`):

| Required binding | Canonical coverage |
|---|---|
| account | `organization_id`, `user_id`, non-null internal `account_id`, applicable `exchange_account_id`, expected NET mode and permission-attestation identity |
| venue | distinct evidence and execution venue/market identities |
| instrument | distinct typed evidence and execution instrument identities |
| side | `side` |
| quantity | `quantity`, quantity unit and execution-venue position size |
| order type | `order_type` |
| time in force | `time_in_force` |
| price/market semantics | typed limit price/unit or explicit null plus `MARKET` marker; entry zone and derivation |
| slippage | slippage policy and conservative allowance |
| reduce-only | `reduce_only` |
| contract multiplier | multiplier plus linear/inverse and currency identities |
| tick/lot rules | tick, lot, minimum quantity/notional and instrument-rule version |
| basis policy | both prices, formula, timestamp, freshness, tolerance and policy version |
| risk | budget, maximum loss, fees/funding/slippage allowance, R values and leverage/margin assumptions |
| stop/targets | typed stop, ordered targets and runner rules |
| validity | `valid_from` and `valid_until` |
| instrument mapping/version | execution mapping version and complete execution-instrument rule identity |

Any change creates a new immutable revision (`:1719-1722`). `ExecutionService` loads and locks
that revision, recomputes its hash and derives the venue payload only from it. The transport
command may carry redundant assertions for early error reporting, but cannot add or change
executable semantics; any mismatch fails before authorization consumption, reservation,
execution write, durable effect or network call (`:1744-1749`). The approved-order contract is
therefore complete.

## 4. PR #67 explicit closure table

The evidence column cites the corrected target, excluding §31's claimed resolution rows.

| Finding | Status | Independent evidence | Required deterministic proof at implementation |
|---|---|---|---|
| BLOCKER-01 — account-bound approval | RESOLVED | Complete plan/authorization/account and provider binding at `:1676-1765`, `:2120-2137` | Authorization for account A cannot act on account B; zero consumption, write, effect or call |
| BLOCKER-02 — semantic canonical hash | RESOLVED | Exhaustive payload and exact serializer at `:1769-1807` | Transport variants converge; each semantic mutation conflicts |
| BLOCKER-03 — atomic first writer | RESOLVED | Commit-before-I/O transaction and fenced recovery at `:1836-1912` | PostgreSQL 2/5-writer barriers and crashes at every claim/send/update boundary yield at most one venue order |
| BLOCKER-04 — concurrent risk | RESOLVED | Safety epoch, locked accounting and reservation at `:1836-1875` | Distinct commands competing for one limit permit one claim and block the other |
| BLOCKER-05 — one plan/one entry | RESOLVED | Unique authorization and entry claim at `:1739-1765`, `:1841-1848` | Concurrent tabs/channels/different keys produce one available grant, claim, receipt and effect |
| BLOCKER-06 — permanent paper | RESOLVED | Exact global invariant at `:1610-1634` | Local/test/staging/production settings/API/worker/service/provider matrix rejects non-paper, true real-trading and executing read-only |
| HIGH-01 — risk-BLOCK retry | RESOLVED | Block is an immutable terminal receipt; authorization remains available unless invalidated; later attempt needs a new explicit command/key and fresh checks (`:1828-1834`) | Replay old block unchanged; clear condition; one new explicit command consumes and executes once |
| HIGH-02 — consumer-time freshness | RESOLVED | Every assessment/candidate/plan/approval/execution recomputes immutable freshness with policy, clocks, evaluation time and expiry (`:1982-1986`) | Advance time with no new event; every downstream boundary fails closed |
| HIGH-03 — reconnect/CVD recovery | RESOLVED | Reconnect starts a new epoch, invalidates current CVD, dedupes bounded backfill, proves continuity and requires fresh warm-up; V1 forbids cross-epoch windows (`:1977-1981`) | Disconnect/overlap/reorder/duplicate/reset/gap fixtures replay identically and remain unusable until complete |
| HIGH-04 — worker storage fence | RESOLVED | Every worker write commits under the current monotonic lease-epoch predicate; renewal loss cancels work (`:2227-2235`) | Pause stale worker A, commit worker B, resume A; every A write/outbox insert fails |
| HIGH-05 — candidate semantic convergence | RESOLVED | `CanonicalEvidenceWindowV1`, exact source/policy/window rules, terminal non-resurrection and unique delivery intent are defined (`:2093-2110`) | Equal/enriched/corrected/adjacent/policy/venue/expired concurrent cases converge or separate exactly as specified |
| HIGH-06 — cross-venue units/identity | RESOLVED | Separate full evidence/execution identities, rule mapping, basis snapshot and execution-venue conversion are mandatory (`:1988-2000`) | Multiplier, lot, quote, inverse/linear and tick differences convert/round conservatively or block eligibility |
| HIGH-07 — partial-fill exposure | RESOLVED | Reservation-to-actual conversion and every-fill position/exposure update are atomic; cancel releases only authoritative remainder (`:1863-1870`, `:1923-1927`) | Zero/multiple/duplicate/late fills, partial cancel and partial close preserve unique net exposure after every event |
| HIGH-08 — fill identity/finality | RESOLVED | Bounded repeated absence proof, no single-negative inference, uncertainty quarantine and fill identity/source precedence are defined (`:1896-1912`, `:2138-2158`) | Missing/repeated IDs, overlapping pages, delayed visibility and timeout never duplicate accounting or release quarantine early |
| HIGH-09 — approved payload comparison | RESOLVED | Service hash-verifies and derives only from the plan; assertion mismatch fails before all downstream effects (`:1744-1749`) | Mutate every executable assertion independently; all fail before consumption/reservation/write/effect |
| HIGH-10 — deterministic candle finality | RESOLVED | OHLCV has exact interval/provider-complete semantics; `FINAL` requires provider completion and evaluation after interval end plus versioned grace; corrections append (`:1958-1963`) | Before close, at close, during grace, after grace and corrected-source cases allow only the qualifying appended final revision |
| HIGH-11 — trade/CVD identity and arithmetic | RESOLVED | Natural identity excludes adapter version; units, formulas, event ordering, half-open windows, event-set hash and revision selection are explicit (`:1963-1975`) | Adapter revisions, linear/inverse vectors, boundaries, duplicates and corrections count each natural trade once |
| HIGH-12 — TradingView ownership | RESOLVED | Public observations and tenant assertions have disjoint privacy, indexes, hash namespaces, caches and dedupe (`:1938-1949`) | Similar alert IDs/payloads for two tenants never cross ownership or dedupe |
| HIGH-13 — scan lineage/recovery | RESOLVED | Scan, source and subscription attempts are durable, fenced and linked to every output (`:2229-2235`) | Crash after each persistence boundary leaves honest recoverable lineage and no duplicate candidate/delivery |
| HIGH-14 — operation-specific risk | RESOLVED | Execution has only `ALLOW/BLOCK`; warnings cannot implicitly allow (`:1669-1672`). Entry/increase blocks, while authenticated exact cancel/reduce-only actions follow no-increase rules (`:1873-1876`, `:2175-2182`) | Kill switch/daily loss before/after submit, partial fill, cancel and close yields no exposure increase and exact operation outcomes |
| HIGH-15 — Telegram durable identities | RESOLVED | Webhook boundary is constrained at `:946-976`; bot installation, hashed enrollment, binding, bot-scoped receipts, nonce and durable action execution are specified at `:2184-2198` | Concurrent/replayed enrollment, wrong user/chat/bot, expiry, revoke, endpoint mismatch and bot rotation fail safely |
| HIGH-16 — durable serialized close | RESOLVED | Close binds account, position/version, exact side/quantity, NET/reduce-only, working-order hash, second confirmation and policies (`:1816-1819`); nonce/command/receipt/effect creation is atomic under account/instrument serialization (`:2200-2204`) | TP/late-fill race, duplicate callbacks, web/Telegram race and crashes create at most one exact current-exposure close |
| HIGH-17 — account credentials/fresh NET mode | RESOLVED | Exact `ExchangeAccount` secret resolution forbids global/singleton fallback; fingerprint/version, UID, demo host, attestation and immediate per-effect NET probe fail before POST (`:2120-2137`) | Cross-wired cache, credential rotation, UID mismatch and mode changes at each boundary never POST |
| HIGH-18 — receipt identity/state truth | RESOLVED | Stable receipt, immutable transitions and rebuildable monotonic projection/watermark are separated (`:1914-1927`) | Replays across acknowledgement, fills, cancel, close and correction retain identity and immutable history |
| HIGH-19 — journal venue truth | RESOLVED | Projector-owned fills, fees, funding, gross/net PnL, venue IDs and links cannot be edited/deleted; corrections are append-only and sourced (`:2206-2225`) | Post-fill edits/deletes cannot alter facts; corrections retain actor, reason, prior/new values, source and supersession |
| HIGH-20 — descendant action cascade | RESOLVED | Exact atomic matrix defines reject/skip/reduce-preview/revision behavior before and after command claim/submission (`:2160-2173`) | Full candidate/plan/grant/command state cross-product, including claim races, has no stale authorization or erased venue truth |
| MEDIUM-01 — entry/cancel/close commands | RESOLVED | Three discriminated commands bind exact resource/account/version semantics and use separate hash namespaces (`:1809-1824`) | Cross-operation key reuse conflicts; same command replays; changed resource/account/version rejects |
| MEDIUM-02 — Telegram/domain idempotency | RESOLVED | `ActionExecution` is persisted before delegation, its ID/hash enters every domain mutation, and recovery queries the linked result (`:2184-2204`) | Crash after each mutating domain commit returns the original result and performs one mutation |
| MEDIUM-03 — one canonical journal trade | RESOLVED | Trade aggregate is database-unique by organization/execution lifecycle and every projector transaction resolves it before append (`:2206-2225`) | Concurrent plan/fill/close/reconciliation events in all orders create one trade and one source effect |
| MEDIUM-04 — L2 is not CVD | RESOLVED | Order book is explicitly optional resting-liquidity evidence (`:1964-1966`); signed perpetual executions are mandatory and L2 cannot substitute (`:2112-2116`) | Changing only the book cannot change CVD; complete book with absent trades cannot confirm |
| MEDIUM-05 — canonical replay fixtures | RESOLVED | Raw bundles bind arrival order, clocks, reconnects, specs, versions, expected hashes, cursor/gap ledger, windows, reasons and candidate key (`:2257-2261`) | Empty/partial database, shuffled delivery, restart and adapter revision select identical semantic results |
| MEDIUM-06 — manual/worker persistence race | RESOLVED | One typed evaluation command has preview/evidence/notify modes; preview writes nothing and persistent modes share exact repositories/keys (`:2237-2241`) | Worker, manual preview and authorized manual persistence race; preview is write-free and persistent callers converge |
| MEDIUM-07 — journal source/draft boundary | RESOLVED | Candidate/reject/skip never create a trade; source identity includes system/account/event version/supersession (`:2206-2225`) | Same textual source ID across accounts plus correction/reject/skip cases append correctly and create no candidate-only trade |

## 5. Idempotency, first-writer and crash recovery

`CanonicalExecutionPayloadV1` excludes command, correlation, request, receipt, timestamps,
retry count, HTTP and trace metadata and hashes exact canonical bytes (`:1790-1807`). The
idempotency row's scope includes organization, account principal, operation namespace and
opaque key. Same semantic binding replays; any principal, operation or payload mismatch
conflicts (`:1841-1848`).

Two simultaneous first writers cannot both become submitters: the insert-or-lock and unique
plan execution claim are in the same transaction as authorization CAS, risk reservation,
receipt and one venue effect. That transaction commits before network I/O (`:1836-1859`).
The network worker uses a renewable lease, monotonic fence, persisted deterministic client
order ID and compare-and-set effect state. Ambiguous send or crash recovery queries by client
ID through the bounded finality window and does not issue a blind second semantic POST
(`:1878-1912`).

## 6. Concurrent risk and kill-switch semantics

The reservation accounts for daily-loss allocation, trade slots, account/total exposure,
symbol exposure, pending/ambiguous exposure and open-order notional. It remains charged during
`SUBMITTING`, `ACKNOWLEDGED`, `PARTIALLY_FILLED` and `RECONCILIATION_REQUIRED`; uncertainty
cannot release it (`:1861-1870`).

The command claim and kill-switch activation use the same account safety epoch and stable lock
order. Activation wins if its epoch commits before the command's final claim predicate; a
stale epoch blocks and rolls back the reservation/effect (`:1855-1859`). This defines a
database linearization point for the race. After exposure or uncertainty exists, the operation
matrix permits only authenticated exact-order cancellation or fresh reconciled no-increase
reduce-only recovery (`:2175-2182`).

## 7. Entry, cancel, close and execution state

Entry, cancel and close have distinct typed commands and semantic hash namespaces
(`:1809-1824`). Close binds the reconciled position ID/version, side, exact quantity/unit,
`reduce_only=true`, NET mode, working-order set/hash, current basis/freshness state and second
confirmation. Account/instrument serialization and fresh reconciliation make duplicate
Telegram/web close and concurrent fill/working-order races converge or reject
(`:1816-1819`, `:2200-2204`).

| Required state/truth | Deterministic contract |
|---|---|
| `SUBMITTING` | Stable receipt and effect exist after claim commit; reservation remains charged |
| `ACKNOWLEDGED` | Appended only from authoritative venue order identity |
| `PARTIALLY_FILLED` | Each unique fill immediately updates cumulative quantity, weighted price, fees, position and actual exposure |
| `CANCEL_PENDING` | Cancel is an independent exact-order command; late fills remain ingestible |
| `CANCELLED` | Authoritative terminal zero-fill cancellation; only unused reservation is released |
| `PARTIALLY_FILLED_CANCELLED` | Filled exposure remains an open position; only remainder is cancelled |
| `POSITION_OPEN` | Derived from unique net fills, including partial entry fills |
| `CLOSE_PENDING` | One serialized position/version-bound reduce-only close effect exists |
| `RECONCILIATION_REQUIRED` | Uncertain submit/cancel/fill/PnL remains visible and quarantined; no fabricated fill/finality |
| absence proof/recovery | `ABSENCE_PENDING -> ABSENCE_PROVEN -> RESUBMIT_AUTHORIZED`; repeated bounded client-ID proof is required |
| `OPERATOR_HOLD` | Unresolved conflict preserves account/instrument quarantine |
| `CLOSED` | Authoritative reduce-only fills and reconciled position/fees/funding/PnL support final closure |

The applicable evidence is `:1896-1927`, together with the entry/position/close lifecycle at
`:1013-1032` where it does not conflict with the controlling normative layer. Transmission or
an ambiguous timeout can never fabricate a fill.

## 8. Account, credential and position mode

There is no global credential fallback. Provider resolution starts from the exact authorized
`ExchangeAccount`, resolves only its secret reference and verifies credential version/
fingerprint, venue account UID, demo host and permission attestation (`:2120-2137`). A NET-mode
probe runs immediately before every entry or close POST and is bound to the effect attempt.
Wrong account, stale/rotated credentials, UID/host mismatch, stale/failed attestation, or
hedge/unknown mode blocks before POST and leaves durable state recoverable.

## 9. Market data, CVD and watcher

Public market identity is venue/product/instrument/provider-symbol specific. Typed payloads
define source/event identity, source/event/receive clocks, units, finality, sequence and
correction behavior (`:1938-1975`). Perpetual signed executions exclusively supply CVD; spot,
fallback, stale, wrong-market, unknown-aggressor, gapped or incomplete-warm-up input is
ineligible. Order-book data is optional resting-liquidity evidence and cannot substitute.

V1 reconnect starts a new connection epoch, proves a deduplicated contiguous backfill and
requires full new warm-up; cross-connection CVD windows are forbidden (`:1977-1981`).
Freshness is re-evaluated from event and receive clocks at every safety boundary, so an old
stored `FRESH` label cannot remain executable (`:1982-1986`). Final candles require provider
completion plus versioned post-close grace (`:1962`).

Watcher writes are protected by a database-enforced monotonic fence, and scan/source/
subscription attempts make crashes and health outcomes attributable (`:2227-2235`). Manual
preview is write-free; authorized manual and worker persistence use the same command,
policies, repositories and uniqueness (`:2237-2241`).

## 10. Telegram

The inbound boundary requires HTTPS secret-token validation, bounded body size, rate limits
and an update allowlist before action parsing (`:946-971`). Enrollment is a hashed, expiring,
one-time web-originated challenge bound to organization/user/bot and a private chat. Durable
bot-installation-scoped update/callback receipts, action nonce and `ActionExecution` bind the
tenant, user, chat, bot, exact resource revision, action hash and domain idempotency
(`:2184-2204`).

`REJECT` and `SKIP` cannot issue authorization. `REDUCE_RISK` preview is non-persistent;
confirmed revision creation revokes only the old available grant and requires separate
approval. `CLOSE` requires a second confirmation plus fresh serialized reconciliation
(`:2160-2182`, `:2200-2204`). Recovery looks up the authoritative domain result and cannot
repeat an unbound mutation.

## 11. Journal truth

Users may edit reflective notes but cannot overwrite or hard-delete projector-owned fills,
fees, funding, gross/net PnL, venue IDs, order/position IDs, reconciliation links or execution
outcomes. Corrections append actor, reason, prior/new value, source and supersession
(`:2206-2225`). One execution lifecycle maps through a database uniqueness constraint to one
canonical `JournalTrade`; candidate/reject/skip events never create a trade. Projection retries
use source-system/account/event-version identity and explicit leased retry/dead-letter states.

## 12. Cross-venue safety

Evidence and BloFin DEMO execution identities remain distinct on assessment, candidate, plan,
eligibility, authorization, command, receipt, reconciliation and journal. Each identity binds
venue, product type, provider symbol, currencies, linear/inverse type and timestamp; execution
also binds mapping, multiplier, quantity and tick/lot/minimum-rule versions
(`:1988-2000`).

`BasisSnapshot` binds both prices/units, formula, timestamp, freshness, tolerance and policy
version. Conversion uses only execution-venue rules, rounds quantity down and computes
conservative risk. Stale or failed basis blocks `ActionEligibility` without rewriting
`SetupAssessment`.

## 13. Adversarial failure matrix

| Failure | Required deterministic target state | Result |
|---|---|---|
| duplicate first writer | One idempotency binding, authorization consumption, entry claim, receipt, effect, client ID and at most one venue order | DEFINED |
| different-key same-plan race | Unique plan/account entry claim admits one; other conflicts without a second effect | DEFINED |
| different plans racing risk cap | Serializable account reservation admits only capacity-fitting claims | DEFINED |
| kill-switch race | Shared safety epoch/lock order gives a deterministic claim linearization; stale claim rolls back | DEFINED |
| crash before DB commit | Transaction rollback leaves no consumption, reservation, receipt, effect or call | DEFINED |
| crash after DB commit before send | Persisted single effect is recovered under lease/fence and uses one client ID | DEFINED |
| crash after effect claim / possible send | Treat as uncertain, query by client ID and finality window; never blind POST | DEFINED |
| ambiguous network send | `RECONCILIATION_REQUIRED`; reservation/quarantine remain; query before any recovery decision | DEFINED |
| venue accepted but response lost | Client-ID lookup appends acknowledgement/fill transition | DEFINED |
| partial fill | Unique fill immediately updates position, actual exposure and remaining reservation | DEFINED |
| late fill | Append and idempotently update the open position even after cancel request/result | DEFINED |
| cancel race | `CANCEL_RECONCILIATION_REQUIRED`; settle as zero-fill `CANCELLED` or `PARTIALLY_FILLED_CANCELLED` | DEFINED |
| duplicate close | Position/version/working-order binding plus account serialization yields one close or stale-state rejection | DEFINED |
| close plus concurrent fill | Fresh serialized re-reconciliation changes the bound projection or rejects the stale close | DEFINED |
| wrong account | Plan/authorization/provider binding rejects before consumption/reservation/effect/POST | DEFINED |
| stale credential | Version/fingerprint/attestation check rejects before POST | DEFINED |
| position-mode change | Immediate per-effect NET probe rejects hedge/unknown mode before POST | DEFINED |
| fallback market data | Display-only degraded fact; cannot confirm, plan, approve or execute | DEFINED |
| forming candle | Ineligible until an appended provider-complete post-grace final revision exists | DEFINED |
| trade-stream gap/reconnect | Current CVD invalid; new epoch/backfill/continuity/warm-up required | DEFINED |
| Telegram replay | Bot-scoped receipts, nonce CAS and domain-linked result return the original outcome | DEFINED |
| wrong nonce/user/chat/bot | Boundary rejects and audits; no domain mutation | DEFINED |
| journal projector retry | Source-version dedupe plus unique aggregate and leased retry applies one fact | DEFINED |
| reconciliation timeout | New exposure quarantined; uncertainty remains visible; no absence/final PnL inference | DEFINED |

No requested failure has an undefined unsafe state.

## 14. Remaining issues

None. There are no remaining PR #67 partial/unresolved findings and no new blocker or high.
Implementation must still satisfy every deterministic test in the closure and failure tables;
failure to implement those contracts would invalidate this architecture approval.

## 15. CI and scope gate

CI is evidence separate from architecture safety. At the review's initial exact-head query,
GitHub's push workflow for canonical commit
`549e42a42fb16765ec0947ef3ba08550459dd1f5` was still in progress. The following exact-head
checks/status had succeeded:

- deployment-safety;
- docker-build;
- frontend;
- Vercel.

The backend check was still in progress; evaluation and e2e-smoke had not yet appeared on the
canonical merge-commit run. PR #64's pre-merge head had green backend, deployment-safety,
frontend, docker-build, evaluation, e2e-smoke, Vercel and Vercel Preview Comments, but that is
not substituted for exact canonical-head CI. The final publication step must record the latest
canonical exact-head result without changing the safety verdict solely because documentation
CI is green.

The canonical change is documentation-only relative to prior `main`. This re-review adds only
this report. It changes no architecture, product code, migration, deployment configuration,
feature flag or runtime capability.

## 16. Final safety verdict

**APPROVED FOR PHASE 1 IMPLEMENTATION**

This authorizes only the dependency-ordered Phase 1 safety foundation in
`agentic_redesign_target_architecture.md:2267-2293`. It does not authorize Phase 2+, deployment,
feature activation, worker/watcher operation, Telegram delivery/action, BloFin connectivity or
demo execution, production-host access, real trading, or merging any review PR. All flags and
external execution remain disabled until their later architecture, deterministic-test and
separate deployment-review gates pass.
