# Staging ops notes (PRIVATE — do not commit)

Copy to `docs/staging_ops.local.md` (gitignored). Store demo password and other secrets only here or in Render/Vercel dashboards.

## URLs (public)

| Key | Value |
|-----|--------|
| `FRONTEND_URL` | https://alpha-trade-ai-eight.vercel.app |
| `BACKEND_URL` | https://alphatrade-api-staging.onrender.com |
| Demo email | `demo@alphatrade.ai` |

## Secrets (local only — never commit)

| Key | Your value |
|-----|------------|
| `DEMO_SEED_PASSWORD` | `<private-demo-password>` |
| `REDIS_URL` | Upstash `rediss://default:<token>@<host>.upstash.io:6379` (not `redis-cli` prefix) |

## Reseed staging (no Render shell)

```bash
export DEMO_SEED_PASSWORD='<private-demo-password>'   # or use server env:
DEMO_SEED_USE_SERVER_PASSWORD=true ./scripts/seed-demo.sh --api
```

## Validate demo login (never prints password)

```bash
export DEMO_SEED_PASSWORD='<private-demo-password>'
./scripts/validate-demo-staging.sh
```
