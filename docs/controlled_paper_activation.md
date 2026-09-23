# Controlled paper activation

One operator procedure for staging paper activation:

real read-only Binance USD-M evidence → Watcher paper monitoring → canonical
SetupAssessment → Candidate → paper workflow → Journal, evaluation, and
learning → Telegram alert and discussion.

This repository change does not merge the source pull requests, does not
deploy, and does not edit the live staging environment. `render.yaml` already
contains the step-3 evidence values as a blueprint. Applying that blueprint,
and every later flag below, is a human action.

## Pins that stay true

| Pin | Required value |
| --- | --- |
| `EXECUTION_MODE` | `paper` |
| `ENABLE_REAL_TRADING` | `false` |
| `EXCHANGE_MODE` | `paper_internal` during this package |
| Exchange credentials | unset. No Binance or BloFin key is added. |
| Exchange mutation | none. Public `GET` on `https://fapi.binance.com` only. |
| Risk | `BLOCK` remains final. |
| Kill switch | Monitoring continues: the process stays up, heartbeats, and health still reports source and freshness. New automated paper actions stop: no Candidate mint, no Watcher-started paper workflow, no new Telegram outbox enqueue, and no delivery of queued automated messages. An unreadable switch is active. Rollback does not clear it. |
| Evidence | `binance_usdm`, BTCUSDT first, quote freshness 10 seconds. No spot fallback and no fabricated fallback. |
| Replay | rollback and test mode. It cannot start the Watcher arm. |
| Watcher | dedicated process `python -m app.workers.watcher_paper`. Unique worker id. PostgreSQL leases and fencing. Approved compiled strategy only. `CONFIRMED_SETUP` is the only Candidate authority. |
| Telegram | verified private binding, idempotent outbox, retry/backoff, restart recovery, audit, explicit confirmation. |
| Telegram authority | cannot mint a Candidate, override SetupAssessment, override risk, activate a strategy, place an order, or enable live trading. |
| Migration head | `f1a2b3c4d5e6` (revises `e0f1a2b3c4d5`). Do not downgrade Alembic as part of rollback. |

Production refuses `binance_usdm`, the Watcher arm, and every Telegram arming
flag. Defaults stay disarmed.

## Activation order

Do the steps in this order. Do not skip a failed step.

### 1. Preflight

Confirm the deployed revision is this package and that no Binance or BloFin
credential is set. Confirm `EXECUTION_MODE=paper` and `ENABLE_REAL_TRADING=false`.
Run, without changing environment variables:

```bash
./scripts/check-env.sh
./scripts/validate-live-market-staging.sh --self-check
./scripts/watcher-paper-rollback.sh --self-check
./scripts/telegram-paper-activation-preflight.sh
./scripts/controlled-paper-activation-rollback.sh --self-check
```

`telegram-paper-activation-preflight.sh` must exit 0 while the process is still
disarmed (`NOT_ARMED`).

### 2. Migrations

Apply Alembic through head `f1a2b3c4d5e6` on the staging database. Confirm a
single head. Do not downgrade.

### 3. Live market activation

Set these on the staging API and worker together. Leave Watcher and Telegram
disarmed.

| Variable | Value |
| --- | --- |
| `PERPETUAL_EVIDENCE_SOURCE` | `binance_usdm` |
| `MARKET_DATA_FUTURES_BASE_URL` | `https://fapi.binance.com` |
| `PERPETUAL_EVIDENCE_TIMEOUT_SECONDS` | `10` |
| `EXECUTION_MODE` | `paper` |
| `ENABLE_REAL_TRADING` | `false` |
| `EXCHANGE_MODE` | `paper_internal` |
| `WATCHER_ORCHESTRATION_ENABLED` | `false` |
| `WATCHER_PAPER_STAGING_ACTIVATION` | `false` |
| `TELEGRAM_ALERTS_ENABLED` | `false` |
| `TELEGRAM_INTERACTION_ENABLED` | `false` |
| `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED` | `false` |
| `TELEGRAM_PAPER_ACTIVATION_ARMED` | `false` |
| `TELEGRAM_INBOUND_MODE` | `off` |
| `TELEGRAM_NETWORK_PERMITTED` | `false` |

Do not set `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `BINANCE_FUTURES_API_KEY`,
`BINANCE_FUTURES_API_SECRET`, `FAPI_API_KEY`, or `FAPI_API_SECRET`.

Restart the API and worker so `Settings` reloads.

### 4. Verify fresh Binance USD-M evidence

```bash
BASE_URL=https://YOUR-API.onrender.com \
  ./scripts/validate-live-market-staging.sh --remote --expect active --require-active
```

This check is for step 4, while Watcher and Telegram are still off. Expect
`perpetual_evidence_source=binance_usdm`, `perpetual_evidence_activation=active`,
freshness 10 seconds, symbol BTCUSDT, `execution_mode=paper`, and
`real_trading_enabled=false`. A stale, missing, or wrong-source quote is a stop.

### 5. Watcher activation

On the dedicated worker only (not the API):

| Variable | Value |
| --- | --- |
| `WATCHER_PAPER_STAGING_ACTIVATION` | `true` |
| `WATCHER_ORCHESTRATION_ENABLED` | `true` |
| `PERPETUAL_EVIDENCE_SOURCE` | `binance_usdm` (already set) |

Start only:

```bash
python -m app.workers.watcher_paper
```

The API does not autostart this process. The worker id must be the configured
id plus a unique suffix. Legacy `MARKET_WATCHER_*` flags stay false.

### 6. Verify scans and monitoring

Confirm the worker log shows a cleared preflight and scans, and that
`GET /health` still has `execution_mode=paper` and `real_trading_enabled=false`.
API flag fields are the API process configuration. Observed worker state is
`worker_runtime`: heartbeat age against `watcher_heartbeat_stale_after_seconds`
(default 90 seconds; age equal to the threshold is fresh). A missing heartbeat
is `UNAVAILABLE`. A future or older heartbeat is `STALE` with `available=false`
and is never `RUNNING`. A persisted row alone is not liveness. Lease, last
scan, market source, market freshness, and activation state are also reported.
A replay source, provider outage, stale quote, invalid
strategy lineage, or migration mismatch skips the scan and backs off. The
process stays up. No order is placed. An active kill switch keeps that
monitoring and blocks new Candidates and Telegram actions.

`./scripts/validate-live-market-staging.sh --remote` still expects Watcher and
Telegram off. After this step, use `./scripts/verify-safety.sh` instead.

### 7. Telegram enrollment

Only after step 6. Change the Telegram process only. Leave the Watcher
environment unchanged so it does not restart.

| Variable | Value |
| --- | --- |
| `TELEGRAM_INTERACTION_ENABLED` | `true` |
| `TELEGRAM_NETWORK_PERMITTED` | `true` |
| `TELEGRAM_INBOUND_MODE` | `polling` |
| `TELEGRAM_PAPER_ACTIVATION_ARMED` | `false` |
| `TELEGRAM_BOT_ID` | bot id |
| `TELEGRAM_ALERTS_ENABLED` | `false` |
| `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED` | `false` |
| `TELEGRAM_WEBHOOK_SECRET` | empty |

Staging does not use a webhook. `TELEGRAM_BOT_TOKEN` comes from the secret
store on the Telegram process only. Do not log it, do not commit it, and do
not put it in `render.yaml`. Set `TELEGRAM_BOT_ID` on the API as well so an
authenticated operator can start enrollment. Do not put the token on the API.

Start `python -m app.telegram_activation run`. Call
`POST /telegram-paper/enrollment/start` as the tenant. The response token is
shown once and is not logged. Send that token in a private chat. The Telegram
process completes the binding and advances the durable cursor. The Watcher
keeps scanning. There is no configuration in which projection is armed and
the network is off: that combination fails Settings validation and does not
boot.

### 8. Atomic projection

Set these on the Watcher and the Telegram process together, then restart both:

| Variable | Value |
| --- | --- |
| `TELEGRAM_PAPER_ACTIVATION_ARMED` | `true` |
| `TELEGRAM_CHAT_ID` | the verified private chat |
| `TELEGRAM_NETWORK_PERMITTED` | `true` (already true) |
| `TELEGRAM_INBOUND_MODE` | `polling` |
| `TELEGRAM_BOT_TOKEN` | secret store, not logs |

The Watcher installs an enqueue-only scan hook. The Telegram process drains
the outbox and polls. A retry must not create a second send for the same
idempotency key. Discussion stays advisory. It cannot place an order.

### 9. Observe the full paper loop

Confirm one path, without a manually inserted `CONFIRMED_SETUP`:

fresh USD-M evidence → Watcher scan → genuine `CONFIRMED_SETUP` → one
Candidate → paper eligibility and paper plan → paper execution → Journal →
evaluation facts (`watcher_orchestration_enabled=false` and
`telegram_interaction_enabled=false` on the measurement record) → learning
text with `activate=false` → Telegram projection of that scan.

No live order. Risk `BLOCK` still wins.

### 10. Rollback verification

Run the rollback below on a non-production rehearsal before relying on it.
Confirm health returns to replay, Watcher off, and Telegram `NOT_ARMED`, and
that Candidate, Journal, outbox, and audit rows are still present.

## Rollback

Fail closed. This disables Telegram, Watcher, and live evidence and returns to
paper execution, replay evidence, and no automated monitoring. It does not
delete rows and does not downgrade Alembic.

Print the checklist without applying it:

```bash
./scripts/controlled-paper-activation-rollback.sh
```

`--apply` exits 2 and changes nothing. A human then:

1. Send SIGTERM to the dedicated Watcher and any Telegram intake process. Confirm both have exited.
2. Set `TELEGRAM_PAPER_ACTIVATION_ARMED=false`.
3. Set `TELEGRAM_INBOUND_MODE=off`.
4. Clear `TELEGRAM_WEBHOOK_SECRET` without logging the previous value.
5. Set `TELEGRAM_NETWORK_PERMITTED=false`.
6. Set `TELEGRAM_INTERACTION_ENABLED=false`.
7. Keep `TELEGRAM_ALERTS_ENABLED=false` and `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false`.
8. Set `WATCHER_PAPER_STAGING_ACTIVATION=false`.
9. Set `WATCHER_ORCHESTRATION_ENABLED=false`.
10. Keep `MARKET_WATCHER_ENABLED=false` and both bridge flags false.
11. Set `PERPETUAL_EVIDENCE_SOURCE=replay` only after both Watcher flags are false. Replay while the Watcher is still armed fails Settings validation.
12. Keep `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, and `EXCHANGE_MODE=paper_internal`.
13. Do not add exchange credentials.
14. Leave outbox, audit, cursor, send-ledger, Candidate, Journal, and lease rows in place.
15. Do not downgrade Alembic.
16. Leave the kill switch unchanged.
17. Restart the API and worker.
18. Confirm `GET /health` shows `execution_mode=paper`, `real_trading_enabled=false`, `perpetual_evidence_source=replay`, `perpetual_evidence_activation=inactive`, and `worker_runtime` for the disarmed workers. API flag fields are configuration, not a substitute for `worker_runtime`.
19. Confirm `GET /health/telegram-paper-activation` shows `NOT_ARMED`.

## What is not in the blueprint

`render.yaml` adds `alphatrade-watcher-paper-staging` (`python -m app.workers.watcher_paper`)
and `alphatrade-telegram-paper-staging` (`python -m app.telegram_activation run`).
Both include the staging Settings contract required to boot (secure refresh
cookie, `SameSite=none`, HTTPS `CORS_ORIGINS`, Redis rate limit and access-token
denylist, trusted proxy hop) and stay disarmed. Secrets stay out of the blueprint.
Both stay disarmed: Watcher flags false, Telegram flags false, inbound `off`,
network false, and no bot token. Adding the services to the blueprint does not
deploy or activate them. `.env.staging.example` keeps the same disarmed posture.
