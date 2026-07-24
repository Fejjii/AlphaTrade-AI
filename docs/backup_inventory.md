# Backup inventory (AT-019)

**Scope:** Staging / paper-MVP data stores and configuration artifacts that matter for
recovery. No secrets, connection strings, or personal financial data are recorded here.

**Related:** [backup_restore_runbook.md](backup_restore_runbook.md),
[backup_restore_drill_plan.md](backup_restore_drill_plan.md).

---

## 1. Classification legend

| Class | Meaning | Backup required? |
|-------|---------|------------------|
| **SoR** | System of record — loss is user-visible data loss | Yes |
| **Rebuildable** | Can be reconstructed from SoR or fixtures | Prefer snapshot; rebuild OK |
| **Ephemeral** | Cache / denylist / rate-limit state | No logical backup |
| **Config** | Env/secrets in platform stores — never in DB dumps | Platform backup / export process |
| **Out of scope** | Not AlphaTrade-owned durable state | Document only |

---

## 2. Inventory

| Asset | Class | Typical host | What to protect | Retention (target) | Notes |
|-------|-------|--------------|-----------------|--------------------|-------|
| **Postgres** | SoR | Render Postgres (or Neon/Railway) | Schema + all workflow tables: users/orgs, auth refresh hashes, proposals, approvals, paper orders/positions, journal, audit, usage, knowledge chunk metadata, risk settings, kill switch, validation sessions | Daily ≥ 7 days; weekly ≥ 4 weeks | Primary restore target. Prefer platform automated snapshots + verified `pg_dump` drill. |
| **Alembic revision state** | SoR (inside Postgres) | Same as Postgres | `alembic_version` | With Postgres | Restore must land at a known app/schema revision before serving traffic. |
| **Qdrant collection `alphatrade_knowledge`** | Rebuildable | Qdrant Cloud or local Compose | Vectors + payload for RAG | Daily snapshot if available; else rebuild | Prefer re-ingest from Postgres knowledge rows + fixtures (`scripts/reingest-knowledge-base.sh`) after DB restore. |
| **Redis** | Ephemeral | Upstash / Render Redis | Rate-limit windows, JWT access-token denylist | None | Recreate empty instance. Users may need re-login if denylist lost mid-compromise response; acceptable for paper staging. |
| **Platform env / secrets** | Config | Render / Vercel / Qdrant dashboards | `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`, `QDRANT_*`, `OPENAI_API_KEY`, CORS/cookie flags, safety flags | Platform history / sealed ops notes (`*.local.md`, gitignored) | **Never** commit values. Backup = documented variable *names* + sealed operator worksheet. |
| **Render / Vercel deploy revisions** | Config | Platform | Prior Docker image / frontend deployment | Keep prior revision ≥ 48h after promote | Application rollback ≠ data restore. See [deploy_rollback_runbook.md](deploy_rollback_runbook.md) (AT-005). |
| **Object/file storage** | Out of scope | N/A today | — | — | No durable blob store in current architecture. |
| **Exchange account state** | Out of scope | BloFin demo (Mode C) when configured | Demo venue positions | Venue-owned | Not restored from AlphaTrade backups. Paper-internal Mode A state lives in Postgres. |
| **LLM provider state** | Out of scope | OpenAI | — | — | Stateless from our side; usage meters live in Postgres. |
| **Local Docker volumes** `postgres_data`, `qdrant_data` | SoR / Rebuildable (dev only) | Developer machine | Local demo data | Operator discretion | Use local drill scripts only; not a staging backup. |

---

## 3. Postgres table groups (logical)

Groupings for restore verification — not an exhaustive schema dump:

| Group | Examples (logical) | Criticality |
|-------|--------------------|-------------|
| Identity / tenancy | users, organizations, memberships, RBAC | Critical |
| Auth sessions | refresh-token hashes (not raw tokens) | Critical |
| Trading workflow (paper) | proposals, approvals, paper orders/positions | Critical |
| Safety controls | org kill switch, user risk settings | Critical |
| Audit / usage | audit events, usage events | High (compliance + quotas) |
| Knowledge metadata | documents/chunks metadata in Postgres | High (RAG integrity) |
| Learning / validation | journal, lessons, validation sessions/observations | Medium–High |
| Billing scaffold | billing tables if present | Low (billing disabled) |

---

## 4. Explicit non-goals

- No backup of live exchange production accounts (Mode D disabled; not in scope).
- No commitment of dump files, snapshot IDs with account numbers, or connection URLs.
- No Redis AOF/RDB as durability strategy (Compose intentionally disables Redis persistence).
- AT-005 deploy rollback runbook / automated post-deploy smoke gate —
  [deploy_rollback_runbook.md](deploy_rollback_runbook.md); this inventory only notes
  deploy revisions as a related config asset.

---

## 5. Operator checklist (names only)

Before a real restore, confirm sealed access to:

- [ ] Managed Postgres console / snapshot UI (no URL pasted into git)
- [ ] Ability to create a **scratch** restore target (never overwrite staging SoR blindly)
- [ ] Platform env worksheet (`docs/staging_deployment_worksheet.local.md` or equivalent, gitignored)
- [ ] Qdrant Cloud console (or decision to rebuild via re-ingest)
- [ ] Redis recreate path
- [ ] Post-restore smoke: `./scripts/post-deploy-smoke-gate.sh` (or `verify-safety.sh` minimum)
