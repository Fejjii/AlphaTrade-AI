# Agent 2 runtime contract

Baseline: current main `b165b92276346f0e0fe3ccdbd2bec3443dc75d40` (PR233 merge).
Owner branch: `codex/reviewer-wave-agent`. No merge, deployment or trading activation.

## Interfaces and dependencies

- Keep both interactive capability orchestration and the LangGraph chat engine.
  Both routes and model-based capture retry use the same `agent_chat` admission
  policy and tenant rate-limit bucket; model usage goes to the existing
  ModelCallAttempt/UsageEvent ledger in independent committed sessions. Admission is
  a zero-token `agent_chat` event; actual model attempts retain existing feature mapping
  and count separately toward applicable request/token quotas. Recovery does not add
  admission or attempt events. Embeddings use the existing `rag_search` usage feature.
- Client: send a fresh UUID `Idempotency-Key` for each intentional turn/retry,
  retain it through timeouts and resend the same payload/key for recovery.
  An in-flight request returns 409 with a machine reason; an already completed
  request replays its durable response. Reusing a key with different input is 409.
  A process-interrupted provider call is not automatically executed again. A running
  reservation expires after 360s; the same key reports `turn_interrupted`, and an
  intentional new key may proceed while the old finalizer is barred. Keys are tenant/user
  scoped and bound to route + original payload. Legacy clients without a key still work.
  The optional header is declared in OpenAPI: Agent 1 must regenerate its owned contracts.
- Provider transport: official OpenAI Python SDK 3.28.0, HTTPX2 2.13.1; SDK retries disabled. One
  application retry budget, explicit per-attempt timeout, sanitized categories,
  every upstream attempt has its own stable ledger identity. No model downgrade.
- Budget: conversation and capture may be sequential frontier calls. Preserve
  `agent_reasoning_model`, effort and output limits. Browser should allow 360s
  for a turn (two stages plus retrieval), retain the key on timeout, and offer recovery rather
  than start a new request. Browser cancellation stops waiting; accepted server
  work may finish and its committed result remains replayable.
- Coordination uses existing conversation_messages JSON payload and deterministic
  primary keys for durable reservation/replay, with brief PostgreSQL row locks.
  No new migration head or new accounting tables are requested. Each database
  phase owns a Session; provider execution holds no conversation lock/transaction.
  Simultaneous turns on one conversation conflict; unrelated conversations proceed.
  Finalization rechecks tenant ownership, reservation identity and transcript state.
  Completed reply is committed before capture; capture errors retain that reply.
- Capture must snapshot entry revisions before model I/O, then revalidate revisions
  under its brief private-user lock before writing; correction/Undo remains intact.

## Request to Agent 3

Read Agent 3 contract at `3ab96b0` (previous contract `361d493b`). It specifies `RagQuery.include_shared` and asynchronous
indexing generations. Agent retrieval adapter is owned here. No turn migration
is needed: existing transcript storage supplies durable coordination.
Please support `RagService.search`/vector filters with both private own documents
and organization-shared documents when user_id is supplied, reload/check BOTH
chunk and parent document scope, and include STRATEGY_TEMPLATE in
`retrieve_for_agent`. Search overfetch must remain bounded. Keep original/named
full document SQL access. Expose honest degraded/fallback/index freshness state.
The latest remote publishes the schema/outbox migration but retains the old search
implementation. A schema field alone must not activate own-only filtering. Please
add `RagService.supports_shared_search = True` with the implemented shared/private
SQL/vector semantics, so independently shipped schemas preserve safe compatibility.
No competing RagService edits or migration will be created on this branch.

## Integrator verification contract

CI selection must explicitly include provider SDK/embedding tests, model router
and ledger tests, interactive Agent, chat/LangGraph, conversation continuity,
Agent capture, proposal/risk/approval, recorded trade grounding, decimal/hash
contracts, retrieval tenant tests, and PostgreSQL turn concurrency/rollback tests.
Run Ruff and affected type checks. Record existing type errors separately. Shared
workflows remain integrator-owned; one consolidated full release gate remains
supervised per `.ai/RELEASE.md`.

## Delivery ledger

- Completed: baseline/ancestry verification, isolated worktree, scope/dependency contract.
- Completed: pinned official SDK transport, 142 focused provider checks; shared admission
  and vector adapter; durable SQL phases and replay (implementation verified in focused checks).
- Completed: affected cross-module regressions, PostgreSQL stall/rollback checks,
  baseline type comparison and Ruff. See `agent2_runtime_review.md` for exact results.
- In progress: draft PR and cloud handoff publication.
- Dependency: Agent 3 shared vector visibility and strategy-template semantics. The adapter
  uses `RagQuery.include_shared` when RagService advertises
  `supports_shared_search = True`. Until then it safely overfetches 50
  organization hits and checks both SQL scopes; a dominating foreign private set may
  crowd out permitted relevance. Integrator must test combined branches with include_shared
  and indexing generations before release. No unbounded search is substituted.
- Deferred: deployment, live paid model acceptance, consolidated release gate, Mac mirroring.
