# Workflow: REFACTOR (no behavior change)

> Authoritative rules: `.ai/MASTER_WORKFLOW.md`. Statuses: `IN_PROGRESS`, `REVIEW_REQUIRED`,
> `BLOCKED`, `FAILED`, `READY` (no `DRAFT`). Sync the handoff at start, phase boundaries,
> blockers/reviews/failures, and completion.

## Rules
- Behavior must be preserved exactly. Public APIs and outputs unchanged.
- No functional or safety changes. Keep diffs scoped; no unrelated edits.

## Procedure
1. Establish a green baseline (tests, lint, types) before touching code.
2. Refactor in small steps; keep tests green after each step.
3. Improve naming, reduce nesting/duplication, strengthen typing.
4. Re-run full local validation; confirm identical behavior.
5. Note structural decisions in `DECISIONS.md` if significant.
6. Regenerate handoff docs; run sync.
