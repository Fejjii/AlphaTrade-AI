# Full governed paper closed-loop acceptance 001

> **Historical / release-specific record.** Original decisions, procedures and results below are preserved for their stated date/base. They are not current runtime observations or complete MVP acceptance. Read the [current status and pending acceptance](current_status.md), [architecture](architecture.md) and [deployment entry point](deployment.md) first; recheck commit-specific environment, migration and activation values before using older procedures.


Base: `codex/release_consolidation_wave_003` at
`8673d8f69779ea516ca97456baea7b3064daf089`.
Branch: `codex/full_paper_closed_loop_acceptance_001`.
No commits or files are taken from the canonical evidence diagnostic branch.

The acceptance test discovers one genuine supported bearish liquidity-sweep/CVD
setup from deterministic public-market REST fixtures and completes its governed
internal paper lifecycle. It never inserts a Candidate, assessment, eligibility,
plan, authorization, execution command, fill or Journal record as test setup.

## Reproduce

Use a **disposable PostgreSQL test database**: the existing test factory drops
and recreates its `public` schema for each scenario. Run sequentially with other
PostgreSQL tests. Install backend dependencies with `uv sync --extra dev`.

```bash
cd backend
export AT028_POSTGRES_URL='postgresql+psycopg://USER:PASSWORD@localhost/alphatrade_test'
export PHASE1_POSTGRES_URL="$AT028_POSTGRES_URL"
export ENABLE_REAL_TRADING=false EXECUTION_MODE=paper EXCHANGE_MODE=paper_internal
export TELEGRAM_NETWORK_PERMITTED=false
export ALPHATRADE_CLOSED_LOOP_PROOF_PATH=/tmp/alphatrade-closed-loop-proof.json
uv run pytest tests/test_full_paper_closed_loop_acceptance.py -ra
```

All 12 cases must **pass**, with no PostgreSQL skips. The successful positive
case exports its identities, compiled AST, evaluated rules, evidence window,
final attribution, Daily Review, Attention item, Agent explanation and outbox
identities. A captured passing run is in
[`evidence/full_paper_closed_loop_acceptance_001.json`](evidence/full_paper_closed_loop_acceptance_001.json).
The fixture uses ordered microsecond ORM timestamps within the fixed day so
normal transcript ordering remains deterministic. Fresh runs generate new
authority identities; fixed market facts and resulting
economics are deterministic. `proof_hash` hashes the report without its own key
using the product's canonical serialization.

## Evidence and authority

The scenario uses the existing executable first-slice strategy family at a fixed
clock (`2026-01-15T16:15:05Z`). It supplies 100 closed 15-minute bars, 30 context
4-hour bars, aggregate trades, contract discovery, funding and open interest.
The trigger sweeps a confirmed swing high and a tenant-owned manual 4-hour
resistance at 100200: high 100220, close back below at 100080, trigger volume
200 versus quiet volume 20, with trade-derived CVD divergence and sell flow.
Every required strategy rule must pass through the normal evaluator.

`BinanceUsdmPerpetualSource` consumes these inputs through `httpx.MockTransport`.
The normal assembler, market monitor, Watcher and approved compiled strategy
policy consume the adapter output. Its live-adapter metadata is simulated for
contract verification; this is fixture evidence, not a live-market observation.
Actual sync and async HTTP transports are forbidden throughout every acceptance
case. Mutation endpoints are absent from the fixture.

| Transition | Authority and recorded identity |
| --- | --- |
| Market Evidence | Normal first-slice assembler; complete evidence window and content hash |
| Watcher | Durable scan lineage and request hash |
| Strategy Evaluation | Approved strategy version, compiler version, compiled setup ID/hash/AST |
| SetupAssessment | Evaluator assessment ID/hash, evaluated rules and evidence references |
| Candidate | Normal Candidate lifecycle ID/hash and assessment/window lineage |
| ActionEligibility | Canonical eligibility ID/hash and Risk snapshot ID |
| Risk | Deterministic RiskService verdict captured in the execution transcript |
| TradePlan | Immutable canonical revision ID and content hash |
| Explicit Confirmation | Exact presented revision/hash message, approval and authorization identities |
| Execution | Canonical execution command and receipt IDs |
| Internal Paper Fill | Immutable fill ID/hash, venue `paper_internal` |
| Journal | Same JournalTrade and append-only approved-plan/fill/close event IDs |
| Learning / Analytics | Final attribution ID/hash/source events; strategy-version bucket |
| Daily Review | Review ID/hash; recorded paper entry, close and net PnL |
| Attention Queue | Open-position item ID and Journal source reference |
| Agent Explanation | Persisted assistant message and canonical source connections |
| Notification | Durable paper notification intent and pending candidate outbox; zero attempts |

The initial scan intentionally has no execution account. Normal automated
continuation therefore stops at `execution_account_missing` after discovery.
The fixture then enrolls a paper NET account and calls the existing canonical
eligibility command builder/evaluator with actual server-side risk accounting.
The normal Agent paper gateway prepares the plan and requires its exact separate
confirmation. No authorization, execution or Journal record exists before that
confirmation.

The explicit operator fixture supplies entry/stop/targets; deterministic sizing
and RiskService remain authoritative. The approved plan shorts 0.004 BTC at
100080 with stop 100240, maximum loss 0.64 USDT, and targets 99920/99760.
The existing canonical paper-close authority closes the same filled lifecycle at
the first target, yielding 0.64 USDT net PnL under the existing zero-fee,
zero-funding, zero-slippage internal paper policy. Analytics sees one closed
trade attributed to the actual approved strategy version. The Attention snapshot
is captured while the position is open, before this deterministic close.

## Agent and Journal changes

`paper_trade.explain_execution` is a typed, tenant/user-scoped read action. It is
also reachable with `Explain paper execution command=<UUID>`. It reads the
immutable plan, canonical Candidate/receipt, fill facts, captured execution Risk
result and current Journal status. A missing or mismatched execution transcript
fails closed. It returns source connections and saves their references in the
conversation. No model composition, arithmetic, Risk evaluation, approval,
execution or provider call occurs. The captured Risk verdict describes the
historical execution decision, not present eligibility. Executions without a
captured Agent confirmation result cannot use this explanation action; it
refuses to invent a historical Risk decision.

The acceptance exposed two Journal projection defects and verifies their fixes:

- Canonical fills now project the earliest immutable fill timestamp as
  `entry_time`, making the real paper entry discoverable by Daily Review.
- A verified duplicate fill reuses its existing immutable Journal event payload.
  PostgreSQL decimal scales or subsequent partial fills cannot change that
  event's idempotency hash. If the event was never committed, normal projection
  still reconstructs it for recovery.

The existing controlled rehearsal outage/stale tests now share the same offline
contract discovery stub as their positive test; all reach their intended scripted
evidence failure instead of an external discovery refusal.

No migration or frontend response-field change is required. The Agent catalog
has an additional read action using its existing typed contracts.

## Negative paths and safety

The same suite verifies NO_SETUP, WATCH, stale evidence and missing evidence
produce no Candidate; a newly blocking Risk decision and an activated kill
switch produce no fill; missing confirmation and a changed confirmation hash
produce no fill. Repeated confirmation through a restarted Agent and duplicate
execution/fill/close converge on one command, fill, authorization and Journal
record. Cross-tenant Candidate/receipt/learning/Agent reads and confirmation fail;
other-tenant Analytics and Attention expose no outcome.

Deployment settings throughout the fixture are permanent paper:
`ENABLE_REAL_TRADING=false`, `EXECUTION_MODE=paper`,
`EXCHANGE_MODE=paper_internal`, `TELEGRAM_NETWORK_PERMITTED=false`, with Telegram
activation/delivery and deployment Watcher flags off. Only the local, isolated
Watcher builder is explicitly enabled for one fixture scan.

Informational notification projection uses a persistent PostgreSQL protocol
store and `FakeTelegramTransport`. Its local projection adapter is enabled to
create a durable pending outbox; delivery is never invoked. Both fake transport
attempts and delivered messages remain empty. No Telegram API request, real
exchange order, withdrawal or transfer path is used. Nothing is deployed.

## Verification

All 3,788 collected backend cases are verified passing with zero skips. The
complete suite ran in three isolated PostgreSQL batches (1,194 / 1,219 / 1,375
cases). Initial batches passed 3,755 cases; 31 cases needed the explicitly
registered shared Agent fixture, one migration case required the disposable
`alphatrade_test` database name, and one redaction assertion needed a clean
process before migration logging disabled its library logger. A 47-case focused
rerun passed all of these plus 14 repeated cases. No backend case is omitted.

The 12 new acceptance cases and four controlled rehearsal cases pass. Frontend
verification passes 1,316 cases in 218 files, lint and TypeScript. The production
build passes with Next's `NEXT_FONT_GOOGLE_MOCKED_RESPONSES` hook because this
workspace cannot fetch Google Fonts; production font source is unchanged.
Agent/RAG/guardrail evaluations pass 16/16, 5/5 and 7/7. Ruff and formatting
pass, as does mypy for all five changed production modules. Nine local
deployment safety checks pass; Telegram preflight remains NOT_ARMED with safe
defaults. No deployment is performed.

[`evidence/full_paper_closed_loop_verification_001.json`](evidence/full_paper_closed_loop_verification_001.json)
records coverage, requested-suite counts, harness retries, frontend/evaluation
results and deployment checks.
