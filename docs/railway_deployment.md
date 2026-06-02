# Railway Deployment Notes

Alternative to Render for the **backend + Postgres + Redis** layer. Frontend remains on **Vercel**.

> Same safety rules: `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `BILLING_ENABLED=false`.

## When to use Railway

- You prefer one dashboard for API + databases
- You want plugin-based Postgres/Redis without separate Upstash/Neon accounts

Render is still the **default** in this repo because `backend/Dockerfile` + `render.yaml` are first-class.

## Setup outline

1. **New Project** → Deploy from GitHub repo.
2. **Add Postgres** plugin → copy `DATABASE_URL` (ensure `postgresql+psycopg://` driver prefix).
3. **Add Redis** plugin → copy `REDIS_URL`.
4. **Create service** for backend:
   - Builder: Dockerfile
   - Dockerfile path: `backend/Dockerfile`
   - Root / context: `backend`
   - Start command: uses image entrypoint (migrations + uvicorn)
5. **Variables** — paste from [`.env.staging.example`](../.env.staging.example):
   - `ENVIRONMENT=staging`
   - `CORS_ORIGINS=https://your-app.vercel.app`
   - Cookie auth vars same as runbook
6. **Public networking** → generate HTTPS domain → use as `NEXT_PUBLIC_API_URL` on Vercel.
7. **Qdrant:** Add Qdrant Cloud URL or accept degraded RAG + `ALLOW_DEGRADED_READY=true` in smoke tests.

## Migrations

Run on deploy via Dockerfile entrypoint, or one-off Railway shell:

```bash
alembic upgrade head
```

## Smoke tests

```bash
BASE_URL=https://your-service.up.railway.app ./scripts/staging-smoke.sh
```

## Differences from Render

| Topic | Railway | Render |
|-------|---------|--------|
| Blueprint | Manual service setup | [`render.yaml`](../render.yaml) optional |
| Redis | Plugin | Add-on or Upstash |
| Release command | Entrypoint or custom start | `preDeployCommand` in blueprint |

See [staging_deployment_runbook.md](staging_deployment_runbook.md) for full cross-domain cookie and CORS steps.
