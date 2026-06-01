# Observability Guide

Lightweight observability for staging and production. This slice documents and
scaffolds signals — it does not deploy a full APM stack.

## Structured logs

Enable JSON logs for log aggregation pipelines:

```bash
LOG_JSON=true
LOG_LEVEL=INFO
```

Logs use **structlog** with:

- ISO timestamps (UTC)
- Log level
- Request context (`request_id`, optional `trace_id`)
- Automatic redaction of tokens, passwords, and API keys

Startup logs include **deployment posture** (environment, execution mode, cookie
settings) — never JWT secrets or connection strings.

## Request IDs

Every HTTP request receives or generates `X-Request-ID`. The value is:

- Bound to structlog context for the request lifetime
- Returned in the response header
- Useful for correlating user reports with backend logs

Configure header name via `REQUEST_ID_HEADER` (default `X-Request-ID`).

## Trace IDs

Optional `X-Trace-ID` header is propagated when clients send it (e.g. future
OpenTelemetry instrumentation). Configure via `TRACE_ID_HEADER`.

## Health endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness + trading safety (`execution_mode`, `real_trading_enabled`) |
| `GET /health/ready` | Readiness based on provider registry health |

Use `/health` for platform uptime checks. Alert if `real_trading_enabled` is ever
`true` in staging/production (should be impossible due to startup validation).

## Audit events

Authenticated `GET /audit/events` exposes security-relevant events:

- Auth login/logout/refresh failures and reuse detection
- Rate limit violations
- Narrative validation fallbacks
- Guardrail blocks

Filter by `event_type` for incident review.

## Usage summary

Authenticated `GET /usage/summary` and `GET /usage/events` provide placeholder
cost estimates per feature. **Not billing-grade** — suitable for demos and
capacity planning only.

## Provider status dashboard

Public `GET /providers/status` returns health for LLM, embeddings, vector
store, exchange (mock/paper), and market data providers. The frontend Provider
Status card reads this endpoint.

Use during deploy smoke tests to confirm fallback/mock posture.

## Future integrations

| Integration | Status | Enable when |
|-------------|--------|-------------|
| **LangSmith** | Placeholder provider | `LANGSMITH_API_KEY` set; tracing wired in future slice |
| **OpenTelemetry** | Not wired | Export traces/metrics to Honeycomb, Datadog, etc. |
| **Log shipping** | Platform stdout | Configure Render/Railway log drain to your SIEM |

Recommended next steps after staging is stable:

1. External uptime monitor on `/health`
2. Log drain with JSON parsing
3. LangSmith for LLM trace debugging (optional)
4. OpenTelemetry SDK + OTLP exporter when traffic warrants it

## Local debugging

```bash
# Human-readable logs
LOG_JSON=false uv run uvicorn app.main:app --reload

# JSON logs (matches staging)
LOG_JSON=true uv run uvicorn app.main:app --reload
```

See [deployment.md](deployment.md) for monitoring plan in deploy context.
