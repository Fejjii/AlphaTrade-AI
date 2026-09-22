# Telegram and continuous evaluation integration (AT-075)

Paper measurement (AT-073) and paper Telegram discussion (AT-074) sit on the
paper Watcher stack (AT-072). This slice does not merge those source PRs, does
not deploy, and does not enable Watcher, Telegram, or live trading.

## Authorities

One canonical trading authority remains:

- Setup truth: `evaluate_canonical_strategy` → SetupAssessment
- Candidate: persisted only on `CONFIRMED_SETUP` with approved compiled policy
- Risk: ActionEligibility `BLOCK` is final
- Execution: paper worker and Telegram do not place orders

`paper_evaluation` copies facts. `telegram_paper_agent` discusses them.
`paper_interaction` only composes those two. AI refinement is a suggestion
(`activate=false`, `auto_activate=false`). Narrative is excluded from
`content_hash` and from Telegram fact lines.

## Loops

Watcher scan → `WatcherPaperEvaluationObserver` → observation store.

The same scan report → optional `telegram_scan_hook` → durable
`PaperNotificationIntent` and Telegram outbox → bound discussion.

Journal close and learning attribution → `PaperEvaluationQueryService` →
deterministic facts and a refinement suggestion → `EvaluationLearningContext`
→ Telegram learning reply.

`build_paper_runtime` leaves the scan hook unset. `PERSIST_AND_NOTIFY` stays
`notify_disabled`. `TELEGRAM_INTERACTION_ENABLED` stays false.

## Schema

Single Alembic head:

`c8d9e0f1a2b3` (setup-lifetime pins)
→ `e3f4a5b6c7d8` (paper evaluation observations)
→ `d9e0f1a2b3c4` (paper Telegram notification, thread, message, confirmation)
→ `e0f1a2b3c4d5` (paper Telegram activation cursor and send ledger).

## Still disabled

Watcher orchestration, market watcher, Telegram interaction, and real trading
remain false. A separate authorized task is required before any of those flags
can be turned on.
