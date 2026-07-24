# Deployment Guide

This document describes how to deploy AlphaTrade AI to a **managed cloud staging
environment** suitable for portfolio demos and early product validation — without
Kubernetes unless you outgrow this path.

> **Safety:** Real exchange execution remains **disabled**. All execution is
> **paper only**. Staging and production startup validation refuses unsafe
> trading configuration.

## Recommended hosting options

| Component | Options | Notes |
|-----------|---------|-------|
| **Frontend** | [Vercel](https://vercel.com) (preferred), Netlify, Cloudflare Pages | Next.js 15 standalone build; env vars at build time |
| **Backend API** | [Render](https://render.com) (preferred), Railway, Fly.io, Azure Container Apps | Docker image from `backend/Dockerfile` |
| **Postgres** | Render Postgres, Railway Postgres, Supabase, Neon, Azure Database | Required for workflows, auth, audit |
| **Redis** | Render Redis, Upstash, Railway Redis, Azure Cache | Required in staging/production for rate limits + denylist |
| **Qdrant** | [Qdrant Cloud](https://cloud.qdrant.io), self-hosted container on Fly/Railway | Vector search for RAG; in-memory fallback if unreachable |

### Preferred option (portfolio MVP)

**Vercel (frontend) + Render (backend + managed Postgres + Redis) + Qdrant Cloud**

Why this path:

- No Kubernetes operational overhead
- HTTPS by default on Vercel and Render
- Docker-based backend deploy reuses existing `backend/Dockerfile`
- Secrets via platform env / secret stores
- Alembic migrations as a Render **release command** or pre-deploy job
- Fits a solo developer or small team validating the product

Alternatives (equally valid):

- **Railway** — all-in-one monorepo deploy with plugins for Postgres/Redis
- **Fly.io** — good if you want Qdrant co-located as a Fly app
- **Azure Container Apps** — enterprise-friendly with managed Postgres/Redis

## Architecture (staging)

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         Staging (managed cloud)                          │
├──────────────────────────────┬──────────────────────────────────────────┤
│  Vercel (HTTPS)              │  Render / Railway / Fly (HTTPS)          │
│  Next.js frontend            │  FastAPI backend (Docker)                │
│  NEXT_PUBLIC_API_URL ────────┼──► CORS_ORIGINS = Vercel URL             │
│  credentials: include        │  httpOnly refresh cookie (Secure)        │
│  (cookie mode)               │  Bearer access token (short TTL)         │
├──────────────────────────────┼──────────────────────────────────────────┤
│                              │  Managed Postgres ◄── Alembic migrations  │
│                              │  Managed Redis    ◄── rate limits, denylist│
│                              │  Qdrant Cloud     ◄── RAG vectors         │
└──────────────────────────────┴──────────────────────────────────────────┘
```

Cross-domain auth (Vercel frontend + separate API host):

- `AUTH_REFRESH_COOKIE_ENABLED=true`
- `AUTH_COOKIE_SECURE=true`
- `AUTH_COOKIE_SAMESITE=none` (required for cross-site cookies)
- `CORS_ORIGINS=https://your-app.vercel.app` (exact origin, credentials enabled)
- `NEXT_PUBLIC_AUTH_COOKIE_MODE=true` on Vercel

Same-domain (API behind reverse proxy on same site):

- `AUTH_COOKIE_SAMESITE=strict` or `lax` may suffice
- Still require `AUTH_COOKIE_SECURE=true` in staging/production

## Environment templates

| Template | Purpose |
|----------|---------|
| [`.env.example`](../.env.example) | Local development (bearer auth) |
| [`.env.docker.example`](../.env.docker.example) | Docker Compose overrides |
| [`.env.staging.example`](../.env.staging.example) | Staging / managed backend |
| [`frontend/.env.example`](../frontend/.env.example) | Local frontend |
| [`frontend/.env.staging.example`](../frontend/.env.staging.example) | Vercel / staging frontend |

### Required staging / production variables

| Variable | Staging / production |
|----------|---------------------|
| `ENVIRONMENT` | `staging` or `production` |
| `EXECUTION_MODE` | `paper` |
| `ENABLE_REAL_TRADING` | `false` |
| `PROVIDER_MODE` | `fallback` or `live` (trading still disabled) |
| `DATABASE_URL` | Managed Postgres URL (not localhost) |
| `REDIS_URL` | Managed Redis URL (not localhost) |
| `QDRANT_URL` | Hosted Qdrant URL (not localhost) |
| `JWT_SECRET` | 32+ byte random secret |
| `AUTH_REFRESH_COOKIE_ENABLED` | `true` |
| `AUTH_COOKIE_SECURE` | `true` |
| `AUTH_COOKIE_SAMESITE` | `none` (cross-domain) or `strict`/`lax` (same-site) |
| `CORS_ORIGINS` | Deployed frontend URL(s) |
| `RATE_LIMIT_USE_REDIS` | `true` |
| `OPENAI_API_KEY` | Optional — enables real LLM/embeddings with fallback |

Startup validation in `app.core.deployment_safety` **fails fast** if these
invariants are violated.

Validate before deploy:

```bash
ENV_FILE=.env.staging.example ./scripts/check-env.sh   # after filling real values
```

## Secrets management

**Never commit** `.env`, production secrets, or API keys.

| Secret | Where to store |
|--------|----------------|
| `JWT_SECRET` | Platform secret store (Render/Railway/Vercel env) |
| `DATABASE_URL` | Managed DB connection string (platform-provided) |
| `REDIS_URL` | Managed Redis URL |
| `OPENAI_API_KEY` | Platform secret (optional) |
| `QDRANT_API_KEY` | Qdrant Cloud dashboard (if using API key auth) |

Local development: copy `.env.example` → `.env` (gitignored).

Staging: copy `.env.staging.example`, fill values in the **platform UI**, run
`./scripts/check-env.sh` with `ENV_FILE` pointing at a local copy (never push
that file).

## Backend deployment (Render example)

1. **Create Web Service** from repo, root directory `backend`, Dockerfile path `backend/Dockerfile`.
2. **Release command** (migrations before traffic):

   ```bash
   alembic upgrade head
   ```

   Or use `./scripts/run-migrations.sh` locally / in CI; Render supports
   `preDeployCommand: alembic upgrade head`.

3. **Environment variables** — paste from `.env.staging.example` (filled).
4. **Health check path:** `/health` (liveness), optional readiness `/health/ready`.
5. **Port:** 8000 (uvicorn listens on `API_PORT`).

The Docker entrypoint runs migrations on startup by default; for zero-downtime
deploys prefer a **release command** so migrations complete before the new
revision serves traffic.

```bash
# Manual migration (local or CI against staging DB)
DATABASE_URL='postgresql+psycopg://...' ./scripts/run-migrations.sh
```

## Frontend deployment (Vercel)

1. Import the repo; set **Root Directory** to `frontend`.
2. Framework preset: **Next.js** (auto-detected).
3. Set environment variables (Production + Preview):

   | Variable | Example |
   |----------|---------|
   | `NEXT_PUBLIC_API_URL` | `https://alphatrade-api.onrender.com` |
   | `NEXT_PUBLIC_AUTH_COOKIE_MODE` | `true` |
   | `NEXT_PUBLIC_EXECUTION_MODE` | `paper` |
   | `NEXT_PUBLIC_PROVIDER_MODE` | `fallback` |

4. Deploy. Verify login → dashboard → logout with browser devtools (refresh
   cookie on API domain, no refresh token in `sessionStorage`).

5. Update backend `CORS_ORIGINS` to match the Vercel URL exactly (including
   `https://`).

**Note:** `NEXT_PUBLIC_*` vars are baked at **build time**. Redeploy frontend
after changing the API URL.

## Docker Compose (local production simulation)

See the original local stack documentation below. Compose remains the fastest
way to validate cookie auth, migrations, and safety scripts before cloud deploy.

```bash
docker compose up --build
./scripts/docker-validate.sh
./scripts/staging-smoke.sh
```

## Health checks

| Endpoint | Use | Returns |
|----------|-----|---------|
| `GET /health` | Liveness + **trading safety posture** | `execution_mode`, `real_trading_enabled`, version |
| `GET /health/ready` | Readiness | Provider registry availability |
| `GET /providers/status` | Dashboard + smoke | Mock/fallback provider visibility (incl. `billing`) |
| `GET /billing/status` | Billing UI | Plan + mock/live billing mode (authenticated) |

Platform probes should use `/health` for liveness. Use `/health/ready` for
readiness when you want to drain traffic during provider degradation.

Post-deploy smoke:

```bash
BASE_URL=https://your-api.example.com ./scripts/staging-smoke.sh
./scripts/verify-safety.sh
```

## Database migration process

1. Develop migration locally: `cd backend && uv run alembic revision --autogenerate -m "..."`.
2. Test against local Postgres (Compose or local instance).
3. Run in staging release command: `alembic upgrade head`.
4. Verify with `./scripts/staging-smoke.sh`.
5. Promote same image + migration to production.

Rollback:

- **Application:** redeploy previous Docker image / Render revision.
- **Database:** Alembic downgrade one revision only if the migration is
  reversible; otherwise restore from backup. Document breaking migrations in PR
  descriptions.

## Rollback plan

| Layer | Action |
|-------|--------|
| Backend | Revert to previous deploy revision in Render/Railway/Fly |
| Frontend | Redeploy previous Vercel deployment (Instant Rollback) |
| Database | `alembic downgrade -1` if safe; else restore snapshot — see [backup_restore_runbook.md](backup_restore_runbook.md) |
| Secrets | Rotate `JWT_SECRET` only with planned session invalidation |

Keep previous revision available for 24–48 hours after staging deploy.

Full backup inventory, RPO/RTO targets, and restore-drill evidence: [backup_restore_runbook.md](backup_restore_runbook.md),
[backup_inventory.md](backup_inventory.md), [backup_restore_drill_evidence.md](backup_restore_drill_evidence.md).
Deploy rollback automation / smoke gating is tracked separately as **AT-005**.

## Monitoring plan

Current observability (no over-build):

| Signal | Mechanism |
|--------|-----------|
| Structured logs | `LOG_JSON=true` — structlog JSON to stdout |
| Request IDs | `X-Request-ID` middleware on every request |
| Trace IDs | `X-Trace-ID` header propagated when present |
| Health | Platform probe on `/health` |
| Audit events | `GET /audit/events` (authenticated) |
| Usage summary | `GET /usage/summary` (authenticated) |
| Provider status | `GET /providers/status` (public dashboard data) |

Future (documented, not wired):

- **LangSmith** — set `LANGSMITH_API_KEY` when tracing provider is implemented
- **OpenTelemetry** — export traces/metrics to your APM of choice
- **Uptime** — external ping on `/health` + PagerDuty on `real_trading_enabled=true`

Log ingestion: pipe Render/Railway stdout to Datadog, Axiom, or CloudWatch.
Ensure log pipeline respects redaction (tokens/passwords stripped via structlog
processor).

## Environment configuration hardening

Staging/production startup checks (`deployment_safety.py`):

- Rejects `enable_real_trading=true` and `execution_mode=trade`
- Rejects localhost `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`
- Requires HTTPS cookies and refresh cookie mode
- Requires strong `JWT_SECRET` (32+ bytes, no known placeholders)
- Requires `rate_limit_use_redis=true`
- Requires `debug=false` in **production** only
- Logs deployment posture at startup **without secrets**

Run `./scripts/verify-safety.sh` after every deploy.

## Known limitations

- **No real exchange or broker execution** — paper mode only by design.
- Single backend instance — no horizontal autoscaling yet.
- Access token remains in `sessionStorage` (short TTL; refresh in httpOnly cookie).
- No email verification or password reset.
- Usage costs are estimates, not billing-grade.
- Qdrant dimension mismatch when switching embedding providers — re-index required.
- Full browser E2E optional in CI (API smoke is stable).
- LangSmith / OpenTelemetry integration is scaffolded only.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Startup crash in staging | Failed deployment safety check | Run `./scripts/check-env.sh` with your env file |
| Login works locally, fails on Vercel | CORS or cookie SameSite | Set `CORS_ORIGINS`, `AUTH_COOKIE_SAMESITE=none`, `SECURE=true` |
| Refresh 401 cross-domain | Cookie mode off on frontend | `NEXT_PUBLIC_AUTH_COOKIE_MODE=true` + redeploy |
| `/health/ready` degraded | Qdrant/OpenAI unreachable | Expected in fallback mode; check `/providers/status` |
| Migrations fail on deploy | Wrong `DATABASE_URL` | Verify SSL params for managed Postgres |

## Related commands

```bash
# Validate env file (after filling secrets locally)
ENV_FILE=.env.staging ./scripts/check-env.sh

# Apply migrations
./scripts/run-migrations.sh

# Post-deploy smoke
BASE_URL=https://api.example.com ./scripts/staging-smoke.sh

# Safety invariants only
BASE_URL=https://api.example.com ./scripts/verify-safety.sh

# Local Docker stack
docker compose up --build
./scripts/docker-validate.sh
```

See also: [staging_deployment_runbook.md](staging_deployment_runbook.md),
[staging_deployment_checklist.md](staging_deployment_checklist.md),
[security_checklist.md](security_checklist.md), [security.md](security.md),
[observability.md](observability.md).

## Docker Compose reference (local)

```text
┌──────────────────────────────────────────────────────────────────────┐
│                     docker compose (local)                            │
├─────────────┬─────────────┬─────────────┬─────────────┬──────────────┤
│   backend   │  frontend   │  postgres   │    redis    │    qdrant    │
│  FastAPI    │  Next.js    │  primary DB │ rate limit  │ vector store │
│  :8000      │  :3000      │  :5432      │  :6379      │  :6333       │
└─────────────┴─────────────┴─────────────┴─────────────┴──────────────┘
```

Compose defaults: paper mode, cookie auth, mock providers. See
[`docker-compose.yml`](../docker-compose.yml) and [`.env.docker.example`](../.env.docker.example).

## Fresh clone troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'app'` | Use `./backend/scripts/run_dev_server.sh` or `PYTHONPATH=src` |
| `error parsing value for field "cors_origins"` | Pull latest; `CORS_ORIGINS` is comma-separated in `.env.example` |
| Backend health OK but auth fails | Start Postgres or use `docker compose up` for the full stack |
| Frontend cannot reach API | Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local` |
