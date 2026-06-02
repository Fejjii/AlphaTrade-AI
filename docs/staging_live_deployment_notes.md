# Staging Live Deployment Notes

Working notes for **Slice 32** — staging validation after Slice 31 analytics.  
**Do not commit** filled secrets or this file if you paste credentials into §0.

Related: [pre_deployment_checklist.md](pre_deployment_checklist.md) · [deployment_command_pack.md](deployment_command_pack.md) · [staging_deployment_worksheet.template.md](staging_deployment_worksheet.template.md) · [staging_execution_checklist.md](staging_execution_checklist.md) · [staging_deployment_runbook.md](staging_deployment_runbook.md)

---

## 0. Record your deployed URLs

| Item | Value |
|------|--------|
| **Backend URL** | `https://________________________` |
| **Frontend URL** | `https://________________________` |
| **Deploy date** | |
| **Smoke passed** | ☐ |
| **Demo ready** | ☐ |

---

## 1. Render backend setup

1. [Render Dashboard](https://dashboard.render.com) → **New** → **PostgreSQL**  
   - Name: `alphatrade-staging-db`  
   - Copy **External Database URL** (often `postgres://...` — app normalizes to `postgresql+psycopg://`)

2. **New** → **Web Service** → connect **Fejjii/AlphaTrade-AI** (or your fork).

3. **Docker settings**
   - Environment: **Docker**
   - Dockerfile path: `backend/Dockerfile`
   - Docker context: `backend`
   - Branch: `main`

4. **Deploy settings**
   - Health Check Path: `/health`
   - Pre-Deploy Command: `alembic upgrade head`

5. Optional: apply [render.yaml](../render.yaml) via **Blueprint** (then add secret env vars in UI).

6. **Environment** → paste variables from §3 → **Save** → **Manual Deploy**.

7. When live, copy service URL (e.g. `https://alphatrade-api-staging.onrender.com`) into §0.

**Render note:** Platform sets `PORT`; entrypoint binds `PORT` then `API_PORT` (no extra env needed).

---

## 2. Vercel frontend setup

1. [Vercel](https://vercel.com) → **Add New** → **Project** → import repo.

2. **Root Directory:** `frontend`

3. **Environment Variables** (Production + Preview) — see §3 frontend table.

4. Deploy → copy URL (e.g. `https://alphatrade-ai.vercel.app`) into §0.

5. Update Render `CORS_ORIGINS` to that exact URL → **redeploy backend**.

Optional: [frontend/vercel.json](../frontend/vercel.json) is already present.

---

## 3. Required environment variables

### Backend (Render)

| Variable | Staging value |
|----------|----------------|
| `ENVIRONMENT` | `staging` |
| `EXECUTION_MODE` | `paper` |
| `ENABLE_REAL_TRADING` | `false` |
| `BILLING_ENABLED` | `false` |
| `PROVIDER_MODE` | `fallback` |
| `MARKET_DATA_ENABLED` | `true` |
| `DATABASE_URL` | Render Postgres external URL |
| `REDIS_URL` | Upstash `rediss://...` or Render Redis URL |
| `QDRANT_URL` | Qdrant Cloud `https://...` **or leave empty** for in-memory RAG fallback |
| `QDRANT_API_KEY` | If Qdrant Cloud requires it |
| `JWT_SECRET` | 32+ bytes (`openssl rand -base64 32`) |
| `CORS_ORIGINS` | `https://YOUR-APP.vercel.app` (no trailing slash) |
| `AUTH_REFRESH_COOKIE_ENABLED` | `true` |
| `AUTH_OMIT_REFRESH_FROM_BODY` | `true` |
| `AUTH_COOKIE_SECURE` | `true` |
| `AUTH_COOKIE_SAMESITE` | `none` |
| `ACCESS_TOKEN_DENYLIST_ENABLED` | `true` |
| `ACCESS_TOKEN_DENYLIST_USE_REDIS` | `true` |
| `RATE_LIMIT_USE_REDIS` | `true` |
| `RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK` | `false` |
| `DEBUG` | `false` |
| `LOG_JSON` | `true` |
| `OPENAI_API_KEY` | Optional |

**Render Postgres SSL:** If connections fail, append `?sslmode=require` to `DATABASE_URL`.

### Frontend (Vercel)

| Variable | Value |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | Backend URL from §0 |
| `NEXT_PUBLIC_AUTH_COOKIE_MODE` | `true` |
| `NEXT_PUBLIC_EXECUTION_MODE` | `paper` |
| `NEXT_PUBLIC_PROVIDER_MODE` | `fallback` |

---

## 4. Exact migration command

**Slice 31 analytics:** Before validating analytics endpoints in staging, apply migration **`j0k1l2m3n4o5`** (setup linkage on positions and paper orders for analytics). Without it, `/analytics/*` may fail or return incomplete data.

**On Render (recommended):** Pre-Deploy Command:

```bash
alembic upgrade head
```

**From your laptop** (against staging DB):

```bash
cd backend
DATABASE_URL='postgresql+psycopg://USER:PASS@HOST:5432/DB?sslmode=require' \
  uv run alembic upgrade head
```

Or:

```bash
DATABASE_URL='...' ./scripts/run-migrations.sh
```

Container entrypoint also runs migrations on start (backup if pre-deploy fails).

---

## 5. Exact CORS settings

| Setting | Value |
|---------|--------|
| `CORS_ORIGINS` | Single origin: `https://your-app.vercel.app` |
| Multiple previews | `https://app.vercel.app,https://app-git-main-user.vercel.app` |
| Rules | HTTPS only · no trailing slash · must match browser address bar exactly |

Backend uses `allow_credentials=True` — wildcard `*` is **not** used.

After changing CORS → **redeploy Render**.

---

## 6. Exact cookie settings

Cross-domain: Vercel (site A) + Render (site B).

| Variable | Value | Why |
|----------|--------|-----|
| `AUTH_REFRESH_COOKIE_ENABLED` | `true` | Refresh in httpOnly cookie |
| `AUTH_OMIT_REFRESH_FROM_BODY` | `true` | No refresh token in JSON |
| `AUTH_COOKIE_SECURE` | `true` | HTTPS only |
| `AUTH_COOKIE_SAMESITE` | `none` | Cross-site cookie from API |
| `NEXT_PUBLIC_AUTH_COOKIE_MODE` | `true` | Frontend sends `credentials: include` |

Cookie name: `alphatrade_refresh` · path: `/auth` · set on API host only.

Access token stays in `sessionStorage` (short TTL).

---

## 7. Exact smoke test commands

Replace URLs with §0 values.

```bash
# 1) Validate env locally (copy filled .env.staging, never commit)
ENV_FILE=.env.staging ./scripts/check-env.sh

# 2) Safety invariants on live API
BASE_URL=https://YOUR_BACKEND_URL ./scripts/verify-safety.sh

# 3) Full staging smoke (cookie + CORS + auth + chat)
FRONTEND_URL=https://YOUR_FRONTEND_URL \
COOKIE_MODE=true \
ALLOW_DEGRADED_READY=true \
BASE_URL=https://YOUR_BACKEND_URL \
./scripts/staging-smoke.sh

# 4) Optional — analytics smoke (Slice 31; requires migration j0k1l2m3n4o5)
INCLUDE_ANALYTICS=true \
FRONTEND_URL=https://YOUR_FRONTEND_URL \
COOKIE_MODE=true \
ALLOW_DEGRADED_READY=true \
BASE_URL=https://YOUR_BACKEND_URL \
./scripts/staging-smoke.sh

# Or standalone analytics smoke
BASE_URL=https://YOUR_BACKEND_URL ./scripts/analytics-smoke.sh
```

**Expected:** All steps print OK; safety shows `execution_mode=paper`, `real_trading_enabled=false`, exchange mock/paper-only.

**If Qdrant is down:** keep `ALLOW_DEGRADED_READY=true` (readiness may be degraded; app still runs).

---

## 8. Known failure cases and fixes

| Symptom | Fix |
|---------|-----|
| Deploy crash: `deployment safety check failed` | Run `check-env.sh`; fix JWT length, HTTPS CORS, managed DB/Redis URLs |
| `connection refused` / timeout on DB | Use **external** Postgres URL; add `?sslmode=require` |
| `postgres://` driver error | Fixed in app (auto `postgresql+psycopg://`); redeploy latest `main` |
| Health check fails / 502 | Ensure Render `PORT` is used (entrypoint fix on `main`); check logs |
| CORS error in browser | `CORS_ORIGINS` exact Vercel URL; redeploy backend |
| Login OK, refresh fails | `AUTH_COOKIE_SAMESITE=none`, `SECURE=true`, `NEXT_PUBLIC_AUTH_COOKIE_MODE=true` |
| `/health/ready` not ready | Qdrant/OpenAI optional; use `ALLOW_DEGRADED_READY=true` or fix `QDRANT_URL` |
| Redis TLS errors | Use Upstash `rediss://` URL as provided |
| Migrations fail pre-deploy | Run manual `alembic upgrade head` with `DATABASE_URL` from laptop |
| Vercel still calls localhost API | Redeploy Vercel after setting `NEXT_PUBLIC_API_URL` |
| 429 on smoke tests | Wait or use fresh `SMOKE_EMAIL` (script uses unique email by default) |

---

## 9. Upstash Redis (quick)

1. [console.upstash.com](https://console.upstash.com) → Create database.
2. Copy **Redis URL** (`rediss://...`) → Render `REDIS_URL`.
3. Same region as Render if possible (latency).

---

## 10. Qdrant Cloud (quick)

1. [cloud.qdrant.io](https://cloud.qdrant.io) → cluster → HTTPS endpoint.
2. API key → `QDRANT_API_KEY`.
3. **Skip for first smoke:** leave `QDRANT_URL` empty — staging allows in-memory vector fallback.

---

## 11. After smoke passes

1. Mark §0 checkboxes.
2. Update README **Staging Deployment** with your live URLs (see README template).
3. Run browser demo: [demo_script.md](demo_script.md).
4. Share §0 backend URL only for API smoke; frontend for portfolio demos.

---

## 12. Slice 30 smoke / safety log (fill after deploy)

```text
Date:
BASE_URL:
FRONTEND_URL:

verify-safety.sh:
staging-smoke.sh:

Browser login:
Paper banner:
Chat response:
```

When you share staging URLs in chat, we can re-run §7 commands and interpret output together.
