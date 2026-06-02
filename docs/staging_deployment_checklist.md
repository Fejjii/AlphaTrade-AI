# Staging Deployment Checklist

Copy this checklist when deploying to **Vercel + Render + managed data stores**.
**Paper-only** — real trading and live Stripe remain disabled.

> Store secrets in platform env UIs only. Never commit `.env.staging` or filled templates.

**Runbook:** [staging_deployment_runbook.md](staging_deployment_runbook.md)

---

## Record your URLs (fill after deploy)

| Item | Your value |
|------|------------|
| **Frontend URL** | `https://________________.vercel.app` |
| **Backend URL** | `https://________________.onrender.com` |

---

## 1. Platform provisioning

| Component | Recommended | Status |
|-----------|-------------|--------|
| Frontend | Vercel (`frontend/` root) | ☐ |
| Backend API | Render Docker (`backend/Dockerfile`) | ☐ |
| Postgres | Render Postgres or Neon | ☐ |
| Redis | Upstash or Render Redis | ☐ |
| Qdrant | Qdrant Cloud (or degraded RAG fallback) | ☐ |

---

## 2. Backend environment variables

Template: [`.env.staging.example`](../.env.staging.example)

| # | Variable | Required value | ☐ |
|---|----------|----------------|---|
| 1 | `ENVIRONMENT` | `staging` | ☐ |
| 2 | `EXECUTION_MODE` | `paper` | ☐ |
| 3 | `ENABLE_REAL_TRADING` | `false` | ☐ |
| 4 | `DATABASE_URL` | Managed Postgres (not localhost) | ☐ |
| 5 | `REDIS_URL` | Managed Redis (not localhost) | ☐ |
| 6 | `QDRANT_URL` | Qdrant Cloud HTTPS (not localhost) | ☐ |
| 7 | `JWT_SECRET` | 32+ byte random (not placeholder) | ☐ |
| 8 | `CORS_ORIGINS` | Exact frontend URL, `https://...` | ☐ |
| 9 | `AUTH_REFRESH_COOKIE_ENABLED` | `true` | ☐ |
| 10 | `AUTH_COOKIE_SECURE` | `true` | ☐ |
| 11 | `AUTH_COOKIE_SAMESITE` | `none` (Vercel + separate API host) | ☐ |
| 12 | `AUTH_OMIT_REFRESH_FROM_BODY` | `true` | ☐ |
| 13 | `PROVIDER_MODE` | `fallback` | ☐ |
| 14 | `BILLING_ENABLED` | `false` | ☐ |
| 15 | `MARKET_DATA_ENABLED` | `true` | ☐ |
| 16 | `OPENAI_API_KEY` | Optional (mock/fallback without) | ☐ |
| 17 | `RATE_LIMIT_USE_REDIS` | `true` | ☐ |
| 18 | `RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK` | `false` | ☐ |
| 19 | `ACCESS_TOKEN_DENYLIST_ENABLED` | `true` | ☐ |
| 20 | `ACCESS_TOKEN_DENYLIST_USE_REDIS` | `true` | ☐ |
| 21 | `LOG_JSON` | `true` (recommended) | ☐ |

Validate before deploy:

```bash
ENV_FILE=.env.staging ./scripts/check-env.sh
```

---

## 3. Frontend environment variables (Vercel)

Template: [`frontend/.env.staging.example`](../frontend/.env.staging.example)

| Variable | Required value | ☐ |
|----------|----------------|---|
| `NEXT_PUBLIC_API_URL` | Backend HTTPS URL | ☐ |
| `NEXT_PUBLIC_AUTH_COOKIE_MODE` | `true` | ☐ |
| `NEXT_PUBLIC_EXECUTION_MODE` | `paper` | ☐ |
| `NEXT_PUBLIC_PROVIDER_MODE` | `fallback` | ☐ |

Redeploy frontend after changing `NEXT_PUBLIC_*` (build-time vars).

---

## 4. Pre-deploy (local)

```bash
docker compose up --build
./scripts/docker-validate.sh
./scripts/e2e-smoke.sh
ENV_FILE=.env.staging ./scripts/check-env.sh
COOKIE_MODE=true ./scripts/staging-smoke.sh
./scripts/verify-safety.sh
```

---

## 5. Backend deploy (Render)

- [ ] Web Service from `backend/Dockerfile`
- [ ] Release command: `alembic upgrade head`
- [ ] Health check: `/health`
- [ ] All backend env vars from §2
- [ ] Deploy healthy

---

## 6. Frontend deploy (Vercel)

- [ ] Root directory: `frontend`
- [ ] Env vars from §3
- [ ] Deploy successful
- [ ] Update `CORS_ORIGINS` on backend to match Vercel URL
- [ ] Redeploy backend if CORS changed

---

## 7. Post-deploy smoke

```bash
BASE_URL=https://YOUR-API.onrender.com ./scripts/verify-safety.sh
FRONTEND_URL=https://YOUR-APP.vercel.app \
COOKIE_MODE=true \
ALLOW_DEGRADED_READY=true \
BASE_URL=https://YOUR-API.onrender.com \
./scripts/staging-smoke.sh
```

Manual:

- [ ] Browser login → workspace chat → logout
- [ ] Paper banner visible
- [ ] Provider status shows paper exchange
- [ ] No secrets in screenshots

---

## 8. Safety invariants (must pass)

| Check | Expected |
|-------|----------|
| `GET /health` → `execution_mode` | `paper` |
| `GET /health` → `real_trading_enabled` | `false` |
| `GET /providers/status` → exchange | mock / paper-only |
| `BILLING_ENABLED` | `false` |
| Startup logs | No deployment safety crash |

---

## 9. Rollback

| Layer | Action |
|-------|--------|
| Backend | Render rollback revision |
| Frontend | Vercel Instant Rollback |
| Database | Snapshot restore or safe `alembic downgrade` |

---

## Related

- [staging_deployment_runbook.md](staging_deployment_runbook.md)
- [deployment.md](deployment.md)
- [railway_deployment.md](railway_deployment.md)
- [security_checklist.md](security_checklist.md)
