# Deployment Command Pack

Copy-paste commands for staging prep and post-deploy verification.  
Replace placeholders — **never paste real secrets into committed files**.

| Placeholder | Example |
|-------------|---------|
| `<BACKEND_URL>` | `https://alphatrade-api-staging.onrender.com` |
| `<FRONTEND_URL>` | `https://alpha-trade-ai-eight.vercel.app` (Vercel Root Directory = `frontend`) |

---

## 1. Generate JWT secret

```bash
openssl rand -base64 32
```

Store in local `.env.staging` or `docs/staging_deployment_worksheet.local.md` only.

---

## 2. Validate staging env locally

```bash
cp .env.staging.example .env.staging
# Edit .env.staging with placeholders from docs/staging_deployment_worksheet.template.md

ENV_FILE=.env.staging ./scripts/check-env.sh
```

---

## 3. Run migrations

Against **local** Postgres (Docker):

```bash
docker compose up -d postgres
DATABASE_URL='postgresql+psycopg://alphatrade:alphatrade@localhost:5432/alphatrade' \
  ./scripts/run-migrations.sh
```

Against **staging** Postgres (from laptop, after Render DB exists):

```bash
DATABASE_URL='postgresql+psycopg://USER:PASS@HOST:5432/DB?sslmode=require' \
  ./scripts/run-migrations.sh
```

Render pre-deploy (on platform):

```bash
alembic upgrade head
```

---

## 4. Verify safety (deployed backend)

```bash
BASE_URL=<BACKEND_URL> ./scripts/verify-safety.sh
```

Expect: `execution_mode=paper`, `real_trading_enabled=false`, exchange mock/paper-only.

---

## 5. Staging smoke (backend + optional frontend CORS)

```bash
BASE_URL=<BACKEND_URL> ./scripts/verify-safety.sh

FRONTEND_URL=<FRONTEND_URL> \
COOKIE_MODE=true \
ALLOW_DEGRADED_READY=true \
BASE_URL=<BACKEND_URL> \
./scripts/staging-smoke.sh

# Slice 47 extended live smoke (dashboard, risk, notifications, market watcher, CORS)
FRONTEND_URL=https://alpha-trade-ai-eight.vercel.app \
COOKIE_MODE=true \
BACKEND_URL=https://alphatrade-api-staging.onrender.com \
./scripts/staging-live-smoke.sh
```

### Demo seed (Slice 50 — synthetic paper-only tenant)

Render shell or local with staging `DATABASE_URL`:

```bash
cd backend
DEMO_SEED_PASSWORD='your-chosen-demo-password' uv run python scripts/seed_demo.py
```

Owner API seed (requires `DEMO_SEED_ENABLED=true` and deployed backend):

```bash
DEMO_SEED_PASSWORD='...' BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/seed-demo.sh --api
```

Demo login: `demo@alphatrade.ai` · Frontend: https://alpha-trade-ai-eight.vercel.app

Local Docker (cookie mode):

```bash
COOKIE_MODE=true FRONTEND_URL=http://localhost:3000 ./scripts/staging-smoke.sh
```

---

## 6. Test provider status

```bash
curl -fsS <BACKEND_URL>/providers/status | python3 -m json.tool
```

Check: `exchange` is mock/paper; `billing` is mock/disabled; `fallback_used` where expected.

---

## 7. Test health and readiness

```bash
curl -fsS <BACKEND_URL>/health | python3 -m json.tool
curl -fsS <BACKEND_URL>/health/ready | python3 -m json.tool
```

Readiness may be **degraded** if Qdrant/OpenAI are down — use `ALLOW_DEGRADED_READY=true` in smoke.

---

## 8. Stop local Docker stack

```bash
docker compose down
```

Remove volumes (destructive):

```bash
CONFIRM=yes ./scripts/docker-reset-db.sh
docker compose down -v
```

---

## 9. Rebuild Docker stack

```bash
docker compose up --build -d
./scripts/docker-validate.sh
```

---

## 10. Run E2E locally

```bash
docker compose up --build -d
./scripts/e2e-smoke.sh

cd frontend
npm run test:e2e
```

Backend-only smoke (no Playwright browser tour):

```bash
BASE_URL=http://localhost:8000 FRONTEND_URL=http://localhost:3000 ./scripts/e2e-smoke.sh
```

---

## CLI availability (optional later)

Check without installing:

```bash
for cmd in render vercel upstash gh docker openssl; do
  command -v "$cmd" >/dev/null && echo "$cmd: OK" || echo "$cmd: MISSING"
done
```

Cloud deploy can use web dashboards if CLIs are missing.

---

## Related docs

- [pre_deployment_checklist.md](pre_deployment_checklist.md)
- [staging_execution_checklist.md](staging_execution_checklist.md)
- [staging_live_deployment_notes.md](staging_live_deployment_notes.md)
