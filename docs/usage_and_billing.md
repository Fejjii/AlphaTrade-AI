# Usage and Billing

AlphaTrade AI tracks LLM, embedding, and feature usage at the **organization** level.
Slice 24 added billing-grade metering and quotas. Slice 26 adds a **billing scaffold**
(mock by default, Stripe placeholder) without enabling live payments in local development.

## Usage tracking design

Each metered action creates a `usage_events` row with:

| Field | Purpose |
|-------|---------|
| `organization_id` / `user_id` | Tenant scoping |
| `request_id` | Correlates with audit logs |
| `feature` | e.g. `agent_chat`, `rag_ingest`, `market_analyze` |
| `provider` / `model` | Provider attribution |
| `input_tokens` / `output_tokens` / `total_tokens` | Token metering |
| `provider_reported_cost` | Cost from provider when available |
| `estimated_cost` | Fallback estimate |
| `cost_source` | How cost was determined |
| `fallback_used` / `cache_hit` | Provider reliability signals |
| `latency_ms` / `status` | Operational metadata |

Events are persisted via `UsageService.record()` from the agent graph, RAG ingest,
market analyze, paper execution, and observability emitters.

## Cost source types

| `cost_source` | Billing-grade? | Meaning |
|---------------|----------------|---------|
| `provider_reported` | **Yes** | Provider returned authoritative cost |
| `tokenizer_estimated` | No | Tokens from provider API + internal rate table |
| `static_estimated` | No | Placeholder rates (mock/offline) |
| `unavailable` | No | Non-LLM or zero-token request |

The frontend **Usage** page labels estimates explicitly — static and tokenizer
estimates must not be shown as invoice-ready amounts.

## Quota enforcement

Organization quotas (`organization_quotas` table) support:

- Monthly token and cost limits
- Daily request limit
- Per-feature limits (chat, RAG ingest, market analyze, narrative, paper execution)
- `plan_id` — linked to subscription plan (Slice 26)
- Soft warning threshold (default 80%) — request allowed, audit `quota_warning`
- Hard block threshold (default 100%) — request blocked with HTTP 429, audit `quota_block`

Owners can view and update quotas:

```bash
GET /usage/quota
PATCH /usage/quota   # OWNER only
```

## Billing provider modes (Slice 26)

| Mode | When | Behavior |
|------|------|----------|
| **Disabled** | Default (`BILLING_ENABLED=false`) | Mock provider; safe mock checkout/portal URLs; no external charges |
| **Mock** | Local dev / tests | In-memory customer IDs; `mock.billing.local` URLs |
| **Stripe scaffold** | `BILLING_ENABLED=true` + `STRIPE_SECRET_KEY` | Placeholder Stripe URLs; webhook signature verification; no full API wiring yet |

Provider status: `GET /providers/status` (`kind: billing`).

### Environment variables

```bash
BILLING_ENABLED=false          # default — billing disabled
STRIPE_SECRET_KEY=             # blank → mock provider
STRIPE_WEBHOOK_SECRET=         # required for webhook verification in Stripe mode
STRIPE_PUBLISHABLE_KEY=        # placeholder for future checkout UI
```

Stripe secrets and webhook signatures are **never logged**; webhook payloads are redacted before persistence.

## Subscription plans

Static plan catalog (`free`, `pro`, `team`) maps to organization quotas:

| Plan | Purpose |
|------|---------|
| Free | Default limits for local / trial |
| Pro | Higher limits (placeholder pricing) |
| Team | Organization-scale limits (placeholder pricing) |

Plan changes (webhook or `apply_plan`) update `organization_quotas` safely via `QuotaService`.

## Billing API

| Endpoint | Role | Description |
|----------|------|-------------|
| `GET /billing/plans` | Reader+ | List plans |
| `GET /billing/status` | Reader+ | Billing + subscription status |
| `POST /billing/customer` | Owner | Create billing customer |
| `POST /billing/checkout` | Owner | Start checkout (mock or Stripe placeholder) |
| `POST /billing/portal` | Owner | Customer portal URL |
| `POST /billing/usage/export` | Owner | Aggregate usage for billing period |
| `POST /billing/webhook` | Public (signed) | Provider webhooks |

## Usage export

`POST /billing/usage/export` aggregates tenant usage for a billing period:

- Tokens, requests, per-feature line items
- Separates `provider_reported_cost` vs `estimated_cost`
- Sets `cost_is_billing_grade` only when totals are fully provider-reported
- Stores `usage_export_batches` record
- Mock provider records export in memory (no external call)

**Not exported:** raw prompts, raw LLM responses, secrets, journal text, or personal trading content.

## Webhook security

- Signature verification via `Stripe-Signature` when Stripe mode is enabled
- `webhook_events.provider_event_id` unique — duplicates ignored (idempotent)
- Supported scaffold events: `checkout.session.completed`, `customer.subscription.*`, `invoice.paid`, `invoice.payment_failed`
- Unknown events stored and ignored safely
- Audit: `billing_webhook_received`

## Frontend

**Billing** page (`/billing`):

- Current plan and billing status
- Quota summary (links to Usage)
- Plan cards with mock checkout when billing disabled
- OWNER actions: customer, portal, usage export

## Known limitations

- No live Stripe Checkout/Portal API calls yet (placeholder URLs)
- No tax, proration, or invoice PDFs
- OpenAI often lacks per-request USD — tokenizer/static estimates are not billing-grade
- Per-seat billing is a placeholder (`seat_limit` on plans only)
- Real trading remains disabled — paper execution quotas are abuse prevention only

## Future production billing roadmap

1. Wire Stripe Checkout + Customer Portal APIs
2. Stripe Billing Meters for `provider_reported` usage
3. Entitlement sync from subscription → quotas
4. Payment failure handling and dunning
5. Admin billing dashboard and invoice history

See also: [security.md](security.md), [deployment.md](deployment.md), [limitations_roadmap.md](limitations_roadmap.md).
