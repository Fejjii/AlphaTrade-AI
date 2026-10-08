# BloFin demo executable quote repair

## Evidence and limits

The supplied live preview failed at quote acquisition on 8 October 2026 at
10:01:24 UTC: venue ticker `ts` was 10:01:07.097 UTC, age 17.170055 seconds.
Account checks passed and no order was submitted. PR226 (`d8ef205`) correctly
exposed the age and retained the strict **0 <= age < 10 seconds** rule.
The old path used ticker `last`, which is a last traded price rather than proof
of an executable buy/sell price or sufficient liquidity.

This task could not measure live BloFin request latency, inspect a live demo
book or exercise an authenticated deployed preview. Both attempted HTTPS reads
below were rejected by the environment's proxy with **CONNECT 403**, before a
BloFin response:

- `https://docs.blofin.com/index.html`
- `https://demo-trading-openapi.blofin.com/api/v1/market/books?instId=BTC-USDT&size=50`

No demo secrets were configured in the cloud environment. No production price,
Binance price, synthetic price, receipt timestamp or increased freshness limit
substitutes for missing demo evidence. Live quote reliability remains **pending**.

## Documentation and timestamp semantics

Official BloFin GitHub API documentation inspected:

- [Official SDK MarketAPI](https://github.com/blofin/blofin-sdk-python/blob/df75d514292d90fd6ad67eb12a9f0ca6db738a73/src/blofin/rest_market.py):
  `last` is latest trade price; `getOrderBook` reads `/api/v1/market/books`, with
  asks/bids `[price, size]` and venue `ts`. `contractValue` is in base currency;
  `minSize` is contracts and `lotSize` is the contract increment.
- [Official SDK demo environment](https://github.com/blofin/blofin-sdk-python/blob/df75d514292d90fd6ad67eb12a9f0ca6db738a73/README.md):
  demo REST and public WebSocket use `demo-trading-openapi.blofin.com`.
- [Official MCP public endpoint reference](https://github.com/blofin/blofin-mcp/blob/25d296062075329b743630cb9a969dfe09dd3a27/src/tools/public.ts):
  depth size is at most 100 (the SDK docstring says 400; this repair uses 100,
  which is supported by both references).

The current documentation website could not be read. The accessible SDK calls
`ts` a timestamp without specifying the generation trigger. An older documentation
source ([index.md](https://github.com/Anonymous-fe/blofin-api-docs/blob/main/index.md),
sections GET tickers / GET order book) describes milliseconds, ticker **data
generation time**, book **generation time**, and depth sizes in **contracts**.
Its current official ownership was not verified, so it is corroboration rather
than a claim about current live behavior. Do not interpret the supplied ticker
age as proof of time since last trade, venue caching or request latency. Verify
current official semantics and live generation cadence at acceptance.

## Implementation

Preview and confirmation use the same demo-only REST book path, after existing
account/rule checks. A buy references the best ask and consumes asks; a sell
references the best bid and consumes bids. No ticker fallback is attempted.
The requested instrument is bound through the REST request; a conflicting
response instrument is rejected when present. Venue timestamp parsing remains
strict Unix milliseconds, including malformed, stale and future refusal.

Both sides must contain bounded, positive, finite, ordered, unique levels with
exact price ticks and contract lot increments. Crossed/locked books and spreads
above the existing 10 bps demo allowance are refused. The requested contract
quantity must meet min/max/lot rules, and the accumulated side depth must cover
it within 10 bps of the executable top price. This is executable snapshot
availability, not a promise about a later market fill. Base quantity remains
`contracts * contractValue`; no base/contract interchange is permitted.

The manual preview keeps the conservative 10 bps entry zone and existing
fee/slippage/risk calculation. Governed sizing checks the final sized contract
quantity against the captured book. Its authorized entry zone spans the best
and worst consumed prices, and gross R uses the adverse edge. Depth that breaks
1R, geometry, the 1% loss ceiling or 10% strategy notional ceiling is refused. Confirmation reacquires
account/rules/book and validates the full quantity. Both best and worst consumed
prices must fit both the authorized entry zone and slippage bound. A strategy
plan whose depth all executes at one price has a point entry zone: price drift
outside it requires a new plan, even when drift is within 10bps. This preserves
the strategy 1R floor rather than promising it at an unapproved worse price. Existing cross-venue governed
basis checks remain; Binance never substitutes for demo execution evidence.

The final quote/plan deadline is checked before the safety callback and again
at native transport send, after throttle. No order retry was added. Existing
GET-only transport retries remain bounded (default two retries / three attempts);
stale or malformed successful responses receive no automatic data-refresh loop.
Request duration is measured with a monotonic clock across the book read and its
bounded retries. Safe timing diagnostics retain venue/receipt timestamps, age,
source and duration, without price/account payloads or credentials.

Preview errors now give fixed actionable guidance, together with existing
`error.details.preflight` stage, endpoint, reason and safe venue/HTTP codes.
Strategy minimum 1R, exact hash-bound plan confirmation, owner/account pins, duplicate
prevention, risk reservations/limits, final kill/fence checks and attached stop/
target verification remain authoritative. Uncertain confirmation remains held
for reconciliation rather than becoming a retry shortcut. Real trading stays
disabled; credentials, account settings and activation flags were not changed.

## Explicit manual connectivity policy

The owner authorized a manual demo connectivity test without strategy qualification
or minimum 1R. New manual plans carry the immutable calculation marker
`manual_connectivity_rr` with formula `manual-demo-connectivity-no-minimum-rr/v1`.
The shared approval, claim and dispatch checks recognize it only on a fully
validated `ManualDemoTradePlanV1` / `manual-blofin-demo/v1` plan. Demo-only venue,
market-only entry, no strategy/Candidate lineage, valid stop/target geometry, full
allocation and all other safety checks remain mandatory. Missing, incorrect or
duplicate markers do not grant an exception; legacy manual plans retain 1R.
Canonical strategy construction and execution still enforce the original 1R floor.

Manual preview displays calculated gross R and the exception. Risk refusals
include a fixed blocking identifier and calculated R when geometry was valid;
invalid venue evidence returns its precise safe stage/reason without inventing R.
Preview now enforces the same 5% demo-equity notional bound as confirmation.
Manual journal records remain `MANUAL_DEMO_TEST`, carry no strategy/learning
attribution and are explicitly excluded from strategy analytics even if later
closed or requested by source filter. They still count in daily risk accounting.

## Focused verification

Provider and transport IO in all tests is mocked. Persistence tests use a
new disposable loopback PostgreSQL 16 database, not staging or a shared account.
No actual exchange orders are sent by tests.

From `backend/` (set `AT028_POSTGRES_URL` to the disposable database only):

```sh
uv run pytest tests/test_demo_order_book.py tests/test_demo_quote_timing.py tests/test_demo_preflight_diagnostics.py tests/test_governed_blofin_quote_freshness.py tests/test_blofin_provider.py tests/test_blofin_execution.py tests/test_planned_reward_risk.py tests/test_strategy_analytics_foundation.py -q -o addopts=''
uv run pytest tests/test_manual_blofin_demo.py tests/test_governed_blofin_demo.py tests/test_governed_demo_lifecycle.py tests/test_governed_demo_readiness.py -q -o addopts=''
uv run pytest tests/test_manual_demo_migration.py tests/test_planned_reward_risk_postgres.py -q -o addopts=''
uv run pytest tests/test_config.py tests/test_deployment_safety.py tests/test_backend_ci_scope.py tests/test_deployment_scripts.py tests/test_watcher_paper_activation.py -q -o addopts=''
```

Final quote/policy/analytics verification: **255 passed**. Safety/configuration
verification: **116 passed**. Frontend voice and manual preview verification:
**56 passed** (49 voice, 7 manual UI). Scoped Ruff/format, mypy (13 source files),
ESLint and frontend TypeScript checks passed. PostgreSQL manual/governed
lifecycle verification: **100 passed**. Persisted policy/migration verification:
**3 passed**. Full backend CI was not dispatched; the unchanged PR workflow uses focused backend selection and retains
mandatory safety/lint/frontend/evaluation/build/smoke checks.

## Remaining live acceptance — read-only / preview only

After PR review and a separately authorized deployment:

1. Verify the deployed commit and existing paper/real-trading-disabled posture.
   Do not change credentials, account position mode, leverage, account pins or
   activation flags as part of these checks. Read the current official sections
   at `https://docs.blofin.com/index.html` for ticker/book `ts` and depth units.
2. From a network permitted to read the demo host, sample instruments, ticker
   and book **three times**. Public reads require no credentials. Example commands:

   ```sh
   curl --fail --silent --show-error --max-time 10 -w '\nrequest_seconds=%{time_total}\n' 'https://demo-trading-openapi.blofin.com/api/v1/market/instruments?instId=BTC-USDT'
   curl --fail --silent --show-error --max-time 10 -w '\nrequest_seconds=%{time_total}\n' 'https://demo-trading-openapi.blofin.com/api/v1/market/tickers?instId=BTC-USDT'
   curl --fail --silent --show-error --max-time 10 -w '\nrequest_seconds=%{time_total}\n' 'https://demo-trading-openapi.blofin.com/api/v1/market/books?instId=BTC-USDT&size=100'
   ```

   Record UTC before/after each request, venue `ts` in UTC, exact age at receipt,
   duration, bid/ask spread and side depth in contracts. Confirm the documented
   contract multiplier/lot/tick/min/max. Compare ticker and book generation
   cadence; receipt time may measure latency but may never replace venue time.
   If demo books are unavailable/stale, record that failure and keep preview
   refused. Do not switch hosts or loosen freshness.
3. In the existing authenticated owner's manual demo UI, choose BTC-USDT,
   BUY or SELL, exact venue contract quantity, stop and target. Use **Preview**
   only. Equivalent API is `POST /execution/manual-demo/preview` with JSON:
   `{"symbol":"BTCUSDT","side":"BUY","quantity":"<contracts>","stop":"<tick-aligned-stop>","target":"<tick-aligned-target>"}`.
   Select valid stop/target beyond the conservative executable entry zone.
   Manual connectivity preview may show gross R below 1: this explicit exception
   applies only to manual demo tests. Strategy execution still requires 1R.
   Keep within existing risk/notional limits; a risk refusal is expected
   when limits are exceeded. Repeat a SELL preview with its own prices.
4. Verify `reference_price` uses ask for BUY / bid for SELL, `quantity_unit` is
   CONTRACTS, and `base_quantity` is exactly quantity times contract value.
   Check the safe `blofin_demo_quote_timing` log for source
   `blofin_demo_rest_order_book`, book endpoint, venue/receipt UTC, duration and
   age below 10s. Do not collect private account logs or secrets.
5. For any failure, record the fixed UI message and safe
   `error.details.preflight` reason/stage/endpoint/timing. A malformed timestamp,
   stale/future quote, wide/crossed book, unavailable/insufficient depth or invalid
   quantity must refuse preview. Do not manufacture invalid exchange data in a
   deployed environment; the focused mocks cover these injected cases.
6. **Do not click Confirm, call `/execution/manual-demo/confirm`, submit orders,
   cancel exchange orders or enable worker execution.** Validate confirmation's
   fresh-read/refusal behavior using the focused mocked tests. Any live order
   acceptance is outside this task and requires separate explicit authorization.

Record observed results before declaring either live blocker resolved. For Chrome
and Safari, follow [the separate device procedure](chrome_voice_diagnostics.md).
