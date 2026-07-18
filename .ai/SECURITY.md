# Workflow: SECURITY / TRADING-SAFETY hardening

## Scope
Auth/RBAC, secrets, provider trust boundaries, trading-mode gating, audit, data freshness.

## Rules
- Never weaken paper-only invariants. `real_trading_enabled` stays false.
- Never print or commit secrets. Posture/logs expose booleans only, not values.
- Sanitize external inputs. Least privilege. Fail closed on ambiguity.

## Checklist
1. Confirm `deployment_safety` + `exchange_safety` invariants still hold and are tested.
2. Verify secrets come from env/`Settings`, never literals; `.env*` real files gitignored.
3. Verify audit logging + idempotency for any sensitive path.
4. Verify degraded/stale/conflicting data triggers conservative behavior.
5. Add tests for failure and refusal paths.
6. Run: deployment-safety tests + full suite; run `scripts/verify-safety.sh` against staging if relevant.
7. Record decisions in `DECISIONS.md`; regenerate handoff; run sync.
