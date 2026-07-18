# AlphaTrade AI — MASTER (AI Collaboration Index)

> Version-controlled project governance for AI assistants (not application code).
> This `.ai/` layer and `.cursor/rules/` are committed so any clone gets the same guidance.
> Generated handoff artifacts (`HANDOFF.md`, `CHANGELOG_SESSION.md`) stay gitignored/local.
> Purpose: give any AI assistant (Cursor / ChatGPT) a consistent, truthful entry point.

## Project identity

| Field | Value |
|-------|-------|
| Project name | AlphaTrade AI |
| Slug | alphatrade-ai |
| Task prefix | AT |
| Capability profiles | base, agentic, high_risk, trading |
| Remote | https://github.com/Fejjii/AlphaTrade-AI.git |
| Local checkout | Path varies per machine; clone of the remote above |

## How to use this layer

1. Read `PROJECT_CONTEXT.md` for what the system is and hard safety rules.
2. Read `ARCHITECTURE.md` for the verified technical map.
3. Pick the workflow doc for the task type:
   - `AUDIT.md` — inspect / report only
   - `IMPLEMENT.md` — build a feature (paper-safe)
   - `BUGFIX.md` — fix a defect
   - `REFACTOR.md` — restructure without behavior change
   - `SECURITY.md` — security / trading-safety hardening
   - `RELEASE.md` — release / deploy validation
   - `LINKEDIN_DEMO.md` — portfolio / demo packaging
4. Track durable decisions in `DECISIONS.md` (AT-ADR-XXX).
5. Track work in `TASKS.md` (AT-XXX).
6. End every task by regenerating root `HANDOFF.md` + `CHANGELOG_SESSION.md`
   and running the handoff sync (see `RELEASE.md` / repo rules).

## Non-negotiable safety (summary — full text in PROJECT_CONTEXT.md)

- Paper only. `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `EXCHANGE_MODE=paper_internal`, `PROVIDER_MODE=fallback` (staging).
- No live orders, withdrawals, transfers, leverage changes, or exchange account mutations.
- No commit / push / merge / rebase / history rewrite unless the task explicitly authorizes it.
- No secrets printed or committed.
- Verified repository facts only. Mark unknowns as UNKNOWN.

## Canonical handoff files

Generated per session; gitignored (never committed):

- Source (repo root): `HANDOFF.md`, `CHANGELOG_SESSION.md`
- Optional local mirror + automation (machine-specific, outside the repo):
  - iCloud mirror folder under `~/Library/Mobile Documents/com~apple~CloudDocs/...`
  - Sync script: `~/.local/bin/sync-alphatrade-ai-handoff.sh`
  - LaunchAgent: `~/Library/LaunchAgents/<your-label>.alphatrade-ai-handoff-sync.plist`
