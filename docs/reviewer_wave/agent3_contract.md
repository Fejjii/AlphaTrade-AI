# Agent 3 contract — order diagnostics and knowledge consistency

Baseline: `main` / PR233 merge `b165b92276346f0e0fe3ccdbd2bec3443dc75d40`,
verified identical through GitHub on 2026-10-09. Branch: `codex/reviewer-wave-data`.
No external order, deployment, shared migration, runtime flag or credential change.

## Storage and readiness

`RagService.ingest(..., commit=True)` commits normalized SQL documents, chunks and
one scoped durable indexing intent together. `commit=False` flushes within the
caller transaction; its receipt must set `sql_chunks_stored=false` until that
authority commits. No remote embedding/vector work occurs in this transaction.
Linked replacement and deletion enqueue durable work in the same transaction.

`vector_index_status`: `pending` means durable indexing is queued; `ready` means
the current generation was written, verified and acknowledged; `failed` means
bounded attempts were exhausted; `unknown` means legacy/unobserved state.
Legacy `upsert_acknowledged` remains readable, but new pending receipts never use
it. Readiness belongs to a specific document generation, version and source hash.
`vector_backend` is nullable before observation. Attempts, next retry and sanitized
error codes will be visible in document indexing metadata. SQL content remains the
authority for retrieval and citations; vector payloads cannot supply missing SQL.

## Schema and migration order

Add document indexing generation and a tenant/user scoped `knowledge_indexing_jobs`
outbox with stable job identity, operation, version/hash, claim token/lease,
attempt count, retry time and error code. Deletion intents survive document deletion.
Generate a new additive Alembic revision after `a8agentcapture001` using disposable
PostgreSQL and repository autogeneration. Do not edit historical migrations.
Upgrade schema before starting the bounded indexing runner; do not turn on trading.

Agent 2 durable turn schema is currently unknown: its requested sibling branch
returns 404. Please publish `docs/reviewer_wave/agent2_contract.md` and provide the
proposed model/table ownership and revision. A consolidated linear chain must be
reviewed before deployment; this branch will not invent Agent 2's schema.

## Compatibility and visibility

Keep RagService method names, normalized text, SQL chunk identity/hash, source
provenance and scoped deduplication. Add `include_shared` retrieval filtering so
an authenticated principal can retrieve own private and organization-shared rows.
Retain strategy templates in Agent retrieval. Agent 2 owns the adapter and final
document/chunk checks; Agent 3 validates SQL scope and current generation at RAG.
Linked source URI lookup must use the exact organization and user, including NULL.
Vector abstraction gains scoped document inventory and deletion, never collection reset.

## Shared file requests to Agent 1

Agent 1 owns frontend transport/types and generated contracts. Update Knowledge
response unions for pending/ready/failed/unknown, render stored separately from
searchable, and refresh readiness through document listing. Do not show successful
indexing for a pending receipt. `sql_chunks_stored=false` indicates an uncommitted
composed receipt, not a successful save. No independent shared transport edits here.

Manual orders use authenticated `/execution/manual-demo/instrument`, `/preview`,
`/confirm`, command detail and `/reconcile`; decimal fields remain strings, quantity
is exchange contracts. Preserve exact revision/content hash and command identity
after a lost response. Preparation, submission, exchange acceptance/rejection,
unknown outcome and fill must remain distinct. No automatic retry with a new order.
Agent 3 owns dedicated widgets only if a defect is reproduced.

## Coordination availability

Update: sibling manifests are now published and were read at Agent 2 `daa4f384`
and Agent 1 `d24b45e0`. Agent 2 requests no new schema or accounting table: durable
turn storage uses existing conversation messages. This leaves a coherent linear
migration chain `a8agentcapture001 -> a9knowledgeoutbox001`, with one final head.
The private/shared RAG filter and parent/chunk SQL checks implement Agent 2's
requested interface; `STRATEGY_TEMPLATE` remains in Agent retrieval. Agent 1 owns
the generated contracts and readiness UI after these schemas are published.
Concrete response schemas are in `backend/src/app/schemas/rag.py`; document listing
contains the indexing observation, including job ID, attempts, retry time and error.
Pending uploads return SQL storage true, status pending and null vector backend.
No claim of embedding/vector fallback is made before provider work occurs.

The indexing worker is opt-in through `KNOWLEDGE_INDEXING_ENABLED`, default false,
in the existing supervised paper worker. Review schema upgrade, Agent 1 UI/contracts
and resource budget before enabling it. This task does not change runtime flags.

`codex/reviewer-wave-agent` and `codex/reviewer-wave-frontend` do not yet exist on
GitHub (connector 404 and git remote-ref failure). This manifest records requests
without implying agreement. No authenticated failing order request, sanitized
owner error, account/session or service log has been supplied. Incident root cause
remains unknown; local fake-venue tests cannot prove external acceptance.
