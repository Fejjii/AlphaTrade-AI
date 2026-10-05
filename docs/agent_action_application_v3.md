# Governed Agent action application V3

Branch `codex/agent_action_application_v3_001` starts exactly at
`42b9803aee5111e7c5708285afc8614f315411dd` (PR159). V3 extends the existing
Agent action registry and transcript confirmation boundary. It adds no domain
stores or migrations. Turns draft; the separate confirmation endpoint applies
supported requests through existing authorities.

| Action | Confirmation result | Canonical record identity |
| --- | --- | --- |
| Journal create and reflection/mistake/lesson/observation append | JournalService writes, with scoped targets and stale-note checks | `journals.id` |
| Knowledge lesson/rule/observation | RagService ingests documents, chunks and vectors, enforcing the existing quota and HTTP ingestion rate limit | `documents.id` |
| Strategy observation/hypothesis/evidence links | RagService ingests a review note containing strategy and evidence references | `documents.id` |
| Strategy creation/refinement proposal | Checks and returns the existing StrategyProposalService DRAFT; does not confirm its version | `strategy_conversation_proposals.id` |
| Watcher enable/disable/replace/reorder/universe | WatcherWatchlistRepository applies the reviewed replacement through five-slot validation and compare-and-swap revision fencing | `watcher_watchlists.organization_id` plus resulting revision |
| Qualified historical validation/replay | BacktestService creates a QUEUED request; the existing worker or HTTP background fallback executes it | `backtest_runs.id` |
| Complete paper pretrade request | PreTradeAnalysisService computes advisory analysis; ConversationService persists its request and result | `conversation_messages.id` |
| Existing paper trade proposal | Rechecks the scoped canonical plan and risk, then retains `confirmed_unapplied` for its execution gates | Existing proposal ID appears in the handoff receipt |

Every applied action returns `resulting_record_id`. `application_result` describes
the record type and outcome. These result fields are separate from the immutable
reviewed payload: draft flags such as `ingested`, `configuration_changed`,
`validation_ran` and `sizing_performed` remain the original preview. Use the
receipt and canonical status endpoint for the result. A saved refinement draft
is applied as a proposal with `authority_mutated=false`; version confirmation and
activation remain separate operations.

## Confirmation and isolation

Confirmation requires explicit user intent, the expected content hash, persisted
owner/trader membership and organization/user scope. The transcript row stays
locked through canonical application and receipt persistence. Pending targets
and evidence references are revalidated; a changed Watcher revision or strategy
draft conflicts. Completed confirmations return the original receipt, even if
the domain later changes. Existing journal-create recovery also remains intact.

Knowledge documents link to the source conversation/message through `source_uri`.
Ingested text retains action, organization/user, source-message, strategy and
evidence-document provenance. Strategy tags remain on canonical chunks and
vectors. Provenance also prevents the existing organization-wide source-hash
deduplication from returning another user's private document for identical prose.
Evidence links are research notes, not acceptance into an executable strategy.

RagService has an optional caller-owned commit mode. The default ingestion route
behavior is unchanged. Agent application uses this mode to preserve the row lock
and commit the document/chunks and receipt together. Vector upserts remain the
existing external operation and cannot participate in a PostgreSQL transaction;
provider failure never produces an applied receipt. Production embedding and
authoritative Qdrant checks still belong to RagService.

Changed action descriptors cause pending V2 drafts to require a fresh proposal;
the Agent does not reinterpret their sealed authority contracts.

## Supported job input

`strategy.request_validation` accepts a scoped strategy and a canonical
`backtest` request. The Agent requires explicit symbol, timeframe, start date and
end date, captures a version belonging to that strategy, and supplies its own
proposal-scoped idempotency key. Confirmation creates the request with inline
execution disabled. HTTP confirmation commits before calling the existing
backtest enqueue helper, once per new confirmation. The receipt records the
QUEUED snapshot and `/backtests/{id}` status path; it never claims a completed
validation. Direct service callers own their commit and worker dispatch.

```json
{
  "name": "strategy.request_validation",
  "arguments": {
    "text": "Replay this historical interval",
    "strategy_id": "<scoped strategy UUID>",
    "backtest": {
      "assumptions": {
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "start_date": "2026-09-01",
        "end_date": "2026-09-02"
      }
    }
  }
}
```

Incomplete or unsupported requests remain `confirmed_unapplied` with explicit
missing inputs or an unavailable-authority reason. No new job runner is invented.
The existing backtest engine may update its canonical validation/eligibility
metadata when it finishes; the Agent never activates a strategy version.

## Paper trade boundary

A paper request can carry `pretrade`, using the existing PreTradeAnalyzeBody.
Its symbol, direction and timeframe must match the stated trade; account size
and maximum risk per trade must be explicit. Scoped strategy and chart-level
references are checked again at confirmation. A conservative conversational
example is:

> Enter a paper trade BTCUSDT long 1h entry 100 stop 95 targets 110, 120.
> Account size 10000 max risk 1%.

This only drafts a request. A separate hash-protected confirmation runs advisory
pretrade analysis. User-stated prices remain in the result transcript alongside
the service's analysis; suggested levels are not substituted into a trade plan.
Canonical pretrade owns any advisory sizing calculation. Its result is not a
RiskService approval or ActionEligibility decision, and any advisory provider
limitations remain in the stored response. Requests lacking account/risk inputs
stay unapplied. Existing risk BLOCK cannot be overridden at confirmation.

The Agent never mints Candidate, supplies position size, overrides risk, accepts
planned loss, approves an executable TradePlan, submits orders or enables live
trading. Required trade confirmation, ActionEligibility and execution gates stay
with their canonical authorities. There are no frontend, Telegram, voice,
deployment or worker-arming changes.

## Verification

Focused application/orchestration/foundation tests cover the HTTP contracts,
canonical identities, immutable hashes, duplicate receipts and dispatch, scope
rechecks, shared quotas/rate limits, provider failure, Watcher fencing, unchanged
strategy versions, observable backtest requests, and advisory paper handoffs.
PostgreSQL tests use isolated temporary schemas and concurrent confirmations for
knowledge, Watcher and pretrade. They skip when the test database is unavailable.
Adjacent RAG, backtest, quota, journal and ActionEligibility regressions are also
run; no frontend or deployment verification is needed for this backend change.
