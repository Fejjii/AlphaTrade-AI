# Telegram paper MVP activation

Activate Telegram on the existing staging paper worker after Watcher health is
fresh. This document does not deploy, does not edit `render.yaml`, and does
not enable live trading.

The blueprint service is `alphatrade-paper-worker-staging`
(`python -m app.workers.paper_worker`). Do not start
`python -m app.telegram_activation run` beside it.

## Preconditions

Watcher is already healthy:

- `EXECUTION_MODE=paper`
- `ENABLE_REAL_TRADING=false`
- `EXCHANGE_MODE=paper_internal`
- `PERPETUAL_EVIDENCE_SOURCE=binance_usdm`
- `WATCHER_PAPER_STAGING_ACTIVATION=true` on the worker only
- `WATCHER_ORCHESTRATION_ENABLED=true` on the worker only
- `GET /health` `worker_runtime.watcher.available` is true and status is fresh
- Alembic head `f1a2b3c4d5e6`
- `TELEGRAM_ALERTS_ENABLED=false`
- `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false`
- `TELEGRAM_WEBHOOK_SECRET` empty

`TELEGRAM_BOT_ID` is the numeric bot user id (the digits before `:` in the
BotFather token). A numeric id that does not match the token fails closed
with `bot_identity_mismatch`. Do not log the token.

## 1. Enrollment variables

Set on `alphatrade-paper-worker-staging`, then restart that one service.

| Variable | Value |
| --- | --- |
| `TELEGRAM_INTERACTION_ENABLED` | `true` |
| `TELEGRAM_NETWORK_PERMITTED` | `true` |
| `TELEGRAM_INBOUND_MODE` | `polling` |
| `TELEGRAM_PAPER_ACTIVATION_ARMED` | `false` |
| `TELEGRAM_BOT_ID` | numeric bot user id |
| `TELEGRAM_BOT_TOKEN` | secret. Not in git. Not in `render.yaml`. |
| `TELEGRAM_CHAT_ID` | empty until the private chat is verified |
| `TELEGRAM_ALERTS_ENABLED` | `false` |
| `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED` | `false` |
| `TELEGRAM_WEBHOOK_SECRET` | empty |

Set the same `TELEGRAM_BOT_ID` on `alphatrade-api-staging`. Do not set
`TELEGRAM_BOT_TOKEN` on the API. Leave Watcher flags false on the API.

## 2. Enroll

Authenticated tenant call:

`POST /telegram-paper/enrollment/start`

Send the one-time token in a private chat with the bot. The paper worker
polling loop binds that chat and advances the durable cursor. Group chats are
rejected. A bare chat id is not a binding.

Confirm `GET /health` `worker_runtime.telegram` heartbeats. State is
`enrollment` until projection is armed.

## 3. Projection variables

Set on the paper worker, then restart it once.

| Variable | Value |
| --- | --- |
| `TELEGRAM_PAPER_ACTIVATION_ARMED` | `true` |
| `TELEGRAM_CHAT_ID` | verified private chat id |
| `TELEGRAM_INTERACTION_ENABLED` | `true` |
| `TELEGRAM_NETWORK_PERMITTED` | `true` |
| `TELEGRAM_INBOUND_MODE` | `polling` |
| `TELEGRAM_BOT_ID` | same numeric bot user id |
| `TELEGRAM_BOT_TOKEN` | same secret |
| `WATCHER_PAPER_STAGING_ACTIVATION` | `true` |
| `WATCHER_ORCHESTRATION_ENABLED` | `true` |

Keep alerts, automatic delivery, and the webhook secret off.

## 4. What the worker does

One process supervises Watcher and Telegram. The Watcher enqueues Candidate
and blocked-scan notices. Telegram drains the outbox with idempotency keys,
retry backoff (5s, 30s, 120s, then dead letter), and a durable polling cursor.
Restart reclaims an expired lease and does not send the same key twice.

Private replies can discuss the latest stored Candidate, paper status, the
latest journal trade, and paper-evaluation learning facts. Those replies do
not reconstruct a SetupAssessment and cannot place an order.

`GET /health/telegram-paper-activation` reports the preflight. `GET /health`
`worker_runtime.telegram` reports heartbeat, outbox counts, and last error.

## Rollback

Follow `docs/controlled_paper_activation.md` rollback. Do not downgrade
Alembic. Do not delete outbox, cursor, or audit rows.
