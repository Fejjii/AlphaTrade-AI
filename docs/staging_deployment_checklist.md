# Staging Deployment Checklist

Use this checklist before deploying AlphaTrade AI to a **managed staging environment**
(Vercel frontend + Render/Railway backend). **Paper-only execution** — real trading
remains disabled.

> Do not commit filled `.env` files. Store secrets in platform env / secret stores only.

---

## 1. Platform provisioning

| Component | Recommended | Notes |
|-----------|-------------|-------|
| Frontend | [Vercel](https://vercel.com) | Root dir: `frontend` |
| Backend API | [Render](https://render.com) or [Railway](https://railway.app) | Docker: `backend/Dockerfile` |
| Postgres | Render / Railway / Neon / Supabase | Required |
| Redis | Render / Upstash / Railway | Required for rate limits + denylist |
| Qdrant | [Qdrant Cloud](https://cloud.qdrant.io) | RAG vectors; fallback if unreachable |

---

## 2. Required environment variables

Copy from [`.env.staging.example`](../.env.staging.example) and
[`frontend/.env.staging.example`](../frontend/.env.staging.example).

### Backend (Render / Railway)

| Variable | Required | Staging value |
|----------|----------|---------------|
| `ENVIRONMENT` | Yes | `staging` |
| `EXECUTION_MODE` | Yes | `paper` |
| `ENABLE_REAL_TRADING` | Yes | `false` |
| `DATABASE_URL` | Yes | Managed Postgres URL (not localhost) |
| `REDIS_URL` | Yes | Managed Redis URL (not localhost) |
| `QDRANT_URL` | Yes | Hosted Qdrant URL (not localhost) |
| `JWT_SECRET` | Yes | 32+ byte random secret |
| `CORS_ORIGINS` | Yes | Exact Vercel URL, e.g. `https://your-app.vercel.app` |
| `AUTH_REFRESH_COOKIE_ENABLED` | Yes | `true` |
| `AUTH_COOKIE_SECURE` | Yes | `true` |
| `AUTH_COOKIE_SAMESITE` | Yes | `none` (cross-domain Vercel + API) |
| `AUTH_OMIT_REFRESH_FROM_BODY` | Yes | `true` |
| `ACCESS_TOKEN_DENYLIST_ENABLED` | Yes | `true` |
| `ACCESS_TOKEN_DENYLIST_USE_REDIS` | Yes | `true` |
| `RATE_LIMIT_USE_REDIS` | Yes | `true` |
| `RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK` | Yes | `false` |
| `PROVIDER_MODE` | Yes | `fallback` |
| `BILLING_ENABLED` | Yes | `false` (until Stripe live wiring approved) |
| `OPENAI_API_KEY` | Optional | Enables real LLM/embeddings with fallback |
| `QDRANT_API_KEY` | Optional | If Qdrant Cloud requires API key |
| `LOG_JSON` | Recommended | `true` |

### Frontend (Vercel)

| Variable | Required | Staging value |
|----------|----------|---------------|
| `NEXT_PUBLIC_API_URL` | Yes | HTTPS backend URL |
| `NEXT_PUBLIC_AUTH_COOKIE_MODE` | Yes | `true` |
| `NEXT_PUBLIC_EXECUTION_MODE` | Yes | `paper` |
| `NEXT_PUBLIC_PROVIDER_MODE` | Recommended | `fallback` |

---

## 3. Pre-deploy validation (local)

Run from repo root after filling a **local copy** of staging env (never commit):

```bash
# Validate env against deployment_safety rules
ENV_FILE=.env.staging ./scripts/check-env.sh

# Full local Docker stack (production simulation)
docker compose up --build
./scripts/docker-validate.sh
./scripts/e2e-smoke.sh
./scripts/staging-smoke.sh
./scripts/verify-safety.sh
```

---

## 4. Backend deploy steps (Render example)

1. Create **Web Service** from repo; Dockerfile path `backend/Dockerfile`.
2. Set **Release command**: `alembic upgrade head` (or use entrypoint migrations).
3. Paste backend env vars from section 2.
4. Health check: `/health` (liveness), optional `/health/ready` (readiness).
5. Deploy and wait for healthy status.

### Migrations (manual / CI)

```bash
DATABASE_URL='postgresql+psycopg://...' ./scripts/run-migrations.sh
```

---

## 5. Frontend deploy steps (Vercel)

1. Import repo; root directory `frontend`.
2. Set env vars from section 2 (Production + Preview).
3. Deploy.
4. Update backend `CORS_ORIGINS` to match deployed Vercel URL exactly.
5. Redeploy backend if CORS changed.

---

## 6. Post-deploy validation

Replace `BASE_URL` with your staging API URL:

```bash
BASE_URL=https://your-api.onrender.com ./scripts/staging-smoke.sh
BASE_URL=https://your-api.onrender.com ./scripts/verify-safety.sh
```

Manual browser checks:

- [ ] Login → dashboard → logout (refresh cookie on API domain)
- [ ] Paper mode banner visible
- [ ] Provider status shows exchange paper-only
- [ ] Chat message returns structured response
- [ ] No secrets in browser devtools or screenshots

---

## 7. Safety invariants (must pass)

| Check | Expected |
|-------|----------|
| `GET /health` → `execution_mode` | `paper` |
| `GET /health` → `real_trading_enabled` | `false` |
| `GET /providers/status` → exchange | mock / paper-only |
| `BILLING_ENABLED` | `false` unless explicitly approved later |
| Startup | No `deployment_safety` crash |

---

## 8. Rollback

| Layer | Action |
|-------|--------|
| Backend | Revert Render/Railway revision |
| Frontend | Vercel Instant Rollback |
| Database | `alembic downgrade -1` if safe; else restore snapshot |

---

## Related docs

- [deployment.md](deployment.md) — full architecture and troubleshooting
- [security_checklist.md](security_checklist.md)
- [demo_script.md](demo_script.md)
