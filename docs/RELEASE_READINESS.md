# AlphaTrade AI — Synthetic staging RELEASE_READINESS

**Task:** AT-059  
**Base:** `main@c39dca6` (Phase 8 final integration, PR #100)  
**Branch:** `cursor/final_staging_readiness`  
**Safety:** Paper only. Live trading is not enabled and cannot be enabled by this change.

This report uses only verified repository and local-run evidence. Unverified
runtime facts are marked **UNKNOWN**.

---

## Cloud complete

These items are complete in-repo and can be validated in GitHub CI / this cloud
agent without Render or Vercel credentials:

| Item | Evidence |
|------|----------|
| Canonical schema deploys via `alembic upgrade head` | Single head `d4f7a2c8e901` revises `c9e2b4a1d078` revises `4fd8c1a90b27` |
| Render blueprint pins paper + Watcher/Telegram off | `render.yaml` |
| Worker `dockerCommand` is honored | `backend/docker/entrypoint.sh` execs `"$@"` before uvicorn |
| Staging/production refuse Watcher + Telegram | `deployment_safety.py` |
| Real trading impossible | `paper_safety.py` (`ENABLE_REAL_TRADING=true` permanently rejected) |
| Required env vars documented | `.env.staging.example`, `.env.production.example`, `frontend/.env.staging.example` |
| `/health` exposes paper + Watcher/Telegram posture | `HealthResponse` |
| Synthetic canonical HTTP smoke | `backend/tests/test_canonical_staging_smoke.py` |
| Remote smoke script (no exchange keys) | `scripts/canonical-staging-smoke.sh` |
| Rollback names the Phase 7/8 revision chain | `docs/deploy_rollback_runbook.md` §5.5 |
| Post-deploy gate can include canonical smoke | `INCLUDE_CANONICAL=true` or `GATE_PROFILE=extended` |

## Blocked (this cloud agent)

| Item | Why |
|------|-----|
| Staging deploy to Render | No `RENDER_API_KEY` / service credentials in this environment |
| Vercel frontend deploy | No `VERCEL_TOKEN` |
| Remote `/health` against live staging | No `BASE_URL` / staging URL in env |
| Hosted Postgres / Redis / Qdrant mutation | Connection strings unset (correct: secrets stay out of the agent) |
| Docker daemon image build | Docker engine not available in this VM (`docker_missing`) |

Do **not** treat these as product defects. They are the exact human/ops boundary.

## Laptop required

| Item | Why |
|------|-----|
| `docker compose up --build` + `./scripts/docker-validate.sh` | Needs local Docker engine |
| Optional: attach Render Postgres/Redis/Qdrant and paste secrets into the dashboard | Secrets must not be placed in git or this agent |
| iCloud handoff sync script | Mac LaunchAgent path; cloud publishes `HANDOFF.md` via GitHub instead |

## Manual required

1. Review this draft PR. **Do not merge** until the human release gate below is green.
2. Confirm Render dashboard env matches `.env.staging.example` placeholders (booleans
   only in chat). Required secrets: `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`,
   `QDRANT_API_KEY`, `JWT_SECRET`, `OPENAI_API_KEY`.
3. Confirm Vercel `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_AUTH_COOKIE_MODE=true`.
4. Authorize a paper-only staging deploy of this SHA (or of `main` after merge).
5. After deploy:  
   `BASE_URL=https://<api> FRONTEND_URL=https://<app> COOKIE_MODE=true ./scripts/post-deploy-smoke-gate.sh`  
   then `INCLUDE_CANONICAL=true` for canonical reads. Happy-path paper execution on
   staging still needs a synthetic Candidate/TradePlan seed (no HTTP mint).
6. Do not enable `WORKER_ENABLED`, Watcher, Telegram, billing, or real trading.

---

## Release gate checklist

- [ ] `EXECUTION_MODE=paper`
- [ ] `ENABLE_REAL_TRADING=false` (permanently rejected if true)
- [ ] `EXCHANGE_MODE=paper_internal` (or explicit `paper_exchange_demo` only)
- [ ] `MARKET_WATCHER_ENABLED=false`
- [ ] `MARKET_WATCHER_BRIDGE_ENABLED=false`
- [ ] `WATCHER_ORCHESTRATION_ENABLED=false`
- [ ] `TELEGRAM_ALERTS_ENABLED=false`
- [ ] `TELEGRAM_INTERACTION_ENABLED=false`
- [ ] `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false`
- [ ] `BILLING_ENABLED=false`
- [ ] Hosted `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL` (not localhost)
- [ ] `OPENAI_API_KEY` set (value never logged)
- [ ] `alembic upgrade head` → `d4f7a2c8e901`
- [ ] `/health` paper + Watcher/Telegram false
- [ ] `/health/ready` ready (or pre-approved degraded)
- [ ] `./scripts/post-deploy-smoke-gate.sh` exit 0
- [ ] `./scripts/canonical-staging-smoke.sh` exit 0
- [ ] Decision UI `/decision` shows paper chrome; no live-order controls
- [ ] Rollback runbook reviewed (`docs/deploy_rollback_runbook.md`)

---

## Required environment variables (no secrets)

### Backend staging (`render.yaml` + `.env.staging.example`)

**Pinned non-secret:** `ENVIRONMENT=staging`, `EXECUTION_MODE=paper`,
`ENABLE_REAL_TRADING=false`, `EXCHANGE_MODE=paper_internal`,
`PROVIDER_MODE=fallback`, Watcher/Telegram/scheduler/metrics flags false,
`DEMO_SEED_ENABLED=true`, cookie HTTPS settings, Redis rate-limit fail-closed.

**Operator secrets (dashboard only):** `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`,
`QDRANT_API_KEY`, `JWT_SECRET`, `OPENAI_API_KEY`.

### Frontend staging (`frontend/.env.staging.example`)

`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_NAME`, `NEXT_PUBLIC_EXECUTION_MODE=paper`,
`NEXT_PUBLIC_PROVIDER_MODE=fallback`, `NEXT_PUBLIC_AUTH_COOKIE_MODE=true`.

---

## Migrations

`preDeployCommand: alembic upgrade head` plus image entrypoint (web only) applies:

1. `4fd8c1a90b27` — canonical Candidate  
2. `c9e2b4a1d078` — ActionEligibility + canonical TradePlan  
3. `d4f7a2c8e901` — learning attribution (current head)

Worker containers skip entrypoint migrations and run `python -m app.workers.entrypoint`
(still `WORKER_ENABLED=false`).

---

## Synthetic smoke coverage

| Surface | Automated |
|---------|-----------|
| Authentication / 401 | pytest + remote script + e2e |
| Canonical Candidate reads | pytest (seeded) + remote list + e2e empty list |
| Eligibility | pytest |
| TradePlan (revision + proposal firewall) | pytest |
| Approval | pytest HTTP create + approve |
| Paper execution | pytest first ALLOW (frozen fixture clock) |
| Journal | pytest `GET /journal/trades` |
| Learning attribution | pytest `GET /canonical/learning/records/{id}` |
| Strategy statistics | pytest + e2e + remote script |
| Decision frontend | Playwright `/decision*` paper chrome + canonical API |
| Kill switch | pytest activate → paper-plan BLOCKED |
| Risk BLOCK | pytest `/risk/check` no-stop + capacity BLOCKED |
| Cross-tenant rejection | pytest 404 + remote disjoint lists |

No BloFin/live exchange credentials are used.

---

## Local validation (filled after this run)

See the pull request body and `CHANGELOG_SESSION.md` for exact commands and
exit codes from this agent run.

---

## Deploy decision

**Stop at the credential boundary.** This cloud agent cannot perform staging
deployment. After PR review, a human with Render/Vercel access can deploy
paper-only using existing configuration. Do not merge until that human accepts
the gate above.
