# Local setup

Use this guide for a disposable local paper demo or development environment. The [README](../README.md) describes the product; [deployment](deployment.md) covers hosted operations. Commands below were checked against repository paths/configuration at main `b58beda` on October 7, 2026, but a new stack was not launched for this documentation task.

## Requirements and safe context

- Git and Docker Compose for the full local stack.
- For host development: [uv](https://docs.astral.sh/uv/), Python 3.12 or compatible manifest-supported Python, Node.js 20+ and npm. Repository Docker images use Python 3.12 and Node 20.
- A disposable local database. Never run migrations, seed scripts or tests using an inherited shared/staging/production database URL.

Copy templates only when local files do not already exist; preserve existing configuration. Inspect environment overrides before starting. Keep `ENVIRONMENT=local`, `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `EXCHANGE_MODE=paper_internal`, `PROVIDER_MODE=mock`, `PERPETUAL_EVIDENCE_SOURCE=replay` and external/worker activation flags off.

```sh
git clone https://github.com/Fejjii/AlphaTrade-AI.git
cd AlphaTrade-AI
cp -n .env.example .env
cp -n frontend/.env.example frontend/.env.local
```

Do not put secrets in `NEXT_PUBLIC_*` fields or commit real environment files. The local dev JWT/default database values are not hosted credentials.

## Full local stack

From the repository root:

```sh
docker compose up --build
```

Compose includes PostgreSQL, Redis, Qdrant, backend **and frontend**. The API container entrypoint applies Alembic migrations to the Compose-local database. It enables local refresh-cookie mode and keeps real trading, Watcher and Telegram off. Compose's mock providers do not establish semantic retrieval or live market behavior. No paper worker service is included in this Compose file.

Open [the frontend](http://localhost:3000). The local auth flow is available at `/register` and `/login`; use a synthetic demo identity. API checks:

```sh
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/health/ready
curl --fail http://localhost:8000/providers/status
```

Open [API docs](http://localhost:8000/docs). Check posture and sources before following [the demo](demo_script.md). The mock/replay stack may show no canonical confirmed setup; it does not promise a seeded live Candidate or a full paper loop.

Stop the containers while retaining local volumes:

```sh
docker compose down
```

## Host development

Start the local data services first:

```sh
docker compose up -d postgres redis qdrant
```

The backend host uses localhost addresses from the local `.env`, rather than Compose service names. In a fresh local backend environment, apply migrations to that disposable database and run the development server:

```sh
cd backend
uv sync --frozen --extra dev
uv run alembic upgrade head
./scripts/run_dev_server.sh
```

The script sets `PYTHONPATH=src` and starts Uvicorn on `127.0.0.1:8000` by default. It does **not** run migrations itself. Host bearer mode differs from Compose cookie mode; keep backend and frontend auth settings aligned. Do not run a host API and container API on the same port.

In a second terminal, from the repository root:

```sh
cd frontend
npm ci
npm run dev
```

The frontend defaults to `http://localhost:8000` for browser API requests. Check `frontend/.env.local` before starting; public API/auth configuration is a build/development input. Do not reuse a hosted API origin for local tests that mutate data.

## Screenshots and demo fixtures

[Fixture capture instructions](screenshots_checklist.md) use synthetic sessions and explicit watermarks. They can demonstrate layout, confirmation controls and unavailable states without live credentials. Older fixture suites preserve earlier UI states; the source may have evolved. Do not substitute their balances, trades or speech callbacks for runtime evidence.

## Checks and common problems

[Testing and evaluation](evaluation.md) lists focused development checks and full release gates. Run only checks appropriate to the change on isolated resources.

| Symptom | Check |
| --- | --- |
| Backend import fails | Use the provided dev script or `PYTHONPATH=src`; install with `uv sync`. |
| Schema/table error | Confirm the selected database is local/disposable and its Alembic revision matches the checkout. |
| Login/refresh fails | API origin, exact CORS origin and cookie/bearer settings must agree. Secure cross-site settings belong to HTTPS hosting. |
| Provider unavailable | Read `/providers/status`; hosted fail-closed rules differ from permissive local mocks. |
| No current price or setup | Replay/mock is not live; stale/missing canonical evidence must stay explicit. Do not force approval or relax risk to create demo activity. |
| Build cannot fetch fonts/packages | Restore permitted network access or report the build unverified. A successful source check is not a completed build. |

No live activation, exchange credentials, Telegram token or billing key is needed for this local path.
