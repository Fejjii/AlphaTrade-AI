# Workflow: RELEASE / DEPLOY validation

> Only commit/push/deploy when the task explicitly authorizes it.

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
- `BASE_URL=<api> ./scripts/verify-safety.sh`
- `BACKEND_URL=<api> ./scripts/validate-exchange-demo-staging.sh`
- Confirm `/health`, `/health/ready`, `/openapi.json`, `/providers/status`.
- Confirm providers remain mock until an operator manually configures keys.

## Handoff (mandatory end of task)
1. Regenerate `HANDOFF.md` + `CHANGELOG_SESSION.md` (update metadata only on material change).
2. Run `~/.local/bin/sync-alphatrade-ai-handoff.sh`.
3. Verify iCloud destination SHA256 matches source; confirm exit status 0.
