# Agent 2 runtime contract

Baseline: current main `b165b92276346f0e0fe3ccdbd2bec3443dc75d40` (PR233 merge).
Owner branch: `codex/reviewer-wave-agent`. No merge, deployment or trading activation.

## Interfaces and dependencies

- Keep both interactive capability orchestration and the LangGraph chat engine.
  Both routes and model-based capture retry use the same `agent_chat` admission
  policy and tenant rate-limit bucket; model usage goes to the existing
  ModelCallAttempt/UsageEvent ledger in independent committed sessions.
- Client: send a fresh UUID `Idempotency-Key` for each intentional turn/retry,
  retain it through timeouts and resend the same payload/key for recovery.
  An in-flight request returns 409 with a machine reason; an already completed
  request replays its durable response. Reusing a key with different input is 409.
  A process-interrupted provider call is not automatically executed again.
- Provider transport: official OpenAI Python SDK; SDK retries disabled. One
  application retry budget, explicit per-attempt timeout, sanitized categories,
  every upstream attempt has its own stable ledger identity. No model downgrade.
- Budget: conversation and capture may be sequential frontier calls. Preserve
  `agent_reasoning_model`, effort and output limits. Browser should allow 240s
  for a turn (two stages), retain the key on timeout, and offer recovery rather
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

At first inspection `codex/reviewer-wave-data` and its manifest were not published
(GitHub 404). Read it once available. Agent retrieval adapter is owned here.
Please support `RagService.search`/vector filters with both private own documents
and organization-shared documents when user_id is supplied, reload/check BOTH
chunk and parent document scope, and include STRATEGY_TEMPLATE in
`retrieve_for_agent`. Search overfetch must remain bounded. Keep original/named
full document SQL access. Expose honest degraded/fallback/index freshness state.
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
- In progress: official provider transport and bounded attempts.
- Pending: shared policy/retrieval/accounting; durable turn phases; focused verification.
- Dependency: Agent 3 shared vector visibility and strategy-template semantics.
- Deferred: deployment, live paid model acceptance, consolidated release gate, Mac mirroring.
