# Presentation repairs — 7 October 2026

Status: REVIEW_REQUIRED. Base: main `e4a781679ccda9258c28d5330671d3aaa54376d8`.
Branch: `codex/presentation-preflight-dashboard`. Task: AT-115.

Implementation and focused local verification are complete. Deployment and live
acceptance are pending. The reported BloFin failure's underlying venue cause is
**unknown**; this delivery makes the next failed preview diagnosable. No exchange
orders, deployments, account-setting changes or full backend runs were performed.
PR220–224 are already merged in this base and were not duplicated. The checkout
was clean; prior operational handoffs were preserved under ignored `.ai/local/`.

## BloFin: evidence and complete preflight path

The owner reports that `POST /execution/manual-demo/preview` returned 403 at
`2026-10-07T16:11:33Z`: “Demo preflight unavailable; preview cannot be saved.”
The owner also reports startup with `paper_exchange_demo`, BloFin demo enabled
and configured, allowlisted demo endpoints, both real-trading flags false, and a
previous successful account sync. These are supplied runtime facts, not a new
live test by this agent. They do not establish which later preflight read failed.
No missing-credential diagnosis or credential recreation is justified.

The authenticated preview route resolves the owner/tenant, validates the manual
capability and exact existing account pins, commits the completed scope read,
then constructs the gated BloFin client and calls `GovernedBloFinDemoProvider`.
The transport asserts the demo host, signs private GETs with the query path,
applies existing throttling and bounded GET retries, and parses the venue envelope.
The following stages preserve that read order and all existing safety predicates:

| Stage | Endpoint | Required evidence |
| --- | --- | --- |
| `provider_initialization` | No venue request yet | Existing execution credential/host gate and client construction |
| `permissions` | GET `/api/v1/user/query-apikey` | Read/trade; no withdrawal or transfer scope |
| `position_mode` | GET `/api/v1/account/position-mode` | Existing NET account mode |
| `instrument` | GET `/api/v1/market/instruments` | Exact live BTC-USDT, linear USDT perpetual; finite positive tick/lot/minimum/multiplier/maximum |
| `leverage` | GET `/api/v1/account/leverage-info` | Existing cross-margin leverage 1; no mutation |
| `positions` | GET `/api/v1/account/positions` | Complete bounded account-wide read and zero positions |
| `pending_orders` | GET `/api/v1/trade/orders-pending` | Complete bounded account-wide read and no pending orders |
| `pending_protection` | GET `/api/v1/trade/orders-tpsl-pending` | Complete bounded account-wide read and no pending TPSL |
| `balance` | GET `/api/v1/account/balance` | Positive available/total USDT balance |
| `quote` | GET `/api/v1/market/tickers` | Exact instrument, positive price, receipt-time age in `[0,10)` seconds |

The former blanket catch discarded all cause information. It now emits
`manual_demo_preflight_failed` with tenant/user/account identity and safe structured
fields, and returns the same 403 policy refusal with `error.details.preflight`.
That object contains stage, fixed reason/type, a fixed endpoint label, and bounded
numeric HTTP/venue codes when available. `snapshot` is the explicit fallback for
an unexpected failure outside a named stage. No arbitrary exception message,
traceback, credential, signature, query, request header, or private response body
is copied into these diagnostics. The transport's retry-failure log also omits
arbitrary error text. Existing HTTP-error code normalization is retained; for an
HTTP rejection the numeric code may represent the HTTP status, while a parsed
venue rejection on HTTP 200 carries the actual numeric venue code.

Example **simulated**, not an observed live cause:

```json
{"preflight":{"stage":"leverage","reason_code":"venue_request_rejected","error_type":"ExchangeRequestError","endpoint_name":"GET /api/v1/account/leverage-info","http_status":200,"venue_error_code":"51000"}}
```

The earlier capability error is not reworked. No response-shape fallback, policy
bypass or speculative account/credential repair was added. Live Render logs were
unavailable because the connector requires a user-confirmed workspace selection;
the optional selection question remained unanswered during AFK work. The cloud
environment has no BloFin credential bindings or permitted BloFin destination.
Package/GitHub and local test access succeeded through the supported network path.

## Dashboard: defect and legitimate scope differences

The original Dashboard loader queried `/positions?status=open` and
`/journal/entries`, backed by `Position` and `TradeJournal`. Attention queries
canonical open `JournalTrade` paper records. The Agent's recorded-trade reader
also queries canonical `JournalTrade`, with additional account ownership and
explicit/contextual symbol, direction, account and selected-trade filters.

This is a demonstrated projection defect, not evidence of a tenant mismatch:
on unchanged main, a local fixture with one canonical open paper trade and no
legacy Position/PaperTrade rows reports **0**; the repaired reader reports **1**
against the same fixture. No historical execution row was rewritten.

| Surface | Final source | Scope |
| --- | --- | --- |
| Dashboard open positions/count | Canonical `JournalTrade`, identical source/status filters to Attention | Authenticated organization **and user**; `paper_execution`/`paper_validation`; OPEN; all accounts, recorded venues and dates |
| Attention paper-position items | Canonical `JournalTrade` | Same paper cohort; separate request/snapshot time and bounded UI display |
| Dashboard recent trades | Existing `/journal/trades` | Authenticated organization/user; all sources, statuses, accounts and dates; newest creation records; recorded net PnL |
| Agent recorded trade | Canonical `JournalTrade` plus owned-account proof and recorded lineage | May narrow to the user's selected account, trade, symbol/direction or paper execution; ambiguous multiple accounts require selection |
| Portfolio value/closed metrics | Existing `Position`/`PaperTrade` performance projection | Proposal/validation history; unchanged and explicitly labeled |
| Daily discipline | Existing daily-risk, Position/PaperTrade and journal-note projections | User timezone/day window; today is distinct from all-time open positions; unchanged and labeled |

The Dashboard uses the repaired summary for both open count and details. Counts
cover every matching row, independent of the ten-row API/eight-row UI limit.
Items expose canonical trade, linked legacy, account and recorded venue IDs.
`paper_execution_count` names the execution cohort; `proposal_flow_count` remains
a compatibility alias. Recent/open trade links select `/journal?trade_id=…`.
Missing canonical data remains unavailable; there is no legacy fallback after an
error. Unrealized PnL and current exposure remain null rather than inventing a
zero or summing absolute unrealized PnL as exposure.

Manual demo tests are deliberately outside the Attention/open-paper count; recent
Journal records include them. This difference, all-account/all-date scope and the
older portfolio metrics scope are labeled. Independent requests can briefly show
different snapshots during a state transition; compare IDs after refreshing.

## Focused local verification

**232 distinct backend cases passed** across the following groups:

- 139: new diagnostics (41), manual demo protocol (31), governed demo (20), demo
  readiness (35), and quote freshness (12). Disposable PostgreSQL 17.11, UTF8,
  `alphatrade_test` on loopback port 55432; all venue traffic is MockTransport.
  JUnit confirms 139 tests, zero failures/errors/skips. Covers exact confirmation,
  minimum 1R, risk/kill switches, tenant isolation, idempotency and protection.
- 41: Dashboard (19) and Attention (22), including authenticated API comparison
  across accounts/venues/older dates, excluded sources/statuses/foreign users,
  complete count with truncated details, and SELECT-only/no-autoflush reads.
- 52: existing BloFin provider regressions. A final focused run also rechecked the
  two new Dashboard regressions after the typed aggregation adjustment; those
  repeated cases are not counted twice.

**80 frontend cases passed**: 32 Dashboard/Daily Review/source-loader cases across
five files, and 48 adjacent Portfolio cases across two files. The loader test
exercises the actual hook and proves canonical endpoints, no legacy reads,
canonical links, Open status, and explicit unavailable PnL. ESLint with zero
warnings, frontend typecheck, scoped Ruff/format, six changed production modules'
strict mypy, and whitespace checks passed. React review preserved concurrent
loads, existing layout, accessible links and truthful failure states.

Reproduce the principal focused groups:

```bash
cd backend
PHASE1_POSTGRES_URL=postgresql+psycopg://alphatrade@127.0.0.1:55432/alphatrade_test \
  uv run pytest tests/test_demo_preflight_diagnostics.py tests/test_manual_blofin_demo.py \
  tests/test_governed_blofin_demo.py tests/test_governed_demo_readiness.py \
  tests/test_governed_blofin_quote_freshness.py -q -ra
uv run pytest tests/test_dashboard_slice_44.py tests/test_attention_queue.py -q
uv run pytest tests/test_blofin_provider.py -q
cd ../frontend
npx vitest run 'src/app/(app)/page.test.tsx' 'src/app/(app)/page.fallback.test.tsx' \
  'src/app/(app)/page.sources.test.tsx' src/components/dashboard/trader-dashboard.test.ts \
  src/components/dashboard/DailyReviewCard.test.tsx
npx vitest run src/components/portfolio/buildOpenPositionRows.test.ts \
  'src/app/(app)/portfolio/page.test.tsx'
npm run typecheck
```

Initial local attempts encountered sandbox socket restrictions and a SQL_ASCII
test-database initialization; the disposable test database was recreated as UTF8.
New diagnostic tests initially omitted the required side and expected an envelope
code on an HTTP rejection; those fixtures were corrected without changing the
transport contract. Final affected groups pass. No full backend suite, local
frontend build, browser/live UI check or successful live preflight is claimed.
Machine-readable results: [verification record](presentation_repairs_20261007_verification.json).

## Review, single release gate and exact deployment acceptance

1. Review the consolidated PR and exact diff. Preserve all required GitHub checks.
   Automatic PR CI uses the existing focused backend selector; it also runs broader
   frontend/deployment-safety/evaluation jobs. Those are automatic CI, separate
   from the local focused evidence. Do not cancel, bypass or skip them.
2. Pin the reviewed head, then dispatch **one** complete backend release gate:
   `gh workflow run ci.yml --ref codex/presentation-preflight-dashboard -f full_backend=true`.
   Verify the run's `head_sha` equals that reviewed commit and require a passing
   “Complete backend release acceptance” job. If the head changes, that earlier
   result does not attest the new release. This agent did not dispatch this gate.
3. Deploy that reviewed/tested revision to the API and frontend through the existing
   release process, initially disarmed. This PR adds no migration: the single
   migration head remains `a6manualdemo001`. Preserve account pins, credentials,
   account history, risk reservations and every execution flag. Keep both real
   trading flags false; do not arm an automatic demo worker.
4. With the authenticated owner and a supervisor present, use the already-authorized
   manual-demo capability window to repeat the **original preview request only**.
   Reuse the existing account and credentials; do not change leverage, NET/cross
   mode or permissions to force acceptance. Record UTC time, request ID, status and
   only `error.details.preflight` on failure. Correlate the
   `manual_demo_preflight_failed` log by request/tenant/account and stage.
5. If 403 persists, the returned stage identifies the next investigation. An auth
   rejection is evidence to inspect that endpoint's authorization, not an automatic
   mandate to recreate keys. A parsed-data refusal calls for controlled comparison
   with the documented response shape. Stale quotes, non-flat accounts, pending
   orders and policy violations remain refusals. Capture the safe fields and hand
   off the concrete cause; never mark live acceptance successful from local tests.
6. If preview returns 200, record the exact revision/hash, immutable plan and expiry,
   and verify native entry-order count is unchanged. **Do not confirm or submit an
   order under this task.** The separately supervised order/protection acceptance
   procedure in [manual demo acceptance](manual_blofin_demo_acceptance.md) requires
   its own authorization; preview success alone proves no fill or protection.
7. Refresh Dashboard as the same owner. Compare its total with all canonical
   `/journal/trades?status=open&source=paper_execution` and
   `...source=paper_validation` totals and Attention's `paper_position` IDs, paging
   when needed. The recent panel should show the Agent's recorded open internal
   trade when it falls within the newest window; otherwise find its exact Journal
   ID. Verify trade links, recorded venue/account labels, explicit unavailable PnL,
   full counts beyond the display limit, and portfolio/date scope labels.
8. Select the same trade/account in the Agent and repeat the recorded-trade query;
   compare the canonical Journal ID and lineage, not symbol alone. Repeat with a
   different user/tenant: their trades must not appear. Do not repair history to
   reconcile totals. Capture deployed SHA, API/UI observations and remaining causes.

Safety remains unchanged: exact preview confirmation, deterministic risk, minimum
gross 1R, tenant isolation, idempotency, freshness and protection verification are
authoritative. No strategy authorization, automatic exchange execution, live money,
order submission, cancellation, transfer, withdrawal or account mutation is added.
