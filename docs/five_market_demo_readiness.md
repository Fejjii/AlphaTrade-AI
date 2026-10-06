# Five-market Nested demo readiness

This first-entry change can be reviewed and released independently of repeat-entry
and exit reconciliation. It does not arm execution, create strategies, approve
versions, mutate venue settings or place orders. Real trading remains disabled.

## Current-main assessment — October 6, 2026

Inspected main `e75e8bf411918094bd50eaf3d633d459efd40b40`, including merged PR212–215.
The first-entry sections below retain their original PR212 boundary. **PR214's
[verified lifecycle](governed_demo_lifecycle.md) supersedes the lifetime-ALLOW and
no-exit limitation for exactly proven supported closes.** Unresolved or ambiguous
commands still block; a mutable Journal close does not release the slot.
No new expansion implementation or activation was performed by this assessment.

| Area | Implemented source | Remaining gap / gate |
| --- | --- | --- |
| Five markets / subscriptions | Exact authored market matching in [Watcher targets](../backend/src/app/workers/watcher_paper_targets.py); owner-scoped [ten-subscription preview](../backend/src/app/strategy_brain/nested_preview.py). | Read current provider contracts and explicitly author/compile/approve exact long/short15m versions. Watchlist membership and preview do not grant approval. |
| Mapping / sizing | [Mapping](../backend/src/app/providers/exchange/mapping.py) produces BTC-USDT, ETH-USDT, ZEC-USDT, TAO-USDT, HYPE-USDT. [Demo provider](../backend/src/app/providers/exchange/governed_blofin.py) binds returned live linear USDT multiplier/tick/lot/minimum/maximum. | These are mappings, not proof the instruments are listed or reachable. Obtain dated Binance/BloFin read-only evidence; unavailable/unreachable stay distinct and never substitute. |
| Protected entry | Canonical authorization/reservation, receipt-time quote checks, final constraints/expiry/fencing and one entry POST with attached stop/target exist. | Prove actual venue parent/protection linkage and fill identities; an acknowledgment or simulated fill is insufficient. The governed generator uses one target; general multi-target/runner execution is not established. |
| Exit / repeat entry | [Native exit reader](../backend/src/app/providers/exchange/governed_blofin_exit.py), [audited resolution](../backend/src/app/services/demo_lifecycle_resolution.py) and [atomic history gate](../backend/src/app/services/demo_account_history.py) support proven closes and same-account reuse. | Prove native closing history, two flat/no-pending snapshots, exact parent linkage, one close/audit/release and another fresh eligible claim. Unfilled/uncertain or unexplained history remains an operator hold. |
| Risk / concurrency | Account safety epoch serializes competing claims; one unresolved demo exposure blocks across all markets. Internal-paper history does not consume the demo slot. | Internal-paper exposure/reservations and retained daily counts/loss allocations can still exhaust risk capacity. Reconcile legitimately; never reset accounts/history or broaden concurrency policy. |
| Journal / learning / Agent | Actual entry/exit fees and native fillPnl evidence, linked close/resolution and explanations exist. | Gross/net PnL, funding and win/loss semantics remain explicitly missing. CLOSED lifecycle can retain OPEN as the current unset result sentinel. Do not present that sentinel as an open position or a realized outcome. |
| Entry reward/risk | [PR216](https://github.com/Fejjii/AlphaTrade-AI/pull/216) adds a prospective allocation-weighted gross1R floor. | Review/integrate separately. A below1R approved setup must refuse entry; changing exit definitions requires an explicitly reviewed new version, never moved targets or silent approval. |

Configuration gaps are provider reachability/current instruments, correct existing
PAPER/NET account, explicitly approved exact subscriptions, acquisition budgets,
flat/no-pending account and scoped supervised demo activation. Remaining
implementation limits are bounded/exclusive history, unsupported outcome semantics,
held unfilled/ambiguous lifecycles and no general multi-position or runner executor.
No live provider calls, credential mutations or exchange orders were made here.

Use the later lifecycle's seven acceptance steps for the integrated release:
review → one consolidated exact-SHA full CI/evaluation/browser gate → disarmed
deployment/migration → five-market read-only preflight → explicit version approval →
supervised natural protected fill → native exit and same-account repeat proof.
Keep real trading disabled and SFP detection/notification only. The final activation
is supervising work, not implied permission for this coding task to send orders.

## Existing capabilities and configuration gaps

The tenant watchlist already supports BTCUSDT, ETHUSDT, ZECUSDT, TAOUSDT and HYPEUSDT.
The worker selects only the approved, compiled strategy version authored for each
exact market. Independent long and short strategy roots support ten Nested 15m
subscriptions. Each failed subscription rolls back separately; acquisition is
bounded and the existing cycle scope cap applies (default 20). SFP remains
detection/notification only, with its execution refusal unchanged.

Enabled watchlist slots, explicitly authored/compiled/approved versions for each
direction, provider access, demo instruments and the separately scoped execution
arm are configuration/acceptance requirements. This task has no ready venue
credential binding or venue-host access: live availability, precision and minima
are **unverified**, not declared unsupported or substituted with another market.
The existing Binance contract book does not establish current provider reachability.

## First-entry implementation

Both the early worker gate and the atomic account-epoch claim predicate inspect
immutable plan venue lineage. An internal-paper ALLOW no longer consumes the demo
entry slot. Its reservations, exposure, daily trade count and loss allocation still
participate in the existing deterministic account risk checks. No history is
deleted, reset or rewritten; insufficient risk capacity still refuses entry.

Every prior BLOFIN_DEMO ALLOW, including older policies, still blocks another demo
entry. The reason is reconciliation required, not an instruction to reset or create
an account. Safe lifecycle reuse belongs to the separately reviewed follow-up.
An existing Candidate plan for internal paper or another execution policy cannot
be reauthorized through the governed demo worker.

Before planning and again immediately before its one entry POST, the provider
requires account-wide zero positions and empty normal/TPSL pending-order lists.
Malformed rows, unreadable positions, nonfinite quantities and pages with 100 rows
refuse entry. Reads do not filter by the proposed instrument: an ETH order blocks
a BTC entry. Competing market claims remain serialized by the existing account
safety epoch, independently of the venue preflight. An uncertain entry never retries.

Exact instrument lookup verifies live linear USDT perpetual identity. Contract
multiplier, tick, lot, minimum and maximum come from that instrument's response;
constraints are bound into the plan and checked again before dispatch. Missing,
suspended, inverse or spot instruments are unavailable without substitution.
Quotes are checked against receipt-time injected clock; final plan expiry, risk,
attached stop/target, permissions, idempotency, fencing and kill switch remain in force.

## Bounded supervising acceptance

1. Review this PR and the independent Agent PR211. Keep demo disarmed and real
   trading disabled. After integration, run **one** CI workflow dispatch with
   `full_backend=true` at the exact release SHA; final evaluation and browser smoke
   must also pass. Focused development tests are not full backend acceptance.
2. Deploy through the supervising release process. Use the existing authenticated
   PAPER/NET account UUID; inspect preserved internal-paper reservations/exposure.
   Resolve actual outstanding exposure through its own governed lifecycle. Never
   clear accounting or create another account to evade a refusal.
3. Perform read-only instrument/evidence checks for all five exact markets. Record
   Binance source/finality/freshness and the BloFin demo host, exact `instId`, live
   status, linear units, contractValue, tickSize, lotSize, minSize and maxMarketSize.
   Report unreachable separately from unavailable. Check existing NET/cross/leverage
   1, read/trade-only permissions, USDT equity, flat positions and no pending orders.
4. Explicitly propose and review new Nested long/short 15m versions using the existing
   provisional baseline's exact relative parameters; compile and approve each exact
   version through the existing review endpoint. A baseline's approval does not approve
   copies. Enable only verified market slots. Keep total subscriptions within the
   configured scope/acquisition budgets; leave SFP without execution authority.
5. In supervised activation, pin organization, owner and the existing account UUID
   and arm only the existing governed demo capability. Wait for a fresh natural
   eligible Candidate. Verify its immutable plan, exact authorization, ALLOW claim,
   one dispatch, actual venue fill identities and linked live protection. Verify
   Journal fee/quantity, learning linkage and Agent attribution to BloFin demo.
6. Disarm after the first entry acceptance. This PR cannot reconcile actual exits or
   safely permit another demo ALLOW; no synthetic close is supported. If protection
   is missing/unavailable, preserve the kill-switch hold and supervise venue recovery.

Protocol reference: public BloFin API documentation mirror
`Anonymous-fe/blofin-api-docs/index.md` at commit
`167da57aec7751207d6b53248d002435a397b234`; pending-order GETs support limit 100.
Simulated protocol tests do not establish staging child-order linkage or live quality.
