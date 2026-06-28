# Slice 66b — BloFin demo venue validation (paper mirroring)

Controlled staging validation that places **exactly one** far-from-market BloFin demo **limit** order via `POST /execution/paper` and the demo mirror path, then cancels and cleans up.

**Status: complete** (2026-06-28). Real trading remains disabled. Any future demo venue order requires a new safety review and a **new** idempotency key.

---

## Successful run (commit `7515d23`)

| Field | Value |
|-------|--------|
| Idempotency key | `slice66b-demo-limit-003` (**consumed — never reuse**) |
| Internal order id | `d5377a68-75c1-4c1b-8a96-dbde02edca98` |
| Venue exchange order id | `1000131288930` (created and cancelled) |
| Position mode | `long_short_mode` |
| Position side | `long` (hedge-mode buy opening order) |
| Side / type / size / price | buy / limit / 0.1 / 57267.9 |
| Venue orders attempted | 1 |
| Venue orders created | 1 |
| Pre-cancel fill | `filled_size=0` (resting limit) |
| Post-cancel venue positions | 0 |
| Internal paper position | closed via `/positions/{id}/close-paper` |
| Idempotency retry | same internal order id; no duplicate ExchangeOrder or venue order |
| Staging validation | `validate-exchange-demo-staging.sh` 17/17; `verify-safety.sh` passed |

### Consumed idempotency keys (do not reuse)

| Key | Status |
|-----|--------|
| `slice66b-demo-limit-001` | Used in earlier attempts / tests |
| `slice66b-demo-limit-002` | Reserved — do not reuse without review |
| `slice66b-demo-limit-003` | **Consumed** — successful controlled retry |

---

## Prerequisites

- Staging: `EXCHANGE_MODE=paper_exchange_demo`, `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`
- `WORKER_ENABLED=false`, Telegram/external delivery disabled
- BloFin demo provider healthy; venue positions **0** before run
- `position_mode=long_short_mode` with hedge `positionSide=long` for buy opens (commit `7515d23+`)
- Migration `e4f5a6b7c8d9` applied (`venue_client_order_id` on exchange orders)
- Seed path: staging `DATABASE_URL` locally **or** Render SSH for `seed-approved-demo-proposal.py`

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run-slice66b-controlled-demo-order.sh` | Full orchestrator (preflight → seed → paper → verify → cancel → cleanup). **Do not re-run without Opus review and a new idempotency key.** |
| `scripts/seed-approved-demo-proposal.py` | Service-layer seed: one approved proposal + approval (`risk_result=ALLOW`). |
| `scripts/test-seed-path-staging.sh` | Smoke test for seed path only (**no order**). |
| `scripts/validate-exchange-demo-staging.sh` | Read-only exchange probes (17 steps, no orders). |

### Orchestrator usage (future runs only after review)

```bash
BACKEND_URL=https://alphatrade-api-staging.onrender.com \
IDEMPOTENCY_KEY=slice66b-demo-limit-004 \
./scripts/run-slice66b-controlled-demo-order.sh
```

Never reuse consumed keys listed above.

---

## Audit API note

`GET /audit/events` returns **`redacted_metadata`**, not `metadata`. Scripts and runbooks must read audit fields from `redacted_metadata` only. DB audit rows for `EXCHANGE_DEMO_ORDER_CREATED` include `position_mode` and `position_side` in that payload.

Example check (orchestrator / manual):

```python
meta = event.get("redacted_metadata") or {}
assert meta.get("position_mode") == "long_short_mode"
assert meta.get("position_side") == "long"
```

---

## Post-cancel order status

After cancel, BloFin may return transient errors on `GET /exchange/orders/{inst_id}/{id}`. Use the read-only query flag:

```http
GET /exchange/orders/BTC-USDT/{exchange_order_id}?after_cancel=true
```

Behavior (commit after Slice 66b hardening):

1. Bounded retry on transient venue probe failures (read-only).
2. If probe still fails but `EXCHANGE_DEMO_ORDER_CANCELLED` audit exists for that order id, returns `status=cancelled` with `status_source=cancel_audit_fallback`.
3. Without cancel audit, returns redacted `502 exchange_provider_error` (does not mask real venue errors).
4. **`GET /exchange/positions` → 0 open positions** remains the final safety source of truth.

---

## Hard rules (all runs)

- Do not enable real trading, worker, or Telegram.
- Do not call `set-position-mode` or `set-leverage`.
- Do not mutate BloFin account settings.
- Do not place a second order if anything fails.
- Do not retry with another consumed idempotency key.

---

## Related docs

- `docs/staging_deployment.md` — staging smoke checklist
- `docs/limitations_roadmap.md` — `paper_exchange_demo` mirroring scope
