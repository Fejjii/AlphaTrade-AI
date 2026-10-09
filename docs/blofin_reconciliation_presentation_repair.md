# BloFin reconciliation and presentation repair

Based on main `642d2d4`. This batch repairs historical reconciliation and the
account/Journal presentation. It introduces no migration or exchange mutation.
The existing real-trading refusal, confirmations, global kill switch and unrelated
holds remain authoritative.

## Native evidence and closure

The previous `effective_protection_history_missing` failure required an effective
TP/SL record before requesting exit fills. That conflated protection attribution
with independently verifiable exits. The documented TP/SL history response does
not guarantee an entry parent `orderId` or a generated child order ID; its
`clientOrderId` can also be empty.

| Fact | Evidence and limits |
| --- | --- |
| Entry filled | Exact command/client/native order and immutable fill identities. Historical entry fills do not establish a currently open position. |
| Current exposure | Fresh whole-account positions, independently reported even when later history retrieval fails. Flatness alone does not establish this trade's closure. |
| Historically configured protection | Native market SL/TP configuration or a prior integrity-checked protection receipt. User screenshots are prior user evidence, not newly authenticated API verification. |
| Active protection | Current pending native protection. A verified closed trade reports protection as not required. |
| Triggered protection | Effective protection with direct native child/TP/SL identity linkage and corresponding actual fills. Matching trigger price or size alone is insufficient. |
| Verified closure | Terminal entry, complete isolated account-wide entry/reduce-only exit sequence, exact exit identities and total filled quantity, then a fresh flat, idle account. Missing protection ancestry remains a separate warning. |
| Realized outcome | Native exit `fillPnl` is gross trading PnL. Entry/exit fees remain separate. Funding and net PnL remain unknown without a native funding ledger. |

Native orders, TP/SL history and fills use documented ID cursors: `orderId`,
`tpslId` and `tradeId`, respectively. Pages contain at most 100 records; each
retrieval has a ten-page budget. Overlapping/malformed pages and budget exhaustion
remain unresolved. Orders history uses the recorded plan-to-observation time
window; TP/SL history uses its supported instrument filter. Native history
retention is three months, so older trades can remain unresolved.

Protection-read failures no longer discard verified exit facts. Conflicting
identities, incomplete exit quantities or unexplained account activity prevent
closure/recovery. Repeated refresh retains unique fills, fee facts, Journal
lineage and scoped accounting release. Historical missing protection or an old
outside-entry-zone fill does not activate a new global kill switch on a flat
account; positively observed open exposure still receives the safeguards. No
existing kill switch is automatically cleared.

BloFin fill `fee` uses positive cost and negative rebate. The native signed value
is retained; applying an absolute value would erase rebates. This was checked
against the [pinned native documentation](https://github.com/Anonymous-fe/blofin-api-docs/blob/167da57aec7751207d6b53248d002435a397b234/index.md)
and [CCXT's native fill parser](https://github.com/ccxt/ccxt/blob/master/python/ccxt/blofin.py).
Starting balance minus current balance is never a realized-return calculation.

## Account and exact record presentation

The default Dashboard presents the configured BloFin demo snapshot once, using
native equity in **USD**, available settlement balance in **USDT**, native open
positions and verified recorded performance. Internal simulator history is an
explicit account selection. Position quantity and currency conversion use the
same validated instrument metadata; unavailable metadata stays unknown.

Saved snapshots now carry their configured execution-account binding in existing
JSON provenance. Older/unbound snapshots have unavailable performance until a
fresh sync. Outcomes require exact owner/account/venue and native lifecycle proof;
editing a Journal outcome does not establish performance. Coverage is explicitly
partial: verified manual AlphaTrade lifecycles only, excluding outside venue
history and unsupported strategy outcomes. Manual connectivity tests count as
account activity and remain excluded from strategy performance. Credential
rotation/native-account mapping is not verified by a local fixture; operators
must validate that mapping before interpreting account history.

The existing visible-page 180-second polling, single-flight requests, hidden-tab
pause, capped retry delays, deadline and preserved stale timestamps remain in the
shared snapshot hook. Errors never replace native metrics with simulator values.

Both `?trade_id=` and `?trade=` resolve the exact canonical Journal trade detail.
The linked manual record supplies execution evidence; tenant/owner checks reject
foreign records. Personal reflections use the existing observation endpoint and
do not replace or modify execution facts. Agent and attempt detail retain one
concise explanation, a useful record action, and collapsed supporting evidence.
Small monetary values retain meaningful precision and zero never uses scientific
notation.

## Validation

Focused tests cover native pagination and linkage, triggered protection, manual
close, partial exits, missing/unavailable history, ambiguity, fee sign, repeated
refresh/recovery, existing holds, exact Journal/reflection authorization, account
scope, unavailable outcomes and concise Agent output. Desktop 1280px and mobile
390px Chromium fixtures cover account refresh/staleness, exact navigation,
reflection, Agent evidence and overflow.

Final counts and commands are recorded in the PR. Screenshots in
[screenshots/blofin-repair](screenshots/blofin-repair/README.md) are synthetic browser
fixtures, not an authenticated BloFin account. Google Fonts are blocked in this
executor; an explicitly opted-in existing font-response fixture permits local
build validation without claiming real font delivery. Ordinary required PR checks
are preserved. Only one final complete backend gate is run for this batch.

The complete gate also exposes baseline test drift: a historical fixture patches
a renamed execution risk function, preflight diagnostics expect HTTP status in
place of the native error code, and several migration checks still expect the
prior head. These fixtures are aligned with main's existing contracts while
preserving the policy, redaction, no-write, ancestry and data-preservation checks.
The cloud executor requires a writable `UV_CACHE_DIR` for script subprocesses.
Its complete-run result and subsequent focused corrections are reported
separately in the PR; a corrected focused run is not a clean complete gate.

## Authenticated acceptance after review and deployment

No BloFin execution/read-only credentials or owner session are bound in this
executor. No live native read, deployment, order or cancellation was performed.
The supplied entry screenshot and flat account report remain prior user evidence;
the actual exit and realized outcome remain unverified here.

1. Review/merge through required checks, verify the deployed API/frontend commit
   and the existing Alembic head `a7manualrecovery001`. This batch needs no new
   migration. Sign in as the same owner of the configured demo execution account.
2. Open `/execution/manual-demo/80958141-a548-4beb-8303-f525f14cf275`.
   Confirm native entry order `1000139786417`, BTCUSDT long, requested/fill quantity
   0.1 contracts = 0.0001 BTC, entry 82234.40 USDT and fee 0.00493406 USDT against
   authenticated native order/fill history. These expected values came from the
   user's prior screenshot; do not silently substitute another attempt.
3. Refresh **the same command twice**. Capture native exit order/trade IDs,
   quantities, timestamps, signed fees and `fillPnl`. Check protection ancestry
   separately. Closure requires the complete quantity/identity proof; flatness
   or a canceled TP/SL record cannot substitute. On incomplete history retain
   the unresolved claim and safe diagnostic.
4. Open `/journal?trade_id=912f2bfd-9061-4196-82bd-a17a0650c14e` from that attempt.
   Verify exact identity, venue, origin, fills, gross/fees and unknown funding/net.
   Attach a reflection and reload: execution evidence stays unchanged and no new
   Journal trade is created. Confirm another tenant cannot read/write this detail.
5. Compare Dashboard USD equity, USDT cash/available and native positions at the
   shown timestamp. Keep visible for 180 seconds, hide the tab, then return.
   Verify failure preserves the earlier successful timestamp. Confirm partial
   performance coverage and that manual tests are excluded from strategy metrics.
6. Ask the Agent from the exact attempt: verify one concise response, no claim
   that an old entry proves a current position, and exact supporting identities.
   If verified closure makes local recovery eligible, use the existing explicit
   confirmation for this command only. Check one resolution/release, no duplicate
   fills/fees/Journal record, and the existing kill switch/unrelated holds unchanged.

This checklist authorizes no new demo/real order, cancellation, deployment or
automatic safety-control reset.
