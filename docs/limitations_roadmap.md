# Limitations and Roadmap

## Current limitations (post Slice 26)

### Trading and execution

- **Real exchange execution is disabled** and not wired. `mock-exchange` is paper-only.
- Market data is **read-only** — no order placement against Binance or any exchange.
- Paper execution simulates fills locally — no broker connectivity.

### MVP workflow (Slice 20–22)

- End-to-end proposal → approval → paper order → position is implemented and tested.
- Journal → RAG sync is on by default; disable via `JOURNAL_RAG_SYNC_ENABLED=false`.
- Playwright E2E: **API workflow in CI**; full browser tour optional locally (skipped in CI).
- LLM narrative polish is **optional** (Slice 21); deterministic analysis + risk engine remain authoritative.
- Docker Compose enables httpOnly refresh cookies + access token denylist (Slice 22).

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

1. **Slice 27B — Production Stripe wiring** (live Checkout, Portal, Billing Meters, entitlements)
2. **Slice 28 — Real exchange integration** (requires explicit enablement, withdrawal-free keys, compliance review)
3. **Slice 29 — LangSmith traces + LLM judge eval at scale** (optional quality loop)

Slice 27A (post-push validation, README/demo polish) is complete in the repo docs and setup scripts.
