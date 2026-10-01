# MVP release readiness 001

Prepared from `580dc183d69fa0ec8bc023a167d67a38e6b62f74`, stacked on Strategy Brain PR153. This is a release preparation pack, not evidence of deployment or a completed staging loop. No platform configuration, secrets, shared database, Watcher activation or Telegram enrollment is changed. Accept PR153 before applying this pack.

## Staging requirements

Use an isolated staging tenant with an existing verified owner/trader login, a dedicated managed PostgreSQL database, shared TLS Redis, hosted HTTPS Qdrant and staging-only credentials. Pin API, worker and frontend to the same accepted commit. Record that SHA, URLs, migration revision and smoke result in the release worksheet. Never put credentials in the worksheet or commit them. Do not use production database URLs or secrets.

The API validates managed Postgres, Redis, JWT (at least 32 random bytes), hosted Qdrant and a nonempty `OPENAI_API_KEY` even with `PROVIDER_MODE=fallback`. The disarmed worker explicitly defers operational dependencies; its successful boot is not proof that those services work. Provider fallback or degraded readiness is not proof of grounded live market evidence.

Use `.env.staging.example`, `frontend/.env.staging.example` and `render.yaml` as the existing contracts. The following values are mandatory on both Render services:

```dotenv
ENVIRONMENT=staging
DEBUG=false
ENABLE_REAL_TRADING=false
EXECUTION_MODE=paper
EXCHANGE_MODE=paper_internal
WATCHER_ORCHESTRATION_ENABLED=false
WATCHER_PAPER_STAGING_ACTIVATION=false
MARKET_WATCHER_ENABLED=false
MARKET_WATCHER_BRIDGE_ENABLED=false
MARKET_WATCHER_BRIDGE_AUTO_TICK=false
ENABLE_PAPER_SCHEDULER=false
PAPER_SIGNAL_ORCHESTRATION_ENABLED=false
WORKER_ENABLED=false
WORKER_ALERTS_ENABLED=false
TELEGRAM_ALERTS_ENABLED=false
TELEGRAM_INTERACTION_ENABLED=false
AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false
TELEGRAM_PAPER_ACTIVATION_ARMED=false
TELEGRAM_NETWORK_PERMITTED=false
TELEGRAM_INBOUND_MODE=off
ALERT_DELIVERY_ENABLED=false
ALERT_WEBHOOK_ENABLED=false
EMAIL_ALERTS_ENABLED=false
TRADINGVIEW_WEBHOOK_ENABLED=false
BLOFIN_DEMO_ENABLED=false
BILLING_ENABLED=false
AUTH_REFRESH_COOKIE_ENABLED=true
AUTH_OMIT_REFRESH_FROM_BODY=true
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
ACCESS_TOKEN_DENYLIST_ENABLED=true
ACCESS_TOKEN_DENYLIST_USE_REDIS=true
ACCESS_TOKEN_DENYLIST_FAIL_CLOSED=true
RATE_LIMIT_USE_REDIS=true
RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK=false
TRUSTED_PROXY_HOPS=1
PROVIDER_MODE=fallback
```

No exchange credentials or Telegram bot token are needed. Leave them absent. Supply `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `QDRANT_URL`, authenticated-cluster `QDRANT_API_KEY`, and `OPENAI_API_KEY` through the staging secret store only. Set `CORS_ORIGINS` to exact approved HTTPS staging frontend origins; do not blindly copy the existing production aliases. Keep `DEMO_SEED_ENABLED=false` for this flow. Use an existing verified user rather than disabling verification to bypass login.

For later read-only market validation, the existing contract is `MARKET_DATA_ENABLED=true`, `MARKET_DATA_CACHE_USE_REDIS=true`, `PERPETUAL_EVIDENCE_SOURCE=binance_usdm`, `PERPETUAL_EVIDENCE_SECONDARY_SOURCE=bybit_usdt_perpetual`, `MARKET_DATA_FUTURES_BASE_URL=https://fapi.binance.com`, `BYBIT_PERPETUAL_BASE_URL=https://api.bybit.com`, timeout 10 seconds. No authenticated exchange calls, spot or fabricated price fallback. The smoke below reads stored Brain records and does not request market acquisition. Local fixtures use scripted evidence and make no live market claim.

## Database sequence (future release operator only)

Do not run these against a shared database in this task. Verify a backup/restore point and database identity before any future release migration. First rehearse on a new disposable PostgreSQL database. `backend/src/app/db/migrations/versions` has a single head:

```text
f1a2b3c4d5e6 (controlled runtime status)
  → a8c3e1b94d20 (worker process memory)
  → b6f2d9a10e73 (tenant Watcher watchlist)
  → a1brain001 (Strategy Brain projections)
```

In `backend/`, after explicitly selecting the disposable database with `ALEMBIC_DATABASE_URL`:

```sh
.venv/bin/alembic heads
.venv/bin/alembic current
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

Do not stamp over missing schema or upgrade only Brain while skipping its parents. An existing database at `b6f2d9a10e73` needs the additive Brain migration; older versions need the intervening migrations. Unknown/multiple revisions are a stop condition. Verify exactly one `alembic_version` row at `a1brain001`, tables `strategy_brain_setups` and `strategy_brain_setup_events`, tenant/strategy/version foreign keys and indexes `ix_brain_org_symbol_time`, `ix_brain_event_setup_time`. No Brain backfill or synthetic production setup is required. Empty reads are valid. The fixture creates ORM metadata and therefore does not replace migration rehearsal.

Render currently runs `alembic upgrade head` in both API `preDeployCommand` and the default Docker entrypoint. Serialize release migrations and avoid concurrent API rollout until the revision is verified. Worker commands bypass that entrypoint migration. Brain downgrade drops its projection tables and histories: rehearse downgrade only on disposable databases; preserve data and prefer a forward fix for shared releases.

## API and worker startup validation

Render API uses `backend/Dockerfile`, backend Docker context, `/health`, and listens on `$PORT` (fallback `$API_PORT`, then 8000). Default image startup migrates; for startup validation after a separately verified migration, an explicit command `uvicorn app.main:app --host 0.0.0.0 --port "$PORT"` bypasses entrypoint migration. Do not start the default image against a shared database during this preparation.

After a separately authorized deployment, validate `/health` has the expected SHA, staging environment, paper/internal exchange and every disarmed flag above. `/health/ready` must report ready; also check `/providers/status` for unavailable or degraded dependencies. Liveness is not readiness. Authenticated Watcher/Brain reads exercise database access; login and revocation depend on Redis. Browser login/refresh must work with Secure cross-domain cookies and exact CORS origins.

Render worker command is `python -m app.workers.paper_worker`. Keep one supervisor, not the older `app.workers.entrypoint` or additional standalone Watcher/Telegram services. For a bounded local process check using the prepared disarmed staging environment:

```sh
cd backend
.venv/bin/python -c 'from app.workers.paper_worker import run_paper_worker_process; assert run_paper_worker_process(once=True) == "disarmed"'
```

Expect `paper_worker_boot` with `posture=disarmed`, paper-only and real trading false. Do not toggle flags to force a heartbeat or scan. Disarmed boot does not open databases/providers and may leave worker observations unavailable; that is honest absence, not an armed worker failure. `/watcher/paper-runtime/status` must stay disabled/non-running. Persisted stale/armed observations require investigation, not activation.

## Vercel frontend

Project root `frontend`, `npm ci`, `npm run build`, Next.js preset (`frontend/vercel.json`). Configure the approved preview/staging environment before a future build:

```dotenv
NEXT_PUBLIC_API_URL=https://YOUR-STAGING-API
NEXT_PUBLIC_APP_NAME=AlphaTrade AI
NEXT_PUBLIC_EXECUTION_MODE=paper
NEXT_PUBLIC_PROVIDER_MODE=fallback
NEXT_PUBLIC_AUTH_COOKIE_MODE=true
```

Public values are build-time inputs; never expose keys, database URLs or JWT secrets through `NEXT_PUBLIC_*`. Add the actual preview origin to staging API CORS. After authorized deployment, check browser login, refresh, Strategies → Nested setup details and journal navigation. HTTP smoke alone does not prove browser cookie/CORS behavior.

## Watcher prerequisites

Read `/watcher/watchlist` as the staging tenant and record its revision and enabled slots (maximum five). Configured universe is tenant configuration, independent of process activation. Confirm symbols resolve to the exact perpetual instrument catalog and the authored Nested timeframe (M15 default; M30/H1 supported). `/watcher/watchlist/status` must match configuration revision; missing/stale observations must remain explicit. This task does not edit staging watchlist or enable activation.

A future closed loop requires an immutable compiled and explicitly approved Nested strategy version, enabled strategy, paper execution account, fresh contracted 256 closed candles and a real contracted fresh quote, canonical eligibility/risk permissions and journal authority. Research `paper_active` alone is not execution approval. Watcher leases, healthy migration head and freshness fences still apply. Do not weaken risk limits or clear kill switches to obtain a fill. Telegram remains off. Activation needs a separate authorized task after release acceptance.

## First smoke: reads followed by controlled fixture

The new `scripts/mvp-readiness-smoke.py` logs in an existing tenant, verifies exact configured universe and disarmed Watcher status, reads Nested overview and makes a stored-record Brain Agent read. Its only POSTs are login and the read-only Agent turn (which persists conversation history). It does not register, scan, seed, approve, execute or activate anything. Supply credentials through process environment without shell tracing:

```sh
# From repository root; set BASE_URL, SMOKE_EMAIL and SMOKE_PASSWORD securely.
export SMOKE_SYMBOLS=BTCUSDT  # replace with the actual expected enabled universe
backend/.venv/bin/python scripts/mvp-readiness-smoke.py
# Only if an existing tenant setup already has paper Candidate/decision/journal links:
backend/.venv/bin/python scripts/mvp-readiness-smoke.py --setup-id EXISTING-SETUP-UUID
```

Without an ID, the result explicitly says linkage NOT VALIDATED. Empty Brain records must produce unknown/absent evidence, never an invented live setup. With an existing linked ID, the script checks Candidate identity, current eligibility decision identity, journal identity and Agent setup reference; old decisions replaced by newer eligibility reads fail visibly. The script performs no execution and makes no profitability claim.

When no linked setup exists, use the existing deterministic fixture in `backend/tests/test_strategy_brain_nested.py`: scripted 256-bar Nested N1 confirmation, frozen clock, controlled quote, canonical Candidate, authoritative eligibility decision, internal-paper fill, journal open/actual close, replay deduplication; a second scenario exercises actual daily-risk rejection without fill/journal creation. These are test-only synthetic observations, not live provider data.

Run it only on a disposable loopback PostgreSQL database named `alphatrade_mvp_smoke` using a dedicated test user. **The existing helpers DROP SCHEMA public CASCADE. Never use a shared/staging database.** Clear inherited database settings with `env -i`; do not copy a managed URL into these commands. First ensure this local database exists and SELECT 1 succeeds (failure or skipped integration is not a paper-loop pass):

```sh
cd backend
env -i PATH="$PATH" ENVIRONMENT=local \
  PHASE1_POSTGRES_URL='postgresql+psycopg://alphatrade:alphatrade@127.0.0.1:5432/alphatrade_mvp_smoke?connect_timeout=2' \
  .venv/bin/python -c 'from tests.support.postgres_persistence import postgres_available; assert postgres_available(), "Disposable local PostgreSQL required"'
env -i PATH="$PATH" ENVIRONMENT=local \
  PHASE1_POSTGRES_URL='postgresql+psycopg://alphatrade:alphatrade@127.0.0.1:5432/alphatrade_mvp_smoke?connect_timeout=2' \
  .venv/bin/pytest -q tests/test_mvp_readiness_smoke.py \
  tests/test_strategy_brain_nested.py::test_restart_replay_setup_idempotency_and_grounded_brain \
  tests/test_strategy_brain_nested.py::test_watcher_confirmed_candidate_existing_paper_path_and_replay \
  tests/test_strategy_brain_nested.py::test_existing_daily_risk_lock_blocks_nested_paper_execution
```

The HTTP fixture uses separate in-memory SQLite and validates real login, configured universe, status, empty Nested/Agent reads and read surfaces. The PostgreSQL scenarios validate Candidate/risk/journal linkage and replay using the existing governed runtime; they do not set staging activation. Require all selected tests to pass with zero skips before claiming the controlled loop validated. Migration rehearsal is a separate prerequisite, using the full existing Alembic integration test only on that same disposable database (`tests/test_phase2_4_alembic_postgres.py::test_pr77_alembic_upgrade_downgrade_reupgrade`). No shared migration is authorized by this guide.

## Handoff

Preparation checks: 85 focused tests passed (HTTP smoke, Brain stored reads, disarmed Render worker boot, Watcher activation safety, single Alembic head and container command forwarding); three PostgreSQL loop scenarios were deliberately deselected. Ruff passed. Offline PostgreSQL SQL generation for `b6f2d9a10e73:a1brain001` confirms both Brain tables and indexes without a database connection. Disposable PostgreSQL loop/migration rehearsal, deployed API/worker startup and Vercel browser behavior remain unverified; no deployment, provider probe or shared migration ran.

Merge after PR153 acceptance. Set staging-only dependencies and frontend origins, rehearse migrations on disposable Postgres, then validate a disarmed deployment and run the first read smoke plus controlled fixture. Missing setup/quote, unavailable dependencies, unexpected authority flags, old migration head, skipped fixture or missing linkage are release blockers for claiming a closed paper loop. Deployment, shared migrations and Watcher activation remain separate authorized operations; Telegram stays off.
