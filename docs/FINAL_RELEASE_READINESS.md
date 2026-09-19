# FINAL_RELEASE_READINESS

Paper-release candidate: `cursor/final_release_integration-c461`  
Draft PR: https://github.com/Fejjii/AlphaTrade-AI/pull/104  
Do not merge. Do not deploy from this agent.

## BLOCKERS

None.

## LAPTOP REQUIRED

- Local Docker engine for `docker compose up --build` and `./scripts/docker-validate.sh`. This cloud VM has no Docker daemon. GitHub CI `docker-build` on run [35466201940](https://github.com/Fejjii/AlphaTrade-AI/actions/runs/35466201940) succeeded.
- Mac iCloud handoff LaunchAgent path. Cloud publishes `HANDOFF.md` via GitHub instead.
- Optional WebKit / iPhone Playwright projects. Chromium e2e is complete (24 passed / 13 skipped).

## CLOUD CREDENTIAL REQUIRED

- Render deploy credentials (`RENDER_API_KEY` / service dashboard). Absent here.
- Vercel deploy token. Absent here.
- Staging operator secrets in the dashboard only (never git): `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `JWT_SECRET`, `OPENAI_API_KEY`.
- Live staging `BASE_URL` / `FRONTEND_URL` for `./scripts/post-deploy-smoke-gate.sh` and `./scripts/canonical-staging-smoke.sh` after an authorized paper-only deploy.

No real exchange credentials are required for this candidate.

## OPTIONAL POST RELEASE

- Human review of draft PR #104, then merge to `main` if desired. Not part of this task.
- Paper-only staging deploy after credentials exist. Keep Watcher, Telegram, billing, and real trading off.
- Canonical HTTP mint remains out of scope; synthetic smoke seeds via existing services.
- Mode D / live execution remains a separate, explicitly authorized safety program.

## FINAL VERDICT

READY FOR STAGING DEPLOYMENT
