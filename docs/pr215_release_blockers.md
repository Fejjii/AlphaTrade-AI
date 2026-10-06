# PR215 release blockers and Watcher diagnosis

PR215 retains the completed Agent continuity, readable explanation, Stored evidence,
and Knowledge import entry. This follow-up updates affected development fixtures,
the browser acceptance check, and migration readiness. It does not change execution
authority, strategy approvals, risk policy, candle admission or SFP tolerances.

## Failed full CI: reproduced causes

Run `37480490124`, backend job `112327028446`, reported 47 failures, 4,348 passes
and six skips. An exact rerun of those 47 nodes on the original PR215 head
`88c647cb0bcac9726d0741cf98a7dbeac77fd79e` reproduced 44 failures; three demo
explanation fixture cases already corrected in PR215 passed.

| Group | Cases | Cause and correction |
| --- | ---: | --- |
| Migration head expectations | 12 | Tests expected `a4knowledge001` after the demo lifecycle migration added `a5demolifecycle001`. The verified single chain is `a5demolifecycle001 → a4knowledge001 → a3release002`; the release merge parents remain `a2tgpolicy002` and `a2sfp002`. Literal head expectations and explicit parent assertions now cover this chain. Existing migration roundtrip, missing/multiple revision and split-head refusal checks remain. |
| Binance read counts | 14 | Thirteen Nested timeframe cases and one five-market probe expected one klines read. REST adapter v2 deliberately confirms the settled closed window with two identical read-only GETs. Tests assert those reads, identical requests, per-market counts, and no additional IO on cached reuse; Bybit still uses one candle read. |
| Confluence/SFP fixture identity | 12 | The fixture built replay-v1 candles, then wrapped them as live-v2 evidence. Strict assembly correctly refused mixed identities. Fixture candles are now constructed with their actual requested identity/version; replay defaults remain v1. No stored receipt is relabelled. |
| Bybit/failover fixture identity | 3 | A synthetic Binance primary supplied v1 trades to a v2 live identity. Coverage correctly rejected the wrong source. The primary fixture now constructs v2 trades. Source-switch, wrong-source and freshness assertions remain. |
| Paper-worker memory fixtures | 3 | In-process and subprocess fixtures also supplied v1 trades to v2 live identities, failing before memory measurements. They now construct matching v2 trades. The original retained-memory and RSS bounds, eight reduction cycles and 25,000-trade batches remain. These failures did not establish memory growth. |
| Demo explanation fixtures | 3 | Original PR215 already adapted these fixtures to the merged lifecycle-resolution read. Their authorization, fill and protection assertions remain. |

These CI failures were stale tests or inconsistent synthetic evidence, not proof
that production must accept mixed identities or remove confirmation reads.
All 47 affected cases now pass alongside migration-readiness and supervisor guards.

## Browser acceptance

`frontend/e2e/simplified-ui-smoke.spec.ts` no longer expects the removed screenshot
placeholder. It checks voice support, an enabled document import entry, its named
Knowledge destination, and the absence of strategy/Journal approval implications.
Using actual authenticated local API calls, it selects a TXT file, previews its
extracted text, verifies the document is absent from the library and no import POST
occurred, then explicitly saves and verifies the returned document in the library.
The existing desktop/mobile navigation, overflow, paper-mode and retained-route
assertions remain.

## Watcher: proven code behavior versus unverified live cause

The reported latest staging scans are October 6, 2026 at 13:30 UTC, after main
`9306410`. Startup logs reported `migration_unhealthy`; the database head was
separately verified as `a5demolifecycle001`. Those facts alone do not identify the
continuing failure of the running worker.

Two behaviors were reproduced:

1. **Readiness depended on the working directory.** `expected_migration_head()`
   located `alembic.ini` by module path but left its `script_location` relative to
   the process directory. From the repository root, it returned `None` even though
   an absolute script path yielded the single correct head. It now anchors the
   migration script directory to the same backend package root. A regression changes
   directory before reading the head; missing and multiple heads still fail closed.
   The declared Docker image uses `/app` and normally resolves the old relative
   path correctly, so this defect is **not established as the staging cause**.

2. **Startup refusal is sticky for that process.** The staging supervisor checks
   activation once during construction. A refusal installs an idle cycle that
   republishes the original reason and fresh heartbeats without opening a scanning
   runtime. Later database recovery does not rerun preflight. A focused regression
   makes readiness recover between cycles and proves one preflight call, repeated
   refusal, fresh heartbeats and no scans. This behavior is documented, not replaced
   with automatic activation. In contrast, a successfully constructed scanning
   runtime rechecks migration/provider/lineage/heartbeat health each cycle.

The hosting platform can therefore report a running process while evaluations have
stopped. The application worker-status reader requires `activation_state=running`
before counting a controlled heartbeat as live; an idle refusal should remain
visible in `controlled_runtime_status`. Old orchestration snapshots and old successful
scans still need separate age checks. Neither a heartbeat nor an enabled setting
proves a fresh scheduled evaluation.

Read-only Render service access requires confirmation of the connector workspace;
that confirmation was not available during implementation. No live logs, service
configuration or database changes were performed. The following operator checks
resolve the remaining uncertainty without changing authority.

## Bounded staging checks

Run these from the **actual paper-worker container**, using its existing settings
and database connection. Do not paste environment variables, DSNs or credentials.
Capture the deployed commit, image/build identity, command, working directory and
worker instance; distinguish API and worker releases and any overlapping instances.

### Migration and fresh read-only preflight

With `PYTHONPATH` pointing at that container's `src`, run this once. It reads the
existing database and public market evidence; it does not construct a worker,
start scans, deliver Telegram messages or place orders.

```python
import json
from pathlib import Path

from app.core.config import Settings
from app.db.session import get_session_factory
from app.workers import watcher_activation
from app.workers.watcher_activation import (
    activation_config_from_settings,
    collect_live_observations,
    evaluate_activation,
    expected_migration_head,
    read_migration_revision,
)
from app.workers.watcher_paper import new_worker_instance_id

settings = Settings(_env_file=None)
factory = get_session_factory()
with factory() as session:
    database_head = read_migration_revision(session)
print(json.dumps({
    "cwd": str(Path.cwd()),
    "module": watcher_activation.__file__,
    "expected_head": expected_migration_head(),
    "database_head": database_head,
}))
observed = collect_live_observations(
    settings,
    session_factory=factory,
    worker_instance_id=new_worker_instance_id(settings.watcher_paper_worker_id),
)
decision = evaluate_activation(activation_config_from_settings(settings), observed)
print(json.dumps({
    "allowed": decision.allowed,
    "reasons": decision.reason_codes,
    "provider_state": observed.provider_state,
    "lineage_valid": observed.lineage_valid,
    "probe_failed": observed.probe_failed,
    "paper_only": observed.paper_execution_only,
}))
```

Require one database revision matching the deployed code's one expected head.
`None` can mean missing/unreadable/split history, packaging/path failure or a DB
read failure; investigate it rather than stamping a revision. A verified head on
another connection or a newer API image does not prove worker readiness.
Review **all** preflight reasons: approved/compiled target lineage, selected live
provider, authority flags and paper-only composition remain independent gates.

### Process posture, scheduling and leases

Use a read-only transaction and an operator-verified authorized tenant bound to
the psql variable `organization_id`. Keep limits and tenant predicates intact.

```sql
BEGIN READ ONLY;
SELECT version_num FROM alembic_version;
SELECT component, worker_id, heartbeat_at, activation_state, last_scan_at,
       last_scan_reason, last_error_code, lease_owner, lease_epoch,
       lease_expires_at, fence_held, market_source
FROM controlled_runtime_status
WHERE component = 'watcher';

SELECT scan_scope, max(created_at) AS last_scheduled_at
FROM watcher_scheduled_scans
WHERE organization_id = :'organization_id'::uuid
GROUP BY scan_scope ORDER BY scan_scope;

SELECT scan_scope, worker_id, lease_epoch, fencing_token, status,
       started_at, heartbeat_at, finished_at, outcome_reason_code,
       sanitized_error, recovery_disposition
FROM watcher_scan_attempts
WHERE organization_id = :'organization_id'::uuid
ORDER BY started_at DESC LIMIT 40;

SELECT scan_scope, subject_id, status, reason_code, created_at, finished_at,
       sanitized_error
FROM watcher_subscription_eval_attempts
WHERE organization_id = :'organization_id'::uuid
ORDER BY created_at DESC LIMIT 40;

SELECT scan_scope, owner_id, lease_epoch, fencing_token, renewed_at, expires_at
FROM watcher_worker_leases
WHERE organization_id = :'organization_id'::uuid
ORDER BY scan_scope LIMIT 40;

SELECT scan_scope, state, enabled, last_beat_at, last_attempt_status,
       lease_owner, lease_expires_at, reason_code, generated_at
FROM watcher_health_snapshots
WHERE organization_id = :'organization_id'::uuid
ORDER BY generated_at DESC LIMIT 40;
ROLLBACK;
```

Compare UTC times to both boot and the most recent 15-minute closed window. Read
startup **and subsequent** bounded logs for the same worker instance, especially
`watcher_paper_activation_refused`, database/provider/runtime probe failures,
runtime-cycle exceptions, worker health and memory termination/restart events.
If runtime posture is running, inspect due target enumeration and enabled owner
subscriptions, exact approved/compiled versions, configured symbol/tenant/scope
limits, lease owner/expiry/fencing, provider budget/freshness, failed attempts and
per-subscription evaluation receipts. Empty/newly stale scheduling and failed
evaluation are different outcomes; successful public-market probes are not strategy
evaluations. Preserve existing refusal reasons, immutable receipts and clocks.

## Remediation and acceptance

If the current process is publishing `refused/migration_unhealthy` while a fresh
same-container preflight is now healthy, the proven sticky startup path explains
why it remains idle. After supervising release review and deployment, restart that
paper worker **with its existing reviewed authority** so startup preflight runs
again. Do not toggle flags, approve strategies, reset accounts, stamp migrations,
delete evidence, relax SFP validation or use an API process to conceal this state.
If fresh preflight still refuses, fix its evidenced packaging/database/provider/
lineage cause first. If the process is running but scans do not advance, investigate
scheduling, leases and subsequent failures before choosing restart as a remedy.

Acceptance requires fresh **naturally scheduled** successful evaluations after the
restart/deployment, with new attempt timestamps, approved strategy lineage and
canonical source receipts for each currently approved scope, including both SFP
scopes. A boot log, replayed result, manual probe or old scan is insufficient.
Repeat the exact Agent trade/followup question and preview/explicit-save UI sequence.
The supervisor owns the final consolidated full CI gate; no complete backend run
or workflow dispatch was started during this repair.

## Focused verification

- Exact failed CI nodes plus activation/supervisor guards: 96 passed, zero skips.
- Real local Chromium browser smoke: one passed (desktop/mobile navigation,
  retained routes and authenticated Knowledge preview/explicit save).
- Strict SFP/settlement, source/failover, confluence, tenant watchlist, monitoring
  state and deployment guards: 273 passed, zero skips. The memory workload and
  immutable historical-receipt rejection assertions remain intact.
- Remote-worker API projection (including fresh refused/disarmed heartbeats):
  nine passed. Scoped Ruff/format (15 files), strict mypy (the readiness source),
  frontend typecheck/ESLint and diff checks passed.
- Local checks do not establish live model quality or deployed Watcher recovery.
