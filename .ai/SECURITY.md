# Workflow: SECURITY / TRADING-SAFETY hardening

> Authoritative rules: `.ai/MASTER_WORKFLOW.md`. Statuses: `IN_PROGRESS`, `REVIEW_REQUIRED`,
> `BLOCKED`, `FAILED`, `READY` (no `DRAFT`). Sync at start, phase boundaries,
> blockers/reviews/failures, and completion.

## Scope
Auth/RBAC, secrets, provider trust boundaries, trading-mode gating, audit, data freshness,
and broker/exchange operating modes (A: none, B: read-only, C: paper/demo, D: real — disabled).

## Rules
- Never weaken paper-only invariants. `real_trading_enabled` stays false.
- Never print or commit secrets. Posture/logs expose booleans only, not values.
- Sanitize external inputs. Least privilege. Fail closed on ambiguity.
- When a secret/credential is required: set `HANDOFF.md` to `REVIEW_REQUIRED`, state only the
  env-var name and where the operator enters it, never ask for it in chat, and resume after
  confirmation. Broker/exchange mode D (real execution) stays disabled and cannot be enabled here.

## Checklist
1. Confirm `deployment_safety` + `exchange_safety` invariants still hold and are tested.
2. Verify secrets come from env/`Settings`, never literals; `.env*` real files gitignored.
3. Verify audit logging + idempotency for any sensitive path.
4. Verify degraded/stale/conflicting data triggers conservative behavior.
5. Add tests for failure and refusal paths.
6. Run: deployment-safety tests + full suite; run `scripts/verify-safety.sh` against staging if relevant.
7. Record decisions in `DECISIONS.md`; regenerate handoff; run sync.
