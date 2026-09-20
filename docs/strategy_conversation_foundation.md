# Strategy conversation foundation (AT-065–066)

Persistent conversational strategy intelligence. Paper only. No Watcher, Telegram,
live trading, or autonomous activation.

## Loop

User discusses an idea → durable conversation → AI structures a **preview**
proposal → user reviews → explicit confirmation → versioned strategy draft →
later explicit strategy approval + compile (AT-067). Conversational confirmation
does not compile, approve, or activate.

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

## Pattern preview

- Keyword drafts remain non-authoritative `StructuredRules` sketches.
- `pattern_spec` is emitted only for the supported first pattern, and only when
  every authored threshold is stated explicitly. Canonical defaults are never
  copied in.
- Incomplete first-slice ideas list missing fields and stay non-executable.
- Unsupported ideas do not receive a `pattern_spec`. Confirmation of a draft
  still does not mark the version executable.

## Confirmation architecture

- `strategy_conversation_proposals` are `STRATEGY_DRAFT` rows. They do not
  compile, activate, or change evaluation policy.
- Confirm requires an unquoted confirmation-only message (`I confirm` or
  `I confirm proposal <uuid>`). Questions, quote blocks, fenced code, and
  `retrieved:` / `SYSTEM:` lines do not mutate authority.
- HTTP `POST /conversations/{id}/proposals/{proposal_id}/confirm` re-checks
  proposal identity, payload content hash, target strategy, and captured parent
  version. Optional `expected_content_hash`, `expected_parent_version_id`, and
  `expected_target_strategy_id` reject stale clients with 409.
- Duplicate confirm is idempotent and concurrent confirms converge to one
  resulting version. Rejected or superseded proposals cannot be confirmed.
- Confirm forks through `StrategyVersioningService.fork_semantic_update` with
  `StrategyChangeSource.CONVERSATION_CONFIRM`. Provenance is
  `strategy_version_conversation_links` (conversation → proposal → version).
- Confirmed versions are **not** compiled and are **not** Watcher/paper activated.
  AT-067 `resolve_executable_strategy_policy` still requires a later explicit
  compile plus APPROVED or ACTIVE lifecycle.

## Memory usage

Do not create another memory authority. Facts stay in:

- strategy library / immutable versions
- journal
- lessons
- learning attribution
- RAG documents/chunks

Conversation memory is a transcript plus draft proposals only.

## Remaining dependency

AT-067: approved compiled `content_hash` is the only evaluation policy. The
controlled fixture in `test_intelligence_integration_fixture.py` proves
discussion → preview → confirm → compile → approve → canonical evidence →
deterministic `SetupAssessment` on replay. That fixture is not live validation.
Do not enable Watcher.
