# Verified BloFin demo exits and account reuse

This change builds on first-entry readiness PR212. Agent grounding PR211 and the
read-only ten-subscription Nested preview PR213 remain independent. No deployment,
activation, strategy approval, credential change or exchange order is performed
by this implementation task. Real trading stays disabled; SFP stays detection and
notification only. Broader simultaneous positions require a separate explicit policy.

## Current integrated release boundary

PR212–215 are merged in main `e75e8bf` as inspected October 6, 2026. The historical
review order below describes delivery dependencies; do not reimplement those changes.
Use the [current-main capability/gap assessment](five_market_demo_readiness.md#current-main-assessment--october-6-2026)
for remaining gates. PR216's planned gross1R minimum is a separate review change,
not a reason to modify stored targets or approve strategy versions automatically.
Existing full release CI and native venue acceptance remain unverified by this assessment.

## Implemented lifecycle

The existing worker reconciles unresolved demo commands without resubmitting entry
POSTs. A terminal entry with actual recorded fills can be resolved only when:

- The same account is flat and both normal and TPSL pending-order lists are empty,
  checked before and after the history reads without an instrument filter.
- Bounded native order history contains the exact authorized parent entry and only
  explained terminal reduce-only closing activity for its NET/cross instrument.
- Closing fills have actual trade/order identities, opposite side, positive
  quantities/prices, USDT fees and valid chronology. Their total equals the recorded
  entry fills, including a partially filled entry whose remainder was canceled.
- Triggered stop/target orders match the approved trigger price and exactly one
  effective parent TPSL record matches client identity, instrument, direction,
  mode and actual size. A trigger acknowledgment or flat balance is insufficient.

The public TPSL history contract has no child order ID. Linkage therefore requires
the unique effective parent plus exact native closing category/trigger/size/fills
and exclusive account history. Do not fabricate a child ID or accept ambiguous
history. Staging must prove the actual venue response supports this contract.

Under the account safety epoch, one transaction creates the canonical Journal CLOSE,
existing learning attribution, strict audit and immutable lifecycle resolution,
then releases only that command's actual exposure and unused reservation. Audit or
projection failure rolls back the close/release and activates the existing operator
hold; previously committed entry facts survive. Concurrent/restarted reconcilers
produce one close/release/audit, and late open snapshots cannot regress a verified close.
ORM guards and PostgreSQL triggers forbid changing/deleting resolution history.
Migration downgrade refuses preserved rows; use forward recovery.

The atomic claim gate ignores a previous demo ALLOW only with its scoped immutable
resolution. Changing mutable Journal status never releases the slot. Internal-paper
history does not consume the demo slot, but its existing risk accounting remains
charged. One new entry still needs a fresh eligible Candidate, a new exact plan and
authorization, current risk capacity, freshness, fencing, flat preflight and reservation.
The same account is reused; history, daily loss allocations and consumed trade counts
are retained. Risk limits, kill switch, uncertain POST holds and one-venue routing apply.

Actual entry/exit fees and weighted closing price/time are projected. Native
`fillPnl` is preserved in immutable closing evidence, without declaring it gross
or net PnL: the wire documentation does not define those semantics or funding.
Gross PnL, funding, net PnL and win/loss remain explicitly missing. The current
Journal result enum has no unknown value, so its existing OPEN result is retained
as the unset outcome sentinel; lifecycle status is CLOSED. No profit credits or
loss/trade budget replenishment is inferred. Agent command explanations cite the
resolution, close event and audit, show actual fills/fees and identify these gaps.
Natural latest-trade routing is delivered separately by PR211; review both after
integration. Mocked tests do not establish live conversational quality.

Existing Candidate notifications continue through the existing Telegram policy and
deduplication path. This PR adds no independent exit-alert sender or unreviewed
notification policy. No external notifications were sent from this coding task.

## Deliberate holds and bounds

- Unfilled/rejected/proven-unsent commands, uncertain entry POSTs, unexplained
  account activity, missing protection history or insufficient lineage remain held.
  This first lifecycle slice does not release an unfilled historical ALLOW.
- Each account page must contain fewer than 100 rows. Reconciliation admits at most
  20 history rows, ten closing orders and 100 total closing fills. Exhausted or
  incomplete history is an operator hold; no silent pagination or guessed close.
- Normal reduce-only closes and documented TP/SL closes are supported. Liquidations,
  hedge mode, other currencies, fee rebates and undocumented outcomes remain held.
  `ts` is persisted from the venue's fill data-generation timestamp; exact economic
  execution-time semantics remain a venue acceptance question.
- Existing accounting is conservatively retained, including sub-unit rounding
  remainder and existing daily allocations/counts. A reconciled lifecycle removes
  the lifetime gate, not existing risk limits or cumulative-budget constraints.
- Live Binance/BloFin market availability, protection linkage and outcome quality
  are unverified here. Unreachable, unsupported and malformed data must be reported;
  never substitute another instrument or reset/create an account to evade a refusal.

## Bounded supervising activation and acceptance

1. Review PR211, PR212, PR213 and this stacked lifecycle PR. Integrate under review,
   then run **one** `full_backend=true` workflow dispatch at the exact release SHA.
   Complete backend acceptance, final evaluation and browser smoke must pass.
   Focused development results are not complete backend or live acceptance.
2. Deploy with demo disarmed and real trading disabled. Apply the lifecycle migration
   through the normal release process. Inspect the existing authenticated PAPER/NET
   account UUID and preserved reservations/exposure; no live repair is run here.
3. Follow the read-only five-market preflight in `five_market_demo_readiness.md`.
   Record exact Binance closed-candle source/freshness and demo instrument status,
   mapping, multiplier, tick, lot and minimum/maximum for BTCUSDT, ETHUSDT, ZECUSDT,
   TAOUSDT and HYPEUSDT. Disable unavailable slots without substitution. Confirm
   NET/cross/leverage 1, permissions, equity and account-wide flat/no-pending state.
4. Use PR213's authenticated read-only preview with the actual stored provisional
   Nested baseline. Review, explicitly create/reuse, compile and approve each exact
   long/short 15m version; proposal or source approval grants no copy authority.
   Enable only verified subscriptions within the existing acquisition/scope budgets.
5. Under supervision, pin the existing owner/tenant/account and activate only the
   governed demo arm. Wait for a fresh natural eligible Nested setup. Prove one
   immutable authorization/ALLOW and one entry dispatch; inspect actual native fill
   identities and matching attached protective stop/target. Inspect Journal, learning,
   Agent references and existing Telegram policy/deduplication. Disarm on uncertainty.
6. Observe a natural or separately supervised protective exit. Verify real closing
   order/fills/fees, parent protection linkage, flat account and no pending orders,
   immutable resolution/audit/CLOSE and only owned exposure release. Unsupported
   PnL/funding/result fields must remain missing. Do not treat an acknowledgment as exit.
7. With unchanged account history, verify a genuinely new eligible setup can claim
   once after resolution and existing risk checks; competing market signals must
   admit only one. Disarm after acceptance. For unresolved states preserve holds,
   gather bounded native evidence and use supervised forward correction, never a
   synthetic receipt, uncertain POST retry, account reset or history deletion.

Protocol reference: `Anonymous-fe/blofin-api-docs/index.md` at commit
`167da57aec7751207d6b53248d002435a397b234` (public API documentation mirror).
