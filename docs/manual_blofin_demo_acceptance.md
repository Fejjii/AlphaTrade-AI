# Supervised manual BloFin demo acceptance

Implementation scope: one owner-confirmed BTCUSDT **market** entry on the allowlisted
BloFin demo venue. This is a **manual demo test**, not a detected strategy, Candidate,
research validation or strategy approval. No execution flag is enabled by this PR.
Simulated venue tests are protocol evidence; they do not prove live venue acceptance.

## Reviewed deployment and preflight gates

1. Review this PR and its focused tests. Consolidate the release, run the supervising
   final CI gate, then deploy **disarmed**. Migration head must be `a6manualdemo001`
   (parent `a5demolifecycle001`); preserve missing/multiple revision refusals.
2. A supervisor must explicitly authorize the acceptance window. Keep real trading
   disabled. Reuse the authenticated owner's existing enabled PAPER/NET execution
   account and stored demo credentials. Do not create/reset an account to bypass
   history, change leverage/margin/permissions, or approve a strategy for this test.
3. Only after review, configure the separate API capability
   `MANUAL_BLOFIN_DEMO_ENABLED=true` in **staging**, with existing
   `GOVERNED_BLOFIN_DEMO_ORGANIZATION_ID`, `...USER_ID`, `...ACCOUNT_ID` pinned to that
   owner/account. Required posture remains `EXECUTION_MODE=paper`,
   `ENABLE_REAL_TRADING=false`, `EXCHANGE_MODE=paper_exchange_demo`,
   `BLOFIN_DEMO_ENABLED=true`, complete existing credentials and
   `BLOFIN_DEMO_REST_BASE_URL=https://demo-trading-openapi.blofin.com`.
   The manual capability does not require or enable Watcher scheduling or the
   automatic governed demo arm. Ensure automatic demo dispatch cannot compete
   during the supervised window; preserve strategy definitions and approvals.
4. Preflight must verify read/trade permissions without withdrawal/transfer scope,
   NET position mode, **existing** cross margin/1x, the exact live linear BTC-USDT
   instrument, tick/lot/minimum/maximum contract size, USDT equity/available balance,
   and account-wide absence of positions and normal/TPSL pending orders. Ticker age
   must be under 10 seconds at receipt, never future dated. Unsupported/unreadable
   data refuses the entry. Instrument substitution is forbidden.
5. Review application history too: unresolved demo ALLOW commands hold this account;
   internal paper history does not consume that demo slot but its actual exposure,
   trade count and loss allocations still affect risk. Do not reset reservations,
   delete receipts or manually manufacture lifecycle resolution to open the gate.

## Exact owner preview and confirmation

Use **Settings → Account and system → Supervised manual BloFin demo test**.
Opening the form performs no venue request and cannot place an order. Enter side,
quantity in **venue contracts**, stop and target in USDT. There is no limit entry,
runner, multi-target or automatic sizing path in this capability.

Click **Preview demo entry**. Review instrument, side, market order type, contracts
and base BTC quantity, reference quote, entry range, exact stop/target, maximum
planned loss, gross R and expiry. Venue increments are validated; stop/target prices
are never moved to satisfy policy. Preview saves an immutable plan but issues no
authorization and submits no order.

Manual connectivity tests have an explicit hash-bound exception from strategy
qualification and minimum 1R; strategy execution retains **gross 1R**. Preview
shows allocation-weighted gross R using the worst price within the ±10bps entry
range. Manual tests are excluded from strategy performance statistics. Fee/slippage allowances are reserved in the
maximum planned loss (each 0.1% of conservative notional); this is not a net 1R or
maximum realized loss guarantee. Funding allowance is zero for this bounded entry
preview; actual funding is **unknown**, not recorded as zero. Per-trade planned
loss is capped at the lesser of the existing user limit and 1% of conservative
equity; existing risk engine/portfolio/daily/account reservation checks still apply.
Fresh dispatch balance also rechecks the 1% loss and 5% notional ceilings.

The preview expires in 60 seconds. Immediately before the POST, the provider must
receive a fresh quote within 10bps of the reference, unchanged instrument rules,
flat account evidence and sufficient balance; the final guard checks plan expiry,
kill switch, account safety epoch, dispatch owner and fencing token.

Only with the supervisor present, check **I confirm this exact manual demo test
plan** and click **Confirm and submit demo market order**. Confirmation binds the
exact revision/hash, creates the existing approval authorization and durable
command/reservation/effect, then sends one native entry POST with attached SL/TP.
Do not change settings or strategy authority as part of confirmation.

HTTP equivalents (authenticated owner; no tenant/user/account IDs accepted):

- `POST /execution/manual-demo/preview` with `symbol: "BTCUSDT"`, `side: "BUY"` or
  `"SELL"`, `order_type: "MARKET"`, and decimal strings `quantity`, `stop`, `target`.
- `POST /execution/manual-demo/confirm` with the returned `revision_id`,
  `content_hash`, `confirm: true`, `label: "manual demo test"`.
- `POST /execution/manual-demo/{command_id}/reconcile` to refresh native evidence.
- `POST /execution/manual-demo/{command_id}/cancel` with `confirm: true` to cancel
  only the unfilled normal entry remainder. Protective TPSL orders are not cancelled.

## Acceptance proof and uncertain responses

Success requires actual native order/fill IDs with instrument/side/NET/size identity,
fill quantities/prices/times and supported USDT fees, plus identity-linked live
stop/target protection at the confirmed trigger prices covering actual exposure.
An order acknowledgment alone is **not** successful fill/protection proof.

Verify in both the returned Stored evidence and BloFin demo UI:

- one durable command/client order ID and at most one entry POST;
- actual filled quantity and average price distinct from the planned quote;
- verified stop **and** target protection;
- Journal source `manual_demo_test`, label “Manual demo test”, the linked immutable
  plan and execution command, actual fill facts and fees;
- no strategy/Candidate/assessment lineage or learning attribution; strategy
  validation counts are unchanged. Manual demo exposure still counts for risk.

If an entry response is lost, recover **the same exact confirmation** or command.
The server never resends an existing command, including one interrupted before
send; absence from a venue lookup never authorizes a retry. Do not open another
account or submit a new preview to escape an uncertain command.

A partial fill records the actual portion, verifies its protection and explicitly
holds for operator review. Cancel the unfilled remainder if still pending; only a
subsequent identity-verified terminal venue read releases unused reservation. A
cancel acknowledgment is insufficient. Cancellation intent commits before its one
POST; uncertain cancellation is reconciled by reads and is never retried automatically.
Existing partial exposure, protective orders and daily risk history remain intact.

Missing/unreadable/mismatched protection or an actual fill outside the planned range
records the actual fills and activates the existing kill switch/operator hold.
Conflicting repeated fill fees cannot overwrite stored receipt fees. Inspect the
venue and persisted evidence; do not clear the hold merely to obtain a green status.

## Quote freshness diagnosis (preview only)

If preview refuses at `quote`, inspect `error.details.preflight` or the existing
`manual_demo_preflight_failed` log. Public timing evidence contains
`raw_timestamp_ms`, `timestamp_unit`, `parsed_timestamp_utc`,
`receipt_timestamp_utc`, `quote_age_seconds` and `freshness_status`.
Non-numeric/oversized input is omitted; malformed values cannot become fresh.
The UTC receipt clock is sampled after the demo order-book GET. The requirement
remains `0 <= age < 10` seconds; HTTP Date or receipt time never refreshes venue
evidence. Preview and confirmation use side-specific bid/ask depth in contracts.
Never confirm an order to diagnose preview.

The verified October 8 ticker age was 17.170055 seconds. Cloud access to the current
documentation site and live demo book was rejected with proxy CONNECT 403; live
latency, demo book availability and generation cadence remain unverified. See the
[current repair and exact read-only acceptance procedure](blofin_demo_quote_repair.md)
for official SDK references, timestamp semantics limitations and bounded demo-only
reads. No Binance or production evidence substitution or freshness relaxation.

## Explicit limits

- BTCUSDT market entry only; all other instruments and LIMIT requests are refused.
- One target allocating 100%, no runner; existing cross/NET/1x only.
- The preview slippage check cannot guarantee a market fill price or realized loss.
- Native fills require complete bounded history pages and supported nonnegative
  USDT fees; other fee currencies/rebates remain unsupported.
- No manual exit submission, exit/PnL/funding reconciliation or repeat-entry release
  is added. Journal remains OPEN after entry; a missing pending protective order
  does not prove a close. The account stays held for operator review, including
  after an unfilled cancellation. No reset, synthetic close or history deletion.
- Protection linkage must be proven against actual BloFin demo responses during
  supervised acceptance. Mock responses do not establish native API compatibility.
- This coding task performs no deployment, arming, strategy approval or exchange
  requests. Live acceptance and final release CI remain supervising gates.
