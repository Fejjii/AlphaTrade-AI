# RAG System

AlphaTrade RAG provides **rules, playbooks, journal lessons, and policy context** —
never direct trading signals or order instructions.

## Components

| Layer | Implementation |
|-------|----------------|
| Ingestion | `RagService.ingest()` — chunk, embed, persist to DB + vector store |
| Embeddings | `mock-embeddings` (deterministic) or `openai-embeddings` when configured |
| Vector store | in-memory (default/tests) or Qdrant when `PROVIDER_MODE=fallback` |
| Retrieval | `RagService.search()` with metadata filters and citations |

## Embedding dimensions

| Mode | Default dimensions |
|------|--------------------|
| No `OPENAI_API_KEY` (mock) | **384** |
| `text-embedding-3-small` with key | **1536** |
| Explicit `EMBEDDINGS_DIMENSIONS` | that value (OpenAI `-3-*` models receive it via API) |

Mock fallback used by the OpenAI provider is always constructed with the **same**
dimension as the live provider so runtime fallback never mixes sizes.

Qdrant is configured with that same size. If collection `alphatrade_knowledge`
already exists with a different size, upserts/searches **do not write incompatible
vectors into Qdrant**; they fall back to in-memory and provider status reports a
dimension mismatch.

## Enabling real embeddings

```bash
OPENAI_API_KEY=...          # set in Render secrets; never commit
PROVIDER_MODE=fallback
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDINGS_MODEL=text-embedding-3-small
# optional explicit size:
# EMBEDDINGS_DIMENSIONS=1536
```

## Enabling Qdrant

```bash
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=...          # required for Qdrant Cloud; wired into Settings
PROVIDER_MODE=fallback
```

Docker Compose starts local Qdrant on port 6333 (usually no API key). When Qdrant
is unreachable, the backend falls back to the shared in-memory store automatically.

Collection `alphatrade_knowledge` is created on first upsert with cosine distance
and the configured embedding dimensions.

## Staging: switch mock → OpenAI (operator procedure)

Paper-only. No orders, proposals, workers, scanners, or Telegram.

1. Keep safety flags unchanged:
   - `EXECUTION_MODE=paper`
   - `ENABLE_REAL_TRADING=false`
   - `EXCHANGE_MODE=paper_internal`
   - `PROVIDER_MODE=fallback`
2. Set on Render (names only): `OPENAI_API_KEY`, and if needed `QDRANT_API_KEY`,
   optional `OPENAI_BASE_URL`, `LLM_MODEL`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_DIMENSIONS`.
3. Redeploy API (worker stays disabled).
4. Recreate **only** the knowledge collection (deletes existing vectors in that collection):

   ```bash
   ENV_FILE=.env.staging ./scripts/recreate-rag-collection.sh --dry-run
   ENV_FILE=.env.staging ./scripts/recreate-rag-collection.sh --i-understand-this-deletes-vectors
   ```

5. Reingest playbook / knowledge fixtures:

   ```bash
   ACCESS_TOKEN=... BASE_URL=https://<staging-api> ./scripts/reingest-knowledge-base.sh --api
   ```

6. Validate:

   ```bash
   ./scripts/provider-validation-smoke.sh local
   BASE_URL=https://<staging-api> ./scripts/provider-validation-smoke.sh --remote
   ACCESS_TOKEN=... BASE_URL=https://<staging-api> ./scripts/provider-validation-smoke.sh --remote --ingest
   ```

Expected login badges after a healthy OpenAI key: `openai-llm`, `openai-embeddings`,
`qdrant`, still `Provider mode: fallback`, paper trading disabled.

## Metadata filters

Search supports organization, user, source type, and strategy/symbol/timeframe/risk tags.
Payloads are stored with chunk metadata for tenant-scoped retrieval.

## Agent integration

The `rag_retriever` tool is the only RAG entry point for the agent graph. Citations
appear in chat responses and the structured `analysis.evidence` field when context
was retrieved.

## Journal auto-ingest (Slice 20)

Trade journal entries can automatically sync into the knowledge base for future retrieval.

| Setting | Default | Description |
|---------|---------|-------------|
| `JOURNAL_RAG_SYNC_ENABLED` | `true` | When true, create/update triggers RAG upsert |

**Service boundary:** `JournalRagSyncService` (`backend/src/app/services/journal_rag_sync_service.py`)

- Source type: `trade_journal`
- Stable URI: `journal://{entry_id}` for idempotent updates
- Metadata tags: symbol, timeframe, strategy/setup type, result, emotion/mistake tags in body text
- Secrets stripped via `sanitize_journal_text()` before ingestion
- Lessons and **improvement rules** are indexed for retrieval; mistake tags are included in chunk text
- Agent retrieval boosts `trade_journal` / mistakes sources when the user asks about mistakes, emotions, or improvements
- **Analytics API summaries are not ingested** unless explicitly designed later ([trading_analytics.md](trading_analytics.md))

Agent retrieval includes `TRADE_JOURNAL` in `RagService.retrieve_for_agent()`.

Disable sync:

```bash
JOURNAL_RAG_SYNC_ENABLED=false
```

## Evaluation notes

- Mock embeddings are deterministic — use them for unit tests and RAG regression.
- Integration tests with real OpenAI/Qdrant should be isolated and env-guarded.
- Usage events record embedding provider, token estimates, and fallback status.
- Run regression: `uv run python ../evaluation/evaluate_rag.py` from `backend/`.
- Local provider smoke (no live calls): `./scripts/provider-validation-smoke.sh`
