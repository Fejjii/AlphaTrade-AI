# Agent Strategy Analytics 001 — handoff

Branch: `codex/agent_strategy_analytics_001`.
Exact parent: `9f6e2edd16b43dfc5a6585462ba77919a0c5a6fc`.
The draft PR stacks on `codex/strategy_analytics_api_v2` ([PR 165](https://github.com/Fejjii/AlphaTrade-AI/pull/165)).

## Result

The existing Brain Agent (`POST /agent/turns`) routes historical strategy questions
through `StrategyAnalyticsService.compute`, the same authority used by
`GET /strategy-analytics/report`. No analytics formulas, attribution rules,
thresholds, migrations, execution paths, strategy mutations, or Telegram code
are added or changed.

Supported prompts include:

- How did Nested perform? How did N2 perform?
- Compare N2 versus N3.
- How did BTC setups perform?
- What is expectancy for this strategy version?
- What are average R and median R? What is profit factor?
- How many samples exist? What are MAE and MFE?
- Which results have insufficient evidence?

Setup-state questions such as “Which Nested setups are forming?” still read
Strategy Brain setup state. Strategy-performance turns use the new
`strategy_analytics` capability with `operation=read` and no proposals.

The response's additive `strategy_analytics` field contains the complete returned
canonical reports. Each preserves filters, strategy/version/stage bucket
identities (including unassigned identities), samples for every metric,
confidence, missing and invalid fields, all warning messages, source bases,
contract version, timestamps, pagination/scan metadata, and limitations.
Two-stage comparisons return two independently filtered canonical reports,
including an empty report when one side has no history.

Visible replies are deterministic, show metric denominators, and explicitly
label unavailable metrics and insufficient evidence. Overall figures pool all
matching versions/stages; exact version filters select a single version.
Long replies and bucket summaries may be abbreviated; complete returned reports
remain in the response and assistant transcript payload. Canonical reports retain
the service's default 50-bucket page and configured journal row cap.
No model prose is used for analytics turns, so a narrative model cannot turn a
small sample into a profitability claim. MAE/MFE remain recorded monetary amounts.

## Selection and authorization

Organization and user come exclusively from the existing authenticated Agent
route. Its owner/trader role requirement is unchanged; viewer access to the
separate canonical GET API does not grant access to Agent turns. Strategy and
version lookup always checks both organization and user ownership. Foreign
identities never fall back to another strategy or pooled history.

A strategy-bound conversation or explicit `strategy_id` selects a strategy.
A unique owned Nested strategy can also be resolved for Nested/stage questions.
Exact strategy names are supported by “How did NAME perform?”; unavailable,
duplicate, or conflicting names require clarification. Version numbers require a
strategy identity. “This/current/latest strategy version” requires an exact
version ID or strategy ID with a version number; the Agent does not guess a version.
BTC, ETH and SOL shorthand use their USDT symbols. Explicit canonical symbols and
timeframes are supported. Only two maturity stages can be compared per request.

Optional `analytics_filters` accepts the existing `StrategyAnalyticsFilters`
contract for exact version, source, market regime, symbol/timeframe and inclusive
timezone-aware dates. Textual date/source/regime constraints that cannot be
resolved require these explicit filters. Conflicting filters require clarification;
structured analytics filters on a proposal/refusal turn are rejected.

```json
{
  "message": "What is expectancy for this strategy version?",
  "analytics_filters": {
    "strategy_version_id": "<owned-version-uuid>",
    "symbol": "BTCUSDT",
    "source": "paper_execution",
    "date_from": "2026-09-01T00:00:00Z",
    "date_to": "2026-09-30T23:59:59Z"
  }
}
```

The analytics adapter performs only SELECTs under `session.no_autoflush` and
calls no snapshot builder. Existing conversation persistence appends the user
and assistant turns. No journal, strategy/version, setup/event, proposal, or order
records are written by analytics. A service failure is unavailable, not an empty
history or a zero-valued result.

## Validation

`tests/test_agent_strategy_analytics.py`: 25 focused tests cover read routing,
canonical API equivalence, comparison, version selection, empty/missing values,
coverage/truncation, scope/identity spoofing, authentication, existing roles,
foreign conversation/strategy denial, SELECT-only/no-autoflush reads, and no
model or legacy performance calls.

Validation: the related Agent, Brain and canonical analytics suite passed
148 tests with 3 optional PostgreSQL tests skipped. Backend-wide Ruff lint and
format checks passed. Focused mypy checks passed for all six modified source files.

Run from `backend`:

```sh
uv run pytest tests/test_agent_strategy_analytics.py tests/test_interactive_agent_foundation.py tests/test_strategy_brain_nested.py tests/test_strategy_analytics_foundation.py tests/test_strategy_analytics_api_v2.py
uv run ruff check .
uv run ruff format --check .
```

The existing optional PostgreSQL proposal concurrency tests require their
configured test database and are skipped when it is absent. No migration or
PostgreSQL integration behavior is changed by this slice.

Review and merge through the existing stacked dependency chain. No deployment,
activation, execution, or follow-on work is part of this handoff.
