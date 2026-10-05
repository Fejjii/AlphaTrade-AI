# External integration staging acceptance

Base: `codex/release_consolidation_wave_003` at
`87885e591714f44843eddb46c9549417a50b9a9e` (includes PR186/PR187/PR188/PR189/PR191).
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
TELEGRAM_INBOUND_MODE=off
PERPETUAL_EVIDENCE_SOURCE=binance_usdm
PERPETUAL_EVIDENCE_SECONDARY_SOURCE=bybit_usdt_perpetual
TRADINGVIEW_WEBHOOK_ENABLED=false
TRADINGVIEW_AUTO_CREATE_CANDIDATE=false
PAPER_SIGNAL_ORCHESTRATION_ENABLED=true
PAPER_SIGNAL_ORCHESTRATION_MODE=observe_only
BLOFIN_READONLY_SYNC_ENABLED=false
BLOFIN_DEMO_REST_BASE_URL=https://demo-trading-openapi.blofin.com
```

These are documented acceptance values; this PR changes no staging or production
environment variables. TradingView and BloFin are optional and stay disabled until
their external configuration is available. Enable `TRADINGVIEW_WEBHOOK_ENABLED`
only with the signing relay/secret, and `BLOFIN_READONLY_SYNC_ENABLED` only with
the dedicated credentials and demo origin configured.

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
call or execution. `/health` exposes only sync-enabled, credential-present and
demo-origin-present booleans. Missing credentials or origin return NOT CONFIGURED
before the acceptance harness requests a sync.

Internal paper signal orchestration skips optional BloFin context when sync is
disabled or credentials/demo origin are missing, including any retained unusable
snapshot. Once sync is enabled and configured, missing, stale, future-dated or
unhealthy snapshots still block that signal's orchestration. Risk and approval
checks remain mandatory in either case.

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
**NOT CONFIGURED**. Exit code is nonzero when any integration FAILs; missing
optional configuration alone does not fail the gate. A zero exit code does not
certify live acceptance of a NOT CONFIGURED integration. Missing API credentials,
webhook secret, disabled integration or missing sync credentials/demo origin
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

- PR190 rebased onto the exact baseline above with **no conflicts**. The accepted
  release evidence pipeline, Watcher, canonical paper execution and PR191 setup
  lifetime fix are unchanged. No migration or deployment configuration changed.
- Refresh validation: **51 passed** in `test_external_integrations_acceptance.py`
  (61.01 seconds). No conflicts or production/test code changes were required;
  all PR189 files and previously validated PR190 production/test files are preserved.
- Previous validation at `33a86e922d6f638d822f486db48e9563e585c0a9`
  covered `test_external_integrations_acceptance.py`,
  `test_external_integrations_postgres.py`, `test_at037_tradingview_blofin.py`,
  `test_at038_paper_signal_orchestration.py`, `test_blofin_provider.py`, and
  `test_blofin_execution.py`: **144 passed, 1 skipped** (97.43 seconds). The
  PostgreSQL concurrency case is skipped because no local test database is
  reachable; GitHub CI provides PostgreSQL. All external HTTP calls in this run
  use deterministic mocks. The command sandbox required network permission for
  FastAPI TestClient's local event loop; no application fix was needed for that.
- Ruff lint and format checks: **PASS** for all 14 changed Python files.
  `git diff --check`: **PASS**.
- No broad backend rerun or repeated staging Watcher campaign. Previous full-suite
  figures and failures belong to the older baseline; GitHub CI supplies the normal
  current-baseline full gate, including its PostgreSQL service.

The existing real BTCUSDT Watcher scans, API health 200 and stable retained worker
structures are accepted staging evidence supplied for this rebase, not new live
claims from these local tests. Binance/Bybit adapter acceptance uses deterministic
GET-only transports here. TradingView Inbox/Candidate flow and paper signal
orchestration are exercised against authenticated isolated test apps; BloFin sync
uses a GET-only mock demo venue with read-only permissions.

This workspace has no TradingView signing secret/relay configuration, dedicated
BloFin sync credentials/demo origin, or acceptance API URL/owner token/organization.
Those live checks remain **NOT CONFIGURED**, rather than core MVP blockers. An
actual chart alert through the relay and a permission-verified BloFin account
snapshot require external setup. Telegram remains off and real exchange execution
remains disabled. No deployment, Telegram message, exchange order or funds change
is performed by this completion work.
