# Agent 1 — frontend reliability and API contracts

Baseline: `b165b92276346f0e0fe3ccdbd2bec3443dc75d40` (current main and PR233 merge).
Branch: `codex/reviewer-wave-frontend`. Original checkout is clean and preserved.

## Owned scope

Frontend except dedicated manual order widgets; frontend dependencies; existing authenticated
API transport; generated OpenAPI boundary types/validators and export/generation scripts.
Logical phases: immediate acknowledged Agent turns, pagination recovery, canonical routes and
strategy handoff, schema generation, private TanStack Query pilot, delayed-fixture verification.
No merge, deployment, trading activation, CI workflow edits, or automatic mutation retries.

## Dependencies and narrow requests

- Agent 2: retain required `AgentTurnResult.user_message_id` and `assistant_message_id`;
  publish accurate `authority_mutated: bool` and Agent/provider schema changes. Frontend uses
  existing `AgentTurnRequest.strategy_id` only after an authorized strategy read.
- Agent 3: publish ingestion/indexing pending/ready/failed response schema and endpoints,
  evidence timestamps and retry semantics. Indexing UI waits for this contract; no invented states.
- Integrator: run the deterministic regeneration/drift command after Agent 2/3 integration,
  add the check to CI, and own consolidated release/live acceptance.

At initial inspection neither sibling `codex/reviewer-wave-agent` nor
`codex/reviewer-wave-data` existed remotely. Read their manifests when published.
No independent changes to Python provider/Agent/RAG schemas, database or manual-order widgets.

## Source of truth and validation

Generate from local FastAPI code with explicit offline paper settings and no lifespan/provider
I/O; export schema hashes and exact regeneration commands here when established.
Reuse `apiFetch` authentication, refresh, sanitized errors and cancellation. Preserve decimal
strings, omitted/null differences, enums and Boolean authority semantics.
Development checks: focused frontend unit/API tests, lint/typecheck/build, routed Playwright
fixtures and export-only backend checks. These do not establish database persistence,
authenticated live acceptance or the final integrated `.ai/RELEASE.md` gate.

## Initial ledger and estimate

Completed: baseline/ancestry/ownership inspection, isolated worktree, contract manifest.
Pending: all implementation/validation phases and draft PR.
Blocked: indexing schema until Agent 3 publishes; Mac iCloud mirroring unavailable on Linux.
Deferred: broad redesign, React Compiler, integrated release and authenticated live acceptance.
Estimate: several hours for implementation and validation; revise after schema export and tests.
Open PRs inspected through GitHub connector: 217,197,184,183,182,181,180 and older work;
none is a reviewer-wave branch. CLI GitHub API returned Forbidden; Git transport works.

## Baseline generated contracts (published before backend integration)

Local full OpenAPI SHA256: `7696544c1abb69b05b694ea0f56ffd985d3a69003399b4fad379f81bc109e33c`.
Exact per-component hashes and pilot hash: `frontend/src/lib/api/generated/hashes.json`.
Regenerate: `cd frontend && npm run api:generate`; drift: `npm run api:check`.
Both export fresh local code through `backend/scripts/export_openapi.py`, clear inherited
configuration, disable Redis caches, use mock/replay paper settings and prohibit socket
connections. No lifespan, database sessions, provider resolution or deployed credentials.
Pinned dependency locks are required (`uv sync --extra dev`, `npm ci`).
Generated pilot: strategy PATCH; Agent turn/confirm/reject; attention and daily review.
AJV standalone validators and TypeScript/client derive from the same OpenAPI closure;
no coercion, defaults or property stripping. Existing `apiFetch` owns all authentication/I/O.
Integrator must regenerate after Agents 2 and 3 merge; do not treat this baseline as final.

Sibling manifests read at Agent 2 `daa4f384` and Agent 3 `361d493b`. Agent 2 requests
240-second waiting and an `Idempotency-Key` per intentional turn, durable timeout recovery.
Agent 3 defines pending/ready/failed/unknown and SQL storage separately from indexing;
concrete document response model is awaited before generation/UI integration.
Revised estimate: core implementation is present; allow another 1–2 hours for browser
journeys, integration fixes, schema/indexing handoff and delivery. No live acceptance claim.

## Development phase status update

Implemented: immediate stable-ID acknowledgment with independent cancellable history;
all supported filter offset resets and first-page recovery; canonical usage fragment and
Agent authoring handoffs; generated pilot boundaries; independent private Query sources,
30-second freshness/5-minute GC, one transient read retry, no mutation retries, cache
cancellation/clearing and transport session guards; one summary prefetch on tab intent.
Agent waiting budget follows Agent 2's published 240-second contract.

Evidence so far: 100 focused cases passed; export-only backend test passed; lint/typecheck
passed; deterministic drift check passed. Six routed Chromium journeys passed with no
skips/retries: usage URLs/query/fragment, authorized and denied authoring handoff, delayed
acknowledgment. A 200ms response plus 5000ms stale-history fixture measured 352ms
click-to-answer and 92ms acknowledgment-to-visible, one turn and one history request.
Full frontend run: 1449 passed/one obsolete Create strategy label assertion; corrected
assertion now verifies the Agent URL. Useful usage/billing state tests are retained on
shared views after redundant route wrappers are deleted. Final checks still in progress.
Normal build cannot fetch Google Fonts; existing test-only offline-font production
build passed. This does not verify real font delivery or a deployed/live release.
Revised estimate: roughly another 30–60 minutes for final checks, API persistence journey,
logical commits and draft PR. Indexing waits for the Agent 3 response schema publication.
