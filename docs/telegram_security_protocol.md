# Telegram security protocol foundation (AT-041)

Isolated **Telegram enrollment, identity, nonce, receipt, outbox, and
authorization-boundary** contracts. This slice does **not** connect Telegram to
execution, BloFin, market data, the watcher, candidate generation, journal
automation, the frontend, or PostgreSQL.

**Telegram remains disabled.** `TELEGRAM_INTERACTION_ENABLED` defaults to `false`.
The protocol is not mounted on FastAPI. There is no inbound webhook. There are no
Alembic migrations and no shared ORM model changes.

See also: [notifications.md](./notifications.md) (outbound alert delivery, still
disabled by default) · [security.md](./security.md)

## What this slice is

A channel-neutral protocol foundation that a later integration phase can bind to
PostgreSQL and an HTTPS Telegram webhook. Tests use a deterministic in-memory store
and a fake Telegram transport with no network I/O.

## Feature flags (defaults)

| Setting | Default | Notes |
|---------|---------|-------|
| `TELEGRAM_INTERACTION_ENABLED` | `false` | Inbound interaction protocol. Fail-closed when false. |
| `TELEGRAM_ALERTS_ENABLED` | `false` | Existing outbound alert delivery. Unchanged. |
| `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED` | `false` | Existing automatic delivery preview/send. Unchanged. |

`Settings.telegram_interaction_enabled` is independent of outbound alert delivery.
Enabling interaction is **not** implemented as an HTTP surface in this slice.

## Allowed future action vocabulary

| Action | Protocol effect | Executes? |
|--------|-----------------|-----------|
| `STATUS` | Read-only response intent | No |
| `EXPLAIN` | Read-only response intent | No |
| `SHOW_CHART` | Read-only response intent | No |
| `REJECT` | Reject-resource intent | No |
| `SKIP` | Skip-resource intent | No |
| `APPROVE` | Authorization intent for the exact bound payload | **Never** |
| `REDUCE_RISK` | Non-persistent lower-risk preview intent | No |
| `CLOSE` | **Unavailable** | No |

`EXECUTE_PAPER_PLAN` is **not** a Telegram action. It remains the only explicit
execution entry path and is outside this package.

`APPROVE` records a protocol-level `AuthorizationIntent` with `executes=false`.
It does not call `ExecutionService`, does not consume a plan authorization, and
does not create an execution command.

## Security contracts

- Private-chat enrollment only. Group, supergroup, and channel chats are rejected.
- Enrollment starts as an AlphaTrade-authenticated challenge (org + user + bot),
  hashed, one-time, and expiring. Completing it with a chat id alone is rejected.
- A verified binding binds organization, AlphaTrade user, Telegram user, private
  chat, chat type, and bot identity, with `verified_at` / `revoked_at` and an
  allowed-action list that never includes `CLOSE`.
- Callback data is an opaque nonce. The nonce record binds organization, user,
  account, Telegram user/chat/bot, resource, revision/content hash, exactly one
  action, expiry, and single-use state.
- Exact action payload binding: a mutated payload hash is rejected.
- Cross-user, cross-organization, and cross-account presented identities are
  rejected without consuming the nonce.
- Expired and already-used nonces are rejected.
- Exact replay: duplicate Telegram `update_id` / `callback_query_id`
  deliveries return the original receipt only when the inbound semantic
  fingerprint is identical. The fingerprint binds Telegram user, chat, bot,
  nonce or enrollment-token hash, action, organization, AlphaTrade user,
  account, resource type, resource ID, revision ID, content hash, and payload
  hash. Same transport identity with changed semantic content fails closed as
  `REPLAY_CONFLICT`.
- Inbound size: `MAX_INBOUND_UPDATE_BYTES` applies to
  `TelegramInboundUpdate.body_size` (raw Telegram request payload). It is never
  derived from nonce or enrollment-token length. Webhook wiring is out of
  scope; a later adapter must pass the raw body length.
- Compare-and-set receipt states: `RECEIVED → CLAIMED → APPLIED | REJECTED`.
- Enrollment-aware rate limits apply per AlphaTrade user (challenge start) and per
  Telegram user/chat (inbound complete/callback).
- Transactional outbox: outbound messages are inserted in the same store
  transaction as the domain mutation. Delivery is at-least-once via durable claim
  + idempotent fake/real transport. Duplicate idempotency keys converge.
- Delivery acknowledgement is a separate `SENT → ACKNOWLEDGED` step.

## Persistence

`TelegramSecurityStore` is a persistence interface. This slice ships
`InMemoryTelegramSecurityStore` for tests. A later phase may implement the same
interface on PostgreSQL. No Alembic migration is included.

## Transport

`TelegramTransport.send_private_message` is the outbound abstraction. Tests use
`FakeTelegramTransport` (deterministic, no network, idempotent by key). Bot tokens
are not accepted or stored by this protocol.

## Isolation

Package `app.telegram_security` does not import execution services, ORM models, or
Alembic. `create_app()` does not register a Telegram webhook. Live trading remains
disabled (`real_trading_enabled` is always false).

## Not in this slice

- HTTPS webhook adapter / Telegram secret-token header verification
- FastAPI routes
- PostgreSQL / Alembic
- RemoteActionGateway delegation to ApprovalService / ExecutionService
- `EXECUTE_PAPER_PLAN`
- `CLOSE` confirmation nonces
- Frontend enrollment UI
