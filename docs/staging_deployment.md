# Staging Deployment (Slice 47)

Public staging for **AlphaTrade AI** — paper-only execution, no live trading, no live Stripe.
This document records live URLs, required safe environment flags, smoke commands, demo flow,
and known gaps after Slice 47 QA (baseline commit `28873f1`).

> **Never commit secrets.** Store credentials only in Render / Vercel / Upstash dashboards.

---

## Live URLs (Slice 47)

| Service | URL | Status (2026-06-17) |
|---------|-----|---------------------|
| **Backend API** | https://alphatrade-api-staging.onrender.com | Live — health OK, paper mode |
| **Frontend (intended)** | https://alpha-trade-ai.vercel.app | Deployed from `main` but **not serving Next.js app** — see gaps below |
| **Legacy / wrong host** | https://alphatrade-ai.vercel.app | Unrelated static app (“AlphaTrade AI Analyzer”) — **do not use for demo** |

GitHub shows Vercel production deploy for commit `28873f1` (2026-06-17). Preview URLs may require Vercel SSO.

---

## Required safe environment flags (backend)

These must be set on Render before any demo. Defaults in code are safe; staging should set explicitly.

| Variable | Required staging value |
|----------|------------------------|
| `ENVIRONMENT` | `staging` |
| `EXECUTION_MODE` | `paper` |
| `ENABLE_REAL_TRADING` | `false` |
| `BILLING_ENABLED` | `false` |
| `PROVIDER_MODE` | `fallback` |
| `ALERT_DELIVERY_ENABLED` | `false` (unless testing with safe test webhook) |
| `ALERT_WEBHOOK_ENABLED` | `false` |
| `TELEGRAM_ALERTS_ENABLED` | `false` |
| `MARKET_WATCHER_ENABLED` | `false` (manual scan API still works when env off) |
| `MARKET_WATCHER_BRIDGE_ENABLED` | `false` |
| `EMAIL_PROVIDER` | `mock` |

Frontend (Vercel, when correctly configured):

| Variable | Value |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | Backend URL above |
| `NEXT_PUBLIC_AUTH_COOKIE_MODE` | `true` |
| `NEXT_PUBLIC_EXECUTION_MODE` | `paper` |
| `NEXT_PUBLIC_PROVIDER_MODE` | `fallback` |

Templates: [`.env.staging.example`](../.env.staging.example), [`frontend/.env.staging.example`](../frontend/.env.staging.example)

Validate locally before saving platform env:

```bash
ENV_FILE=.env.staging ./scripts/check-env.sh
```

---

## Redeploy

### Backend (Render)

1. Render Dashboard → **alphatrade-api-staging** → confirm branch **`main`**
2. **Manual Deploy** → Deploy latest commit
3. Confirm pre-deploy: `alembic upgrade head`
4. Health check path: `/health`

Optional blueprint: [`render.yaml`](../render.yaml)

### Frontend (Vercel)

1. Vercel Dashboard → project → **Settings → General → Root Directory** = **`frontend`**
2. Framework: Next.js 15
3. Set env vars from table above
4. Redeploy production from **`main`**
5. Copy production URL → update Render `CORS_ORIGINS` → redeploy backend

---

## Live smoke checklist

Replace URLs if your deployment differs.

```bash
# Safety only
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/verify-safety.sh

# Full auth + chat + cookie mode
FRONTEND_URL=https://alpha-trade-ai.vercel.app \
COOKIE_MODE=true \
ALLOW_DEGRADED_READY=true \
BACKEND_URL=https://alphatrade-api-staging.onrender.com \
./scripts/staging-smoke.sh

# Slice 47 extended live smoke (dashboard, risk, notifications, market watcher)
FRONTEND_URL=https://alpha-trade-ai.vercel.app \
BACKEND_URL=https://alphatrade-api-staging.onrender.com \
./scripts/staging-live-smoke.sh

# Focused smokes
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/notifications-smoke.sh
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/market-watcher-smoke.sh
```

**Expected backend invariants:**

- `GET /health` → `execution_mode: paper`, `real_trading_enabled: false`
- `GET /providers/status` → exchange mock/paper-only, billing mock/disabled
- Authenticated routes return paper-only safety fields

**Slice 47 live results (backend):**

| Check | Result |
|-------|--------|
| `/health` | OK — paper, real trading off |
| `/health/ready` | OK — ready (Qdrant/Redis may use fallback) |
| `verify-safety.sh` | Passed |
| `staging-smoke.sh` | Passed (auth, chat, cookie refresh) |
| `staging-live-smoke.sh` | Passed (dashboard, risk, notifications, watcher) |
| `notifications-smoke.sh` | Passed — external delivery disabled |
| `market-watcher-smoke.sh` | Passed — watcher/bridge env off, paper only |

---

## Demo flow (staging)

Use [demo_script.md](demo_script.md) with these staging notes:

1. Register or log in (set `REQUIRE_EMAIL_VERIFIED=false` on staging for frictionless demo login, or verify email)
2. Confirm **Paper mode active** and **Real trading disabled** badges
3. Dashboard → Today's discipline, workflow stepper, next action
4. Risk Settings → show limits and save
5. Strategy Lab → backtest / paper eligibility status
6. Paper Validation → scan/tick (simulated only)
7. Market Watcher → manual scan (env disabled = safe no-op with clear status)
8. Alerts → delivery summary; external channels skipped
9. Notifications Settings → webhook/Telegram off; test notification skips external delivery
10. Lessons → pending / accept flow
11. AI Workspace → read-only question; mutation requires confirmation
12. Confirm no real trade path exists

**Notification safety (external delivery off):**

- Preferences show webhook/Telegram disabled
- Test notification creates in-app path or skips external with clear reason
- No Telegram/webhook calls when `ALERT_DELIVERY_ENABLED=false`
- Alerts page shows skipped/disabled counts

---

## Known staging limitations (Slice 47)

| Gap | Impact | Fix |
|-----|--------|-----|
| `ENVIRONMENT=local` on live API | Misleading health metadata | Set `ENVIRONMENT=staging` on Render |
| `REDIS_URL` scheme invalid | In-memory rate-limit fallback | Use Upstash `rediss://...` URL |
| Qdrant unreachable | In-memory vector fallback | Fix `QDRANT_URL` or leave empty |
| CORS preflight HTTP 400 | Browser may fail cross-origin | Set exact Vercel URL in `CORS_ORIGINS`, redeploy |
| Vercel not serving Next.js | Demo UI unavailable at production URL | Root Directory = `frontend`, rebuild |
| `alphatrade-ai.vercel.app` | Wrong legacy app | Use correct Vercel project URL only |
| Intermittent register 500 | Smoke flakes under load | Retry; check Postgres connection on Render |
| Preview deploy SSO | Automated frontend checks blocked | Disable protection for staging or use production URL |

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
