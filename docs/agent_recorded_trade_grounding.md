# Agent recorded trade grounding

## Reproduced failure

Natural questions such as “Explain my latest BTCUSDT short paper trade:
strategy, entry, stop, target, authorization and execution venue” did not
reach the durable execution reader. Only the grammar `Explain paper execution
<command UUID>` selected that reader. Ordinary retrieval used `JournalService`
(the legacy `journals` notes table), whereas canonical execution projects into
`journal_trades`. Its adapter supplied only matching record titles, never
prices, plan authorization, historical eligibility, risk or fill facts.
When no legacy entry matched, `_trade_reply` fell back to Knowledge content.
Thus a stored playbook could dominate model context while the canonical trade
was never read.

The old explicit internal-paper reader also requires a captured Agent execution
response. Scheduled/internal executions need not have that transcript. Its strict
capture refusal remains unchanged; the new recorded-trade read does not depend on
that optional narrative.

## Read behavior

`paper_trade.read_recorded` is a typed, authenticated read action. Tenant and
owner identities come from the request principal, never its arguments. Selectors
are symbol, direction, optional account/Journal UUID, latest and paper-only.
Selection filters the existing Journal by tenant, owner, account ownership,
symbol and direction before limiting. BTCUSDT and BTC-USDT spellings match;
no base/quote or contract substitution is introduced. Latest uses recorded entry
time, falling back to creation time. Multiple matching accounts, an unspecified
trade among multiple matches, or a latest timestamp tie produces a targeted
selection question, without asking the model to choose.

The read loads the exact immutable canonical plan and linked historical
eligibility, owner-scoped strategy version, Candidate, command, authorization,
receipt, risk reservation and first ten immutable fills. It verifies plan
semantic hashes and linked identities. Missing lineage is reported; mismatches
refuse. It does not replace historical eligibility with the latest evaluation or
use today's strategy selection/approval to explain a past execution.

Facts distinguish planned entry zone/reference price, stop and ordered target
allocations from actual fill quantities/prices. Journal evidence includes the first ten
ordered target prices and recorded allocations. Up to 100 targets are compared
against the linked immutable plan after numeric normalization; labels and ordering
are preserved. Matching values are explicitly confirmed as planned values only,
never verified protection or exit fills. Unreadable or over-budget target lists
leave the comparison unverified. Empty Journal targets with plan
targets are identified as a projection discrepancy; no repair occurs. Venue
attribution requires matching recorded fill sources. A planned BloFin venue with
fake/internal fills cannot be described as exchange execution; ALLOW or an
acknowledgment without fills cannot prove execution.

A risk snapshot UUID/reservation is not the detailed RiskEngine narrative. If an
exact, validated Agent execution capture exists, its recorded Risk decision is
cited. Otherwise the detailed narrative is explicitly unavailable while recorded
eligibility, exact authorization and deterministic reservation evidence remain
available. Nothing is recalculated. Long risk narratives and target/fill lists
have explicit context limits, with source records retained and omissions stated.

Knowledge retrieval is skipped for this action. The responder receives a compact
summary, recorded authorization explanation, missing-evidence list and detailed
source-labelled facts. Full constructed evidence and record references persist
in the normal Agent transcript; display prose stays bounded. An unavailable model
falls back to the deterministic summary. This is historical evidence, never
permission to approve a strategy, alter risk or execute another trade.

## Verification and release acceptance

Run the focused recorded-trade, Agent routing/presentation, canonical internal
paper and simulated demo regressions. PostgreSQL tests must target a disposable
`alphatrade_test` database; fixtures recreate its schema. Simulated venue proof
uses MockTransport, not exchange orders. No full backend run is part of this task.

After supervising review, consolidated release CI and deployment, repeat the
original live question in the authenticated owner account. Verify the selected
Journal UUID against that account's latest matching record, actual strategy
version, plan prices/allocations, fill price/venue and authorization references.
If the Journal is unrepaired, verify the Agent identifies the plan target source
and projection discrepancy. For a repaired Journal, verify the bounded Journal
prices and allocations are visible in Stored evidence and the reply explicitly
confirms they match the linked immutable plan. The known historical BTC short
should show TP1 at 84714.10 with 100% allocation. This match must not be described
as verified stop/target protection or an exit fill. If detailed RiskEngine capture is absent, verify it
reports that limit rather than inventing a reason from the playbook. Confirm the
read creates no order, authorization, fill, Journal mutation or strategy change.

Local context and mocked synthesis tests do not establish live model quality.
No merge, deploy, demo activation, strategy approval or exchange order is performed
by the implementation task. The five-market/repeatable-demo expansion is a separate
follow-up branch; documentation PR210 remains untouched.
