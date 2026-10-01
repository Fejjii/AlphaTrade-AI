# Governed Agent action orchestration V2

The next application layer is documented in
[Agent action application V3](agent_action_application_v3.md). The behavior below
describes the V2 baseline.

Extends `interactive_agent` at base
`79b76d6313c7d1a269a9e32d67f89e39eca9df96` (PR153). The existing Agent,
ConversationService, model responder, retrieval, Strategy Brain reads and paper
safety stay in place. No new database tables or domain stores are introduced.

## Public contract

`GET /agent/capabilities` includes an `actions` catalog. Every tool declares its
name, JSON input schema, authority, read/propose/confirm behavior, required
permission, explicit-confirmation requirement, record identity and limitations.

`POST /agent/turns` accepts the existing message/context and an optional typed
action. Without that field, a deterministic grammar recognizes supported
requests. Ambiguous identifiers are not guessed: missing fields stay explicit.
An explicit action's input wins over inferred routing. A live-trading request in
the message always takes precedence and is refused.

Example journal append request:

```json
{
  "message": "Record this lesson in my journal",
  "action": {
    "name": "journal.record_lesson",
    "arguments": {
      "journal_entry_id": "00000000-0000-0000-0000-000000000001",
      "text": "Wait for a closed candle before entering."
    }
  }
}
```

Tools are a closed registry. Unknown names, extra input fields such as risk
overrides or position sizes, and turn-time `proposal.confirm` calls fail safely.
Only the separate existing confirmation endpoint accepts a decision statement
and content hash. Model prose never supplies a tool name, input or permission.

## Authority and application

| Actions | Proposal behavior | Confirmation behavior |
| --- | --- | --- |
| `context.read` | Existing scoped Agent reads | No confirmation |
| `journal.create` | Parsed draft; missing symbol, direction and timeframe are labeled | Complete drafts apply through JournalService |
| `journal.append_reflection`, `record_mistake`, `record_lesson`, `record_observation` | Scoped target and content snapshot; absent target stays incomplete | JournalService appends pending notes to lessons, or mistakes to the mistakes list; stale content conflicts |
| `strategy.observation`, `hypothesis` | Durable transcript proposal with scoped strategy/evidence references | `confirmed_unapplied` |
| `strategy.create`, `refinement` | Existing StrategyProposalService DRAFT, with evidence in context_refs; refinement requires an existing strategy | `confirmed_unapplied`; linked draft uses the existing strategy confirmation gateway |
| `strategy.associate_evidence` | Explicit scoped strategy/document association proposal | `confirmed_unapplied`; does not claim association was applied |
| `strategy.request_validation` | Durable validation/replay request | `confirmed_unapplied`; validation_ran, replay_ran and scheduled remain false |
| `knowledge.propose` | Existing IngestDocumentRequest for canonical documents/chunks, plus scoped evidence references | `confirmed_unapplied`; existing `/knowledge/ingest` applies its own quota and ingestion gates |
| `watcher.change` | Enable/disable/replace/reorder/universe preview using existing five-slot validators and current revision | `confirmed_unapplied`; stale revision conflicts; existing Watcher PUT route owns application |
| `paper_trade.propose` | User-stated prices, or a scoped existing trade proposal; explicit risk state and authority handoff | `confirmed_unapplied`; current risk BLOCK refuses confirmation; changed plans conflict |
| `proposal.confirm` | Catalog describes the separate endpoint; turns cannot dispatch it | Existing statement, hash, transcript row lock and lifecycle checks |

Each proposal seals the action metadata, validated input, target identities,
snapshot and linked strategy draft identity into the existing content hash.
Journal append confirmations reuse transcript locking and acquire the target
journal lock. A proposal tag makes replay converge on the existing record.
Persisted owner/trader membership is required for proposals and decisions and is
rechecked at confirmation. Target journals, strategies, documents and trade
proposals are scoped by organization and user; organization-shared documents are
accepted only inside the caller's organization.

Paper requests without an existing proposal point to `/pretrade/analyze` and
label risk `not_assessed`. Named existing proposals are read through
ProposalService and point to their workflow route. These are review handoffs;
the Agent does not run pretrade analysis, set size, mint a Candidate or executable
TradePlan, approve a trade, accept planned loss, or call execution. Prices are
never filled from placeholder analysis. Current canonical Candidate eligibility,
risk, confirmation and execution gateways remain necessary for paper execution.

## Intentionally deferred integration

- Automatic application of knowledge ingestion and evidence associations;
  canonical RAG ingestion, vector updates and domain review stay separate.
- Agent application of strategy versions, activation, later validation/replay
  jobs, and Watcher changes. The proposal captures intent and supported links;
  it does not report these operations as completed.
- Conversational binding to canonical Candidate/ActionEligibility/TradePlan
  construction, approved sizing and paper execution. No executable authority is
  invented from an analysis proposal or prose.
- Frontend integration, Telegram commands/delivery/preferences changes and
  voice implementation. Existing NotificationPreferencesService remains the
  preference owner; this branch introduces no Telegram action. Voice remains
  contract only.

Live trading remains refused. This branch does not merge, deploy or arm workers.

## Focused validation

`pytest tests/test_agent_action_orchestration.py tests/test_interactive_agent_foundation.py`
passes 66 tests, including real Agent route contracts against an isolated database,
routing, journal append, strategy drafts, knowledge/Watcher proposals, paper-only
handoffs, risk rejection and current-risk rechecks, live refusal, hash protection,
tenant/user isolation, persisted permission checks, duplicate confirmation and
unknown-action failure. The existing concurrent journal-create tests also pass.
Ruff and targeted mypy checks pass. No full suite or CI wait is required.
