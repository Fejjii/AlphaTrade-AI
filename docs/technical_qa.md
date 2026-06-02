# AlphaTrade AI — Technical Interview Q&A

Likely questions and concise, accurate answers. Align answers with the codebase—do not claim live trading or production Stripe unless explicitly enabled.

---

## 1. Why FastAPI?

FastAPI gives async-capable HTTP, automatic OpenAPI docs, and first-class Pydantic v2 integration—which matches our schema-heavy API (proposals, risk results, structured agent responses). Python also fits the ML/agent ecosystem (LangGraph, evaluation scripts) in one repo with pytest and Ruff. For a modular monolith with many domain routes, FastAPI keeps handlers thin while services hold business logic.

---

## 2. Why LangGraph?

Trading workflows are **multi-step and conditional** (guardrails may short-circuit, risk may block, approval may be required). LangGraph expresses that as an explicit state machine with testable nodes, rather than one monolithic prompt. It separates orchestration from implementation: nodes call services; persistence and audit sit outside individual prompts. Compared to ad-hoc chains, graphs are easier to extend (e.g. narrative node after structured response) and to document for interviews.

---

## 3. Why a deterministic risk engine?

Risk decisions must be **repeatable, auditable, and unit-testable**. Fifteen pure rule functions take a `RiskCheckRequest` and limits; they return `ALLOW`, `WARN`, or `BLOCK` with stable rule IDs. An LLM cannot reliably enforce leverage caps, stop-loss requirements, or kill switches across sessions. Deterministic risk also lets us assert in CI that `BLOCK` prevents paper execution even if the UI mis-clicks approve.

---

## 4. Why RAG?

Traders need **organizational context**—playbooks, risk policy wording, past journal lessons—not generic LLM knowledge. RAG grounds the agent in tenant-scoped documents with citations. We deliberately exclude RAG content that acts as a trading signal; source types are controlled and retrieval is filtered by metadata. Journal auto-ingest closes the loop from review → future retrieval.

---

## 5. Why Qdrant?

We need **semantic search** over chunked knowledge with metadata filters (org, symbol, source type). Qdrant offers a simple self-hosted or cloud deployment, cosine similarity, and collection management without running a full search cluster. When Qdrant is unreachable, the app falls back to an in-memory vector store so dev and CI keep working—important for portfolio demos and tests.

---

## 6. Why Redis?

Redis handles **low-latency, ephemeral** concerns: API rate limiting and JWT access-token denylist on logout. It’s not the system of record—that’s Postgres. With `RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK`, local dev survives without Redis; staging/production expect Redis for consistent limits across instances. Connection pooling and timeouts apply per Redis best practices.

---

## 7. Why Postgres?

Workflow entities—users, organizations, proposals, approvals, paper orders, positions, journal, audit events, usage events, billing scaffold tables—need **ACID transactions and relational integrity**. SQLAlchemy 2.0 + Alembic migrations give versioned schema evolution. Postgres is widely available on Render, Railway, Neon, etc., matching our deployment guide.

---

## 8. Why human-in-the-loop?

Autonomous crypto trading from LLM output is unsafe and often non-compliant for portfolio scope. Humans must **explicitly approve** simulated actions; the product educates and structures decisions rather than hiding them. Approval states (reject, modify, needs more analysis) are first-class and block execution APIs.

---

## 9. Why no real trading?

Scope, safety, and **interview/portfolio clarity**: demonstrating AI architecture without exchange API keys, withdrawal risk, or regulatory exposure. `ENABLE_REAL_TRADING=false` and `EXECUTION_MODE=paper` are defaults with startup validation in non-local environments. Market data is read-only public REST where enabled. An exchange adapter may exist as scaffolding but live order placement is not the MVP story.

---

## 10. How do guardrails work?

Early in the graph, guardrails check user input for injection patterns, moderation concerns, and trading policy (e.g. disallowed advice). After optional LLM narrative, validators ensure output does not claim guaranteed profits, live execution, or altered risk/approval facts. Failures emit audit events and fall back to deterministic narrative. Offline `evaluate_guardrails.py` regression-tests language policy cases.

---

## 11. How do approval gates work?

The agent’s approval decision node sets whether an approval record is required (e.g. execute intent, low confidence, risk warnings). `ApprovalService` tracks status. `ExecutionService.place_paper_order` requires `approved` status, passing risk (not `BLOCK`), real-trading disabled, and optional idempotency key. Workflow endpoints expose linked proposal + approval + eligibility for the UI.

---

## 12. How do audit logs work?

`AuditService` persists typed events (auth, guardrails, proposals, approvals, paper orders, quota blocks, refresh reuse, etc.) with organization scope and metadata redaction. Clients use `GET /audit/events` with filters. Events correlate with `request_id` from middleware and usage events for incident timelines.

---

## 13. How do provider fallbacks work?

`ProviderRegistry` selects implementations from env: mock LLM/embeddings by default; OpenAI when keyed; Qdrant when URL reachable; Binance public for market data in `fallback|live` provider mode; in-memory substitutes when dependencies are down. Usage events record `fallback_used`. `GET /providers/status` exposes health for demos and deploy smoke tests—never hide mock as live.

---

## 14. How do testing and evaluation work?

**Unit/integration:** pytest in `backend/tests`—risk rules, workflow, guardrails, journal RAG, auth.  
**Frontend:** Vitest + Playwright API workflow in CI.  
**Offline eval:** `evaluation/evaluate_rag.py`, `evaluate_agent.py`, `evaluate_guardrails.py` with JSON datasets asserting retrieval types, narrative policy, and safe language.  
**E2E:** Docker validate scripts + optional browser tour locally.

Evaluation is regression-oriented, not a live LangSmith production loop yet.

---

## 15. What production gaps remain?

| Gap | Notes |
|-----|--------|
| Live Stripe | Scaffold only; `BILLING_ENABLED=false` default |
| Live exchange execution | Disabled; compliance review required before enablement |
| LangSmith / OTel | Placeholder; no distributed trace UI |
| Streaming LLM | HTTP request/response only |
| Invite → signup | API exists; full onboarding flow incomplete |
| Embedding migration | Re-index when switching mock → OpenAI dimensions |
| Cost billing | Only `provider_reported` cost is billing-grade |
| HA / multi-region | Single-region managed hosting documented |

---

## Quick cross-links

- [interview_package.md](interview_package.md)
- [architecture.md](architecture.md)
- [agent_workflow.md](agent_workflow.md)
- [security.md](security.md)
- [evaluation.md](evaluation.md)
