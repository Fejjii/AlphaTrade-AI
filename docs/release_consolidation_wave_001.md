# AlphaTrade release consolidation wave 001

Prepared on 2026-10-01 (Europe/Berlin) on `codex/release_consolidation_wave_001`.
The branch starts exactly at PR150 head
`830f8c29c085baa21e51c278a0643903b1eab018`.
PR150 already contains PR153 Strategy Brain at
`79b76d6313c7d1a269a9e32d67f89e39eca9df96`; that history is inherited once.

## Included work

Only unique commits after the common PR153 ancestor were cherry-picked with
source provenance (`git cherry-pick -x`). No source branch was modified.

| PR | Accepted work | Exact source head | Unique commits |
| --- | --- | --- | --- |
| #154 | MVP release readiness | `2672295aabfa0eb8360b5febc098057510ae3100` | 1 |
| #155 | Nested informational Telegram alerts | `558af78fc1ef36d0d0f857945813bf539b82c168` | 1 |
| #156 | Strategy Analytics foundation | `5494f6d4e00faed6518edd09738d20aad75802f0` | 1 |
| #157 | Trader UI polish | `94954e7d243be0c03ce667403964adb6e4e2b850` | 3 |
| #158 | SFP detector foundation | `ad08031229899e3299830a9767a2ca39ff5cb9b6` | 1 |

PR157's three source commits are `a05d5c1024996bb01ba9478f3dddb0ce0dd881a0`,
`061a07b04f2afe367dff5e2d71ce65aff65363a7`, and its exact source head above.
PR159 is excluded. No accepted feature was redesigned.

## Conflicts and safety

All seven unique commits applied without conflicts. The consolidation adds this
release record, updates the current handoff, and removes five inherited Markdown
trailing spaces from `docs/trader_interface_polish_handoff.md`.
Accepted implementation files remain byte-for-byte identical to their source
branches.

Paper execution remains the only supported execution path; real trading remains
disabled. Existing risk, Candidate, journal, and Agent authority are preserved.
Five-symbol Watcher configuration and tenant/freshness fences remain intact.
Nested alerts use the existing canonical gateway and outbox, stay informational,
and do not introduce action confirmations. No activation flag changed.

Strategy Analytics remains a service-only read of the canonical journal. SFP
remains isolated causal research, with no new compiler, Watcher, Candidate, risk,
execution, or Telegram registration. Its documented future integration is outside
this consolidation. No schema change was introduced; the single Alembic head
remains `a1brain001`.

## Focused validation

397 backend tests and 51 frontend tests passed. The entire suite was not run.

- Foundations: 206 passed across `test_mvp_readiness_smoke.py`,
  `test_nested_candidate_alerts.py`, `test_strategy_analytics_foundation.py`,
  `test_performance.py`, `test_sfp_detector.py`, `test_strategy_brain_nested.py`,
  `test_at067_canonical_strategy_evaluation_policy.py`, and
  `test_interactive_agent_foundation.py`. Three PostgreSQL cases were selected
  separately below.
- Safety and integration regressions: 186 passed across
  `test_phase6_candidate_telegram_alerts.py`, `test_telegram_paper_agent.py`,
  `test_watcher_five_symbol_watchlist.py`, `test_watcher_tenant_watchlist.py`,
  `test_watcher_paper_activation.py`, `test_watcher_watchlist_migration.py`, and
  `test_deployment_safety.py`. One PostgreSQL case was selected separately below.
- Disposable PostgreSQL 16: five passed with zero skips, covering confirmed
  Nested Candidate/paper execution/journal/replay, forming setup refusal, daily
  risk rejection, concurrent watchlist revisions, and full Alembic
  upgrade/downgrade/reupgrade through `a1brain001`. Tests used only a newly created
  local container on loopback port 25432, which was removed afterward.
- Frontend: 51 passed across the nine focused Dashboard, Agent, Journal, and
  statistics test files listed in `docs/trader_interface_polish_handoff.md`.
  Full TypeScript checking and ESLint on changed TypeScript files passed.
- Backend: scoped Ruff lint/format and mypy on the analytics and SFP source
  passed. `alembic heads` returned only `a1brain001`; offline PostgreSQL SQL
  generation for `b6f2d9a10e73:a1brain001` passed.
- Source provenance, protected authority/configuration/API/dependency paths,
  branch ancestry, and `git diff --check` passed.

The first backend HTTP run stalled at Starlette TestClient startup in the default
network-isolated command sandbox. Repeating the same focused selection with
local network access enabled passed without application changes.

## Handoff boundary

Open a draft consolidated release PR against `main` and let GitHub CI run.
Do not wait for CI, deploy, activate runtime services, or merge. Local validation
is not deployment acceptance or a claim about live market performance.
