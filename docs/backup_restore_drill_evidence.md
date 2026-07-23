# Backup / restore drill evidence (AT-019)

**Sanitization rule:** No connection strings, passwords, API keys, dump contents, PII, or
tenant identifiers. Allowed: timestamps, durations, sizes, file SHA256, pass/fail, marker
UUIDs created solely for the drill.

**Related:** [backup_restore_drill_plan.md](backup_restore_drill_plan.md) ·
[backup_restore_runbook.md](backup_restore_runbook.md)

---

## 1. Tier A — Local Compose (executed)

| Field | Value |
|-------|-------|
| Session | AT-SESSION-20260723-232211 |
| Date (UTC) | 2026-07-23 |
| Tier | A — local Docker Compose Postgres |
| Branch / commit baseline | `feat/at-019-backup-restore-drill` @ `46e8b3b` (+ uncommitted docs/scripts) |
| External services contacted | **No** |
| Result | **passed** |

### Procedure executed

```bash
CONFIRM=yes ./scripts/drill-backup-restore-local.sh
```

### Measured results (sanitized)

| Metric | Value |
|--------|-------|
| Marker UUID | `46aa01c5-59c8-405f-b077-1a3051686f56` |
| Marker label | `at019-local-drill` |
| Migrations before dump | applied (`alembic upgrade head`) |
| Dump path (gitignored) | `.ai/local/backups/postgres/alphatrade-local-20260723T212352Z.dump` |
| Dump size | 716384 bytes |
| Dump SHA256 | `6680490845584cb888ef0e2184ce73ad63f11264a6bfb4c6889374a30f978292` |
| Backup wall time | 3 s |
| Restore wall time | 4 s |
| Total backup+restore | 7 s |
| Marker present after restore | yes |
| Machine-local JSON summary (gitignored) | `.ai/local/backups/postgres/drill-summary-20260723T212342Z.json` |

### Interpretation vs RPO/RTO targets

| Target (runbook) | Drill note |
|------------------|------------|
| Postgres RPO ≤ 24 h | Local logical dump proved; staging still relies on enabling platform daily snapshots (operator) |
| Postgres RTO ≤ 4 h | Local restore ≪ target (7 s dump+restore on empty-ish local DB); staging cutover not exercised |
| Redis / Qdrant | Not in Tier A path (ephemeral / rebuildable per inventory) |

### Safety checks

- Scripts used Compose service `postgres` only; no `DATABASE_URL` accepted.  
- Dump and summary remain under `.ai/local/` (gitignored).  
- Paper trading posture untouched (no backend/frontend code changes).

---

## 2. Tier B / C — Managed / staging (not executed)

| Field | Value |
|-------|-------|
| Status | **Deferred — human approval required** |
| Reason | Operator instruction: stop before any real external service interaction |
| Next action | Approve scratch managed restore (Tier B) if desired; do not overwrite staging SoR without dual confirmation |

---

## 3. Evidence completeness for AT-019 validation

| Validation criterion (TASKS.md) | Status |
|---------------------------------|--------|
| Documented RPO/RTO | Yes — `docs/backup_restore_runbook.md` §2 |
| Successful restore drill recorded | Yes — Tier A above |
| No secrets in docs | Yes — this file + inventory/runbook/plan |
| Staging/managed drill | Pending approval (explicitly out of this session) |
