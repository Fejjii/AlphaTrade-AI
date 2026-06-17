# Lesson review workflow (Slice 37)

## Lifecycle

1. **Detection** — discipline analyzers (human vs system, runner analysis, stop loss refusal, journal) produce lesson *candidates*.
2. **Pending review** — candidates appear on `/lessons` with source metadata, severity, and confidence. They are *observations*, not rules.
3. **Accept** — trader explicitly accepts; lesson becomes **accepted trading memory** (optional RAG ingest).
4. **Reject** — kept for audit trail; not ingested as truth.
5. **Archive** — historical retention without active review queue.

## Accepted vs pending

| Status | Agent treatment | RAG |
|--------|-----------------|-----|
| `pending_review` | Observation only — do not treat as rule | No ingest |
| `rejected` | Historical audit only | No ingest |
| `accepted` | Searchable lesson / memory | Ingest when `journal_rag_sync_enabled` |

## Rule updates from lessons

Accept flow supports:

- Accept lesson only
- Accept + attach `structured_rules_patch` to latest strategy version (explicit flag)
- Accept + create new strategy version (explicit flag)

**No automatic mutation** of active strategy without user action.

## Real trading

Real trading, broker execution, and live billing remain **disabled**. All execution is paper-only.
