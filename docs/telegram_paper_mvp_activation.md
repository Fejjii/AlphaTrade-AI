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
- Alembic head `a8c3e1b94d20`
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

### Verify the enrollment intake fix

No new database migration is required. After deploying the PR revision to the
existing paper worker, keep `ENABLE_REAL_TRADING=false`, `EXECUTION_MODE=paper`,
`EXCHANGE_MODE=paper_internal`, and projection disarmed. Confirm fresh
`GET /health` Telegram state `enrollment` and `kill_switch_active=false`.

1. Record the current cursor using the SQL below. The previously consumed
   update `967148778` cannot be recovered by normal polling; do not rewind or
   delete the cursor.
2. Call authenticated `POST /telegram-paper/enrollment/start`. Keep the returned
   `challenge_id` and `expires_at` for verification; keep the token private and
   out of terminals, logs, tickets, and screenshots.
3. Before expiry, send the exact token as a **new private message** to the
   configured AlphaTrade bot. Wait for the next fresh worker heartbeat.
4. Query the challenge by its returned ID. Expect `COMPLETED`, a non-null
   `completed_at` and `binding_id`, a `VERIFIED` private binding for the intended
   organization/user, an `APPLIED` receipt with the new update ID, and
   `enrollment_completed`. The cursor must advance to that new update ID.
5. Send a wrong token as another private message. Expect no new binding and one
   worker log event `telegram_enrollment_rejected` with
   `reason=ENROLLMENT_NOT_FOUND` and `parser_rejection_reason=null`. Reusing the
   completed token in a new message must report `ENROLLMENT_USED`.

Run these read-only queries in the existing database console, replacing the
bot and challenge placeholders. They deliberately omit token hashes and text:

```sql
SELECT bot_id, last_update_id, updated_at
FROM telegram_activation_inbound_cursors
WHERE bot_id = '<configured bot id>';

SELECT challenge_id, organization_id, user_id, state, expires_at,
       completed_at, binding_id
FROM telegram_security_enrollment_challenges
WHERE challenge_id = '<returned challenge UUID>';

SELECT binding_id, organization_id, user_id, chat_type, state, verified_at
FROM telegram_security_bindings
WHERE binding_id = (
    SELECT binding_id FROM telegram_security_enrollment_challenges
    WHERE challenge_id = '<returned challenge UUID>'
);

SELECT update_id, state, reason_code, binding_id
FROM telegram_security_action_receipts
WHERE bot_id = '<configured bot id>'
ORDER BY created_at DESC LIMIT 5;

SELECT event_type, reason_code, at
FROM telegram_security_audit_events
WHERE event_type IN ('enrollment_started', 'enrollment_completed', 'enrollment_rejected')
ORDER BY at DESC LIMIT 10;
```

For any rejected enrollment update, use its update ID to find
`telegram_enrollment_rejected`. The event contains only the update ID,
bounded kind/chat-type labels, reason, parser rejection reason, and text/user-ID/
message-ID presence flags. Parser failures have reasons such as
`chat_not_private`, `telegram_user_id_missing`, and `message_id_missing`.
The first rejection reason in a polling batch also appears in the worker's
`last_error_code` for that cycle; each rejected update has its own log event.
Parser-rejected updates never enter the security protocol, so they do not create
bindings, receipts, or security audit events. Protocol exceptions are also logged
before cursor advancement, independently of transaction rollback.

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
