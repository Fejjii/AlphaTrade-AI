# Workflow: RELEASE / DEPLOY validation

> Authoritative rules: `.ai/MASTER_WORKFLOW.md`. Only commit/push/deploy when the task explicitly
> authorizes it; otherwise stop at `REVIEW_REQUIRED` before the protected action.

## Pre-commit gate
```
# backend/
uv run ruff check .
uv run ruff format --check .
uv run pytest
# frontend/
npm run lint && npm run typecheck && npm run test && npm run build
```
- Inspect `git status` and full diff; confirm every changed file is intentional.
- Secret scan the diff; confirm no secrets, keys, or private URLs.
- Confirm `render.yaml` preserves paper-safe values: `PROVIDER_MODE=fallback`,
  `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `EXCHANGE_MODE=paper_internal`.

## Deploy validation (staging, paper-only)
- `ENV_FILE=.env.staging ./scripts/check-env.sh`
- `BASE_URL=<api> ./scripts/post-deploy-smoke-gate.sh` (AT-005 mandatory gate; exit 0)
- On gate exit 1 → follow `docs/deploy_rollback_runbook.md` before further work
- `BASE_URL=<api> ./scripts/verify-safety.sh` (included in the gate; may run alone)
- `BACKEND_URL=<api> ./scripts/validate-exchange-demo-staging.sh`
- Confirm `/health`, `/health/ready`, `/openapi.json`, `/providers/status`.
- Confirm providers remain mock until an operator manually configures keys.
- Never enable real trading during deploy or rollback.

## Handoff (mandatory end of task)
1. Regenerate `HANDOFF.md` + `CHANGELOG_SESSION.md` from the `.ai/` templates; set the correct
   status (`READY`, or `REVIEW_REQUIRED`/`BLOCKED`/`FAILED` as applicable — never `DRAFT`).
2. Recompute the normalized `Source File SHA256` (hash of each doc with its own
   `Source File SHA256:` line removed) and write it back.
3. Run `~/.local/bin/sync-alphatrade-ai-handoff.sh`.
4. Verify the iCloud destination matches source via SHA256 **and** `cmp`/`diff`; confirm exit
   status 0. Sync immediately on any blocker/review/failure — never wait for task end.
