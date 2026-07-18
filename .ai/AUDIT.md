# Workflow: AUDIT (inspect and report only)

Use when the task is to understand / assess without changing behavior.

## Rules
- Read-only. No file edits to application code. No git mutations.
- Use verified facts; mark unknowns as UNKNOWN. Never print secrets.

## Procedure
1. Confirm repo path, branch, `git status`, last commits (read-only).
2. Map the relevant modules; cite exact file paths and line ranges.
3. For safety-critical areas, confirm paper-only invariants remain intact.
4. Produce a findings report: what is true, what is risky, what is unknown.
5. Record durable conclusions in `DECISIONS.md`; queue follow-ups in `TASKS.md`.
6. Regenerate `HANDOFF.md` + `CHANGELOG_SESSION.md`; run handoff sync.

## Output
- Structured report (facts → risks → recommendations), no code changes.
