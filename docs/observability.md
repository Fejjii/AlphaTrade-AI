# Monitoring and audit

Use this guide to observe an authorized environment without confusing configured flags, health, durable authority and actual outcomes. It reflects source at main `b58beda`, October 7, 2026. No runtime probes or metric scrapes ran for this documentation task.

## Signals and their limits

| Surface | What it reports | What it does not establish |
| --- | --- | --- |
| `GET /health` | Liveness, build and safety/evidence metadata. | Dependency readiness, fresh setup success or a fill. |
| `GET /health/ready` | Provider/dependency readiness under the current policy. | Every workflow's operational acceptance. |
| `GET /providers/status` | Registered provider health and mock/degraded/fallback observations; public status. | The resolved model or retrieval mode of every Agent turn. |
| Authenticated `GET /watcher/paper-runtime/status` | Persisted/runtime Watcher monitoring state. | An enabled flag alone does not prove a successful evaluation. |
| Authenticated `GET /watcher/watchlist/status` | Scope/slot status, configuration revision and freshness-bound observations. | A new Candidate or successful execution for every slot. |
| Authenticated `GET /audit/events` | Scoped typed security/workflow events and request filters. | A complete production security audit or immutable authority for every log message. |
| Usage/model-call observations | Provider, model/cost/fallback information where recorded. | Billing-grade cost when labeled estimated; instrumentation coverage for every path. |
| `GET /metrics` when explicitly enabled | Low-cardinality RED HTTP metrics. | A deployed Prometheus/APM service or full distributed tracing. |

Sources: [health routes](../backend/src/app/api/routes/health.py), [provider routes](../backend/src/app/api/routes/providers.py), [Watcher routes](../backend/src/app/api/routes/watcher_paper.py), [audit routes](../backend/src/app/api/routes/audit.py), [metrics](../backend/src/app/observability/metrics.py).

## Logs and worker health

Structlog supports `LOG_JSON=true` and `LOG_LEVEL=INFO`. Request middleware binds request/trace IDs and returns request correlation metadata. Redaction covers known token/key/password patterns, but evidence collection still needs sanitization before sharing. Do not print environment values, connection URLs with credentials, raw prompts, private accounts or sensitive audit records.

The [paper worker supervisor](../backend/src/app/workers/paper_worker.py) maintains separate Watcher/Telegram heartbeats, errors, restart/cycle counts and authority-drift checks. Process/memory diagnostics are recorded by the relevant runtime modules. A healthy process can still report stale evidence, no setup or a refused action; those meanings should remain distinct.

`METRICS_ENABLED=false` is the default. Outside local, the metrics route requires a configured scrape token. HTTP RED metrics use method/route/status-class labels, not user IDs, symbols, prompts or raw query strings. LangSmith configuration fields exist; a key does not establish wired tracing. Complete distributed OpenTelemetry/APM acceptance is not established here.

## Follow a bounded event

Record evidence date and exact service SHA first. Follow the canonical assessment/evidence hash, Candidate, eligibility/risk decision, immutable plan authorization, execution receipt/fill and Journal lineage. Use internal references in the secured operational record; publish only sanitized conclusions.

Telegram queue/admission/preview state is different from successful transport receipt. Internal paper execution is different from BloFin demo acknowledgment, protection and identity-checked fills. Existing demo exposure is not closed merely because the kill switch prevents new risk.

For PR209/SFP, follow the [bounded recovery procedure](sfp_candle_finalization_recovery.md): correct v2 policy/receipt clocks, preserved v1 rows and fresh evaluation acceptance. A `no_setup`/warm-up result can be legitimate; do not treat repeated contract errors as successful acceptance.

The October 7 package includes supplied API/worker verification on `b58beda`, applied migration `a6manualdemo001`, received Watcher notification, historical internal-paper/Journal record and successful BloFin demo account sync. [Current status](current_status.md) separates those reports from independently checked GitHub metadata. Native demo order acceptance, fresh SFP recovery and existing Journal repair remain pending.

## Operational references

[Deployment](deployment.md) · [source contracts](market_source_contracts.md) · [worker stability](runtime_stability_ci_memory_001.md) · [backup/restore runbook](backup_restore_runbook.md) · [evaluation](evaluation.md).

Earlier smoke/drill/handoff results apply to their stated date, environment and commit. Repeated status pages or a green CI badge do not establish new operational evidence.
