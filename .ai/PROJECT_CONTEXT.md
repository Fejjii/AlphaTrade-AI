# AlphaTrade AI — Project Context

> Authoritative ChatGPT ↔ Cursor workflow: `.ai/MASTER_WORKFLOW.md` (v2.0).
> Handoff statuses: `IN_PROGRESS`, `REVIEW_REQUIRED`, `BLOCKED`, `FAILED`, `READY`
> (never `DRAFT`). See `.ai/MASTER.md` for the governance index.

## What it is

Human-in-the-loop AI trading **copilot** for crypto markets. It produces structured
analysis, applies a deterministic risk engine, requires explicit human approval, and
executes **paper-only** (simulated) trades. There is no live broker/exchange execution
wired in this release.

Release line: `v0.1.0-paper-mvp` (built in vertical slices 1–~91A per `docs/`).

## Primary objectives (where implemented, must be preserved)

- Human-vs-system comparison and paper validation of trading discipline
- Position sizing, stop loss, take profit, and runner logic (paper)
- Behavioral coaching / journal → lessons → RAG learning loop
- Deterministic risk engine with final `BLOCK` authority over proposals and paper execution
- Explicit approval workflow (approve / reject / modify) before any paper order

## Hard safety rules (NON-NEGOTIABLE)

1. **Paper first.** `real_trading_enabled=false` unless explicitly authorized in a separate future task.
2. No automatic live orders, withdrawals, transfers, leverage changes, or exchange account mutations.
3. Any future sensitive action requires: explicit human approval, audit logs, idempotency,
   conservative validation, and a kill switch.
4. Risk calculations must be deterministic and tested.
5. Market data must carry source and freshness timestamps (`is_live`, `fallback_used`).
6. Missing / stale / conflicting / degraded data must trigger conservative behavior.
7. Never imply guaranteed returns or autonomous profitability.
8. Protect credentials, API keys, exchange secrets, personal financial data, and audit records.
9. Preserve existing safety-critical behavior unless a task explicitly and safely changes it.

## Safety-critical surfaces (treat with extra care)

- `backend/src/app/core/deployment_safety.py` — staging/production invariants (paper-only enforcement)
- `backend/src/app/core/exchange_safety.py` — exchange mode gating; `trade_live` tombstone
- `backend/src/app/core/config.py` — `Settings`, trading-mode validators
- Risk engine, guardrails, approval workflow, audit/usage services
- Provider factories (LLM / embeddings / Qdrant / market data / exchange)

## Verified environment defaults

| Setting | Value |
|---------|-------|
| `EXECUTION_MODE` | `paper` |
| `ENABLE_REAL_TRADING` | `false` (Mode D real execution remains disabled) |
| `PROVIDER_MODE` | `mock` (repo/local default) / `fallback` (staging) |
| `EXCHANGE_MODE` | Safe default `paper_internal` (Mode A). Staging may run Mode C `paper_exchange_demo` when demo credentials are configured; never live. |
| `BILLING_ENABLED` | `false` |
| Notifications (Telegram/webhook) | disabled by default |
| Worker / scanner / scheduler automation | disabled by default |

## Live surfaces (staging, paper-only)

- Frontend: https://alpha-trade-ai-eight.vercel.app
- API: https://alphatrade-api-staging.onrender.com
- Demo user `demo@alphatrade.ai`; password only in Render `DEMO_SEED_PASSWORD` (never in repo)

## Unknowns / notes

- The local checkout path and any handoff-sync automation (script, LaunchAgent label,
  iCloud folder) are machine-specific and live outside the repo; do not hardcode them here.
