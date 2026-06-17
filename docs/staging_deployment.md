# Staging Deployment (Slice 48)

Public staging for **AlphaTrade AI** — paper-only execution, no live trading, no live Stripe.
This document records live URLs, Vercel/Render configuration, smoke commands, browser demo flow,
and known gaps after Slice 48 QA (baseline commit `b4c30d0`).

> **Never commit secrets.** Store credentials only in Render / Vercel / Upstash dashboards.

---

## Live URLs (Slice 48)

| Service | URL | Status (2026-06-18) |
|---------|-----|---------------------|
| **Backend API** | https://alphatrade-api-staging.onrender.com | Live — paper mode, API smoke OK |
| **Frontend (production alias)** | https://alpha-trade-ai-eight.vercel.app | **Next.js app** — `/login` 200, API URL baked in |
| **Frontend (git-main alias)** | https://alpha-trade-ai-git-main-alphatrade-ai.vercel.app | Same deployment family |
| **Blocked / wrong** | https://alpha-trade-ai.vercel.app | Unrelated Vite placeholder (`Your Project`) — **do not use** |
| **Legacy / wrong** | https://alphatrade-ai.vercel.app | Unrelated static app — **do not use** |

`https://alpha-trade-ai.vercel.app` is owned by another Vercel account and cannot be aliased to this project. Use **`alpha-trade-ai-eight.vercel.app`** for demos until that domain is reclaimed.

---

## Vercel project configuration (alpha-trade-ai)

Verified via Vercel CLI (Slice 48):

| Setting | Value |
|---------|--------|
| Root Directory | `frontend` |
| Framework | Next.js 15 (detected at build) |
| Build Command | `npm run build` |
| Install Command | `npm ci` |
| Output Directory | `.next` (via `frontend/vercel.json`) |
| Production Branch | `main` |

### Frontend environment variables (Production + Preview)

| Variable | Value |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | `https://alphatrade-api-staging.onrender.com` |
| `NEXT_PUBLIC_AUTH_COOKIE_MODE` | `true` |
| `NEXT_PUBLIC_EXECUTION_MODE` | `paper` |
| `NEXT_PUBLIC_PROVIDER_MODE` | `fallback` |
| `NEXT_PUBLIC_APP_NAME` | `AlphaTrade AI` |

Templates: [`frontend/.env.staging.example`](../frontend/.env.staging.example)

Redeploy after changing `NEXT_PUBLIC_*` (build-time vars):

```bash
npx vercel link --yes --project alpha-trade-ai
npx vercel --prod --yes
```

---

## Render backend environment (alphatrade-api-staging)

Apply in Render Dashboard → **Environment** → **Save** → **Manual Deploy**.

| Variable | Required staging value |
|----------|------------------------|
| `ENVIRONMENT` | `staging` |
| `EXECUTION_MODE` | `paper` |
| `ENABLE_REAL_TRADING` | `false` |
| `CORS_ORIGINS` | `https://alpha-trade-ai-eight.vercel.app,https://alpha-trade-ai-alphatrade-ai.vercel.app,https://alpha-trade-ai-git-main-alphatrade-ai.vercel.app` |
| `BILLING_ENABLED` | `false` |
| `PROVIDER_MODE` | `fallback` |
| `ALERT_DELIVERY_ENABLED` | `false` |
| `ALERT_WEBHOOK_ENABLED` | `false` |
| `TELEGRAM_ALERTS_ENABLED` | `false` |
| `EMAIL_PROVIDER` | `mock` |
| `MARKET_WATCHER_ENABLED` | `false` |
| `MARKET_WATCHER_BRIDGE_ENABLED` | `false` |
| `REQUIRE_EMAIL_VERIFIED` | `false` (frictionless demo login) |
| `RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK` | `true` (when Redis URL invalid) |
| `REDIS_URL` | Valid `rediss://...` (Upstash/Render) **or** fix/clear invalid scheme |
| `QDRANT_URL` | Reachable HTTPS endpoint **or** empty (in-memory RAG fallback) |

Blueprint defaults: [`render.yaml`](../render.yaml) · template: [`.env.staging.example`](../.env.staging.example)

Validate locally before saving platform env:

```bash
ENV_FILE=.env.staging ./scripts/check-env.sh
```

---

## Redeploy

### Backend (Render)

1. Render Dashboard → **alphatrade-api-staging** → branch **`main`**
2. Set env vars from table above (especially `CORS_ORIGINS`, `ENVIRONMENT=staging`)
3. **Manual Deploy** → Deploy latest commit
4. Pre-deploy: `alembic upgrade head` · health path: `/health`

### Frontend (Vercel)

1. Confirm Root Directory = `frontend` (already set)
2. Confirm env vars from table above
3. `npx vercel --prod --yes` from repo root (linked project)
4. Use production alias URL in docs and Render `CORS_ORIGINS`

---

## Live smoke checklist

```bash
# Safety only
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/verify-safety.sh

# Full auth + chat + cookie mode
FRONTEND_URL=https://alpha-trade-ai-eight.vercel.app \
COOKIE_MODE=true \
ALLOW_DEGRADED_READY=true \
BACKEND_URL=https://alphatrade-api-staging.onrender.com \
./scripts/staging-smoke.sh

# Slice 48 extended live smoke
FRONTEND_URL=https://alpha-trade-ai-eight.vercel.app \
BACKEND_URL=https://alphatrade-api-staging.onrender.com \
COOKIE_MODE=true \
./scripts/staging-live-smoke.sh

# Focused smokes
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/notifications-smoke.sh
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/market-watcher-smoke.sh
```

**Expected backend invariants:**

- `GET /health` → `execution_mode: paper`, `real_trading_enabled: false`
- `GET /providers/status` → exchange mock/paper-only, billing mock/disabled
- Authenticated routes return paper-only safety fields

**Slice 48 live results:**

| Check | Result |
|-------|--------|
| `/health` | OK — paper, real trading off (`environment` still `local` until Render env updated) |
| `/health/ready` | OK |
| `verify-safety.sh` | Passed |
| `staging-live-smoke.sh` | Passed (API routes); CORS preflight **WARN HTTP 400** until Render `CORS_ORIGINS` redeploy |
| Frontend `/` + `/login` | OK on `alpha-trade-ai-eight.vercel.app` (Next.js) |
| Frontend `alpha-trade-ai.vercel.app` | Wrong placeholder app — blocked domain |
| `notifications-smoke.sh` | Passed — external delivery disabled |
| `market-watcher-smoke.sh` | Passed — watcher/bridge env off |

---

## Browser demo checklist (staging)

Open **https://alpha-trade-ai-eight.vercel.app**

1. Register or log in (`REQUIRE_EMAIL_VERIFIED=false` on backend recommended)
2. Confirm **Paper mode active** and **Real trading disabled** badges
3. Dashboard → Today's discipline, workflow stepper
4. Risk Settings → limits and save
5. Strategy Lab → backtest / paper eligibility
6. Paper Validation → scan/tick (simulated)
7. Market Watcher → manual scan (env off = safe status)
8. Alerts → delivery summary; external skipped
9. Notifications Settings → webhook/Telegram off; test notification safe
10. Lessons → pending / accept flow
11. AI Workspace → read-only question; mutation requires confirmation
12. Confirm no real trade path

**Blocked until Render CORS fix:** cross-origin API calls from the browser (register/login/dashboard) will fail with CORS 400 until `CORS_ORIGINS` includes the Vercel alias and backend is redeployed.

**CORS / auth cookie checks (after Render redeploy):**

- OPTIONS preflight returns 200/204 (not 400)
- Register/login from browser works
- Authenticated requests persist across page refresh (httpOnly refresh cookie)
- Logout clears session
- No mixed content; API URL is `https://alphatrade-api-staging.onrender.com` (not localhost)

---

## Notification safety (external delivery off)

- Preferences show webhook/Telegram disabled
- Test notification skips external with clear reason
- No Telegram/webhook calls when `ALERT_DELIVERY_ENABLED=false`
- Alerts page shows skipped/disabled counts; `paper_only: true`

---

## Known staging limitations (Slice 48)

| Gap | Impact | Fix |
|-----|--------|-----|
| `ENVIRONMENT=local` on live API | Misleading health metadata | Set `ENVIRONMENT=staging` on Render |
| `CORS_ORIGINS` not set to Vercel alias | Browser API calls fail (OPTIONS 400) | Apply Render env table above, redeploy |
| `alpha-trade-ai.vercel.app` blocked | Intended short URL unavailable | Use `alpha-trade-ai-eight.vercel.app`; reclaim domain separately |
| `REDIS_URL` invalid scheme | In-memory rate-limit fallback | Use `rediss://...` or enable `RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK=true` |
| Qdrant unreachable | In-memory vector fallback | Fix `QDRANT_URL` or leave empty |
| Preview deploy SSO | Automated preview checks blocked | Use production alias for smoke |
| Browser demo | Blocked on CORS until Render redeploy | Manual Render env update required |

**Real trading remains disabled.** All execution is paper-only.

---

## Notification provider defaults

| Provider | Default | Notes |
|----------|---------|-------|
| In-app alerts | Enabled | Always safe |
| Webhook | Off | `ALERT_WEBHOOK_ENABLED=false` |
| Telegram | Off | `TELEGRAM_ALERTS_ENABLED=false` |
| Email | Mock | `EMAIL_PROVIDER=mock` |
| External master | Off | `ALERT_DELIVERY_ENABLED=false` |

See [notifications.md](notifications.md) and [alerts.md](alerts.md).

---

## Related docs

- [staging_deployment_runbook.md](staging_deployment_runbook.md) — full provisioning steps
- [staging_deployment_checklist.md](staging_deployment_checklist.md) — env sign-off
- [staging_execution_checklist.md](staging_execution_checklist.md) — manual click order
- [deployment_command_pack.md](deployment_command_pack.md) — copy-paste commands
- [demo_script.md](demo_script.md) — portfolio walkthrough
- [limitations_roadmap.md](limitations_roadmap.md) — scope boundaries
