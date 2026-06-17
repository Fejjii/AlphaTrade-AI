# Limitations and Roadmap

## Current limitations (post Slice 39)

### Lesson learning loop

- Lesson candidates require **explicit accept** before RAG/memory promotion
- Three accept paths: lesson only, attach rule, new strategy version (Slice 38) — no silent mutation
- Pending observations block paper promotion when critical; **accepted** lessons only affect eligibility
- Post-exit runner analysis depends on stored historical candles
- Missed profit estimates are **capped** to reduce hindsight bias
- Structured rule editor improves testability scoring but complex NL still needs human review

### Trading and execution

- **Real exchange execution is disabled** and not wired. `mock-exchange` is paper-only.
- Market data is **read-only** — no order placement against Binance or any exchange.
- Paper execution simulates fills locally — no broker connectivity.

### MVP workflow (Slice 20–39)

- End-to-end proposal → approval → paper order → position is implemented and tested.
- Journal → RAG sync is on by default; disable via `JOURNAL_RAG_SYNC_ENABLED=false`.
- Trading analytics (Slice 31) are **paper-only** and deterministic; discipline score is not LLM-generated.
- Strategy library & pre-trade (Slice 33–39): Strategy Lab includes backtest v1, structured rules, lesson → version flow, and **paper validation runtime**.
- Agent routes strategy-workflow, backtest, and paper validation intents to registered tools (Slice 34–39).
- **Backtest v1** replays stored OHLCV with fees/slippage — historical simulation only; not a profit guarantee. Complex NL rules may require structured translation (`needs_structured_rules`).
- **Paper validation runtime (Slice 39):** deterministic scan/tick bot creates `paper_signals` and simulated `paper_trades` — no exchange orders. Modes: `scan_only` (default) and `auto_paper`. Manual scan/tick only — no autonomous scheduler yet.
- **Paper eligibility (Slice 38):** conservative gates via `/paper-eligibility`; `paper_validated` does **not** enable live trading.
- Human-vs-system v2 adds delta fields; PnL simulation and runner tracking remain placeholders.
- Analytics do not replace the risk engine; small sample sizes can skew setup statistics.
- Playwright E2E: **API workflow in CI**; full browser tour optional locally (skipped in CI).
- LLM narrative polish is **optional** (Slice 21); deterministic analysis + risk engine remain authoritative.
- Docker Compose enables httpOnly refresh cookies + access token denylist (Slice 22).

### Paper validation runtime (Slice 39 — remaining gaps)

- Manual scan/tick only — no production scheduler; background loop disabled by default
- `scan_only` default creates signals without trades; `auto_paper` opens simulated positions locally
- Partial TP closes full position at first TP in v1 (multi-TP schema deferred)
- Mock/deterministic candles in tests; production uses stored historical data
- Not connected to proposal approval flow or exchange fills
- Does not change `ENABLE_REAL_TRADING` or execution mode

### Providers

- OpenAI integration uses HTTP directly (no streaming, no tool-calling from LLM yet).
- LLM narrative uses mock provider without `OPENAI_API_KEY`; real LLM only when configured.
- Usage metering records both `agent_chat` (light) and `agent_narrative` features.
- Binance public API may rate-limit or block; mock fallback is automatic.
- Qdrant vectors use 384 dimensions for mock embeddings; OpenAI `text-embedding-3-small` may differ — re-index when switching embedding providers.
- LangSmith tracing provider remains a mock placeholder.

### Frontend

- Mobile-first bottom nav with Dashboard, Workspace, Market, Proposals, Journal + More menu.
- Account UI: email verification notice, forgot/reset password, invitations page (OWNER).
- Settings shows email verification status; provider toggles remain env-driven.

### Auth and ops

- Email verification and password reset implemented (Slice 25); mock email in local dev.
- Organization invitations: create/list/accept/revoke API; no new-user invite signup yet.
- Staging/production default to `must_verify_email`; local allows unverified login.

- **Bearer mode** (local dev): both tokens in `sessionStorage`.
- **Cookie mode** (Docker / staging): refresh in httpOnly cookie; access token still in `sessionStorage` (short TTL).
- **Staging deployment** (Slice 23): Vercel + Render path documented; startup validation enforces HTTPS cookies and paper-only trading.
- Cost estimates in usage dashboard are **labeled by cost_source** — only `provider_reported` is billing-grade (see [usage_and_billing.md](usage_and_billing.md)).

## Fully mock mode

```bash
PROVIDER_MODE=mock
OPENAI_API_KEY=
# QDRANT_URL may be set but is ignored in mock mode
```

All providers report mock/fallback status at `GET /providers/status`.

## Real LLM + embeddings mode

```bash
PROVIDER_MODE=fallback
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDINGS_MODEL=text-embedding-3-small
```

Real trading remains disabled regardless of provider mode.

## Live market data mode (read-only)

```bash
PROVIDER_MODE=fallback
MARKET_DATA_ENABLED=true
MARKET_DATA_PROVIDER=binance
# No API key required for Binance public endpoints
```

Responses label `is_live`, `fallback_used`, and `is_stale`. Mock data is never presented as live.

### Billing (Slice 26)

- Billing **disabled by default** (`BILLING_ENABLED=false`); mock provider in local dev.
- Stripe Checkout/Portal APIs not fully wired — placeholder URLs when keys present.
- Usage export is aggregation only — not invoice generation.
- Static/tokenizer cost estimates are **not** billing-grade.

## Recommended next slices

1. **Paper validation scheduler** — optional background scan/tick loop (currently manual / disabled by default)
2. **Human-vs-system v2 + backtest comparison** — compare backtest to actual trades; runner tracking
3. **Slice 27B — Production Stripe wiring** (live Checkout, Portal, Billing Meters, entitlements)
4. **Slice 28 — Real exchange integration** (requires explicit enablement, withdrawal-free keys, compliance review)
5. **Slice 29 — LangSmith traces + LLM judge eval at scale** (optional quality loop)

Slice 27A (post-push validation, README/demo polish) is complete in the repo docs and setup scripts.
