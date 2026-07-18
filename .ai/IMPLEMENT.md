# Workflow: IMPLEMENT (paper-safe feature work)

## Preconditions
- A task exists in `TASKS.md` (AT-XXX) with scope, risk, and validation criteria.
- Change must not enable real trading or external account actions.

## Rules
- Small, focused, typed changes. Follow existing project conventions.
- Separate concerns: business logic / IO / data access / external services.
- No hardcoded secrets; use config. Validate inputs at boundaries.
- Preserve all existing APIs and paper-only behavior unless the task explicitly changes them.
- Do not commit/push unless the task authorizes it.

## Procedure
1. Inspect related code first; confirm the simplest robust approach.
2. Implement with type hints; add/adjust tests for behavior and failure paths.
3. Keep deterministic risk logic deterministic and tested.
4. Run local validation (see below). Fix lint/type/test failures.
5. Update docs if behavior/config changed.
6. Regenerate handoff docs; run sync.

## Local validation (backend, from `backend/`)
```
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
Frontend (from `frontend/`): `npm run lint && npm run typecheck && npm run test && npm run build`.

## Definition of done
- Tests green, lint/format/type clean, docs updated, safety invariants intact, handoff synced.
