# PR237 voice and native activity integration

## Candidate and ownership

Continue `codex/reviewer-wave-integration` from reviewed baseline
`bda597c2fffbf1a49beadc64d757100808094ca2`. The current PR237 head is the
publication revision; record it verbatim in the supervising review. Included feature
revisions, preserved by merge commits:

- PR238: `af672dffb4a20fa0a8783cf7b0870cc59f6e3fff`, reviewed with
  [its handoff](../voice_conversation_foundation.md).
- PR239: `18e66dacfc0eb81f897c3f5a6eefbe0f4d29923f`, reviewed with
  [its contract/rollout](../blofin_native_activity.md) and
  [revision verification ledger](../blofin_native_activity_verification.md).

The voice owner retains AgentWorkspace, recovery, controller and voice implementation.
The BloFin owner retains native backend activity, identity, snapshots, worker and
migrations. Integration edits own CI/release policy, generated client, Dashboard and
Journal presentation, and existing integration smoke expectations.

## Implemented and integrated behavior

Dashboard and Journal read only `GET /exchange/blofin/activity`. Native fills use
organization/environment/UID/trade identity for deduplication; linked commands never
add trades. Completed orders are separate context. Internal simulator records are
excluded from BloFin activity. Statistics stay on Dashboard and explicitly describe
only the loaded native facts; no portfolio-return reconstruction is attempted.

Compact rows expand into exact contract quantities/prices, signed fees, nullable PnL,
metadata, freshness and incomplete coverage. Unknown currency/funding remain unknown.
IDs and technical URLs are absent from the main presentation; a matched command is a
link in details. Back closes details and restores focus. Account/session changes fence
late responses and clear private caches; native UID changes invalidate continuation
and require a fresh read. No browser-persistent native history cache is introduced.

The actual Agent page uses the corrected owner's single typed/spoken admission path.
Local validation precedes pending retention; ambiguous transport retains the complete
body, attachment references and original key for explicit recovery. Voice defaults to
review; conversation mode is opt-in. This integration does not activate a provider.

## Focused evidence and limitations

The 15-file frontend selection has **217 passing cases, no skips** (162 voice/shared
Agent cases plus 55 client/presentation/account cases). Repository TypeScript checking,
changed-file ESLint, standard API generation/drift checks and diff checks passed.
Application and test content is committed before publication; the final handoff records
its exact tested revision. No full frontend/backend suite or production build was run.

Standard generated full-schema SHA256:
`250caeb28a2088d71e05269837f98f8ce864bc2811e577d793acaf4dac68fe4e`.
The scoped PR239 contract hash matches
`14b14a34c77f598793207a1fa2485e5572b2afd8eee92f86bc2c1e2f5cb76307`;
all stored scoped route/component schemas equal the combined generated export.

Local backend selection:

```sh
cd backend
.venv/bin/pytest -q -o addopts='' tests/test_backend_ci_scope.py \
  tests/test_blofin_activity_provider.py tests/test_blofin_activity_worker.py
```

**70 passed, one failed**. CI policy has 28 cases and provider has 37; worker has five
passes and one unresolved failure. The failed worker isolation assertion also fails in
an isolated six-case run (**five passed, one failed**). It waits one second for watcher
progress; an instrumented diagnostic measured 2.045 seconds in the watcher's existing
allocator collection. No test is skipped, assertion weakened, or worker edited here.
This remains a BloFin-owner qualification blocker, even though its earlier owner
ledger reports success. Integrate any corrected owner revision only after focused
verification; do not treat old green evidence as acceptance of that change.

PR239's reported **371 distinct focused passes** were reconciled as 107 correction
cases plus 264 existing regressions, with repeated cases not counted again. Local
collection independently reports **371 cases**. This verifies the ledger inventory,
not independent PostgreSQL execution. No disposable PostgreSQL is available here;
Docker socket access is denied. Its identity/snapshot/migration database cases have
not been rerun locally. CI supplies `BLOFIN_ACTIVITY_TEST_POSTGRES_URL` to the existing
PostgreSQL fixture so those cases execute rather than silently skipping.

Chromium fixtures exercise the actual Dashboard/Journal routes and actual Agent page
using deterministic API/Web Speech responses. They do not prove native microphone,
Safari/physical iPhone, live BloFin coverage or authenticated hosted behavior. The
final handoff records browser counts and any integration-smoke failures separately.

## CI trigger policy

Ordinary PR/push and manual dispatch with both booleans false run focused backend,
frontend drift/lint/type/focused unit, and deployment-safety checks. All six job names
are retained; failures propagate. Twelve event/input combinations are tested against
the actual workflow expressions. Superseded PR runs cancel through concurrency;
manual runs use separate groups and are never displaced by development runs.

Only explicit manual `combined_validation=true` or `full_backend=true` enables the
complete frontend unit/build, evaluations, Docker and production-browser jobs.
Only `full_backend=true` runs complete backend acceptance. Both inputs default false.
Skipped combined jobs are not acceptance. No dispatch/rerun was requested or executed.
No branch-protection configuration was changed.

Read-only inspection found the corrected feature runs already completed:
PR239 [38047672083](https://github.com/Fejjii/AlphaTrade-AI/actions/runs/38047672083)
failed generated drift; PR238
[38048249178](https://github.com/Fejjii/AlphaTrade-AI/actions/runs/38048249178)
failed two legacy browser assertions. Combined regeneration resolves drift locally;
existing integration assertions now use the mounted voice region and explicitly open
Strategy options. These feature runs do not accept the combined candidate.
GitHub Actions cancellation is unavailable through current tools/API network access;
no active superseded run was observed among the inspected feature revisions.

## Migration order, preparation and coordinated rollback

Static Alembic inspection: one base, 78 reachable revisions, one current head
`a10blofinactivity001`, with continuation
`a8agentcapture001 -> a9knowledgeoutbox001 -> a10blofinactivity001`.
Historical migrations are unchanged; a10 adds three activity tables and no backfill.
A real PostgreSQL upgrade/downgrade/re-upgrade is owner-reported evidence only here.

Before staging, review this exact combined head and the consumer/worker corrections.
In the approved coordinated window, drain old synchronous ingestion writers before
introducing the a9 API/outbox consumer. Apply a9 then a10 once; align API, frontend
and existing paper worker to the same reviewed commit. Preserve actual operator
settings/credentials, never substitute render.yaml defaults. Knowledge indexing and
native activity opt-in require their separate authorization; do not run a separate
activity service alongside the existing worker component. Disabled indexing leaves
pending documents and cannot establish indexing-readiness acceptance.

Rollback sequence:

1. Stop/drain the optional activity cycle and knowledge consumer, and drain new writes.
   Preserve existing Watcher, Telegram, kill-switch and exchange settings through the
   coordinated worker window; do not reset operator configuration.
2. Export/checkpoint newly admitted indexing jobs and native history. Retain additive
   a9/a10 schema and data while rolling application revisions back together.
3. Use a separately qualified migration-aware rollback image/startup. Baseline b165b92
   automatically runs `alembic upgrade head` but lacks a9/a10; it cannot safely boot
   against the new migration revision. Do not bypass its migration guard.
4. Align API/frontend/worker rollback revisions and API binding, run health/read-only
   gates, then restore only the approved consumer posture. Never combine old synchronous
   ingestion writers and the new indexing flow.
5. Destructive a10 downgrade to a9 requires separate authorization and an activity-data
   export; it drops those three tables. Rolling back further must also preserve the a9
   outbox/history. No hosted upgrade or rollback has been executed.

The existing [staging smoke sequence](staging_smoke_sequence.md) is unchanged.
Use this migration addendum with it; do not interpret its earlier a9-only baseline as
permission to omit the new a10 head.

## Hosted blockers and readiness

| Workstream | Implemented | Integrated | Verified here | Deployed/activated |
| --- | --- | --- | --- | --- |
| CI cost controls | Yes | Yes | Policy/event tests | Published workflow only; no manual run |
| Browser voice | Owner complete | Corrected af672dff | Focused components and simulated Chromium | No new deployment; native microphone unverified |
| Native backend activity | Owner complete | Corrected 18e66dac | Provider/static contract; worker blocker; PostgreSQL inventory only | No new deployment or activity opt-in |
| Dashboard/Journal native views | Yes | Yes | Focused component/account/browser fixtures | No |
| Generated client | Yes | Yes | Generation, drift, strict validation/type checks | No |
| Release acceptance | Preparation only | Candidate assembled | Staging/full acceptance unexecuted | No |

Known existing frontend target: Vercel project `alpha-trade-ai`, project
`prj_y7vFqwbFvdpHvf2nMaDkKQauBhZQ`, team `team_LNgcEGBkqntUnTrktNjFzh7a`,
alias `https://alpha-trade-ai-eight.vercel.app`. Its staging API binding is unverified.
The prior observed API/worker/frontend revision remains
`b165b92276346f0e0fe3ccdbd2bec3443dc75d40`; this task does not refresh or deploy it.

Missing hosted access:

- Render exact-commit deploy and consumer-drain/settings access for existing API
  `srv-d8fvbcd7vvec739mc060` and worker `srv-daqej7o473hc73fsc1k0` in workspace
  `tea-d7hn0fvavr4c73f62c70`; configured-branch-only deployment cannot prove this head.
- Vercel project/team authorization (prior 403) and frontend/API binding visibility.
- HTTPS access to api.render.com, staging API, api.vercel.com and verified frontend.
- Authenticated synthetic staging tenant/session and scoped record-read evidence.
- GitHub Actions write/cancel API access; git transport and connector read access alone
  do not allow explicit cancellation.

**Not release-ready.** Resolve the worker blocker, review any corrected feature SHA,
complete supervising review and authenticated aligned staging smoke, qualify rollback,
and obtain fresh required SFP diagnostics/evaluations. Only then explicitly dispatch
one full acceptance run under [.ai/RELEASE.md](../../.ai/RELEASE.md) with
`full_backend=true`, recording the exact run SHA and all executed/skipped results.
Earlier baseline CI38042313649 accepts only bda597c. No full backend acceptance link
exists for this candidate. The manual BloFin order incident remains undiagnosed.
No main merge, deployment, infrastructure, billing/provider activation, external order,
Telegram message or operator-setting change occurred.
