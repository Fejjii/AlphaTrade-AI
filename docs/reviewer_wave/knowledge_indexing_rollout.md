# Durable knowledge indexing and rollout

SQL document/chunk storage now commits with a scoped durable indexing job. Remote
embedding/vector work happens after that commit in the indexing worker, with all
SQL transactions closed. SQL rollback before enqueue commit produces no vector
write. Linked replacements retain the document ID, increment its version and keep
chunk identity/hash semantics. Scoped URI lookup now includes the exact user.

The worker uses PostgreSQL `FOR UPDATE SKIP LOCKED`, token-fenced acknowledgment,
five attempts, exponential retry delays capped at 300 seconds and 300-second leases
renewed between batches. A session advisory lock serializes remote operations for
one document in autocommit mode, without an open database transaction. Restart
recovers expired claims. Lock contention releases the claim without consuming the
provider retry budget. Versioned point IDs make duplicate delivery and a lost
acknowledgment idempotent. Old work cannot become searchable after replacement or
deletion: retrieval reloads both SQL chunk and parent, scope, source filters and
current indexing generation. Missing SQL content never comes from vector payloads.

Successful acknowledgment requires verified scoped inventory equal to the expected
points after obsolete-point cleanup. Deletes store a durable tombstone without a
document foreign key, remove SQL content in the same transaction and clean remote
points later. No operation resets a collection. Rolling reconciliation inspects
one document per cycle, requeues missing/obsolete inventories and skips metadata-only
documents. Reconciliation cannot discover historical rollback orphans whose document
never existed in SQL without a separately authorized scoped vector inventory.

## API and ownership

New uploads return `sql_chunks_stored=true`, `vector_index_status=pending` and
`vector_backend=null`. A composed `ingest(commit=False)` response has SQL storage
false until the caller commits. Stored content remains available as canonical SQL;
vector search readiness is separate. Pending does not mean upsert acknowledgment.
Documents expose the job ID, attempt count, next retry time, timestamp and sanitized
error code in ingestion metadata. Ready requires a verified current-generation
write and committed acknowledgment; failed means the retry budget was exhausted.
Legacy observations remain readable as unknown or their historical acknowledgment.

SQL admission records one zero-token `rag_ingest` usage event atomically with the
content/job, so pending uploads count toward the existing ingestion quota. A
duplicate does not add an event. Embedding batches/retries record actual or
explicitly estimated provider usage under `rag_indexing`; each batch checks the
existing monthly token/cost and daily request budget before its remote call.
Blocked budgets produce `indexing_quota_exhausted` and bounded pending/failure,
without a provider call. Admission plus indexing events both count toward the
existing daily request counter; review that conservative accounting when sizing
worker throughput. Estimates do not claim billing-grade cost.

`POST /knowledge/documents/{id}/retry-indexing` retries an exhausted/unknown job in
the exact authenticated owner scope, preserves identity and returns pending.
Existing pending/processing/ready jobs are returned without duplicate provider work.
`DELETE /knowledge/documents/{id}` returns 204 after SQL deletion/tombstone commit.
Wrong-owner retry/delete IDs return 404. Existing authentication/rate limits apply.

Agent 1 owns generated frontend contracts, polling and the pending/ready/failed UI.
Agent 2 owns its retrieval adapter and durable turn storage. Its manifest requests
no new tables, so there is one final migration head. Agent retrieval includes own
private and organization-shared documents and preserves strategy templates; direct
search can opt into shared visibility. Rejected vector hits mark search degraded.

## Exact rollout requirements for supervising review

1. Integrate the three branches, regenerate Agent 1's OpenAPI/client contracts,
   and ensure a pending receipt shows stored content without claiming searchable.
2. Upgrade the reviewed schema from `a8agentcapture001` to `a9knowledgeoutbox001`.
   The revision was generated with Alembic against disposable PostgreSQL, filtering
   only the owned additions; historical migrations were not edited. It adds nullable
   document generation and the outbox table/indexes/checks. Local upgrade,
   downgrade/reupgrade and legacy-content preservation are verified.
3. Deploy the reviewed code in a coordinated window. New ingestion needs the
   outbox schema. An old ingestion writer can still perform premature vector writes;
   do not run mixed writers indefinitely. Downgrading the schema drops jobs and
   generation tracking; preserve content and drain/export jobs before any separately
   reviewed downgrade. Prefer disabling the indexing component for rollback.
4. After integration and schema review, explicitly set `KNOWLEDGE_INDEXING_ENABLED=true`
   on the existing supervised paper worker. It defaults false. No Watcher/Telegram
   or trading arm changes are needed. This task does not set the deployed flag or
   edit Render/CI configuration. Leaving it false keeps new uploads pending.
5. Verify worker PostgreSQL, provider credentials, authoritative Qdrant availability,
   collection dimensions and keyword-index permissions. The adapter adds the scoped
   `document_id` payload index alongside existing tenant/user indexes. Missing
   providers/permissions produce retry/failure, not readiness or memory substitution
   in staging/production. Monitor indexing health and document attempt/error states.
6. Size for one indexing thread, two jobs and one reconciliation per poll interval,
   at most 2,048 chunks/document and 32 embeddings/batch. Inventory is capped at
   10,000 points / 80 pages. Existing provider timeouts govern calls; shutdown stops
   additional batches/jobs, completes the current remote call and leaves interrupted
   work retryable. Review embedding spend, provider capacity, DB connections and
   worker memory before rollout. Model/dimension changes require explicit versioned
   reindexing; this task does not change provider settings.
7. Run cross-module Agent, journal/lesson sync, capture, generated contract/UI,
   provider SDK, scope and worker/migration regressions in the consolidated branch.
   Complete one supervised exact-ref release gate under `.ai/RELEASE.md`; focused
   local passes are development evidence. External order acceptance stays supervised.
