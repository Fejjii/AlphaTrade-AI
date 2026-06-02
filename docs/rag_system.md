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

## Enabling real embeddings

```bash
OPENAI_API_KEY=sk-...
PROVIDER_MODE=fallback   # or live
EMBEDDINGS_MODEL=text-embedding-3-small
```

Without a key, mock embeddings produce stable 384-d vectors for tests and offline dev.

## Enabling Qdrant

```bash
QDRANT_URL=http://localhost:6333
PROVIDER_MODE=fallback
```

Docker Compose starts Qdrant on port 6333. When Qdrant is unreachable, the backend
falls back to the shared in-memory store automatically.

Collection `alphatrade_knowledge` is created on first upsert with cosine distance.

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
