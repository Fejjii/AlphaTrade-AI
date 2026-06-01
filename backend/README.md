# AlphaTrade AI — Backend

FastAPI service for the human-in-the-loop trading copilot.

> Safety: this scaffold runs in **paper mode** only. Real exchange trading is
> disabled by default and not wired in this slice.

## Requirements

- Python 3.12 (managed via [uv](https://docs.astral.sh/uv/))

## Setup

```bash
# from backend/
uv sync --extra dev          # create venv + install deps from uv.lock
cp ../.env.example ../.env    # configure environment (safe defaults)
```

## Run

```bash
chmod +x scripts/run_dev_server.sh
./scripts/run_dev_server.sh
```

Or manually (sets `PYTHONPATH` for the `src/` layout):

```bash
PYTHONPATH=src uv run uvicorn app.main:app --reload --port 8000
```

Then open:

- Health:          http://localhost:8000/health
- Readiness:       http://localhost:8000/health/ready
- Provider status: http://localhost:8000/providers/status
- API docs:        http://localhost:8000/docs

## Test & lint

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Docker (production image)

The backend image is built from the repo root Compose file:

```bash
# from repo root
docker compose up --build
```

Migrations run on container startup. For local hot-reload development, use
`uv run uvicorn app.main:app --reload` instead of Docker.

See `docs/deployment.md` and `../scripts/docker-migrate.sh`.
