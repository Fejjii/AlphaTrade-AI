# AlphaTrade AI — Architecture (verified)

## Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0,
  Alembic, LangGraph + langchain-core, structlog, PyJWT, bcrypt, redis, httpx,
  qdrant-client. Managed with `uv`. Lint/format `ruff` (line-length 100, py312),
  types `mypy --strict`, tests `pytest` (`asyncio_mode=auto`, `pythonpath=src`).
- **Frontend:** Next.js 15, TypeScript, Tailwind CSS, Vitest, Playwright.
- **Data:** PostgreSQL, Redis, Qdrant.
- **CI:** GitHub Actions (`.github/workflows/ci.yml`).

## Repository layout

```
backend/            FastAPI app, tests, prompts, Dockerfile, pyproject
  src/app/
    api/routes/      HTTP endpoints (health, providers, knowledge, performance, ...)
    core/            config.py, deployment_safety.py, exchange_safety.py, auth, deps
    providers/       llm, embeddings, qdrant, market_data, exchange, billing, email,
                     factory.py, registry.py, embedding_dimensions.py
    services/        rag_service, quota_service, performance, journal, strategy, ...
    agents/          LangGraph runtime, nodes, response builder
    guardrails/      moderation, output validation
    db/              models, migrations (Alembic)
  scripts/           seed_demo.py, recreate_rag_collection.py, reingest_knowledge_base.py
  tests/             ~89 test modules
frontend/           Next.js 15 app, e2e (Playwright), components, lib
docs/               ~50 docs (architecture, security, staging, rag, etc.)
evaluation/         evaluate_agent.py, evaluate_rag.py, evaluate_guardrails.py, datasets
scripts/            ~48 deploy/smoke/validation shell scripts
render.yaml         Render blueprint (API + worker, paper-safe defaults)
```

## Request / agent flow

```
Next.js (JWT) → FastAPI → LangGraph agent
  guardrails → RAG retrieval (org/source scoped) → deterministic strategy signals
  → risk engine (ALLOW/WARN/BLOCK; BLOCK final) → optional LLM narrative (explanation only)
  → schema-validated response
Persistence: PostgreSQL (workflow), Redis (rate limit/cache), Qdrant (vectors)
```

The LLM layer only **explains**; it cannot change risk decisions or approval state.

## Providers & fallbacks

- LLM: `openai-llm` when `OPENAI_API_KEY` set, else `mock-llm`.
- Embeddings: `openai-embeddings` when keyed, else `mock-embeddings`. Dimension resolved
  by `providers/embedding_dimensions.py` (384 mock / 1536 for `text-embedding-3-small`).
- Vector store: `qdrant` (with `QDRANT_API_KEY` support + collection dimension guard),
  else in-memory fallback. Collection: `alphatrade_knowledge`.
- Market data: `binance-public` (read-only) or mock; provenance labels on responses.
- Exchange: mock / paper by default; optional BloFin **demo** (read-only) under strict gating.

## Key safety modules

- `core/deployment_safety.py`: `validate_deployment_settings`, `deployment_posture`
  (redaction-safe; booleans only for secrets).
- `core/exchange_safety.py`: exchange-mode gating; `trade_live` refuses startup.
- `core/config.py`: trading-mode validators (`execution_mode=trade` requires explicit enable).

## Endpoints of note (backward-compatibility anchors)

- `GET /health`, `GET /health/ready`
- `GET /providers/status`
- `GET /performance/report`, `GET /performance/portfolio`
- `POST /knowledge/ingest`, `POST /knowledge/search`

## CI jobs

`backend` (ruff check, ruff format --check, pytest) · `deployment-safety` ·
`frontend` (lint, typecheck, test, build) · `evaluation` · `docker-build` · `e2e-smoke`.
