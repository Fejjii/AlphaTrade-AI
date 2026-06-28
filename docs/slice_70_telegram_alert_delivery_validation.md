# Slice 70 — Controlled Telegram alert delivery validation

Owner-gated manual delivery of **one selected in-app alert** to Telegram via
`POST /alerts/{alert_id}/deliver-telegram`. No worker, scanner, trading, or bulk delivery.

**Status: complete** (2026-06-28). Commit **`31bd9b7`**.

---

## Successful staging run (commit `31bd9b7`)

| Field | Value |
|-------|--------|
| Endpoint | `POST /alerts/{alert_id}/deliver-telegram` |
| Confirmation phrase | `DELIVER_TELEGRAM_ALERT` |
| Selected alert id | `a1000061-0000-4000-8000-000000000061` |
| First attempt | `status=sent`, `channel=telegram`, `sent_at` present, `delivery_id` present |
| Dedupe attempt | `status=already_delivered`, same `delivery_id` and `sent_at` — **no second message** |
| Routing summary | `telegram_delivered_count` increased; `telegram_failed_count` unchanged (0) |
| Safety | `execution_mode=paper`, `real_trading_enabled=false`, `paper_only=true` |
| Worker / scanner | `worker_enabled=false`, `worker_running=false`, market watcher bridge off |
| Bulk delivery | Not used (`deliver-pending` not called) |
| Orders | **None** — no `/execution/paper`, no BloFin place/cancel |
| Read-only validation | `validate-exchange-demo-staging.sh` 17/17; `verify-safety.sh` passed |

### Prerequisites on staging

- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` configured in Render (never log values)
- `telegram_configured=true`, `telegram_chat_configured=true` on `GET /alerts/routing/summary`
- `telegram_alert_delivery_available=true`
- `TELEGRAM_ALERTS_ENABLED` may remain `false` — manual delivery does not require it

---

## Important: debug sends during initial validation

During the first staging validation session, **two extra Telegram messages** were sent for
**other demo alerts** while recovering from a script error (auto-picking alerts across
retries). Those sends are **non-blocking** for Slice 70 functionality but must not be repeated.

**Authoritative run:** exactly **one** message for alert `a1000061` (first `sent`, second
`already_delivered`).

### Future validation rules (mandatory)

1. Set **one explicit `ALERT_ID`** — never auto-pick or loop over alerts.
2. **Dry-run first** (`DRY_RUN=true`) — preflight only, no HTTP POST to deliver.
3. Print a **warning** immediately before the single send.
4. **Send at most once** per script invocation; **stop** after first `status=sent`.
5. Dedupe check uses the **same `ALERT_ID` only** — never retry with a different alert.
6. **Never** loop over all alerts; **never** call deliver after a script crash without
   checking whether the alert was already sent.
7. Browser smoke is **read-only** — do not click “Send to Telegram” unless explicitly scoped
   as a single controlled send with typed confirmation.

Use: [`scripts/validate-telegram-delivery-staging.sh`](../scripts/validate-telegram-delivery-staging.sh)

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/validate-telegram-delivery-staging.sh` | Guarded staging validation (preflight, optional single send, dedupe on same id) |
| `scripts/browser-smoke-alerts-staging.sh` | Read-only Playwright smoke for `/alerts` (no Telegram send) |
| `scripts/validate-exchange-demo-staging.sh` | Read-only exchange probes (17 steps, no orders) |
| `scripts/verify-safety.sh` | Paper-only safety invariants |

### Guarded delivery validation

```bash
# Preflight only (recommended first)
DRY_RUN=true \
ALERT_ID=a1000061-0000-4000-8000-000000000061 \
BACKEND_URL=https://alphatrade-api-staging.onrender.com \
./scripts/validate-telegram-delivery-staging.sh

# Single controlled send + dedupe (same ALERT_ID required)
ALERT_ID=<uuid> \
STAGING_DEMO_PASSWORD='...' \
BACKEND_URL=https://alphatrade-api-staging.onrender.com \
./scripts/validate-telegram-delivery-staging.sh
```

### Read-only browser smoke

```bash
STAGING_DEMO_PASSWORD='...' \
PLAYWRIGHT_SKIP_WEBSERVER=1 \
PLAYWRIGHT_BASE_URL=https://alpha-trade-ai-eight.vercel.app \
PLAYWRIGHT_API_URL=https://alphatrade-api-staging.onrender.com \
./scripts/browser-smoke-alerts-staging.sh
```

Does **not** click send — verifies panel, alerts list, delivered state, confirmation gate, no secrets.

---

## Hard rules (all runs)

- Do not enable real trading, worker, scanner, or bulk delivery.
- Do not call `/execution/paper` or BloFin place/cancel.
- Do not send more than one Telegram message per validation unless explicitly approved.
- Do not expose bot token, chat id, passwords, JWTs, or DB/Redis URLs in logs or reports.

---

## Related docs

- [alerts.md](alerts.md) — alert delivery model
- [notifications.md](notifications.md) — Telegram provider (Slice 46)
- [slice_66b_demo_venue_validation.md](slice_66b_demo_venue_validation.md) — order validation pattern
- [staging_deployment_runbook.md](staging_deployment_runbook.md) — staging smoke index
