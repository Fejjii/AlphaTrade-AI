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

## Slice 38 — UI accept paths

The `/lessons` accept panel supports three explicit paths:

1. **Accept lesson only** — reviewed memory only
2. **Accept + attach rule** — patches latest strategy version `structured_rules` (requires strategy selector + confirmation)
3. **Accept + new version** — bumps `current_version` and stores `lesson_source_metadata` on the new version

The UI shows current strategy version, editable proposed rule text, reviewer notes, and a confirmation checkbox warning that the active strategy is not silently mutated.

## Strategy version provenance

When a version is created from a lesson, `user_strategy_versions.lesson_source_metadata` stores:

- `lesson_id`, `mistake_type`, `accepted_lesson_text`, `rule_update_summary`, `reviewer_notes`, `created_at`

Strategy Lab detail page lists versions created from lessons.

## Real trading

Real trading, broker execution, and live billing remain **disabled**. All execution is paper-only.
