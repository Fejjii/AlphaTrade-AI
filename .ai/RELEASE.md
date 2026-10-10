# Workflow: RELEASE / DEPLOY validation

> Authoritative rules: `.ai/MASTER_WORKFLOW.md`. Only commit/push/deploy when the task explicitly
> authorizes it; otherwise stop at `REVIEW_REQUIRED` before the protected action.

## Development checks
```
# backend/
uv run ruff check .
uv run ruff format --check .
# Run tests relevant to the changed behavior (not the complete suite each iteration).
uv run pytest tests/<affected-test>.py
# frontend/
npm run lint && npm run typecheck
npx vitest run <affected-test-files>
# Full frontend unit/build/browser validation requires an explicit combined request.
```
- Inspect `git status` and full diff; confirm every changed file is intentional.
- Secret scan the diff; confirm no secrets, keys, or private URLs.
- Confirm `render.yaml` preserves paper-safe values: `PROVIDER_MODE=fallback`,
  `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `EXCHANGE_MODE=paper_internal`,
  Watcher/Telegram flags `false`.

Ordinary push/PR CI keeps the six existing job names and required development quality
checks. PR runs for the same PR cancel superseded runs; main/master pushes and manual
runs have separate concurrency groups and are not cancelled by PR updates. Read-only
workflow permissions and job timeouts bound routine execution.
Backend pytest runs `scripts/run_backend_focused.py`: a small config/deployment/
workflow baseline, changed backend test files, matching module test names and an
explicit SFP/receipt/logging regression group for those paths. This is a development
selection, not exhaustive dependency analysis. For other cross-module changes,
include their focused tests explicitly in the PR; the complete gate below remains
required. A successful focused run is **not complete backend acceptance**.
Native activity/schema/client changes include scoped provider, account and migration
regressions. `BLOFIN_ACTIVITY_TEST_POSTGRES_URL` uses the existing disposable CI
PostgreSQL service so the activity durability/migration cases actually execute.

The frontend keeps generated drift, lint and type checks, then runs
`scripts/run_frontend_focused.py`: contract/cache baselines, changed tests and
module/domain neighbors, including Agent/API/account boundaries. This heuristic is
not exhaustive dependency analysis; owners must record focused local checks for their
actual changes. Preserve backend, frontend and deployment-safety merge checks and
failure propagation. No branch-protection settings are changed by this policy.

Expensive combined validation is manual only: full frontend unit/build, deterministic
evaluations, Docker build and production-browser smoke. Their jobs/steps are skipped
on routine events, and those skips do **not** establish acceptance. Both manual
booleans default to false; `full_backend=true` also enables combined validation.
Only when explicitly requested, run development combined validation with:

```sh
gh workflow run ci.yml --ref <reviewed-ref> -f combined_validation=true -f full_backend=false
```

This still uses the focused backend selection and is not the full release gate.
Manual development selection compares the branch to its `origin/main` merge base,
so a final evidence-only commit cannot omit the accumulated feature changes.
Do not repeat green runs merely to show progress. Record the exact tested SHA,
selected tests, failures and skips; batch related fixes before pushing. Cancel older
active PR runs where authorized access permits. Never cancel the current release
acceptance run as a development cost measure.

## Final consolidated release acceptance

After supervising review, consolidated staging deployment and fresh SFP diagnostics/
evaluations, dispatch **one** complete CI run on the exact reviewed release ref:

```sh
gh workflow run ci.yml --ref <reviewed-release-ref> -f full_backend=true
```

The Actions UI exposes the same `full_backend` boolean, defaulting to false for
manual dispatch. Ordinary push/PR events always use development mode. A manual false
value without `combined_validation=true` requests development checks only. Do not dispatch a full run during routine
implementation or call a focused green check the complete release gate.

The full dispatch runs unfiltered `uv run pytest` with PostgreSQL and all existing
Ruff, frontend lint/type/unit/build, deployment-safety, Docker build, deterministic
Agent/RAG/guardrail evaluation and Playwright browser smoke checks. Record the run
URL, exact `head_sha`, full backend counts/skips and successful results for all
six jobs. Failed, skipped or cancelled evaluation/browser jobs do not establish
acceptance. Investigate skips and do not attribute counts from another commit.
If the reviewed commit changes, its earlier full result is not final acceptance.

No branch protection configuration, credentials, deployment or activation settings
change through this workflow. Demo stays disarmed and real trading stays disabled.
Live acceptance remains supervised; local/mock checks do not prove it.

## Deploy validation (staging, paper-only)
- `ENV_FILE=.env.staging ./scripts/check-env.sh`
- `BASE_URL=<api> ./scripts/post-deploy-smoke-gate.sh` (AT-005 mandatory gate; exit 0)
- Canonical path: `INCLUDE_CANONICAL=true BASE_URL=<api> ./scripts/post-deploy-smoke-gate.sh`
  or `BASE_URL=<api> ./scripts/canonical-staging-smoke.sh`
- On gate exit 1 → follow `docs/deploy_rollback_runbook.md` before further work
- `BASE_URL=<api> ./scripts/verify-safety.sh` (included in the gate; may run alone)
- `BACKEND_URL=<api> ./scripts/validate-exchange-demo-staging.sh`
- Confirm `/health` paper posture, `real_trading_enabled=false`, Watcher/Telegram false.
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
