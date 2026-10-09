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
