# AT-118 focused verification ledger

Actual refreshed PR237 base: `bda597c2fffbf1a49beadc64d757100808094ca2`.
Recorded `4e515ddb8de20f4b2cfb7498ed6ce9bbbd2d2f2f` was superseded before the fork.
The base was checked again before publication and remained unchanged.

All venue responses use deterministic `httpx.MockTransport`. PostgreSQL is a
disposable local PostgreSQL 17 container. Native persistence cases use a distinct
schema per test; migration roundtrip uses its own fresh schema and the actual full
Alembic chain. Existing regression helpers use their established disposable database
fixtures. No shared/deployed database was migrated.

## Final new-package acceptance

```sh
cd backend
BLOFIN_ACTIVITY_TEST_POSTGRES_URL=<disposable-postgresql> \
PHASE1_POSTGRES_URL=<disposable-postgresql> \
  .venv/bin/pytest tests/test_blofin_activity_provider.py \
  tests/test_blofin_activity_postgres.py tests/test_blofin_activity_migration.py
```

Exit 0: **55 passed, no skips, 18.74 seconds**.

Coverage includes exact long decimal strings and signed fees, partial contract fills,
unknown currency/PnL/funding, canonical UID versus parent identity, dedicated read-only
credentials and active-demo compatibility, bounded/signed GET-only transport refusals,
overlap/replay, entire-page conflict rollback, interruption/restart, foreign checkpoint
refusal, organization/UID switching, rotation, stale and missed-window coverage, initial
identity failure, malformed native shapes, pagination loops, rate-limit backoff, competing
worker refusal, keyset cursor scope, unauthenticated/wrong-tenant API refusal, verified
manual command matching without new execution records, and migration rollback/re-upgrade.

The manual matching case creates one real existing manual command through a simulated
venue, then reads separate native activity pages. Two native fills link to that command;
direct native activity has no command. Replays do not add facts, local fill rows or
commands. No external order is sent by the test.

## Focused existing regressions

```sh
PHASE1_POSTGRES_URL=<disposable-postgresql> .venv/bin/pytest \
  tests/test_blofin_provider.py tests/test_blofin_execution.py \
  tests/test_manual_demo_native_pagination.py tests/test_blofin_presentation_evidence.py
```

Exit 0: **90 passed, no skips, 12.68 seconds**.

```sh
BLOFIN_ACTIVITY_TEST_POSTGRES_URL=<disposable-postgresql> \
PHASE1_POSTGRES_URL=<disposable-postgresql> .venv/bin/pytest \
  tests/test_blofin_activity_provider.py tests/test_blofin_activity_postgres.py \
  tests/test_blofin_activity_migration.py tests/test_dashboard_demo_account.py \
  tests/test_external_integrations_acceptance.py
```

The combined development run reported **150 passed and one migration-fixture failure**
in 154.43 seconds, no skips. Both existing Dashboard and external-integration modules
passed all **96** cases, including the unchanged balance-sync and sealed-execution
credential restrictions. Another regression helper had replaced the public schema with
ORM-created tables, so migration version metadata was absent and a fresh full upgrade
hit an existing table. The new migration test was corrected to create its own fresh
schema; the final 55-case package command above passes the complete migration roundtrip.
The passing existing modules were not rerun after this test-only isolation correction.

There are **241 distinct passing focused cases** across the final package and those
existing regression selections. This is not a complete backend or release-suite claim.

## Static and contract checks

Changed-file Ruff check and format check: exit 0. `git diff --check`: exit 0.

```sh
.venv/bin/mypy --follow-imports=silent \
  src/app/services/blofin_activity_config.py src/app/services/blofin_activity_service.py \
  src/app/repositories/blofin_activity.py src/app/providers/exchange/blofin_activity.py \
  src/app/schemas/blofin_activity.py src/app/db/blofin_activity.py \
  src/app/api/routes/blofin_activity.py src/app/workers/blofin_activity.py \
  src/app/core/blofin_readonly_access.py
.venv/bin/alembic heads
.venv/bin/python -m app.workers.blofin_activity
```

Focused typing: no issues in nine source files. One migration head:
`a10blofinactivity001`. Default worker reports disabled and performs no synchronization.
Scoped OpenAPI JSON was regenerated directly from the route and compared byte-for-byte;
SHA256 is recorded in [the package contract](blofin_native_activity.md).

Development-only setup corrections: the first shell fetch required the tool's supported
network permission; uv used a writable `/tmp` cache; the migration generator's Ruff
hook needed the virtualenv executable path (generated SQL was retained and formatted);
initial fixtures needed an explicit demo URL, the actual tenant dependency name and an
order helper import. An assertion was corrected to preserve a completed checkpoint's
last native frontier. A one-case diagnostic without the opt-in PostgreSQL URL skipped;
the final opt-in package command has no skips. An Alembic head check invoked from the
repository root was rerun from its required backend directory. No production workaround
or relaxed safety assertion was introduced for these harness/command issues.

## Completion and remaining acceptance

Implementation, API/ownership contract, migration/rollback notes and focused verification
are complete: **85% before the final publication milestone**. Creating the one draft PR
completes the remaining 15%; its PR description records final 100% package progress.

Next tasks belong to integration/release: owner review, full generated-client refresh,
later Dashboard/Journal integration, reviewed migration rollout, explicitly authorized
read-only native account acceptance and only then any synchronization activation.
The full generated OpenAPI hash will drift until the designated owner regenerates it;
no frontend/generated client or CI workflow was edited by this package.

No full backend CI or manual workflow dispatch, merge, deploy, runtime flag change,
external order/cancellation/transfer, credential change or Telegram message. Automatic
PR checks after publication are separate from this local evidence. The manual-order
incident is still unverified; its failing request/server evidence remains outstanding.
Mac/iCloud synchronization is unverified in this cloud environment.
