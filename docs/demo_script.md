# AlphaTrade AI — Demo Script

Use this script for live demos, stakeholder walkthroughs, and onboarding. Focus is **workflow readiness**, not visual polish.

## 1. What the app is

AlphaTrade AI is a **human-in-the-loop trading copilot** for crypto markets. It combines:

- Read-only market data and deterministic strategy signals
- A deterministic risk engine (final authority)
- Structured trade proposals with mandatory exit plans
- Explicit human approval before any paper execution
- Journaling and RAG-based learning from past trades

## 2. Why it exists

Trading decisions benefit from structure, risk discipline, and review — not impulsive automation. AlphaTrade supports **analysis, planning, approval, paper simulation, and post-trade learning** without placing real exchange orders.

## 3. Safety model

- **Default execution mode: paper**
- **Real trading: disabled** (`enable_real_trading=false`)
- No private exchange API keys in the MVP
- Market data: **Binance public REST only** (read-only) or mock fallback
- LLM is optional; structured responses are built deterministically from agent state
- Risk `BLOCK` is final for paper execution
- Approvals gate paper orders — rejected / needs-more-analysis / modified approvals cannot execute

Show the **Paper mode active** banner on the dashboard.

## 4. Architecture overview

- **Frontend:** Next.js PWA — dashboard, workspace, proposals, approvals, positions, journal, knowledge
- **Backend:** FastAPI + LangGraph agent + domain services
- **Data:** PostgreSQL (metadata), Redis (cache/rate limits), Qdrant or in-memory vectors (RAG)
- **Providers:** mock by default; live OpenAI / Qdrant / Binance public when configured

See [architecture.md](architecture.md) and [agent_workflow.md](agent_workflow.md).

## 5. Live market data (read-only)

1. Open **Market Monitor** (`/market`)
2. Show ticker/OHLCV with provenance: `is_live`, `fallback_used`, `provider_name`
3. Explain: no API key, no order placement

## 6. AI trading workspace

1. Open **Workspace** (`/workspace`)
2. Send: *"Analyze BTC pullback on 4h"*
3. Show structured response: summary, analysis, risk, optional proposal
4. Note deterministic response layer (no reliance on LLM narrative for safety-critical fields)

## 7. Risk engine

1. Open a **Proposal** with risk result
2. Show triggered rules and severity
3. Explain: blocked proposals cannot reach paper execution even if mistakenly approved

## 8. Approval workflow

1. Open **Approvals** (`/approvals`)
2. Show pending approval linked to proposal
3. Demo actions:
   - **Approve for paper review** → enables paper order button
   - **Reject** → execution blocked
   - **Needs more analysis** → execution blocked
   - **Modify** → audit trail preserved; execution blocked until re-approved

## 9. Paper execution

1. On approved proposal, click **Create paper order (simulated)**
2. Confirm messaging: no real exchange order
3. Open **Positions** — show paper position created
4. Optional: close paper position

## 10. Journal and RAG learning loop

1. Open **Journal** — create entry with lessons, emotions, mistake tags
2. Explain auto-sync to knowledge base (`trade_journal` source type) when `JOURNAL_RAG_SYNC_ENABLED=true`
3. Open **Knowledge** — search for lesson text; show citations
4. Future agent runs can retrieve journal lessons via RAG (rules/lessons only — not signals)

## 11. Audit and usage tracking

1. Open **Audit** — show proposal, approval, paper order events
2. Open **Usage** — show LLM/embedding event counts (placeholder costs)

## 12. Intentionally out of scope (MVP)

- Real exchange order execution
- Automated trading without approval
- LLM-generated trade signals bypassing risk
- Billing-grade cost accounting
- Mobile-native apps (responsive web only)

## 13. Future roadmap

See [limitations_roadmap.md](limitations_roadmap.md):

- Live trading adapter (still approval-gated)
- Richer LLM narrative with eval harness
- Advanced charting and alert delivery
- Multi-exchange market data

## 14. Frontend UX polish (demo tips)

- **Paper mode active** and **Real trading disabled** badges visible on dashboard and workspace
- Mobile bottom nav: Dashboard, Workspace, Market, Proposals, Journal + More menu
- Dashboard provider cards show OpenAI, embeddings, Qdrant, Redis, market data status
- Empty states guide next actions; kill switch visible on trading pages
- No "Place real order" or live execution CTAs anywhere

## Quick demo path (15 min)

**Docker (recommended for portfolio):**

```bash
docker compose up --build
./scripts/docker-validate.sh
```

Open http://localhost:3000 — cookie auth enabled by default in Compose.

**Local dev:** Register → Dashboard (safety banner) → Watchlist → Workspace chat → Proposals → Approvals → Paper order → Positions → Journal → Knowledge search → Audit → Usage → Logout

## Local E2E verification

```bash
cd frontend && npm run test:e2e
# Backend uses SQLite via backend/scripts/run_e2e_server.sh — no Docker required
```

See [deployment.md](deployment.md) for full stack with Docker Compose.
