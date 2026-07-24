# Staging Execution Checklist (Manual)

One-page click order for **Slice 30**. Fill URLs in [staging_live_deployment_notes.md](staging_live_deployment_notes.md) as you go.

| Step | Where | Action | Done |
|------|--------|--------|------|
| 1 | Terminal | `openssl rand -base64 32` → save as `JWT_SECRET` | ☐ |
| 2 | Render | New **PostgreSQL** → copy **External** URL | ☐ |
| 3 | Upstash | New **Redis** → copy `rediss://` URL (or Render Redis) | ☐ |
| 4 | Qdrant Cloud | New free cluster → copy HTTPS URL + API key *(or leave `QDRANT_URL` empty for in-memory RAG)* | ☐ |
| 5 | Render | New **Web Service** → Docker, context `backend`, Dockerfile `backend/Dockerfile` | ☐ |
| 6 | Render | Env vars from [staging_live_deployment_notes.md](staging_live_deployment_notes.md) §3 | ☐ |
| 7 | Render | Pre-deploy: `alembic upgrade head` · Health: `/health` | ☐ |
| 8 | Render | Deploy → copy **backend URL** | ☐ |
| 9 | Local | `ENV_FILE=.env.staging ./scripts/check-env.sh` (with real values) | ☐ |
| 10 | Vercel | Import repo · root `frontend` · env vars §3 | ☐ |
| 11 | Vercel | Deploy → copy **frontend URL** | ☐ |
| 12 | Render | Set `CORS_ORIGINS` = Vercel URL → **redeploy backend** | ☐ |
| 13 | Terminal | `./scripts/post-deploy-smoke-gate.sh` (AT-005; exit 0 required) | ☐ |
| 14 | Browser | Login → workspace → paper banner → logout | ☐ |

**Safety defaults (do not change):** `EXECUTION_MODE=paper` · `ENABLE_REAL_TRADING=false` · `BILLING_ENABLED=false` · `PROVIDER_MODE=fallback`
