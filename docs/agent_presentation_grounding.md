# Agent presentation and canonical strategy grounding

Long stored facts previously consumed almost the entire 4,000-character reply,
leaving only a fragment of model explanation. Conversational turns now reserve
up to 2,000 characters for prose, retain deterministic stale/unavailable notices,
and append a bounded evidence excerpt. The full bounded factual context is
persisted as `interactive_agent.recorded_evidence` in the assistant transcript
payload and returned as optional `recorded_evidence` on the turn response.

The Agent UI renders the explanation and notices first. Native `details` and
`summary` elements hold the stored evidence, closed by default and accessible
by keyboard. Existing assistant transcripts using the recorded-facts delimiter
remain readable. User and system messages preserve their original text. The
post-turn history-error fallback retains the full evidence too. Proposal cards
and their confirm/reject actions remain separate from generated prose.

Strategy library hits expose `lifecycle_status` and `selected_version_id` in
addition to the unchanged `validation_status`. Approval comes from the latest
canonical lifecycle event for the selected immutable version. A prior version's
approval, a historical approval before a pause, and research validation do not
approve the current version. Strategy Brain includes stored entry, invalidation,
stop and target rules, structured rules and authored parameters, scoped to the
requested symbol/timeframe/family. Conversational definition reads also respect
the caller's library ownership; organization-shared setup observations retain
their existing organization boundary.

Both-family comparisons allocate separate context to Nested and SFP. Retrieval
interleaves families, and definition/setup records have explicit bounded excerpts.
At most eight selected definitions are rendered per Brain read; omitted details
are labeled. The total model factual context is bounded to 16,000 characters.
The prompt asks for a conclusion, material blockers and one next action. It keeps
research validation, lifecycle approval, setup confirmation and execution
eligibility distinct. SFP retains its governed execution-plan restriction.

The recorded execution reader also recognizes governed BloFin demo plans. It
reads scoped command, receipt, actual `blofin_demo` fill facts, Journal linkage
and stored protection reconciliation. It does not require or fabricate a manual
Agent confirmation transcript. An authorization without fill evidence remains
unfilled; protection observations are labeled as recorded reconciliation facts.
This reader performs no venue calls or order/risk mutations. Automatic exit and
closed-outcome support remains the execution integration's separate limitation.

## Focused verification

From `backend`, using local mock/disarmed process settings:

```sh
uv run pytest tests/test_agent_presentation_grounding.py \
  tests/test_interactive_agent_foundation.py tests/test_brain_current_scope.py \
  tests/test_strategy_brain_nested.py tests/test_sfp_strategy_brain_runtime.py
```

From `frontend`:

```sh
npm run test -- src/components/agent/AgentWorkspace.test.tsx
npm run lint
npm run typecheck
```

These checks use stored/synthetic evidence. They do not prove current prices,
venue orders, fills, strategy performance or live staging acceptance.

## Supervised staging acceptance and rollback

1. After PR review and CI, deploy the reviewed backend and frontend revisions
   through the existing operator deployment process. This change needs no new
   environment variables or database migration. Keep real trading disabled.
2. Ask: `Compare my approved Nested and SFP strategies on BTCUSDT. What evidence
   is missing before execution?` Verify that the explanation is useful and
   concise and that both selected families and directions appear in evidence.
3. Expand **Stored evidence** using keyboard and touch. Match version IDs and
   lifecycle events to the library/Brain records. A `draft` research-validation
   label must coexist with `approved` lifecycle when those are the actual states.
4. Verify that unavailable/stale market or setup evidence is explicit. No stored
   observation may be presented as a current market price. Approval alone must
   not imply a confirmed Candidate, risk approval or execution eligibility.
5. Reopen an old assistant conversation and a user message containing the
   recorded-facts delimiter. Only assistant evidence should collapse. Submit a
   draft proposal and verify that its explicit controls remain separate.
6. Verify the same read from another organization and another library owner;
   selected strategy definitions must respect those scopes.

Rollback: redeploy the prior backend/frontend revisions through the operator
process. The new response field is optional and old transcript text remains
compatible. No strategy approval or execution state is changed by this work.
