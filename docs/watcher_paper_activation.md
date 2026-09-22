# Watcher paper activation (staging, not armed)

Controlled activation is prepared and **not performed**. Staging environment
files, `render.yaml`, and Telegram stay unchanged. `ENABLE_REAL_TRADING`
stays false. Do not deploy from this procedure until a human chooses to arm
the worker.

The worker that may scan is `python -m app.workers.watcher_paper`. The API
process does not autostart it. Production rejects the arm.

## What stays true

| Pin | Rule |
| --- | --- |
| Identity | Each process gets `configured-id` plus a unique 16-hex suffix. The bare configured id cannot hold a lease. |
| Leases | Staging activation uses `PostgresWatcherStore` only. |
| Fencing | Renewing a lease requires the current fencing token. A stale token fails closed. |
| Restart | After expiry, a new process may take the lease. The old token cannot write. |
| Idempotency | One key per tenant, policy, symbol, and closed 15-minute interval. |
| Strategy | Scan targets come only from persisted approved or active compiled versions. |
| Evidence | Canonical windows come only from `FirstSliceEvidenceAssembler` fed by live USD-M evidence. Replay cannot start the arm. |
| Freshness | Stale, degraded, or missing quotes fail closed before a scan. |
| Candidate | Only a genuine `CONFIRMED_SETUP` may mint one Candidate. |
| Risk | `BLOCK` outranks warn and allow. Paper execution cannot override it. |
| Paper | `EXECUTION_MODE=paper`. Real trading cannot be constructed. |
| Kill switch | The global and tenant kill switches still block scans. Rollback does not clear them. |
| Telegram | Alerts, interaction, and automatic delivery stay false. |

## Activation configuration

Leave these unset or false until a human runs the procedure below:

- `WATCHER_PAPER_STAGING_ACTIVATION`
- `WATCHER_ORCHESTRATION_ENABLED`

When both are true, staging settings load only if `PERPETUAL_EVIDENCE_SOURCE`
is live (`binance_usdm`), execution is paper, legacy market watcher and
Telegram stay false, and real trading stays false. Preflight can still refuse
to scan.

## Preflight gate

`run_staging_activation` refuses to start when any pin fails. Proven refusals:

- market evidence is replay while live evidence is required
- provider unavailable
- strategy lineage invalid (including no approved compiled target)
- real trading enabled
- migration unhealthy (missing, duplicate, or not the single Alembic head)

A refused start logs `watcher_paper_activation_refused` and does not scan.

## Runtime health gate

After a cleared start, each cycle re-reads migration, lineage, and the live
monitor. A failed pin stops the process before that cycle scans and logs
`watcher_paper_activation_rollback`. A heartbeat older than
`WATCHER_HEARTBEAT_STALE_AFTER_SECONDS` does the same. The gate does not
deploy and does not edit environment variables.

## Rollback

Trigger: any preflight or runtime refusal, or an operator decision to stop.

Command (prints the plan, does not apply it):

```bash
./scripts/watcher-paper-rollback.sh
```

The plan tells the operator to SIGTERM the dedicated process, keep the arm
and `WATCHER_ORCHESTRATION_ENABLED` false, keep Telegram and
`ENABLE_REAL_TRADING` false, and leave the kill switch unchanged. The command
does not deploy.

## Post-activation smoke

Does not arm the worker. With no target it exits 2.

```bash
./scripts/watcher-paper-activation-smoke.sh --self-check
BASE_URL=https://<staging-api> ./scripts/watcher-paper-activation-smoke.sh
WATCHER_ACTIVATION_SMOKE_JSON=/path/to/snapshot.json ./scripts/watcher-paper-activation-smoke.sh
```

`BASE_URL` checks `/health`: paper mode, real trading false, Telegram and the
legacy watcher false, and the armed pair both true outside production.
The JSON snapshot must report live evidence, a healthy migration, an available
provider, a valid lineage, a unique worker id, PostgreSQL leases, fencing,
restart recovery, idempotency, `CONFIRMED_SETUP`, risk `BLOCK`, freshness
fail-closed, and the kill switch still enforced.

Module check, also without arming:

```bash
cd backend && uv run python -m app.workers.watcher_activation --self-check
```

## Monitoring checklist

Run this only when a human has decided to arm staging. This document does not
do those steps.

- [ ] `EXECUTION_MODE=paper` and `ENABLE_REAL_TRADING=false`
- [ ] `EXCHANGE_MODE` is `paper_internal` or `paper_exchange_demo`
- [ ] Telegram flags false: alerts, interaction, automatic delivery
- [ ] `MARKET_WATCHER_ENABLED=false` and bridge flags false
- [ ] `PERPETUAL_EVIDENCE_SOURCE=binance_usdm` (not `replay`)
- [ ] Alembic is the single head `e0f1a2b3c4d5` and `alembic_version` matches it
- [ ] At least one tenant has an approved or active compiled strategy
- [ ] Live USD-M provider answers for `BTCUSDT` and the quote is fresh
- [ ] `WATCHER_PAPER_STAGING_ACTIVATION=true` and `WATCHER_ORCHESTRATION_ENABLED=true` on the **dedicated worker only**
- [ ] API service does not set the arm (it will not autostart, and it should stay disarmed)
- [ ] Worker command is `python -m app.workers.watcher_paper`
- [ ] Process log shows a unique worker id (`watcher-paper-1:<16 hex>`), not the bare configured id
- [ ] Lease row is in `watcher_worker_leases` and the fencing token advances only for that owner
- [ ] Kill switch GET still reports state, and an active switch blocks scans
- [ ] Risk `BLOCK` still blocks paper execution
- [ ] `./scripts/watcher-paper-activation-smoke.sh` exits 0
- [ ] `./scripts/verify-safety.sh` still shows paper mode and real trading false
- [ ] Rollback command is rehearsed with `--self-check` before the arm, and the plan is known
- [ ] No order, withdrawal, or transfer endpoint was called

## Not done here

No deploy. No activation. No staging environment edit. No Telegram. No live trading.
