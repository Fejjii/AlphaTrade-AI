# Pre-Deployment Checklist

Complete **inside Cursor / locally** before creating Render, Vercel, Upstash, or Qdrant resources.

| # | Item | How to verify | Done |
|---|------|---------------|------|
| 1 | GitHub repo pushed | `git status` clean; `main` on remote | ☐ |
| 2 | Release exists | GitHub Releases or tag `v0.1.0-paper-mvp` (optional) | ☐ |
| 3 | Docker validation passed locally | `docker compose up --build -d` + `./scripts/docker-validate.sh` | ☐ |
| 4 | Staging env vars prepared | Copy `.env.staging.example` → `.env.staging` (gitignored) | ☐ |
| 5 | Worksheet copied | `cp docs/staging_deployment_worksheet.template.md docs/staging_deployment_worksheet.local.md` | ☐ |
| 6 | Render Postgres planned | Account ready; know region | ☐ |
| 7 | Redis provider planned | Upstash or Render Redis | ☐ |
| 8 | Qdrant decision made | Cloud cluster **or** empty `QDRANT_URL` on staging | ☐ |
| 9 | Backend deploy command known | Docker `backend/Dockerfile`; pre-deploy `alembic upgrade head` | ☐ |
| 10 | Migration command known | `alembic upgrade head` or `./scripts/run-migrations.sh` | ☐ |
| 11 | Frontend deploy command known | Vercel root `frontend`; `npm run build` | ☐ |
| 12 | CORS configured (plan) | `CORS_ORIGINS` = exact Vercel HTTPS URL | ☐ |
| 13 | Cookie settings configured (plan) | `AUTH_*` + `NEXT_PUBLIC_AUTH_COOKIE_MODE=true` | ☐ |
| 14 | Safety scripts ready | `./scripts/verify-safety.sh` executable | ☐ |
| 15 | Smoke scripts ready | `./scripts/staging-smoke.sh` + `./scripts/post-deploy-smoke-gate.sh` executable | ☐ |
| 15b | Rollback runbook reviewed | `docs/deploy_rollback_runbook.md` (AT-005) | ☐ |
| 16 | Real trading disabled | `ENABLE_REAL_TRADING=false`, `EXECUTION_MODE=paper` | ☐ |
| 17 | Billing disabled | `BILLING_ENABLED=false` | ☐ |

## Local validation commands

```bash
ENV_FILE=.env.staging ./scripts/check-env.sh   # after filling .env.staging
cd backend && uv run pytest
cd frontend && npm run test && npm run build
```

See [deployment_command_pack.md](deployment_command_pack.md) for full command list.

## After cloud accounts exist

Continue with [staging_execution_checklist.md](staging_execution_checklist.md) and [staging_live_deployment_notes.md](staging_live_deployment_notes.md).
