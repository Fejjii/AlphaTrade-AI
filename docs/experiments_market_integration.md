# Next batch: experiments, market evidence and Strategies

This batch uses `codex/experiments-market-integration`. PR237 and its hosted release
qualification remain frozen at `3600ec89e48a6f3cf2f29b4468ab124d1219f627`.
The initial integration was published early at
`1ebf85357bc33c1f966e06f892a1a9a02adefafb`. The final candidate SHA is recorded in
the integration PR and the generated cloud handoff, rather than embedding a
self-referencing commit hash in this document.

| Included work | Reviewed feature revision | Integrated scope |
| --- | --- | --- |
| PR241 | `6ca6a76201547524275266dfa22fdf12f5932b14` | Immutable experiment domain, lifecycle/approval API, additive a11 |
| PR242 | `88ce82ff620c8fd206154a2e8593d242bad83e5c` | Canonical public market context and corrected acquisition clocks |
| PR243 | `8b9d1b83ee5c4082d87005afbfdfa8343d286a7e` | Reviewed pure adapter receipt correction, research v2 only |

PR243's correction was reviewed after publication: selected candles retain their
fixed boundaries, original receipts must be available by the actual post-close
decision, future/same-close context cannot influence an earlier decision, and
expiry remains close +60 seconds. Its later screening continuation is excluded.
No sibling branch is rewritten or advanced by this integration.

## Product and contracts

The actual `/strategies` page reads generated `GET /experiments` and detail clients.
Cards show the latest version, Exploration/Validation, lifecycle, sample count and
a recorded lifecycle milestone. Details show a compact recent milestone list,
per-variant sample counts and expandable exact configuration/evidence. IDs/hashes
stay in that expansion. Back returns to the cards. Paging uses the real offset API.
All view/read/mutation state is cleared on tenant/user/session changes; aborted or
late responses cannot populate another identity's view. No shared persistent cache
contains experiment data.

Request approval, start/resume, pause and complete use the exact version and
`expected_revision`. Server membership and bounded approval remain authoritative;
the UI exposes no approval bypass. A lost/malformed mutation response disables
another action until an explicit current-state read. No mutation retries automatically.
Starting only changes domain lifecycle. It installs no worker or trading runtime.

Agent or document capture remains the authoring entry. This compact view does not
invent an experiment configuration, risk envelope or native performance from an
ordinary strategy card. Existing experiment creation/version/approval/promotion
APIs are generated, but this UI adds no authoring wizard or Owner approval form.
Performance stays unavailable. Setup observations are not trades, and internal
simulation is never presented as native BloFin performance.

Generated shared artifacts cover both combined backend features and all eight
experiment operations. Generation now handles 201 JSON success responses and
multiple path parameters while retaining the existing single-parameter signatures.
Full OpenAPI SHA256:
`a2d41da19557227474103f917656610329f5521838646e5c2dea13eeb9e02037`.
MarketEvidenceContext and the pure TrendPulse interface keep their separate published
schemas. Context does not replace required canonical qualification evidence.

## Migration sequencing and rollback

There is one head, `a11experiments001`, with explicit continuation:

```text
a8agentcapture001 -> a9knowledgeoutbox001 -> a10blofinactivity001 -> a11experiments001
```

Only the new a11 migration is adopted; historical migrations remain unchanged.
PR242 and the included pure PR243 correction add no migration. Any later screening
migration must be coordinated after a11, then independently reviewed and qualified.
Do not introduce a parallel head or include an unpublished runtime migration.

Disposable PostgreSQL qualification checks upgrade a10 → a11, downgrade/reupgrade
with native history retained, and an application rollback with the populated schema
retained. The rollback test seeds documents/chunks, pending/processing/ready/failed
indexing jobs and a deletion tombstone, native orders/fills/cursors, and a running
experiment with immutable configuration, lifecycle records and a synthetic sample.
Both plain b165 and bda sources refuse the unknown a11 revision. An archived bda
package carrying the byte-identical a10 **and a11** migrations performs a no-op
upgrade, passes API startup/health plus disarmed worker probes twice, and preserves
exact row snapshots. Returning to the current source preserves those snapshots.
This is source/startup proof; no hosted rollback image is built or deployed here.

For a future coordinated rollback:

1. Stop admission of new writes and drain current requests; pause/drain consumers
   through the separately authorized release process, preserving captured operator
   settings. Keep legacy ingestion writers from overlapping the outbox consumer.
2. Take and verify the database/provider snapshot. Retain a11; **do not downgrade a
   populated experiment schema**. Its downgrade drops experiments, versions, events
   and samples. Downgrading a10/a9 also loses native history/outbox state.
3. Use a separately built and tested migration-aware API/worker package containing
   every retained revision through a11. A plain b165 image is not compatible proof.
   Current proof uses bda + immutable a10/a11 overlays, with the worker disarmed;
   an armed worker's compatibility remains unqualified.
4. Coordinate API, worker and frontend revisions/API binding together. Check health,
   exact database head, ownership reads and retained data before reopening writers.
5. Restore only previously approved consumer/operator settings and resume exactly
   one indexing consumer. Replay existing jobs, not duplicate document ingestion.
   No order, Telegram message, provider activation or configuration reset is part
   of the rollback probe or this integration task.

## Focused evidence

These checks cover the final feature/UI contents, not full release acceptance.
The final exact SHA is associated with them in the integration PR/handoff.

- Backend: **255 passed, zero skipped**, 167.21s, disposable PostgreSQL 17. The
  selection includes six experiment persistence/API/risk/identity/migration modules,
  canonical context/timing, three pure TrendPulse modules, and retained-schema rollback.
- Frontend: **28 passed, zero skipped**, four files: experiment view, experiment
  generated boundary, existing generated boundaries and authenticated transport.
- Actual Chromium Strategies flow: **1 passed, zero skipped**, 13.7s against a local
  mock-provider API and PostgreSQL. It creates a domain experiment over an immutable
  synthetic strategy, requests approval, checks Owner approval before start, loses
  a reply after the server commits, checks one transport/no automatic duplicate,
  explicitly reads recovery state, pauses/reloads, checks mobile width, verifies
  default sample ingestion503 and another tenant's detail404.
- Shared API and MarketEvidenceContext schema drift pass; frontend typecheck and
  changed-file ESLint pass; changed Python lint/format pass. One migration head.
- Initial browser fixture used an email rejected by the real `/auth/me` schema;
  the local fixture was corrected to example.com. A subsequent ambiguous Pause
  locator failed before any click; the selector now scopes the experiment details.
  Neither issue changed production behavior or operator controls.

Reproduce the backend selection from `backend/`, with an explicitly disposable
loopback `EXPERIMENT_TEST_POSTGRES_URL` and the same URL in
`PR237_ROLLBACK_POSTGRES_URL`:

```sh
.venv/bin/pytest -o addopts='' -q -rs \
  tests/test_experiment_api.py tests/test_experiment_domain.py \
  tests/test_experiment_migration.py tests/test_experiment_concurrency.py \
  tests/test_experiment_risk.py tests/test_experiment_native_identity.py \
  tests/test_market_evidence_context_contract.py tests/test_required_derivative_acquisition.py \
  tests/test_trendpulse_1r_adapter.py tests/test_trendpulse_1r_experiment_contract.py \
  tests/test_trendpulse_1r_domain.py tests/test_pr237_migration_aware_rollback.py
```

Frontend focused command:

```sh
npx vitest run src/components/strategies/ExperimentsPanel.test.tsx \
  src/lib/api/experiments.test.ts src/lib/api/generated-contracts.test.ts \
  src/lib/api/client.test.ts
```

`backend/scripts/seed_experiment_browser_fixture.py` is a development-only fixture:
run it as `python -m scripts.seed_experiment_browser_fixture` from `backend/`, with
explicit `--database-url`, `--output /tmp/.../auth.json`, and a synthetic
`--local-jwt-secret` matching the local API. It accepts only loopback PostgreSQL
`alphatrade_test`, writes short-lived auth with mode0600, and activates no runtime.
After a11 upgrade and local API/frontend startup, set `EXPERIMENT_BROWSER_AUTH_FILE`,
`PLAYWRIGHT_API_URL`, `PLAYWRIGHT_BASE_URL`, `PLAYWRIGHT_SKIP_WEBSERVER=1` and the
available Chromium executable, then run only
`npx playwright test ui-tests/experiments-api.spec.ts --project=chromium`.
Without an explicit synthetic fixture this browser test reports a prerequisite skip.
Its executed local result above had no skips. Screenshots use synthetic content only.

## Status and remaining gaps

| Capability | Implemented | Integrated | Locally tested | Deployed |
| --- | --- | --- | --- | --- |
| Experiment domain/API/a11 | Yes | Yes | PostgreSQL/API | No |
| Public evidence/Agent context | Yes | Yes | Deterministic receipts/contracts | No |
| Pure TrendPulse receipt correction | Yes | Yes | Synthetic replay/domain | No |
| Compact Strategies lifecycle view | Yes | Yes | Components + actual local browser/API | No |
| Durable screening/read consumer | Separate owner continuation | No | No claim | No |
| Trading/performance/sample adapters | Not installed | No | Fail-closed boundaries only | No |

Remaining integration work: Agent/document-to-bounded-experiment-draft authoring,
Owner approval presentation if requested, durable screening/deduplication/rejection
read consumer, canonical evidence persistence wiring, and separately trusted sample/
performance adapters. Native exchange connectivity/coverage and armed worker/image
rollback acceptance remain unverified. OI change/notional and historical book remain
unsupported; no invented signal counts, portfolio returns or native performance.

Hosted access blockers carry forward independently: Render exact-commit deployment
credentials/HTTPS path, verified frontend artifact/revision and deployment access,
and an authenticated synthetic staging tenant. No hosted deployment or smoke was
attempted or claimed here. Keep PR237's staging smoke instructions unchanged.
Routine PR checks remain focused; expensive combined validation/full backend stays
manual after the repository's explicit review/staging prerequisites. No full CI
dispatch, main merge, deployment, provider activation, external order or operator
setting change occurred.
