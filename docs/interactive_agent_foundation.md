# Interactive agent foundation

Paper-only orchestration for the future Agent surface. This layer does not replace
the existing LangGraph chat graph. It reuses the stores that already own each fact.

## Authority

| Concern | Existing owner | This layer |
| --- | --- | --- |
| Transcript | `ConversationService` | Reads and appends turns |
| Strategy versions | `StrategyLibraryService` | Read only |
| Strategy preview | `StrategyProposalService` | May store a `DRAFT` preview. Does not confirm it |
| Journal rows | `JournalService` | Written only by `POST /agent/proposals/{id}/confirm` |
| Knowledge | `documents` and `chunks` | Lexical retrieval. Optional vector hits are reloaded from those rows |
| Portfolio | `PaperPortfolioService` | Read only |
| Performance | `PerformanceService.build_report` | Read only. No snapshot write |
| Coaching | `CoachingService.summary` | Read only. Lessons are not accepted |
| Watcher | `MarketWatcherObservationRepository` | Read only, provenance `watcher_observed` |
| Market quotes | Injected `MarketDataService` reader | Returned with source, `is_live`, `is_stale`, and `fallback_used` |
| Orders | Existing execution services | Not called |

`/chat` remains the LangGraph entry point. `/agent` is the orchestration contract.

## Turns do not mutate domain records

A turn classifies one capability and may attach a structured proposal to the
assistant message. Free-form text, including `I confirm` inside the same
message or a later chat turn, does not write a journal row, strategy version,
rule, lesson, or order.

Confirm and reject are separate requests. They require an unquoted confirmation
or rejection statement and the proposal content hash. A hash mismatch is a
conflict. Another tenant receives not-found.

Only a complete journal proposal is applied, and it is applied through
`JournalService`. Strategy, rule, lesson, observation, hypothesis, and trade
decision confirms are recorded as `confirmed_unapplied`. The linked strategy
preview stays `DRAFT` until the existing conversation confirm route is used.

## Artifact kinds and provenance

Every proposal names one of: observation, hypothesis, strategy, rule, journal
entry, trade decision, lesson.

Provenance is one of: user supplied, agent inferred, watcher observed, trade
outcome, system generated. Retrieved rows keep the provenance of their source.
Watcher rows stay watcher-observed. Closed journal results stay trade outcomes.

## Contracts that are not implemented

Screenshot analysis and voice input/output return a contract with
`analyzed=false`, `analysis=null`, `transcript=null`, and `audio_generated=false`.
Image and audio bytes are not accepted or interpreted.

## Paper safety

The agent cannot enable real trading. `execution_mode` stays `paper`.
`real_trading_enabled` stays false. No turn sets `execution_attempted`.
Asking to enable real trading stores a refused proposal and does not change
settings.
