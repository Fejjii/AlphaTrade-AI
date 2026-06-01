# AlphaTrade AI

![CI](https://github.com/Fejjii/AlphaTrade-AI/actions/workflows/ci.yml/badge.svg)

**Human-in-the-loop AI trading copilot** for crypto markets — structured analysis, deterministic risk, explicit approvals, and **paper-only** execution.

> **Safety:** Paper trading only. Real exchange execution is **disabled by default** and **not wired** in this release. No broker connectivity. No live Stripe charges unless billing is explicitly enabled with keys.

## At a glance

| | |
|---|---|
| **Release** | `v0.1.0-paper-mvp` — Slices 1–26 |
| **Execution** | `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false` |
| **Providers** | Mock by default; optional OpenAI, Qdrant, Binance public (read-only) |
| **Stack** | FastAPI · LangGraph · PostgreSQL · Redis · Qdrant · Next.js 15 |

## Key features

- **AI Trading Workspace** — LangGraph agent with guardrails, RAG context, and schema-validated responses
- **Deterministic risk engine** — 15 rules; `BLOCK` is final authority over proposals and paper execution
- **Human approval workflow** — proposals require explicit approve / reject / modify before paper orders
- **Paper execution** — simulated fills and positions; no exchange API keys for trading
- **Read-only market data** — Binance public REST or mock fallback with provenance labels (`is_live`, `fallback_used`)
- **RAG knowledge base** — playbooks, policies, and journal lessons (not trading signals)
- **Journal → RAG loop** — trade reviews auto-sync to knowledge for future agent retrieval
- **Observability** — audit events, usage metering, organization quotas, provider status dashboard
- **Auth & tenancy** — JWT sessions, RBAC (OWNER / TRADER / VIEWER), optional httpOnly refresh cookies
- **Billing scaffold** — Stripe placeholder + usage export (`BILLING_ENABLED=false` by default)

## Architecture

```mermaid
flowchart LR
  subgraph client [Frontend PWA]
    UI[Next.js 15]
  end
  subgraph api [Backend]
    API[FastAPI]
    Agent[LangGraph Agent]
    Risk[Risk Engine]
    Guard[Guardrails]
  end
  subgraph data [Data & providers]
    PG[(PostgreSQL)]
    Redis[(Redis)]
    Qdrant[(Qdrant)]
    LLM[LLM mock/OpenAI]
    Market[Binance public read-only]
  end
  UI -->|JWT| API
  API --> Agent
  Agent --> Guard
  Agent --> Risk
  Agent --> LLM
  Agent --> Market
  API --> PG
  API --> Redis
  Agent --> Qdrant
```

Detailed docs: [architecture](docs/architecture.md) · [agent workflow](docs/agent_workflow.md) · [RAG](docs/rag_system.md) · [security](docs/security.md)

## Screenshots

Paper MVP demo captures (local E2E stack, mock providers, **paper-only** execution):

| Dashboard | AI Workspace | Market Monitor |
|-----------|--------------|----------------|
| ![Dashboard](docs/screenshots/dashboard.png) | ![AI Workspace](docs/screenshots/ai_workspace.png) | ![Market Monitor](docs/screenshots/market_monitor.png) |

| Proposal detail | Approval workflow | Paper position |
|-----------------|-------------------|----------------|
| ![Proposal detail](docs/screenshots/proposal_detail.png) | ![Approval detail](docs/screenshots/approval_detail.png) | ![Paper position](docs/screenshots/paper_position.png) |

| Journal | Knowledge search | Usage & quota |
|---------|------------------|---------------|
| ![Journal](docs/screenshots/journal.png) | ![Knowledge search](docs/screenshots/knowledge_search.png) | ![Usage dashboard](docs/screenshots/usage_dashboard.png) |

| Audit events | Provider status | Settings |
|--------------|-----------------|----------|
| ![Audit events](docs/screenshots/audit_events.png) | ![Provider status](docs/screenshots/provider_status.png) | ![Settings](docs/screenshots/settings.png) |

Capture locally with `npm run capture:screenshots` (from `frontend/`) or follow [docs/screenshots_checklist.md](docs/screenshots_checklist.md).

## Tech stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, LangGraph, structlog, uv, Ruff, pytest
- **Frontend:** Next.js 15, TypeScript, Tailwind CSS, Vitest, Playwright
- **Data:** PostgreSQL, Redis, Qdrant
- **CI:** GitHub Actions — lint, tests, build, evaluation harness, optional E2E smoke

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12)
- [Node.js](https://nodejs.org/) 20+ and npm
- [Docker](https://docs.docker.com/get-docker/) — **recommended** for full stack (Postgres, Redis, Qdrant)
- PostgreSQL 16 — only if running backend locally without Docker

## Local setup

### 1. Clone and configure

```bash
git clone https://github.com/Fejjii/AlphaTrade-AI.git
cd AlphaTrade-AI
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Safe defaults: `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `PROVIDER_MODE=mock`.

### 2. Backend

```bash
cd backend
uv sync --extra dev
chmod +x scripts/run_dev_server.sh
./scripts/run_dev_server.sh
```

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/providers/status
```

API docs: http://localhost:8000/docs

> **Note:** `./scripts/run_dev_server.sh` sets `PYTHONPATH=src` so `app` imports resolve after `uv sync`. The default `DATABASE_URL` points at local Postgres — use **Docker Compose** (below) if you do not have Postgres running.

### 3. Frontend

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000 — register at `/register`, then sign in. Local dev uses bearer tokens in `sessionStorage`.

## Docker setup (recommended demo path)

Full stack with Postgres, Redis, Qdrant, backend migrations, and cookie-based auth:

```bash
docker compose up --build
```

Open http://localhost:3000. Smoke checks:

```bash
chmod +x scripts/docker-validate.sh scripts/e2e-smoke.sh
./scripts/docker-validate.sh
./scripts/e2e-smoke.sh
```

Stop: `docker compose down`

## Test commands

**Backend** (from `backend/`):

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

**Frontend** (from `frontend/`):

```bash
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e    # Playwright; starts SQLite backend automatically
```

**Evaluation harness** (from `backend/`):

```bash
uv run python ../evaluation/evaluate_agent.py
uv run python ../evaluation/evaluate_rag.py
uv run python ../evaluation/evaluate_guardrails.py
```

## Demo workflow

15-minute walkthrough for portfolio or stakeholder demos:

1. **Dashboard** — paper mode banner, provider status cards
2. **Market Monitor** — read-only ticker/OHLCV with live/mock labels
3. **AI Workspace** — chat: *"Analyze BTC pullback on 4h"*
4. **Proposals** — structured plan, risk result, exit levels
5. **Approvals** — approve for paper / reject / modify
6. **Paper execution** — simulated order on approved proposal
7. **Positions** — paper position lifecycle
8. **Journal** — lessons and tags → RAG sync
9. **Knowledge** — search ingested journal/playbook content
10. **Usage** — token/cost estimates and quotas
11. **Audit** — proposal, approval, execution events

Full script: [docs/demo_script.md](docs/demo_script.md)

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXECUTION_MODE` | `paper` | Trading mode (`paper` only in MVP) |
| `ENABLE_REAL_TRADING` | `false` | Hard kill switch for live orders |
| `PROVIDER_MODE` | `mock` | `mock` \| `fallback` \| `live` (trading still disabled) |
| `DATABASE_URL` | local Postgres | Workflow persistence |
| `JWT_SECRET` | dev placeholder | Set 32+ bytes for staging/production |
| `OPENAI_API_KEY` | empty | Optional LLM/embeddings |
| `BILLING_ENABLED` | `false` | Stripe scaffold off by default |
| `JOURNAL_RAG_SYNC_ENABLED` | `true` | Journal → knowledge auto-ingest |

Templates: `.env.example`, `.env.docker.example`, `.env.staging.example`, `frontend/.env.example`

## Known limitations

- No real exchange or broker execution
- No automated trading without human approval
- Stripe billing is scaffold-only — no live charges by default
- LLM narrative is optional; deterministic analysis + risk engine remain authoritative
- Binance public API may rate-limit; mock fallback is automatic

Full list: [docs/limitations_roadmap.md](docs/limitations_roadmap.md)

## Roadmap

| Slice | Focus |
|-------|--------|
| **27B+** | Production Stripe wiring (Checkout, Portal, entitlements) |
| **28** | Exchange adapter (still approval-gated; compliance review required) |
| **29** | LangSmith traces + scaled LLM evaluation |

## Deployment

Managed cloud path (Vercel + Render + Qdrant Cloud): [docs/deployment.md](docs/deployment.md)

Security checklist: [docs/security_checklist.md](docs/security_checklist.md)

## Development status

Built in vertical slices (1–26 complete). See [docs/limitations_roadmap.md](docs/limitations_roadmap.md) for scope boundaries.

## Source of truth

Product and architecture references: [docs/source/](docs/source/)
