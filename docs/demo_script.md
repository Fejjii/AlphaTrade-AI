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
- Journal outcomes and feed lessons back into RAG for continuous learning

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

## 3. Login

**Docker (recommended):** http://localhost:3000 — cookie auth enabled in Compose.

**Local dev:** Register at `/register`, sign in at `/login`. Bearer tokens in `sessionStorage`.

Talking points:

- JWT access (15 min) + refresh rotation
- RBAC: OWNER / TRADER / VIEWER
- Docker/staging uses httpOnly refresh cookies

---

## 4. Dashboard

Route: `/`

Highlight:

- **Paper mode active** banner
- Provider status cards (LLM, embeddings, Qdrant, Redis, market data, exchange, billing, email)
- Quick links to Workspace, Market, Proposals
- Kill switch affordance on trading pages (UI guard, not live trading)

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

## 13. Strategy library, backtest & paper validation (Slice 33–35)

Routes: `/strategy-lab`, `/strategy-lab/new`, `/strategy-lab/[id]/edit`, `/manual-levels`, `/pre-trade`

1. Open **Strategy Lab** — list user strategy cards; create via **New strategy** (`StrategyCardForm`).
2. Open a strategy detail — run **Backtest v1** (symbol, timeframe, date range, capital, fees, slippage); review metrics, equity curve summary, and simulated trades table.
3. If rules are vague NL, show **needs structured rules** limitation — do not expect fake trades.
4. Start **paper validation** — metrics from linked paper positions (win rate, PnL, drawdown, recommendation).
5. Open **Manual levels** — add support/resistance for a symbol.
6. Open **Pre-Trade** — run deterministic analysis; review sizing and **Loss acceptance** panel.
7. In **Workspace**, ask:
   - *"Backtest this strategy on BTC 15m"*
   - *"Is this strategy paper eligible?"*
   - *"What did the backtest show?"*
   - *"Why is this strategy not validated?"*
8. Emphasize: backtest is **historical simulation only**; paper validation does not enable live trading.

Optional API smoke: `./scripts/strategy-smoke.sh`

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
- No auto-trading without approval
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
