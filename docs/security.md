# Security Guide

This document describes authentication, tenant isolation, RBAC, rate limiting, and safe defaults in AlphaTrade AI.

## Auth flow

1. **Register** — `POST /auth/register` creates an organization, user, owner membership, and token pair.
2. **Login** — `POST /auth/login` verifies bcrypt password hash and returns tokens.
3. **Access** — Protected routes require `Authorization: Bearer <access_token>`.
4. **Refresh** — `POST /auth/refresh` rotates the refresh token and returns a new access token.
5. **Logout** — `POST /auth/logout` revokes the refresh token, clears the httpOnly cookie (when enabled), and denylists the current access token.
6. **Current user** — `GET /auth/me` returns the authenticated user and organization.

### Bearer vs httpOnly cookie mode

| Mode | When to use | Refresh token | Access token |
|------|-------------|---------------|--------------|
| **Bearer (default)** | Local dev, API scripts, Playwright API tests | JSON body + `sessionStorage` | `sessionStorage` + `Authorization` header |
| **Cookie (production-ready)** | Docker Compose, staging, portfolio demos | httpOnly cookie (`alphatrade_refresh`) | JSON body + `sessionStorage` (short-lived) |

Enable cookie mode:

```bash
# Backend
AUTH_REFRESH_COOKIE_ENABLED=true
AUTH_OMIT_REFRESH_FROM_BODY=true
AUTH_COOKIE_SECURE=false   # true behind HTTPS in production
AUTH_COOKIE_SAMESITE=lax

# Frontend
NEXT_PUBLIC_AUTH_COOKIE_MODE=true
```

Cookie settings:

- **httpOnly** — refresh token not readable by JavaScript (XSS mitigation)
- **Secure** — `true` in staging/production (auto when `ENVIRONMENT != local`)
- **SameSite** — `lax` by default (local-safe; use `strict` if same-site only)
- **Path** — `/auth` (login, refresh, logout routes only)

The frontend sends `credentials: include` in cookie mode so refresh works without JS-readable refresh tokens.

On `401`, the client attempts one refresh (cookie or body); if refresh fails, it clears the session and redirects to `/login`.

**Never log cookies or tokens.** Redaction patterns strip bearer tokens, refresh tokens, and authorization headers from logs and audit metadata.

## Token behavior

| Token | Lifetime (default) | Storage |
|-------|-------------------|---------|
| Access (JWT) | 15 minutes | Client sessionStorage + Bearer header |
| Refresh (opaque) | 7 days | httpOnly cookie **or** sessionStorage + hashed in Postgres |

Access tokens are HS256 JWTs containing `sub`, `org_id`, `email`, and `jti` (for denylist).

### JWT secret requirements

| Environment | Minimum secret length |
|-------------|----------------------|
| `local` | No minimum (dev convenience) |
| `staging` / `production` | 32 bytes (`JWT_SECRET`) |

Startup validation rejects short secrets outside `local`. Use a long random value in Docker, staging, and production.

## Refresh rotation

Each refresh request:

1. Validates the presented refresh token (JSON body **or** httpOnly cookie).
2. Revokes the old refresh token (`revoked_at`, `replaced_by_id`).
3. Issues a new refresh token and access token.

### Refresh reuse detection

If a revoked refresh token that was already rotated (`replaced_by_id` set) is presented again:

- All active refresh tokens for that user are revoked.
- An audit event `auth_refresh_reuse` is recorded (high severity).
- The request is rejected with `401`.

## Logout and revocation

Logout:

1. Revokes the refresh token (from body or cookie).
2. Clears the httpOnly refresh cookie.
3. Denylists the current access token `jti` in Redis (or in-memory fallback) until natural expiry.

Short access token TTL (15 minutes) limits exposure if denylist is unavailable.

Configure denylist:

```bash
ACCESS_TOKEN_DENYLIST_ENABLED=true
ACCESS_TOKEN_DENYLIST_USE_REDIS=true
```

## RBAC roles

Membership roles (organization scope):

| Role | Access |
|------|--------|
| **OWNER** | Full organization access including all mutations |
| **TRADER** | Chat, watchlist, proposals, approvals, paper execution, positions, journal, knowledge, usage |
| **VIEWER** | Read dashboards, proposals, positions, journal, knowledge, usage, audit; **no** approval mutations or paper execution |

Mutations return `403 forbidden` with `required_roles` details when the membership role is insufficient. Cross-organization access remains blocked separately via tenant scoping.

## Protected routes

Require bearer auth:

- `POST /chat/message` (TRADER+)
- `/market/watchlist*` (mutations: TRADER+)
- `/proposals*` (mutations: TRADER+)
- `/approvals*` (mutations: TRADER+; reads: all roles)
- `/execution*` (paper orders: TRADER+)
- `/positions*` (mutations: TRADER+)
- `/journal*` (mutations: TRADER+)
- `/knowledge*` (mutations: TRADER+)
- `/usage*`, `/audit*`
- `/billing/customer`, `/billing/checkout`, `/billing/portal`, `/billing/usage/export` (OWNER)
- `/billing/plans`, `/billing/status` (Reader+)

Public routes:

- `/health`, `/health/ready`
- `/providers/status`
- `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`

## Tenant isolation

- Tenant context is resolved from the access token, not from query/body IDs.
- Create/update routes override `organization_id` and `user_id` from the authenticated tenant.
- Cross-organization access returns `403 forbidden` or `404 not found` (scoped lookups).

## Password policy

- Minimum length: 12 characters
- Maximum length: 128 characters
- bcrypt rejects passwords above 72 bytes

## LLM narrative layer (Slice 21)

- **Deterministic analysis remains the source of truth** for risk level, approval status, proposals, and execution eligibility.
- The LLM may only rewrite or clarify explanation text from **sanitized structured context** — no secrets, tokens, or hidden system prompts are sent.
- Narrative output must match `TradingNarrativeDetail` (extra fields forbidden) and pass `NarrativeValidationGuardrail` plus existing output validation.
- Unsafe or invalid LLM output **falls back** to deterministic narrative; fallback is audited (`narrative_validation_fallback`).
- Mock LLM is used when `OPENAI_API_KEY` is blank; real LLM is optional.
- Real exchange execution remains disabled regardless of narrative provider.

Disable narrative LLM: `NARRATIVE_LLM_ENABLED=false`.

## Redaction

Logs, audit metadata, and guardrail redaction patterns remove:

- Passwords and password hashes
- Bearer tokens and authorization headers
- Refresh/access tokens and cookies
- API keys and exchange secrets

## Rate limiting

Redis-backed fixed-window limiting when `REDIS_URL` is reachable and `RATE_LIMIT_USE_REDIS=true`. Falls back to in-memory limiting when Redis is unavailable and `RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK=true`.

Protected endpoints (IP-scoped; authenticated routes also user-scoped):

| Scope | Endpoint |
|-------|----------|
| `auth:register` | `POST /auth/register` |
| `auth:login` | `POST /auth/login` |
| `auth:refresh` | `POST /auth/refresh` |
| `chat:message` | `POST /chat/message` |
| `knowledge:ingest` | `POST /knowledge/ingest` |
| `execution:paper` | `POST /execution/paper` |

Violations emit structured logs and audit events (`rate_limit_exceeded`). Auth scopes use high severity.

## Smoke / integration verification

```bash
# Backend auth + security tests
cd backend && uv run pytest tests/test_auth.py tests/test_auth_security.py -q

# Full stack curl smoke (requires running backend)
chmod +x scripts/e2e-smoke.sh scripts/docker-validate.sh
./scripts/e2e-smoke.sh

# Docker stack
docker compose up --build
./scripts/docker-validate.sh
```

Playwright API E2E runs in CI (`npm run test:e2e`). Full browser E2E is optional locally (skipped in CI).

Staging deploy helpers:

```bash
./scripts/check-env.sh          # validate ENVIRONMENT settings
./scripts/run-migrations.sh     # Alembic upgrade head
./scripts/staging-smoke.sh      # health, auth, chat, safety
./scripts/verify-safety.sh      # paper-only invariants
```

See [docs/security_checklist.md](security_checklist.md) for pre-deploy checklist.

## Account security (Slice 25)

- Email verification tokens and password reset tokens are **SHA-256 hashed** at rest; never logged.
- Password reset returns **generic** responses (no email enumeration).
- Reset revokes **all refresh sessions**; optional access-token denylist on confirm.
- Rate limits on verification resend and password-reset request (5/hour per IP by default).
- Organization invitations: OWNER-only create/revoke; hashed invite tokens; audit events.
- Email provider abstraction (`mock` default); see [account_management.md](account_management.md).

## Current limitations

- Single primary organization per user (first membership)
- Invite acceptance for **new** users (signup via link) not implemented
- SMTP/Resend/SendGrid delivery placeholders only (mock captures locally)
- Access token still in sessionStorage (short TTL; refresh in httpOnly cookie when enabled)
- Usage metering with org quotas (Slice 24)
- Billing scaffold (Slice 26): mock by default; Stripe secrets/webhook signatures never logged; webhook payloads redacted; usage export excludes journal/prompts/secrets
- Real exchange / broker execution **not implemented** — paper mode only

## Local development

```bash
# Backend (bearer mode — default)
cd backend
uv sync --extra dev
cp ../.env.example ../.env
chmod +x scripts/run_dev_server.sh
./scripts/run_dev_server.sh

# Frontend
cd frontend
npm ci
cp .env.example .env.local
npm run dev

# Docker stack (cookie mode enabled)
docker compose up --build
./scripts/docker-validate.sh
```

Set `JWT_SECRET` to a long random value before any shared/staging deployment.
