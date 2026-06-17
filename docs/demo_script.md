# AlphaTrade AI — Demo Script

Use this script for portfolio demos, interviews, stakeholder walkthroughs, and onboarding.
Estimated time: **15–20 minutes** (Docker Compose recommended).

> **Before you start:** Confirm the **Paper mode active** banner and **Real trading disabled** badges are visible. Never demo with `ENABLE_REAL_TRADING=true`.

---

## 1. Product vision

AlphaTrade AI is a **human-in-the-loop trading copilot** for crypto markets. It helps traders:

- Watch markets with read-only data
- Detect predefined strategy setups (deterministic, not LLM-generated signals)
- Build structured trade proposals with mandatory exit plans
- Pass every plan through a deterministic risk engine
- Require **explicit human approval** before any paper simulation
- Journal outcomes and feed **accepted lessons after review** back into RAG

It is **not** an auto-trading bot. It is analysis, education, risk management, and decision support.

---

## 2. Safety model

Explain these invariants before showing features:

| Control | Value | Meaning |
|---------|-------|---------|
| `EXECUTION_MODE` | `paper` | Only simulated execution |
| `ENABLE_REAL_TRADING` | `false` | Hard kill switch — no live orders |
| Market data | Binance **public REST** or mock | Read-only; no trading API keys |
| LLM | Optional narrative layer | Never overrides risk or approval |
| Risk `BLOCK` | Final | Blocks paper execution even if mistakenly approved |

**Show:** Dashboard paper banner, provider status (`exchange` = mock/paper-only).

---

## 2b. Trader-first demo flow (recommended order)

A tight 8–10 minute path that follows the product workflow:

1. **Dashboard overview** — paper-only status, workflow stepper, "what to do next"
2. **Create or open a strategy** in Strategy Lab (status badge + next action)
3. **Show testability score** — structured rules drive backtest readiness
4. **Run/show a backtest result** — historical sample, fees + slippage
5. **Show paper eligibility** — conservative gates, blockers explained in plain language
6. **Start or view paper validation** — human-readable summary: running, mode, last scan, next action
7. **Run a market watcher scan** — read-only observations, no orders
8. **Show a bridge decision** — bridge triggers paper validation scans only
9. **Show an alert** — severity, source, suggested action; alerts never trade
10. **Review a lesson** — pending vs accepted vs rejected; accepting can update a strategy version
11. **Human vs system** — discipline analysis with calm, non-judgmental wording
12. **Emphasise paper-only safety** — real trading disabled throughout

---

## 3. Login

**Docker (recommended):** http://localhost:3000 — cookie auth enabled in Compose.

**Staging (Slice 48):** https://alpha-trade-ai-eight.vercel.app · API https://alphatrade-api-staging.onrender.com

Do **not** use https://alpha-trade-ai.vercel.app (wrong placeholder) or https://alphatrade-ai.vercel.app (legacy app).

```bash
FRONTEND_URL=https://alpha-trade-ai-eight.vercel.app \
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/staging-live-smoke.sh
```

**Local dev:** Register at `/register`, sign in at `/login`. Bearer tokens in `sessionStorage`.

Talking points:

- JWT access (15 min) + refresh rotation
- RBAC: OWNER / TRADER / VIEWER
- Docker/staging uses httpOnly refresh cookies

---

## 4. Dashboard (trader-first, Slice 43–45)

Route: `/` · API: `GET /dashboard/summary`

Highlight:

- **Paper mode active** banner + `PAPER mode` / `Real trading disabled` status badges
- **Workflow stepper:** Idea → Structure → Backtest → Paper Validate → Review Lessons → Improve Strategy, with per-step complete / blocked / next status
- **What to do next** from backend `next_recommended_action` (with link + reason)
- **Today's discipline** from `daily_discipline` snapshot: trades today, paper PnL today, configured limits, `risk_settings_source`, discipline score band, loss/green-day/frequency states, limitations (collapsed)
- **Strategy readiness** counts and top strategies needing action
- **Active paper validations**, **Open paper trades** (proposal flow + paper validation counts), **Latest alerts**, **Lessons pending review**
- Developer-first details (provider status, backend version, estimated cost, audit events) are tucked into a collapsed **Developer details** section

Talking points:

- Dashboard summary is **deterministic, paper-only, tenant-scoped** — no LLM, no broker data
- Daily PnL aggregates closed paper-validation trades and proposal-flow positions; limitations when unrealized marks are unavailable
- Risk limits resolve from daily state → user settings → system defaults (never silent invention)

---

## 4b. Risk Settings (Slice 45)

Route: `/risk` · API: `GET/PATCH /risk/settings`, `POST /risk/settings/reset-defaults`

1. Show daily loss limit, target, max trades, toggles for green-day / one-loss / overtrading guard
2. Save settings — audit event `risk_settings_updated`
3. Return to dashboard — Today's discipline shows configured limits and source
4. Agent: ask "What are my risk settings?" (read) vs "Set max trades to 3" (requires explicit confirmation)

---

## 5. Market Monitor (read-only)

Route: `/market`

1. Select symbol (e.g. BTCUSDT)
2. Show ticker and OHLCV
3. Point out provenance metadata: `is_live`, `fallback_used`, `provider_name`, `is_stale`
4. Explain: **no API key required** for Binance public data; mock fallback when offline or `PROVIDER_MODE=mock`

Optional: `/market/analyze` via API for indicators + strategy signals (deterministic Python, not LLM).

---

## 6. AI Trading Workspace

Route: `/workspace`

1. Send: *"Analyze BTC pullback on 4h"*
2. Show structured response:
   - Summary and analysis panels
   - Risk level and triggered rules
   - Optional trade proposal with entry/stop/targets
   - RAG citations when context retrieved
3. Separate **Deterministic analysis** from **Narrative explanation** (Slice 21)
4. Note: safety-critical fields come from agent state + risk engine, not free-form LLM text

---

## 7. Proposal generation

Route: `/proposals`

1. Open the proposal created from workspace chat (or list recent)
2. Show:
   - Symbol, side, timeframe, setup type
   - Entry, stop-loss, take-profit levels
   - Risk engine result (rules, severity, allow/block)
   - Confidence and invalidation criteria
3. Open **Proposal detail panel** — workflow status and linked approval

---

## 8. Approval workflow

Route: `/approvals`

1. Show pending approval linked to proposal
2. Demo decision paths:
   - **Approve for paper review** → enables paper order button
   - **Reject** → execution blocked
   **Needs more analysis** → execution blocked
   - **Modify** → audit preserved; re-approval required
3. Emphasize: no path to real exchange orders in MVP

---

## 9. Paper execution

From approved proposal detail or approvals panel:

1. Click **Create paper order (simulated)**
2. Confirm messaging: no real exchange order
3. Show idempotency and audit event emission

---

## 10. Position view

Route: `/positions`

1. Show paper position from prior step
2. Display entry, size, P&amp;L (simulated), status
3. Optional: close paper position
4. Reiterate: local simulation only

---

## 11. Journal entry

Route: `/journal`

1. Create entry: setup type, lessons, improvement rule, emotion and mistake tags
2. Optional: open `/journal?proposal_id={id}` to prefill from a proposal
3. Show **RAG synced** badge when ingest completed
4. Explain redaction of secrets before any RAG ingest
5. Run **Discipline analysis** — link to `/lessons` or create lesson candidate

---

## 11b. Lesson review (Slice 37)

Route: `/lessons`

1. Show pending lesson candidates from runner / stop discipline analysis
2. Accept with optional reviewer notes — accepted lessons may ingest to RAG
3. Reject — audit trail preserved, not promoted to memory
4. Strategy Lab structured rule editor — add/edit/remove blocks; testability score updates

---

## 12. Trading analytics

Route: `/analytics`

1. Setup performance cards (paper win/loss, proposals per setup)
2. Trade review metrics (mistakes, emotions, risk blocks)
3. Discipline score (deterministic 0–100, not LLM)
4. Risk behavior panel (warnings, journal completion rate)

In **Workspace**, ask: “What mistakes do I repeat?” — agent uses `analytics_summary_tool`.

## 13. Strategy library, backtest & paper validation (Slice 33–40)

Routes: `/strategy-lab`, `/strategy-lab/new`, `/strategy-lab/[id]`, `/strategy-lab/[id]/edit`, `/lessons`, `/manual-levels`, `/pre-trade`

1. Open **Strategy Lab** — list user strategy cards; create via **New strategy** (`StrategyCardForm`).
2. Open a strategy detail — save **structured rules**; run **Backtest v1** (symbol, timeframe, date range, capital, fees, slippage); review metrics and simulated trades.
3. If rules are vague NL, show **needs structured rules** limitation — do not expect fake trades.
4. Review **paper eligibility** panel — blockers, accepted vs pending lessons, `real_trading_enabled: false`.
5. **Start paper validation** — choose `scan_only` (signals only) or `auto_paper` (simulated trades).
6. **Run scan** — deterministic setup detection; show paper signals and latest scan result.
7. **Run tick** — monitor open simulated trades (stop, TP, runner, timeout); show closed trades and metrics.
8. Optional: **Stop run** when demo complete.
9. Open **Manual levels** — add support/resistance for a symbol.
10. Open **Pre-Trade** — run deterministic analysis; review sizing and **Loss acceptance** panel.
11. In **Workspace**, ask:
   - *"Backtest this strategy on BTC 15m"*
   - *"Is this strategy paper eligible?"*
   - *"Start paper validation for this strategy"*
   - *"Scan this strategy now"*
   - *"What paper signals were detected?"*
   - *"What did the paper bot do?"*
   - *"Should I improve or retire this strategy?"*
11. **Scheduler & alerts (Slice 40–46)** — scheduler status (disabled by default), manual tick, runtime history, Alerts page with delivery status (external delivery disabled unless configured), Settings notification preferences (Telegram/webhook off by default), Market Watcher read-only scan prep.
12. Emphasize: backtest is **historical simulation**; paper validation is **local simulation** — neither enables live trading.

Optional API smoke:

```bash
./scripts/strategy-smoke.sh
./scripts/paper-validation-smoke.sh
./scripts/market-watcher-smoke.sh   # Slice 42 — read-only watcher + paper scan bridge
./scripts/notifications-smoke.sh    # Slice 46 — preferences, delivery status, test send (no secrets)
```

**Docker full stack** (recommended before demo):

```bash
docker compose up --build -d
./scripts/docker-validate.sh
./scripts/e2e-smoke.sh
./scripts/market-watcher-smoke.sh
./scripts/notifications-smoke.sh
docker compose down
```

---

## 14. Journal → RAG learning loop

Route: `/knowledge`

1. Search for text from the journal entry just created
2. Show `trade_journal` source type and citations
3. Explain agent retrieval includes journal **lessons only** — not signals or order instructions
4. Setting: `JOURNAL_RAG_SYNC_ENABLED=true` (default)

Return to **Workspace** and note how future chats may cite past lessons.

---

## 14. Usage dashboard

Route: `/usage`

1. Show organization usage summary
2. Highlight `cost_source` labels (static vs provider-reported)
3. Show quota panel — soft warnings vs hard blocks
4. Note: billing disabled by default (`BILLING_ENABLED=false`)

Optional: `/billing` — plan catalog and mock checkout (no live charges).

---

## 14. Audit log

Route: `/audit`

1. Filter or scroll to recent events
2. Show chain: `trade_proposal_created` → `approval_*` → `paper_order_created`
3. Mention `request_id` / trace correlation with backend logs

---

## 15. Provider status

Route: `/` (dashboard cards) or `GET /providers/status`

Walk through provider kinds:

- **llm / embeddings** — mock or OpenAI with fallback
- **vector** — in-memory or Qdrant
- **market_data** — mock or Binance public
- **exchange** — mock, paper-only, real trading disabled
- **billing / email** — mock by default

Transparency: every provider reports `is_mock`, `fallback_used`, and detail text.

---

## 16. Limitations and roadmap

Be explicit about MVP boundaries:

- No real exchange or broker execution
- No real broker or exchange execution without explicit future approval (paper validation may open simulated trades in `auto_paper` mode)
- Stripe billing scaffold only — no live payments unless explicitly configured
- Cost estimates labeled by source — not invoice-grade unless `provider_reported`
- Responsive web PWA — not native mobile apps

Roadmap: [limitations_roadmap.md](limitations_roadmap.md)

---

## 17. Screenshot checklist

Capture during this demo for GitHub and interviews. Full list: [screenshots_checklist.md](screenshots_checklist.md)

Minimum set:

1. Dashboard with paper banner
2. AI Workspace with structured analysis
3. Market Monitor with provenance labels
4. Proposal detail with risk result
5. Approval panel
6. Paper position
7. Journal entry
8. Knowledge search hit
9. Usage / quota dashboard
10. Audit events
11. Provider status cards
12. Login or settings (verification status)

Save files under `docs/screenshots/` using names from the checklist.

---

## Quick start commands

**Docker (portfolio default):**

```bash
git clone https://github.com/Fejjii/AlphaTrade-AI.git
cd AlphaTrade-AI
docker compose up --build
./scripts/docker-validate.sh
```

**Local dev (requires Postgres or use Docker for data stores):**

```bash
cp .env.example .env
cd backend && uv sync --extra dev && ./scripts/run_dev_server.sh
# separate terminal:
cd frontend && npm ci && npm run dev
```

**Automated verification:**

```bash
cd backend && uv run pytest
cd frontend && npm run test:e2e
cd backend && uv run python ../evaluation/evaluate_agent.py
```

---

## Closing talking points

- Production-style architecture: guardrails, audit, quotas, RBAC, deployment validation
- Safety-first defaults suitable for portfolio and compliance discussions
- Clear extension path: Stripe entitlements, optional exchange adapter (still approval-gated)
- Evaluation harness for agent, RAG, and guardrail regression

Related docs: [architecture.md](architecture.md) · [agent_workflow.md](agent_workflow.md) · [security.md](security.md) · [deployment.md](deployment.md)
