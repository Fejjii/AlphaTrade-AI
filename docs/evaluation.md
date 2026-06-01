# Evaluation

AlphaTrade includes lightweight evaluation hooks for RAG and agent response quality.

## RAG evaluation

Script: `evaluation/evaluate_rag.py`

Dataset: `evaluation/datasets/rag_cases.json`

Run locally:

```bash
cd backend
uv run python ../evaluation/evaluate_rag.py
```

Cases assert expected source types (playbook, `trade_journal`, risk policy) and retrieval relevance.

## Agent narrative evaluation (Slice 21)

Script: `evaluation/evaluate_agent.py`

Datasets:

- `evaluation/datasets/agent_cases.json` — end-to-end `/chat/message` quality (mock LLM)
- `evaluation/datasets/guardrail_cases.json` — narrative language policy unit cases

Run:

```bash
cd backend
uv run python ../evaluation/evaluate_agent.py
```

Cases verify:

- No guaranteed profit or all-in language in replies
- Risk context, approval status, invalidation (for proposals), mock data disclosure
- No real execution claims
- Invalid or unsafe LLM output falls back to deterministic narrative

## Guardrail evaluation (Slice 22)

Script: `evaluation/evaluate_guardrails.py`

Dataset: `evaluation/datasets/guardrail_cases.json`

Run:

```bash
cd backend
uv run python ../evaluation/evaluate_guardrails.py
```

Cases cover guarantee/all-in language, execution claims, and false market-data quality claims.

## Evaluation summary (copy-paste)

```bash
cd backend
uv run python ../evaluation/evaluate_guardrails.py && \
uv run python ../evaluation/evaluate_rag.py && \
uv run python ../evaluation/evaluate_agent.py
```

All three must report 100% pass for release confidence.

## Journal RAG (Slice 20)

Journal auto-ingest creates searchable `trade_journal` chunks. Verify manually:

1. Create journal entry with unique lesson text
2. Search knowledge base for that text
3. Confirm citation source type `trade_journal`

Backend test: `tests/test_mvp_workflow.py::test_journal_auto_ingest_creates_searchable_content`

## Risk engine evaluation

Covered by `tests/test_risk_engine.py` — rule-level allow/block matrix.

## Workflow evaluation

Covered by:

- `tests/test_workflows.py` — CRUD and paper execution guards
- `tests/test_mvp_workflow.py` — full proposal → approval → paper flow

## Metrics to track (production)

| Metric | Source |
|--------|--------|
| Approval latency | Audit timestamps |
| Paper fill rate | Orders API |
| RAG hit rate | Usage events `rag_search` |
| Narrative fallback rate | Audit `narrative_validation_fallback` |
| Provider fallback rate | Usage `fallback_used` |
| Quota warning / block rate | Audit `quota_warning`, `quota_block` |
| Non-billing cost share | Usage `cost_source != provider_reported` |
| Risk block rate | Proposal `risk_result.action` |

## Usage and quota evaluation (Slice 24)

Backend tests in `tests/test_usage_quota.py` cover provider metadata capture, quota
soft/hard enforcement, audit events, RBAC on quota updates, and tenant isolation.

Run:

```bash
cd backend
uv run pytest tests/test_usage_quota.py -q
```

See [usage_and_billing.md](usage_and_billing.md) for cost source semantics.

## Out of scope for MVP eval

- Live PnL backtesting
- LLM judge scoring at scale
- A/B model comparison infrastructure

See [limitations_roadmap.md](limitations_roadmap.md) for roadmap.
