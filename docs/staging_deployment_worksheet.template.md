# Staging Deployment Worksheet (Template)

> **Do not store real secrets in this file.**  
> Copy locally to `docs/staging_deployment_worksheet.local.md` (gitignored) and fill values there.

---

## Public URLs (safe to note after deploy)

| Placeholder | Your value |
|-------------|------------|
| `BACKEND_URL` | `https://<YOUR-RENDER-SERVICE>.onrender.com` |
| `FRONTEND_URL` | `https://<YOUR-VERCEL-APP>.vercel.app` |
| `CORS_ORIGINS` | `https://<YOUR-VERCEL-APP>.vercel.app` |

---

## Data stores (secrets — local file only)

| Placeholder | Notes |
|-------------|--------|
| `DATABASE_URL` | Render Postgres external URL (`postgres://` OK; app normalizes driver) |
| `REDIS_URL` | Upstash: `rediss://default:<token>@<host>.upstash.io:6379` (TLS). **Do not** paste `redis-cli --tls -u ...` |
| `QDRANT_URL` | Qdrant Cloud HTTPS, **or empty** for in-memory RAG on staging |
| `QDRANT_API_KEY` | Optional; required if Qdrant Cloud uses API key auth |

---

## Auth and safety (required staging values)

| Placeholder | Staging value |
|-------------|----------------|
| `JWT_SECRET` | `<GENERATE_32_PLUS_BYTES>` |
| `AUTH_REFRESH_COOKIE_ENABLED` | `true` |
| `AUTH_COOKIE_SECURE` | `true` |
| `AUTH_COOKIE_SAMESITE` | `none` |

---

## Trading and providers (do not change for MVP staging)

| Placeholder | Required value |
|-------------|----------------|
| `EXECUTION_MODE` | `paper` |
| `ENABLE_REAL_TRADING` | `false` |
| `BILLING_ENABLED` | `false` |
| `PROVIDER_MODE` | `fallback` |
| `MARKET_DATA_ENABLED` | `true` |

---

## Optional

| Placeholder | Notes |
|-------------|--------|
| `OPENAI_API_KEY` | Empty = mock LLM/embeddings with fallback |

---

## Local copy command

```bash
cp docs/staging_deployment_worksheet.template.md docs/staging_deployment_worksheet.local.md
# Edit docs/staging_deployment_worksheet.local.md — never commit it
```

## Related

- [pre_deployment_checklist.md](pre_deployment_checklist.md)
- [deployment_command_pack.md](deployment_command_pack.md)
- [staging_execution_checklist.md](staging_execution_checklist.md)
