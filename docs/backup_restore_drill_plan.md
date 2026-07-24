# Backup / restore drill plan (AT-019)

**Goal:** Prove we can take a Postgres backup and restore it with measurable time and
integrity checks — without putting secrets in git and without touching managed cloud
services until a human approves.

**Related:** [backup_restore_runbook.md](backup_restore_runbook.md) ·
[backup_inventory.md](backup_inventory.md) ·
[backup_restore_drill_evidence.md](backup_restore_drill_evidence.md)

---

## 1. Drill tiers

| Tier | Target | Approval | This AT-019 session |
|------|--------|----------|---------------------|
| **A — Local Compose** | Docker `postgres` service in this repo | None (dev machine) | **Execute** |
| **B — Scratch managed DB** | New empty Render/Neon DB | Explicit human approval | Deferred → REVIEW_REQUIRED |
| **C — Staging cutover** | Point staging API at restored DB | Dual confirmation | Out of scope for ordinary task |

Tier A satisfies the “successful restore drill recorded” validation for paper-MVP docs when
evidence is sanitized. Tier B/C remain follow-ups.

---

## 2. Tier A — Local Compose drill (standard)

### Preconditions

- Docker available; repo `docker-compose.yml` present.  
- No need for OpenAI, Qdrant Cloud, or staging credentials.  
- Working tree may be dirty with docs/scripts only.

### Steps

1. Start Postgres: `docker compose up -d postgres`.  
2. Wait for healthy (`pg_isready`).  
3. Apply migrations if schema missing:
   `docker compose run --rm --no-deps --entrypoint alembic backend upgrade head`
   (or drill script handles marker table without full app if DB empty — prefer migrations).  
4. Insert a **non-sensitive marker** row (UUID + label `at019-drill`, no PII).  
5. Run `./scripts/backup-postgres-local.sh` → dump under `.ai/local/backups/postgres/`.  
6. Record dump byte size + SHA256 (file hash only).  
7. Drop marker (or drop/recreate public schema) to simulate loss.  
8. `CONFIRM=yes DUMP_FILE=… ./scripts/restore-postgres-local.sh`.  
9. Verify marker row present; record wall-clock backup and restore durations.  
10. Write sanitized results into `docs/backup_restore_drill_evidence.md`.  
11. Leave dump in `.ai/local/` (gitignored); do not commit dumps.

### Success criteria

- Marker UUID round-trips after restore.  
- Dump SHA256 recorded.  
- RTO measured for local path (informational; staging RTO target remains ≤ 4h).  
- Zero secrets in tracked docs.

### Failure handling

- If Docker unavailable → document BLOCKED with command evidence.  
- If restore fails → keep dump; do not delete; set FAILED/BLOCKED in handoff.

---

## 3. Tier B — Scratch managed drill (approval-gated)

**Do not run until HANDOFF Status is cleared from REVIEW_REQUIRED with operator OK.**

Outline only:

1. Create scratch Postgres (same major version as staging).  
2. Restore latest staging snapshot **into scratch** (platform UI) or approved `pg_dump`.  
3. Stand up one-off API or `psql` checks — no production cutover.  
4. Run `verify-safety.sh` against scratch API if stood up.  
5. Destroy scratch after evidence captured.  
6. Append sanitized evidence (timestamps, sizes, checksums, pass/fail) — no URLs with
   credentials.

---

## 4. What must never appear in evidence

- Connection strings, passwords, API keys, JWTs  
- User emails, names, or account identifiers from real tenants  
- Full `pg_dump` SQL contents  
- Exchange credentials or wallet addresses  

Allowed: timestamps, durations, byte sizes, SHA256 of dump files, boolean pass/fail,
Alembic revision id, marker UUID created for the drill.
