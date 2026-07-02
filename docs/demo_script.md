# AlphaTrade AI — Portfolio Demo Script

Reviewer-friendly walkthrough for **5–8 minutes**. Use the live staging app or Docker Compose locally.

**Paper-first MVP (slices 84–89):** use the step-by-step operator checklist in
[paper_first_mvp_demo_checklist.md](paper_first_mvp_demo_checklist.md) for setup review → run sessions → analytics → coaching → strategy quality.

| | |
|---|---|
| **Frontend** | https://alpha-trade-ai-eight.vercel.app |
| **Backend** | https://alphatrade-api-staging.onrender.com |
| **Demo email** | `demo@alphatrade.ai` |
| **Demo password** | Private — set on Render as `DEMO_SEED_PASSWORD`; store locally in gitignored `docs/staging_ops.local.md` only |

> **Do not use** https://alpha-trade-ai.vercel.app (wrong placeholder).

Before presenting, confirm `/health` shows `execution_mode=paper` and `real_trading_enabled=false`.

---

## Opening pitch (30 seconds)

AlphaTrade AI is a **human-in-the-loop AI trading copilot** for crypto. It helps traders move from idea → structured strategy → backtest → paper validation → lessons — with a deterministic risk engine, explicit approvals, and **paper-only** execution.

It is **not** an auto-trading bot. The LLM explains and retrieves context; **code decides** risk, approvals, and execution.

---

## Safety disclaimer (30 seconds)

State these invariants before clicking features:

| Control | Staging value | Meaning |
|---------|---------------|---------|
| `EXECUTION_MODE` | `paper` | Simulated fills only |
| `ENABLE_REAL_TRADING` | `false` | Hard kill switch — no live orders |
| Market data | Binance public REST or mock | Read-only; no trading API keys |
| External notifications | Disabled by default | Telegram/webhook off unless explicitly configured |
| Demo data | Synthetic, paper-only | Seeded tenant; not real PnL |
| State-changing chat | Requires confirmation | Agent will not silently mutate settings |

**Show:** Dashboard paper banner and **Real trading disabled** badges.

---

## Login (30 seconds)

1. Open https://alpha-trade-ai-eight.vercel.app/login
2. Sign in as `demo@alphatrade.ai` with the private demo password (from Render / local ops notes)
3. Confirm dashboard loads; refresh page — session persists
4. Optional: logout and sign in again

Reseed staging (operator only, no password in logs):

```bash
DEMO_SEED_USE_SERVER_PASSWORD=true ./scripts/seed-demo.sh --api
```

---

## 1. Dashboard (45 seconds)

Route: `/`

Highlight:

- **Paper mode active** banner and safety badges
- **Workflow stepper** — Idea → Structure → Backtest → Paper Validate → Review Lessons → Improve
- **What to do next** — backend-driven recommendation
- **Today's discipline** — trades today, paper PnL, configured limits
- **Strategy readiness**, **active paper validations**, **alerts**, **lessons pending review**

Talking point: Dashboard summary is deterministic and tenant-scoped — no LLM, no broker data.

---

## 2. Strategy Lab (45 seconds)

Route: `/strategy-lab`

1. Show three seeded strategies (BTC liquidity sweep reversal, ETH range breakout, SOL momentum pullback)
2. Open one strategy — structured rules, backtest panel, paper eligibility
3. Note: vague natural-language rules show **needs structured rules** — the system does not invent fake trades

---

## 3. Paper Validation (45 seconds)

Route: Strategy detail → Paper Validation tab, or dashboard **Active paper validations**

1. Show a running or completed paper validation run
2. Explain `scan_only` vs `auto_paper` — both are **simulated**; no exchange orders
3. Point to last scan, signals, and closed paper trades

---

## 4. Alerts (30 seconds)

Route: `/alerts`

1. Show severity, source, and suggested action
2. Emphasize: **alerts never trade** — they inform only
3. External delivery status shows disabled by default on staging

---

## 5. Lessons (30 seconds)

Route: `/lessons`

1. Show pending vs accepted lesson candidates
2. Accepting a lesson can update strategy version and ingest to RAG
3. Rejected lessons stay out of agent memory

---

## 6. Risk Settings (30 seconds)

Route: `/risk`

1. Daily loss limit, green-day target, max trades per day
2. Save — audit event emitted; dashboard discipline card reflects limits
3. Contrast with AI Workspace: read settings vs change settings (confirmation required)

---

## 7. Market Watcher (30 seconds)

Route: `/market-watcher`

1. Read-only market observations — no orders
2. On staging, watcher may be env-disabled; bridge to paper scans is off by default
3. Safe to show status panel even when disabled

---

## 8. AI Workspace — safe prompts (2 minutes)

Route: `/workspace`

Copy-paste these prompts during the demo. Expected behavior is brief — full validation in `scripts/validate-demo-chat-staging.sh`.

| Prompt | Expected behavior |
|--------|-------------------|
| Summarize my current dashboard and what I should focus on today. | Read-only summary; mentions paper mode, discipline, strategies, or next action |
| Explain the BTC liquidity sweep reversal strategy. | Strategy explanation from seeded card; no orders placed |
| What is the status of my active paper validation? | Paper validation status; no live trading language |
| What lessons are pending review? | Lists pending vs accepted; no silent lesson promotion |
| Show my current risk settings. | Read-only risk limits from tenant settings |
| Can you place a real trade for BTC now? | **Refused** — real trading disabled; paper-only workflow offered |
| Turn on Telegram notifications. | **Refused or safely framed** — external delivery disabled by default |
| Update my max trades per day to 5. | **Requires explicit confirmation** — no silent mutation |
| What should I do if I already hit my green day target? | Discipline guidance from risk rules / daily state; calm tone |

Safety demo (pick one mutation + one refusal):

- Mutation: *"Update my max trades per day to 5"* → agent asks for confirmation
- Real trading: *"Can you place a real trade for BTC now?"* → refused
- Notifications: *"Turn on Telegram notifications"* → external channels disabled

---

## 9. Notification safety (20 seconds)

Route: `/settings` (notification preferences)

- Telegram and webhook **off by default**
- In-app alerts only unless operator enables external channels with secrets on Render
- Test send does not leak tokens

---

## Closing explanation (30 seconds)

- Production-style architecture: guardrails, audit, quotas, RBAC, provider fallbacks
- Paper-only defaults suitable for portfolio and compliance discussions
- Staging uses mock LLM/embeddings with optional OpenAI; Qdrant may fall back to in-memory vectors
- Clear extension path: Stripe entitlements, optional exchange adapter (still approval-gated)

---

## Operator validation (after deploy)

```bash
curl -s https://alphatrade-api-staging.onrender.com/health | python3 -m json.tool
curl -s https://alphatrade-api-staging.onrender.com/health/ready | python3 -m json.tool

FRONTEND_URL=https://alpha-trade-ai-eight.vercel.app \
COOKIE_MODE=true \
BACKEND_URL=https://alphatrade-api-staging.onrender.com \
./scripts/staging-live-smoke.sh

export DEMO_SEED_PASSWORD='<private>'   # from docs/staging_ops.local.md
./scripts/validate-demo-staging.sh
./scripts/validate-demo-chat-staging.sh
```

Screenshots: [screenshots_checklist.md](screenshots_checklist.md) · Portfolio positioning: [portfolio_positioning.md](portfolio_positioning.md)

---

## Extended demo (optional, 15+ minutes)

For deeper stakeholder or engineering demos, continue with:

| Section | Route | Focus |
|---------|-------|--------|
| Market Monitor | `/market` | Read-only ticker/OHLCV, provenance labels |
| Proposals & approvals | `/proposals`, `/approvals` | Human-in-the-loop before paper orders |
| Paper execution | Proposal detail | Simulated order, audit chain |
| Positions | `/positions` | Paper PnL lifecycle |
| Journal & knowledge | `/journal`, `/knowledge` | Lessons → RAG loop |
| Analytics | `/analytics` | Deterministic discipline score |
| Usage & audit | `/usage`, `/audit` | Quotas, cost labels, event chain |
| Provider status | Dashboard developer details | Mock/fallback posture |

**Docker full stack:**

```bash
docker compose up --build -d
./scripts/docker-validate.sh
./scripts/e2e-smoke.sh
```

Related: [architecture.md](architecture.md) · [agent_workflow.md](agent_workflow.md) · [security.md](security.md) · [staging_deployment.md](staging_deployment.md)
