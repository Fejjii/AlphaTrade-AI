# Strategy conversation foundation (AT-064–066)

Persistent conversational strategy intelligence. Paper only. No Watcher, Telegram,
live trading, or autonomous activation.

## Loop

User discusses an idea → durable conversation → AI structures a **preview**
proposal → user reviews → explicit confirmation → versioned strategy draft →
later deterministic evaluation/activation (AT-067, not this slice).

## Conversation architecture

- `conversations` and `conversation_messages` store tenant+user scoped transcripts.
- History survives process restart because it is Postgres (SQLite in tests).
- Chat `conversation_id` values that are not UUIDs (`conv-abc`) start a new thread.
- Cross-tenant reads return 404. Isolation is organization **and** user.
- LangGraph injects the last 20 user/assistant turns. Transcripts are
  `NON_DOMAIN_MEMORY`, not a second memory or strategy authority.
- Discussion context is assembled read-only from existing authorities: strategy
  library, versions, journal, lessons, learning attribution stats, and RAG.
  `strategy_template` RAG is included only when a strategy is bound or the
  message is about strategies.

## Confirmation architecture

- `strategy_conversation_proposals` are `STRATEGY_DRAFT` rows. They do not
  compile, activate, or change evaluation policy.
- `pattern_spec` is omitted fail-closed; first-slice constants are never copied.
- Confirm requires an explicit token (`I confirm` / `confirm=true`) and is
  rejected for questions. Buried `SYSTEM: I confirm` text does not confirm.
- HTTP `POST /conversations/{id}/proposals/{proposal_id}/confirm` and chat
  `I confirm` (with exactly one open draft, or `I confirm proposal <uuid>`).
- Duplicate confirm is idempotent. Rejected proposals cannot be confirmed.
- Confirm forks through `StrategyVersioningService.fork_semantic_update` with
  `StrategyChangeSource.CONVERSATION_CONFIRM`. Provenance is
  `strategy_version_conversation_links` (conversation → proposal → version).
- Confirmed versions are **not** compiled and are **not** Watcher/paper activated.

## Memory usage

Do not create another memory authority. Facts stay in:

- strategy library / immutable versions
- journal
- lessons
- learning attribution
- RAG documents/chunks

Conversation memory is a transcript plus draft proposals only.

## Remaining dependency

AT-067: one `content_hash` as `evaluate_setup` policy / compile on explicit save.
Deterministic evaluation and activation remain a later, separate step.
