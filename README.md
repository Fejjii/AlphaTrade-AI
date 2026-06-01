# AlphaTrade AI

A production-style, modular, **human-in-the-loop** trading copilot. It watches
markets, detects predefined setups, proposes disciplined trade plans, enforces
risk with a deterministic engine, and **requires explicit human approval** before
any sensitive action.

> Safety first: this is an analysis, education, journaling, risk-management and
> decision-support platform. It does **not** execute real trades automatically.
> The default execution mode is **paper**; real exchange trading is **disabled by
> default** and not wired in the current scaffold.

## Status

Scaffold in progress, built in vertical slices.

- [x] Slice 1 — Repo structure & tooling (uv, Python 3.12, ruff, pytest)
- [x] Slice 2 — Backend core boot (settings, logging, errors, request-id
      middleware, working `/health`, `/health/ready`, `/providers/status`, tests)
- [x] Slice 3 — Pydantic v2 schemas for all core boundaries + validation tests
- [x] Slice 4 — SQLAlchemy 2.0 models, Alembic initial migration, SQLite test DB,
      repository base + `UserRepository`
- [x] Slice 5 — Deterministic risk engine (15 rules, allow/block tests)
- [x] Slice 6 — Seven MVP strategy modules + registry + synthetic tests
- [x] Slice 7 — Tool registry (10 tools, paper execution disabled for real exchange)
- [x] Slice 8 — Domain services + API routers wired (`/risk`, `/strategies`, `/tools`,
      `/auth`, `/execution/paper`, stubs for market/journal/knowledge/usage/chat)
- [x] Slice 9 — LangGraph agent skeleton (LangGraph workflow, routing, `/chat/message`)
- [x] Slice 10 — Runtime guardrails (`guardrails/` package, graph wiring, redaction, tests)
- [x] Slice 11 — Observability (audit/usage services, emitters, API, graph persistence, tests)
- [x] Slice 12 — RAG ingestion, embeddings, Qdrant abstraction, knowledge API, tests
- [x] Slice 13 — Stateful workflows (watchlist, proposals, approvals, paper execution,
      positions, journal, agent persistence)
- [x] Slice 14 — Docker Compose local production simulation (Postgres, Redis, Qdrant,
      backend Dockerfile, migrations, safety validation)
- [x] Slice 15 — Frontend PWA scaffold (Next.js, typed API client, core pages, safety UX)
- [x] Slice 16 — Auth, tenant security, session handling, frontend protection
- [x] Slice 17 — Production hardening (Redis rate limits, RBAC, JWT validation, frontend Docker, smoke tests)
- [x] Slice 18 — Live provider integration (OpenAI, embeddings, Qdrant fallback, structured agent responses, Playwright E2E)
- [x] Slice 19 — Live market data provider (Binance public read-only, indicators, market monitor)
- [x] Slice 20 — MVP workflow completion (approval → paper execution, journal RAG, E2E, demo docs)
- [x] Slice 21 — LLM narrative polish + evaluation harness (schema-validated explanation layer, deterministic fallback)
- [x] Slice 22 — Release readiness (httpOnly cookie auth, access denylist, E2E, Docker validation, mobile polish, docs)
- [x] Slice 23 — Staging deployment readiness (managed cloud path, env validation, deployment docs, smoke scripts, CI)
- [x] Slice 24 — Billing-grade usage tracking, organization quotas, cost controls, usage dashboard
- [x] Slice 25 — Email verification, password reset, invitation groundwork, account UI
- [x] Slice 26 — Stripe billing scaffold, subscription plans, usage export, billing UI

Only features wired into runtime are checked above. Nothing else is claimed as done.

## Tech stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, structlog, uv, Ruff, pytest
- **Data:** PostgreSQL, Redis, Qdrant (Docker Compose for local stack)
- **Agent:** LangGraph, OpenAI-compatible provider abstraction (mock by default)
- **Frontend:** Next.js 15, TypeScript, Tailwind, PWA-ready manifest

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (manages Python 3.12 automatically)
- [Node.js](https://nodejs.org/) 20+ and npm (frontend)
- [Docker](https://docs.docker.com/get-docker/) (for Compose stack)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quick start (backend, local dev)

```bash
cd backend
uv sync --extra dev
cp ../.env.example ../.env
uv run uvicorn app.main:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/providers/status
```

Interactive docs: http://localhost:8000/docs

## Quick start (frontend)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000 — register or sign in at `/register` or `/login`. Protected
pages require a valid session. **Local dev** uses bearer tokens in `sessionStorage`.
**Docker Compose** enables httpOnly refresh cookies — set `NEXT_PUBLIC_AUTH_COOKIE_MODE=true`
in frontend (included in Compose build).

See [docs/security.md](docs/security.md) for bearer vs cookie mode, token rotation, denylist, and tenant isolation.

Frontend quality checks:

```bash
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e   # Playwright smoke (SQLite backend via backend/scripts/run_e2e_server.sh)
```

See [docs/demo_script.md](docs/demo_script.md) for stakeholder walkthrough,
[docs/agent_workflow.md](docs/agent_workflow.md) for the approval → paper execution path, and
[docs/evaluation.md](docs/evaluation.md) for RAG and agent response quality evals.

Agent narrative eval:

```bash
cd backend
uv run python ../evaluation/evaluate_agent.py
uv run python ../evaluation/evaluate_rag.py
uv run python ../evaluation/evaluate_guardrails.py
```

Evaluation summary (all three):

```bash
cd backend
uv run python ../evaluation/evaluate_guardrails.py && \
uv run python ../evaluation/evaluate_rag.py && \
uv run python ../evaluation/evaluate_agent.py
```

GitHub Actions runs backend lint/tests, frontend lint/typecheck/tests/build, and optional Playwright smoke on push/PR (`.github/workflows/ci.yml`).

See [docs/architecture.md](docs/architecture.md) for provider fallback behavior and
[docs/rag_system.md](docs/rag_system.md) for RAG/Qdrant configuration.

The frontend is included in `docker-compose.yml`. For local development without Docker, run
`npm run dev` while the backend runs via `uv run uvicorn` or Docker Compose.

## Tests & lint (backend)

```bash
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Docker Compose (local production simulation)

Build and start the full stack (Postgres, Redis, Qdrant, backend, frontend):

```bash
docker compose up --build
```

Open http://localhost:3000 and sign in. The frontend calls the API at
`http://localhost:8000` (configured at build time via `NEXT_PUBLIC_API_URL`).

Smoke checks against a running stack:

```bash
chmod +x scripts/e2e-smoke.sh scripts/docker-validate.sh
./scripts/e2e-smoke.sh
./scripts/docker-validate.sh
```

Run migrations manually (also runs automatically on backend startup):

```bash
chmod +x scripts/docker-migrate.sh scripts/docker-reset-db.sh scripts/docker-validate.sh
./scripts/docker-migrate.sh
```

Check health endpoints:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/providers/status
```

Protected endpoints require a bearer token (register/login first):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"dev@example.com","password":"secure-password-1"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/usage/summary
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/audit/events
```

Validate Docker safety invariants:

```bash
./scripts/docker-validate.sh
```

Stop the stack:

```bash
docker compose down
```

Reset local Docker database (requires explicit confirmation — drops volumes):

```bash
CONFIRM=yes ./scripts/docker-reset-db.sh
```

See [docs/deployment.md](docs/deployment.md) for architecture, env vars, and
troubleshooting. For managed cloud staging (Vercel + Render), see
[docs/security_checklist.md](docs/security_checklist.md) and env templates
(`.env.staging.example`, `frontend/.env.staging.example`).

## Staging deployment (managed cloud)

Preferred path: **Vercel (frontend) + Render (backend + Postgres + Redis) + Qdrant Cloud**.

```bash
# Validate env before deploy (fill .env.staging from template first)
ENV_FILE=.env.staging ./scripts/check-env.sh

# Migrations (release command or manual)
./scripts/run-migrations.sh

# Post-deploy smoke
BASE_URL=https://your-api.example.com ./scripts/staging-smoke.sh
```

Real trading remains disabled — startup validation rejects unsafe staging/production config.

## Configuration

Copy `.env.example` to `.env` and adjust. Safe defaults keep `EXECUTION_MODE=paper`,
`ENABLE_REAL_TRADING=false`, and `PROVIDER_MODE=mock`. Set `JWT_SECRET` to a long random
value before any shared deployment. Real execution requires **both** `EXECUTION_MODE=trade`
and `ENABLE_REAL_TRADING=true`; the app refuses to start in any ambiguous combination.

Security details: [docs/security.md](docs/security.md).

Journal entries optionally sync to RAG when `JOURNAL_RAG_SYNC_ENABLED=true` (default). Secrets in journal text are redacted before ingestion.

## Source of truth

See `docs/source/` for the authoritative PRD, architecture, and trading playbook.
