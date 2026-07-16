# Staging ops notes (PRIVATE — do not commit)

Copy to `docs/staging_ops.local.md` (gitignored). Store passwords and other secrets **only** here, in your shell environment, or in Render/Vercel dashboards. **Never** commit real passwords to tracked files.

## URLs (public)

| Key | Value |
|-----|--------|
| `FRONTEND_URL` | https://alpha-trade-ai-eight.vercel.app |
| `BACKEND_URL` | https://alphatrade-api-staging.onrender.com |
| Demo email | `demo@alphatrade.ai` |
| Bootstrap email | `seed-bootstrap-1782212606@example.com` |

## Secrets (local only — never commit)

| Key | Your value |
|-----|------------|
| `DEMO_SEED_PASSWORD` | `<private-demo-password>` (min 12 characters; Render env for `demo@alphatrade.ai`) |
| `STAGING_BOOTSTRAP_PASSWORD` | `<private-bootstrap-password>` (paper-first workflow smokes) |
| `DEMO_BOOTSTRAP_PASSWORD` | Same as `STAGING_BOOTSTRAP_PASSWORD` when using `./scripts/seed-demo.sh --api` |
| `REDIS_URL` | Upstash `rediss://default:<token>@<host>.upstash.io:6379` (not `redis-cli` prefix) |

Export for smoke scripts (never log the value):

```bash
export STAGING_BOOTSTRAP_PASSWORD='<private-bootstrap-password>'
export DEMO_BOOTSTRAP_PASSWORD="$STAGING_BOOTSTRAP_PASSWORD"
```

## Rotate bootstrap password (operator)

After a compromise or credential loss, rotate in Postgres (never prints the password):

```bash
# Interactive (hidden prompt):
ENV_FILE=.env.staging ./scripts/reset-staging-bootstrap-password.sh

# Non-interactive:
STAGING_BOOTSTRAP_PASSWORD_NEW='<new-password>' ENV_FILE=.env.staging \\
  ./scripts/reset-staging-bootstrap-password.sh
```

Then update `docs/staging_ops.local.md` and re-export `STAGING_BOOTSTRAP_PASSWORD`.

Validate after rotation:

```bash
export STAGING_BOOTSTRAP_PASSWORD='<new-password>'
./scripts/portfolio-smoke.sh
./scripts/browser-smoke-portfolio-staging.sh
```

## Reseed staging demo tenant (no Render shell)

```bash
export DEMO_SEED_PASSWORD='<private-demo-password>'   # or use server env:
DEMO_SEED_USE_SERVER_PASSWORD=true ./scripts/seed-demo.sh --api
```

Uses existing bootstrap owner when `DEMO_BOOTSTRAP_PASSWORD` is set; otherwise registers a temporary bootstrap owner.

## Validate demo login (never prints password)

```bash
export DEMO_SEED_PASSWORD='<private-demo-password>'   # min 12 characters
./scripts/validate-demo-staging.sh
./scripts/validate-demo-chat-staging.sh
```
