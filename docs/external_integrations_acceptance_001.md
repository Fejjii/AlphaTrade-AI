# External integration staging acceptance

Base: `codex/release_consolidation_wave_003` at
`8673d8f69779ea516ca97456baea7b3064daf089`.
Branch: `codex/external_integrations_acceptance_001`.

This work adds external acceptance without enabling real trading, demo orders,
withdrawals, transfers or Telegram networking. PR187/PR188 files and MindPillar
are outside this change. Existing canonical evidence diagnostics are reused.
No database migration is added; the AT-037/AT-038 tables already exist in the base.

## Audited contracts

| Integration | Verified implementation and acceptance boundary |
| --- | --- |
| TradingView | HMAC-SHA256 of `timestamp.raw_body`; stale/future header rejection; strict hex validation; org and strategy linkage; org-scoped unique alert/idempotency keys; Inbox persistence; confirmed paper Candidate creation. PostgreSQL races converge using a savepoint and signal row locks. |
| Paper Signal Orchestration | Eligibility, signal age, timeframes, setup/strategy links, conflicting signals, kill switch, daily loss and cooldown checks. BloFin snapshot age and health are rechecked. Proposal creation needs exact human approval and an active linked Candidate; approval rechecks risk. It never places orders. |
| Binance USD-M | Public GET-only `/fapi/v1/exchangeInfo`, `/klines`, `/aggTrades`, `/openInterest`, `/fundingRate`; `/time` and `/ping` are existing health endpoints. Closed 15m/4h candles, contiguous aggregate trades, provenance, settled funding and OI freshness remain enforced by existing contracts. Current price comes from fresh contracted trades, rather than a substituted spot ticker. |
| Bybit secondary | Public linear USDT perpetual `/v5/market/instruments-info`, `/kline`, `/recent-trade`, `/open-interest`, `/funding/history`, plus `/time`. Trade IDs/aggressor side and bounded overlapping trade pages prove continuity. Failure switches the entire venue identity; old Binance identity cannot label Bybit evidence. Existing tests inject 418, 429 and network failures with MockTransport; no live outage is induced. |
| BloFin demo sync | Separate opt-in sync credentials permit only account balance, position and API-key-permission GET requests to the allowlisted demo HTTPS origin. The execution credential loader remains sealed in `paper_internal`. Permission checks precede account fetches; trade/withdraw/transfer scopes are refused for the dedicated sync key. Credentials echoed by the venue are scrubbed from errors/logs. Snapshots include health, freshness, provenance and bounded balances/positions. |

Order flow is derived from real aggressor prints with complete window coverage.
Candle volume is never used as a replacement for CVD or buy/sell flow. Funding is
a provider-reported settled rate and OI is venue-specific; neither is inferred
from trade flow or combined across venues.

## Deployment configuration

Keep these values throughout acceptance:

```dotenv
ENABLE_REAL_TRADING=false
EXECUTION_MODE=paper
EXCHANGE_MODE=paper_internal
BLOFIN_DEMO_ENABLED=false
TELEGRAM_ALERTS_ENABLED=false
TELEGRAM_INTERACTION_ENABLED=false
TELEGRAM_NETWORK_PERMITTED=false
TELEGRAM_PAPER_ACTIVATION_ARMED=false
AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false
PERPETUAL_EVIDENCE_SOURCE=binance_usdm
PERPETUAL_EVIDENCE_SECONDARY_SOURCE=bybit_usdt_perpetual
TRADINGVIEW_WEBHOOK_ENABLED=true
TRADINGVIEW_AUTO_CREATE_CANDIDATE=false
PAPER_SIGNAL_ORCHESTRATION_ENABLED=true
PAPER_SIGNAL_ORCHESTRATION_MODE=observe_only
BLOFIN_READONLY_SYNC_ENABLED=true
BLOFIN_DEMO_REST_BASE_URL=https://demo-trading-openapi.blofin.com
```

Set `TRADINGVIEW_WEBHOOK_SECRET` securely. A trusted TradingView signing relay
must attach `X-AT-Timestamp` and `X-AT-Signature`; native TradingView alert delivery
does not generate this HMAC/header protocol. The relay binds organization IDs to
its trusted routing configuration and signs the exact bytes it forwards. The
shared HMAC secret authorizes that relay; do not distribute it to tenant browsers.
Acceptance sends the same signed protocol directly, so an actual chart alert
through the configured relay remains a separate deployment check.

Set **dedicated read-only demo credentials** as `BLOFIN_READONLY_API_KEY`,
`BLOFIN_READONLY_API_SECRET`, and `BLOFIN_READONLY_API_PASSPHRASE`. The old
`BLOFIN_API_*` execution credentials are not reused by this capability. The
read-only flag defaults to false; credential presence alone enables no network
call or execution. `/health` exposes only sync-enabled/credential-present booleans.

Apply existing migrations to staging PostgreSQL. Supply an owner access token
for the acceptance organization. Standard staging auth, database and Redis
requirements still apply. Keep the kill switch and daily risk posture honest:
if they block the advisory signal, orchestration acceptance returns FAIL with
no proposal/order rather than treating the block as a successful ready state.
Run in a dedicated acceptance organization so test signals do not conflict with
operational signals.

## One harness

Run from the **deployed backend environment** so public exchange reachability,
provider-region restrictions, TLS and backend dependencies match staging:

```bash
cd backend
export AT_ACCEPTANCE_API_URL=https://your-staging-backend.example
export AT_ACCEPTANCE_ORGANIZATION_ID=your-acceptance-organization-uuid
# Inject AT_ACCEPTANCE_TOKEN securely; do not put it in shell history or arguments.
.venv/bin/python -m app.external_integrations.acceptance \
  --output /tmp/external-integrations-acceptance.json
```

Market probes instantiate the existing Binance/Bybit production adapters in the
harness process. API probes check deployment paper/Telegram posture and token
organization before writes, then test read-only BloFin sync, signed TradingView
intake, Inbox persistence, idempotency, confirmation and governed orchestration.
They create a bounded advisory signal/Candidate/decision in the acceptance org;
they never approve a proposal or call execution APIs. Disabled/missing BloFin
configuration is detected before POST sync, so a missing integration cannot
pollute orchestration with an unavailable snapshot.

For an active Bybit market whose 1000-print REST page cannot cover ten minutes,
collect overlapping pages in this same process before acceptance:

```bash
.venv/bin/python -m app.external_integrations.acceptance \
  --bybit-warmup-seconds 660 \
  --output /tmp/external-integrations-acceptance.json
```

Warmup is bounded to 900 seconds and uses the existing bounded continuity proof.
Page gaps, truncated history, unavailable derivatives or stale data still FAIL.
The harness never fabricates historical prints or relaxes freshness to pass.

Each integration has exactly one top-level `status`: **PASS**, **FAIL**, or
**NOT CONFIGURED**. Exit code is zero only when all five PASS. Missing API
credentials, webhook secret, disabled integration or missing sync credentials
never become PASS. Failure output excludes raw responses/exception strings that
could contain secrets. The harness does not intentionally fail the live primary;
failover is verified using deterministic mocked failures in automated tests.

## Checks still requiring deployment

- Public Binance/Bybit GET reachability from the staging region, live timestamps,
  complete recent-trade/order-flow coverage and actual settled OI/funding data.
- Deployed webhook routing, matching signing secret and an actual chart alert
  through the trusted signing relay.
- Authenticated Inbox/Candidate/orchestration persistence on migrated staging
  PostgreSQL, with the intended organization and configured risk posture.
- BloFin demo permission response, balances/positions, fresh persisted snapshots
  and TLS/IP allowlist access using dedicated read-only credentials.

Local verification uses deterministic market transports and a disposable local
PostgreSQL instance. It does not claim live integration acceptance. There are no
configured external secrets in the development workspace, and its exchange
hosts are not enabled in the network policy.

## Changed files

- `backend/src/app/api/routes/health.py`
- `backend/src/app/core/blofin_readonly_access.py`
- `backend/src/app/core/config.py`
- `backend/src/app/external_integrations/__init__.py`
- `backend/src/app/external_integrations/acceptance.py`
- `backend/src/app/providers/exchange/blofin_client.py`
- `backend/src/app/repositories/tradingview_signal.py`
- `backend/src/app/schemas/health.py`
- `backend/src/app/security/tradingview_webhook.py`
- `backend/src/app/services/blofin_sync_service.py`
- `backend/src/app/services/paper_signal_orchestration_service.py`
- `backend/src/app/services/tradingview_signal_service.py`
- `backend/tests/test_external_integrations_acceptance.py`
- `backend/tests/test_external_integrations_postgres.py`
- `docs/external_integrations_acceptance_001.md`

## Verification results

- Focused integration, signal lifecycle, tenant isolation, idempotency, risk,
  deployment-safety and market-contract run: **671 passed**. This included
  `test_at037_tradingview_blofin.py`, `test_at038_paper_signal_orchestration.py`,
  `test_binance_usdm_staging_reliability.py`,
  `test_bybit_usdt_perpetual_evidence.py`, `test_blofin_provider.py`, and
  `test_blofin_execution.py`, plus the new external integration regressions and
  PostgreSQL intake/Candidate race test.
- Final harness additions: **34 cases** covered in the broader run; targeted
  checks for the final warmup/CLI/disabled-webhook edits: **4 passed**.
- Broader backend suite run **once**, with disposable PostgreSQL:
  **3,802 passed, 3 failed, 6 skipped** (2,791.41 seconds).
- The script self-check failure was environmental: uv's default cache path is
  read-only in this workspace. A targeted rerun with
  `UV_CACHE_DIR=/tmp/alphatrade-uv-cache` **passed**.
- The six skipped Agent proposal PostgreSQL tests require the hardcoded
  `pr150_journal_fix` database. After creating it in the disposable local
  PostgreSQL container, their targeted rerun **passed all six**.
- Ruff: **PASS** (`ruff check src tests`). Format check: **PASS**
  (`ruff format --check src tests`, 1,058 files). `git diff --check`: **PASS**.

Two inherited failures remain in the PR188-owned
`backend/tests/test_controlled_paper_activation_rehearsal.py`:

- `test_provider_outage_does_not_mint`
- `test_stale_live_window_does_not_mint`

Both expect scan status `failed`; the implementation returns `blocked` and
creates zero Candidates. Both reproduce in an isolated checkout of the exact
base commit `8673d8f69779ea516ca97456baea7b3064daf089`. This change leaves the
PR188 test file untouched. They block an entirely green backend suite, while the
external integration focused checks pass. Live staging checks remain pending
configuration and deployment as listed above.
