# Manual BloFin demo lifecycle and recovery

This change follows PR229. It owns execution history, command detail, native lifecycle evidence, scoped recovery and Agent selection. Dashboard balance and position components are untouched.

## Root causes

The original result lived only in `ManualDemoTest` component state. Leaving that component or creating a later attempt lost its selection. There was no durable owner-scoped command list or detail URL.

The Agent's manual reader could scope venue/origin but could not apply submission time, requested contracts or submission status before selection. Ambiguity had no visible selectable commands, and conversation context required a Journal identity that might not yet exist.

`has_demo_entry_history` holds every allowed BloFin demo command until an immutable lifecycle resolution exists. The existing governed resolution requires strategy/Journal-close lineage and cannot represent definitively unsent manual commands. A submitted order, editable Journal status, empty positions response or absent pending protection does not satisfy that gate.

## Shared contracts

All history/detail APIs require an authenticated owner and constrain organization, user, owned account, immutable manual plan authority and `BLOFIN_DEMO` venue. They remain usable when execution is disarmed. They make no provider calls.

- `GET /execution/manual-demo/commands`: bounded pagination (`limit` 1–50, `offset` 0–10000); account, symbol, direction, requested contract quantity, timezone-aware inclusive `since`/`until` and submission-status filters. `attempt` includes blocked records; `submitted` requires acknowledged submission; `filled` requires actual entry fills. Filters apply before ordering and limiting.
- `GET /execution/manual-demo/commands/{command_id}`: immutable identity/plan, account, attempt/submission times, requested contracts/base quantity, outcome and stored evidence.
- UI URL `/execution/manual-demo/{command_id}`: survives reload and a fresh sign-in session. Settings supplies a compact paginated recent-activity list. Journal uses `/journal?trade_id={journal_trade_id}`.
- Existing `POST /execution/manual-demo/{command_id}/reconcile`: refreshes this command through native GETs and controlled local projection; never submits, cancels or modifies a venue order.
- `POST /execution/manual-demo/{command_id}/resolve`, body `{"confirm": true}`: explicit local recovery. It refreshes native evidence and checks eligibility again; a displayed eligible state is not authority to release stale proof.

`ManualDemoAttempt.evidence` is additive to the existing status DTO. Consumers should distinguish:

| Field | Meaning |
| --- | --- |
| `execution_status` | Blocked, uncertain, submitted, partial/filled, canceled/rejected or proven closed entry lifecycle |
| `position_status` | Recorded command lifecycle; `closed_verified` needs native exit proof |
| `account_status` | Latest observed whole account flat/present/unknown state; a present position is not automatically this command's position |
| `protection` | Native pending protection verification, separate from planned stop/target |
| `protection_history` | Identity-linked native effective/canceled/failed protection history; cancellation does not prove an exit |
| `reconciliation_freshness`, `observed_at` | Recorded observation or latest read failure, never a promise that stored account state is current |
| `exit_fills`, `exit_quantity`, `exit_price`, `exit_fees` | Unique immutable native exit facts and their weighted projection |
| `venue_reported_fill_pnl` | Sum only when every exit fill supplies `fillPnl`; does not establish funding or net PnL |
| `recovery_status`, `recovery_reason` | Eligible, unresolved or resolved; reason explains the remaining gate |
| `account_claim_command_ids`, `reservation_status` | Unresolved manual claims and this command's scoped reservation state |
| `can_reconcile`, `can_cancel`, `can_resolve` | Valid actions; cancellation requires a recorded live/partial order remainder, and server revalidation still applies |

The Agent accepts structured `command_id`, account, venue, origin, symbol/direction, requested quantity, time range and submission status. Natural selection supports an explicit ISO/full English date including year plus UTC time (a minute, or ±5 minutes for “around”), contract quantity and blocked/submitted/filled status. A date without a time means its UTC day. Unsupported precision/filters are disclosed and select nothing. “Latest attempt,” “latest submitted order” and “latest filled trade” apply different filters. Remaining ambiguity yields up to five timestamp/quantity/status/command links. Exact selection persists before Journal creation, so “that trade” retains the command. Internal simulator records cannot supply missing manual facts.

## Evidence and recovery invariants

Entry order/fill identity and full-precision immutable hashes from PR229 remain authoritative. Snapshot observations link the current native receipt hash, including a return to an already recorded protection response. Reconciliation retains economic entry/exit facts after a failed read; it does not replay dispatch.

Native reads use order detail, fills history, account positions, pending entry/protection, order history and TPSL history. Exit matching requires a complete bounded account order sequence beginning with the isolated approved entry, correct instrument/side/mode, terminal reduce-only exits, unique native fill identities and exact quantities. TP/SL exits additionally require effective identity-linked native TPSL history with approved trigger geometry and actual size. Canceled protection alone never establishes closure. Additional opening orders, inconsistent positions, missing entry history, unsupported categories, read failures or page/budget limits retain the claim.

Reads are deliberately bounded: a full 100-row page or more than 20 history orders is incomplete proof and produces a safe structured diagnostic. Older/complex account histories can remain unresolved; the implementation does not assume unseen pages are empty. Provider history retention and native linkage on the actual account remain live acceptance questions.

A completed manual command needs matching terminal entry/exit fills and a freshly flat, idle account. An unfilled terminal native order or a locally fenced never-dispatched command also needs a freshly flat, idle account. Unknown dispatch remains unresolved. A local unsent fence persists before reads to prevent dispatch races, but retains its reservation if account reads fail.

The unique immutable `ManualDemoLifecycleResolution` binds tenant/account/command/revision, native evidence, audit and released amount. Under the account epoch, recovery subtracts only this command's verified exposure and owned unused reservation, without clamping missing balances or borrowing another hold. Full-precision plan/fill proof bounds monetary release; sub-unit unused rounding dust remains conservatively charged and is audited. Existing verified cancellation/rejection accounting for unused entry remainder remains separate from full lifecycle/account-claim recovery. Filled-command consumed daily trade/loss budgets remain conservative. Unrelated holdings, reservations, account protections, safety epoch and global kill switch remain unchanged.

Repeated refresh/recovery cannot create duplicate entry/exit fills, Journal trades or releases. Verified exit projection records actual exit price/time/fees and closes the exact Journal lineage. Editable Journal fields alone do not prove closure or release claims. Funding/net outcome remain unknown without evidence. Resolution permits a subsequent preview only when all existing account/safety requirements pass; it grants no new order authority.

## Migration and release gate

Apply Alembic `a7manualrecovery001` after `a6manualdemo001` before deploying code that queries recovery records (`alembic upgrade head`). It adds one immutable, command-unique resolution table and PostgreSQL mutation protection. Existing commands, plans, hashes and attempts are preserved. Downgrade refuses to erase nonempty recovery history; use forward recovery after resolutions exist.

The API deployment sequence in `render.yaml` runs `alembic upgrade head` as its pre-deploy command. The Docker image includes the complete migration tree and uses `backend/docker/entrypoint.sh`; with no API command override, that script repeats the upgrade before starting Uvicorn. Its `set -eu` prevents API startup if the upgrade fails. The disarmed paper worker's custom command remains separate. Read-only Render inspection on 8 October 2026 confirmed that `alphatrade-api-staging` (`srv-d8fvbcd7vvec739mc060`) in the approved workspace has `alembic upgrade head`, an empty Docker command override and the expected backend Dockerfile/context. Before deployment, recheck those settings and verify migrations target the same database as the API.

Before starting recovery acceptance, inspect that database read-only: `alembic_version` must contain exactly one row, `a7manualrecovery001`; `manual_demo_lifecycle_resolutions` must exist with `trg_manual_demo_lifecycle_resolutions_immutable` enabled. Confirm successful migration precedes Uvicorn startup in the deployment logs. Local migration evidence does not establish the deployed database revision.

### Release-check repair evidence

Deployment safety job `113409124728` failed because two watcher contract tests still expected a6, although runtime discovery correctly returned a7. Those expectations now require a7. Missing/empty and ambiguous database revisions, missing/ambiguous migration heads and outdated revisions still fail closed; a6 is explicitly rejected as outdated.

Browser smoke job `113412211823` failed because the notification fixture supplied a synthetic bearer token but did not intercept the new `ManualDemoActivity` history GET. That request reached the real test backend, received 401, then failed refresh and correctly redirected to login. This was reproduced at width 390 with backend request logs. The fixture now intercepts that exact authenticated GET with an explicit 503 outage; both 390 and 320 tests require the activity error, retained cookie/token/session, working notification controls and persistence after reload. Production authentication and refresh handling are unchanged.

Followup focused results: **113 backend tests passed with no skips**, **7 Chromium cases passed**, targeted Ruff/format, notification-spec ESLint and frontend TypeScript passed. The browser cases comprise three notification fixtures, two manual history/detail persistence cases and two existing unauthenticated/stale-cookie rejection cases. The migration test runs the actual Alembic chain on an isolated PostgreSQL schema, seeds a canonical a6 plan, upgrades to a7 twice, verifies its payload/hash and immutability trigger, and exercises a recovery-table-dependent account-history read. A separate test executes the real container entrypoint and proves both successful migration-before-API ordering and failure-before-API rejection. These checks use local test infrastructure and perform no exchange operations.

Reproduce the focused backend release check from `backend` with PostgreSQL available:

```sh
.venv/bin/pytest tests/test_deployment_safety.py tests/test_deployment_scripts.py tests/test_config.py tests/test_watcher_paper_activation.py tests/test_manual_demo_migration.py tests/test_disarmed_render_worker_boot.py::test_blueprint_is_api_plus_one_disarmed_paper_worker -q -o addopts='' --durations=5
```

Run the affected browser files from `frontend`: `npx playwright test e2e/notification-settings-v2.spec.ts e2e/manual-demo-recovery.spec.ts --project=chromium --retries=0`; run the rejection cases with `npx playwright test e2e/auth-boundary.spec.ts --project=chromium --grep 'unauthenticated navigation|stale marker cookie' --workers=1 --retries=0`. Local execution used a matching Next/API origin and system Chromium. No full CI was manually dispatched and required checks were preserved.

The focused release gate includes PostgreSQL manual preview/claim/reconciliation/history/recovery and API tests, mixed-venue Agent/context tests, automated governed demo lifecycle/exit and risk regressions, migration roundtrip/immutability, targeted mypy/Ruff, frontend TypeScript/ESLint/component tests and Chromium fixture persistence checks. No full backend CI was manually dispatched and branch protections were not altered. Test counts/results are recorded in the PR.

Final local results on latest main `d9ebf87` (PR229): **307 backend tests passed**, **45 frontend component tests passed**, **2 Chromium browser fixture tests passed**. Targeted Ruff/format checks, mypy (10 changed-source entry points), TypeScript and ESLint passed. The backend emitted one existing Starlette/TestClient deprecation warning; no tests skipped in the final gate.

Reproduce the consolidated backend gate from `backend` with PostgreSQL available:

```sh
.venv/bin/pytest tests/test_manual_blofin_demo.py tests/test_manual_demo_reconciliation.py tests/test_manual_demo_lifecycle_workflow.py tests/test_manual_demo_migration.py tests/test_agent_recorded_trade.py tests/test_interactive_agent_foundation.py tests/test_governed_blofin_demo.py tests/test_governed_demo_lifecycle.py tests/test_governed_demo_exit_evidence.py tests/test_risk_engine.py tests/test_planned_reward_risk.py tests/test_phase1_slices_7_9_execution_protocol.py -q -o addopts='' --durations=5
```

Frontend gate from `frontend`: `npm run typecheck`; `npx vitest run src/components/settings/ManualDemoTest.test.tsx src/components/settings/ManualDemoHistory.test.tsx src/components/agent/AgentWorkspace.test.tsx`; targeted ESLint on changed components/detail route/browser spec; `npx playwright test e2e/manual-demo-recovery.spec.ts --project=chromium`. The browser API origin must match `NEXT_PUBLIC_API_URL`/`PLAYWRIGHT_API_URL`; all API requests in this spec are intercepted. Local browser execution used system Chromium and the Next dev server, with no backend/exchange mutations.

## Live acceptance after review and deploy

No live exchange read or mutation was performed for this followup. The owner's report of the original position and Chrome recording success are prior user evidence, not deployment acceptance for this repair. All native prices/IDs/closures in tests are fixtures. This environment lacks an authenticated owner session/native demo execution credential binding for live acceptance.

1. Deploy the reviewed PR with migration, then sign in as the owner. In Settings history, find the **8 October 2026 around 12:56 UTC, 0.1 contracts = 0.0001 BTC, BTC long** attempt. Distinguish the separate blocked **1-contract** attempt. Preserve both command IDs; do not infer the original position is still open.
2. Open the original detail, reload, then reopen its saved URL after sign-in in a fresh browser session. Check command/account/plan, native order, filled quantity and Journal lineage. Refresh **that same command twice**; record safe diagnostics or native identities and confirm no duplicated fills/Journal records.
3. Ask the Agent the precise date/time/quantity request, or use the exact-attempt button. If matches remain, select its visible command link. Verify “that trade” keeps the selected command before/after Journal projection.
4. Check recorded entry fills, current whole-account observation, current pending protection, historical protection and actual exit evidence separately. Missing position/protection alone must leave closure unverified. Unknown/incomplete evidence must retain its explained account claim.
5. Only if fresh terminal/exit evidence makes recovery eligible, explicitly confirm **local recovery for this command**. Repeat recovery and verify one resolution, unrelated holds and global kill switch unchanged. If existing safety/account requirements subsequently pass, test **preview only**; do not confirm another exchange order.

Record authenticated live results separately, with exact command/native identities and timestamp. Review, deploy and reconcile the same original order are the remaining gate. This procedure authorizes no venue order, cancellation, modification or automatic global kill-switch reset.
