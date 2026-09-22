# Controlled Telegram activation (paper only)

Paper-mode activation path for a bound recipient:

Watcher or Candidate event → durable outbox → Telegram alert → AlphaTrade discussion.

Telegram stays **disarmed**. This document does not activate Watcher, enable live
trading, change staging environment variables, or send a Telegram message.

See also: [telegram_paper_agent.md](./telegram_paper_agent.md) ·
[telegram_security_protocol.md](./telegram_security_protocol.md)

## Verdict

Local paper can still arm through `TelegramPaperActivation.arm()` after
preflight. The running default process remains `NOT_ARMED`.

Staging uses one polling package, documented in
[controlled_paper_activation.md](./controlled_paper_activation.md). Webhook is
not a staging activation path. `create_app` does not mount a Telegram webhook.
A partial staging flag set, including projection armed without
`TELEGRAM_NETWORK_PERMITTED=true`, fails Settings validation. Production
rejects the package. The Render blueprint services stay disarmed.

## What a human must do later

1. Run `scripts/telegram-paper-activation-preflight.sh` and confirm exit 0
   (`verdict` is `NOT_ARMED` on the default process).
2. Run `scripts/telegram-paper-activation-smoke.sh`. It uses the fake transport
   and a recorded update source. It does not call `api.telegram.org`.
3. Only in `ENVIRONMENT=local` and `EXECUTION_MODE=paper`, with
   `ENABLE_REAL_TRADING=false`, set:
   - `TELEGRAM_INTERACTION_ENABLED=true`
   - `TELEGRAM_PAPER_ACTIVATION_ARMED=true`
   - `TELEGRAM_INBOUND_MODE=polling` (staging does not activate webhook)
   - `TELEGRAM_NETWORK_PERMITTED=true` only when a real send is intended
4. Enroll a private-chat binding through the existing challenge. A chat id
   alone is not a binding.
5. Construct `TelegramPaperActivation` and call `arm()`. `arm` fails closed
   when preflight reports blockers.
6. Pass `paper_scan_hook()` into the paper worker yourself. `main()` does not
   install it. Watcher `PERSIST_AND_NOTIFY` stays `notify_disabled`.

Staging follows the controlled runbook. Do not deploy from this work. Production stays rejected.

## Safety gates

| Requirement | Where it is enforced |
|-------------|----------------------|
| Recipient binding | Verified private binding; org, user, bot, and chat must match |
| Tenant isolation | Cross-org recipient and cursor/ledger conflicts fail closed |
| Delivery idempotency | Outbox key plus send ledger |
| Retry / backoff | 5s, 30s, 120s from durable `attempt` and `updated_at`; then dead letter |
| Restart recovery | Expired outbox lease is reclaimed; polling cursor is durable; exact inbound replay converges |
| Rate limits | Inbound protocol windows and outbound per-chat window. Rate limit defers without burning an attempt |
| Audit | Protocol audits plus `activation_armed` / `activation_disarmed` / inbound dispositions |
| Delivery status | `PENDING → CLAIMED → SENT → ACKNOWLEDGED`, or `RETRYABLE` / `DEAD_LETTER` |
| Confirmation identity | Paper mutations require the issued identity. Bare `I confirm` is not authority |
| Webhook / polling | One inbound mode. Webhook checks `X-Telegram-Bot-Api-Secret-Token`. `create_app` does not mount it |
| Health | `GET /health` and `GET /health/telegram-paper-activation` |
| Rollback | `scripts/telegram-paper-activation-rollback.sh` prints the checklist and refuses `--apply` |

Telegram still cannot mint a Candidate, override SetupAssessment, override risk,
activate a strategy, create a live order, or enable live trading. `APPROVE`
remains an authorization intent with `executes=false`.

## Network

`HttpTelegramTransport` and `HttpTelegramUpdateSource` refuse unless
`telegram_network_permitted` is true. The default builder does not permit it.
Tests inject a fake HTTP callable. No live token is required for the smoke.

## Rollback

`scripts/telegram-paper-activation-rollback.sh` prints the human checklist:

- disarm activation, inbound mode, webhook secret, and network permit
- turn interaction off
- leave alerts and automatic delivery off
- do not change Watcher flags or live-trading flags
- keep outbox, audit, cursor, and ledger rows
- revoke a binding only as a separate explicit action
- confirm `GET /health/telegram-paper-activation` is `NOT_ARMED`

The script does not edit environment files, `render.yaml`, or a deployment.

## Schema

Alembic `e0f1a2b3c4d5` revises `d9e0f1a2b3c4` and adds the activation cursor and send ledger. Current head `f1a2b3c4d5e6` adds `controlled_runtime_status`. The earlier revision adds:

- `telegram_activation_inbound_cursors`
- `telegram_activation_send_ledger`

Outbox delivery state stays on `telegram_security_outbox`.
