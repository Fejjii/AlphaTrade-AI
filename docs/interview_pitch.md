# AlphaTrade AI — Interview Pitch

Timed pitches, demo script, and anticipated Q&A. Tone: professional and factual.

---

## 1. Thirty second pitch

“I built AlphaTrade AI, a human-in-the-loop trading copilot for crypto. It uses LangGraph to orchestrate guardrails, retrieval, deterministic strategies, and a fifteen-rule risk engine—then requires explicit human approval before any paper simulation. Real trading stays off by default. The stack is FastAPI, PostgreSQL, Redis, Qdrant, and Next.js, with full audit and quota metering. It’s designed to show safe AI product engineering, not autonomous trading.”

---

## 2. Sixty second pitch

“AlphaTrade AI helps traders move from chaotic LLM chats to a governed workflow. You analyze markets with read-only data, get structured trade proposals with mandatory stops and risk scores, and only after you approve does the system create a paper position—never a live exchange order in this release.

Under the hood, LangGraph runs a pipeline: auth and quotas, guardrails, RAG for playbooks and journal lessons, Python strategy signals, then a deterministic risk engine that can block execution even if someone clicks approve by mistake. An optional LLM layer only polishes the explanation; it cannot change risk or approval state.

I implemented multi-tenant auth, RBAC, audit logs, usage quotas, provider fallbacks, Docker and cloud deployment docs, and an evaluation harness for regression. It’s a portfolio-grade MVP that prioritizes safety and explainability over hype.”

---

## 3. Two minute technical pitch

“AlphaTrade AI is a modular FastAPI backend with a Next.js PWA front end. The core insight is **separation of authority**: the LangGraph agent orchestrates work, but decisions come from deterministic code—the strategy modules, the risk engine with fifteen pure rules, and the approval service.

The graph nodes are explicit: guardrails first, then RAG retrieval scoped by organization and source type—playbooks and journal lessons, not signals. Market data goes through a provider abstraction—Binance public REST read-only or mock—with provenance on every response. Strategies emit structured setups; the risk engine returns ALLOW, WARN, or BLOCK; BLOCK is final.

When a user wants to act, we persist a proposal and often an approval record. Paper execution is a separate API path that checks kill switches, approval status, risk verdict, and idempotency. Optional OpenAI narrative runs after the structured response is built; validators ensure the LLM cannot claim live execution or override risk.

Persistence is PostgreSQL for workflows and auth; Redis for rate limits and JWT denylist; Qdrant optional for vectors with in-memory fallback. Providers are mock-first with transparent status at `/providers/status`. Observability includes structlog, request IDs, audit events, and usage metering with cost-source labeling.

I shipped this in vertical slices with CI, pytest, Playwright API smoke, and offline evaluation scripts for RAG, guardrails, and agent quality. Real trading and live billing are intentionally disabled—documented kill switches and startup validation enforce that in staging.”

---

## 4. Demo walkthrough script

**Duration:** 15–20 minutes. **Prereq:** Docker Compose up; confirm paper banner and `ENABLE_REAL_TRADING=false`.

| Step | Route / action | Talking point |
|------|----------------|---------------|
| 1 | Open `/` | Paper mode banner; provider status (exchange = mock/paper) |
| 2 | `/market` | BTCUSDT ticker; show `is_live` / `fallback_used` |
| 3 | `/workspace` | “Analyze BTC pullback on 4h”; show deterministic vs narrative panels |
| 4 | `/proposals` | Open proposal; risk rules and exit levels |
| 5 | `/approvals` | Approve for paper (or reject path) |
| 6 | Proposal detail | Create paper order; stress “simulated only” |
| 7 | `/positions` | Paper position and P&amp;L |
| 8 | `/journal` | Lesson entry; mention sanitization before RAG |
| 9 | `/knowledge` | Search journal text; `trade_journal` source |
| 10 | `/usage` | Quotas and `cost_source` labels |
| 11 | `/audit` | Event chain: proposal → approval → paper order |

Full script: [demo_script.md](demo_script.md)

---

## 5. Architecture explanation (spoken)

“Think of three rings. The **outer ring** is the Next.js client—auth, RBAC-aware UI, and workflow screens. The **middle ring** is FastAPI: REST boundaries, tenant context, and services that own business rules. The **inner ring** is the LangGraph agent plus tools, but tools only call services—never the exchange for orders.

Data stores split by concern: Postgres for truth, Redis for ephemeral security and rate limits, Qdrant for semantic search when enabled. Providers sit behind interfaces so CI runs fully offline with mocks, while a demo can flip to OpenAI and Binance public data without changing application code.”

---

## 6. AI engineering explanation (spoken)

“I treat the LLM as an **optional presenter**, not a trader. Retrieval augments context from approved knowledge types. Guardrails run on input and on narrative output. The structured response is assembled deterministically from agent state; evaluation scripts assert no guaranteed-profit language and no false live-data claims.

That pattern—orchestration + retrieval + validators + deterministic authority—is what I’d reuse in other high-stakes copilots.”

---

## 7. Safety explanation (spoken)

“Safety is layered defaults, not a disclaimer. Execution mode is paper; real trading is a separate flag that stays false and is validated at startup in non-local environments. Risk BLOCK wins over UI clicks. Approvals are mandatory on the paths we defined. Audit events capture the chain. Provider status tells you if you’re on mock market data. I can demo the reject path in under a minute to show execution doesn’t happen without approval.”

---

## 8. Business value explanation (spoken)

“For a product org, this reduces reckless AI-assisted trading by forcing structure and human gates. For ops, audit and usage metering support cost control and incident review. For GTM, paper mode allows demos without regulatory exposure of live execution. The billing scaffold shows how plans map to quotas without turning on charges prematurely.”

---

## 9. What I would improve next

1. **Production Stripe (27B)** — real Checkout, Portal, entitlements tied to quotas.  
2. **LangSmith + OTel** — trace each graph node and narrative validation failures.  
3. **Scaled eval** — LLM-as-judge on a golden set in CI with thresholds.  
4. **Embedding dimension strategy** — single embedding model in prod with migration playbook.  
5. **Invite signup flow** — complete org invitation → new user onboarding.  
6. **Exchange adapter** — only after legal/compliance review; still approval-gated.

---

## 10. Expected interview questions and strong answers

**Q: Is this a trading bot?**  
A: No. It’s a copilot. Strategies and risk are deterministic; humans approve; only paper simulation runs.

**Q: Can the LLM place trades?**  
A: No. The graph doesn’t call exchange execution. Paper orders go through a separate service after approval, with kill switches and risk checks.

**Q: Why not use the LLM for risk?**  
A: LLMs are inconsistent and hard to audit. Rules are testable, versionable, and give the same input→output in CI.

**Q: What happens if OpenAI is down?**  
A: Mock LLM and embeddings; narrative falls back to deterministic text; usage records `fallback_used`.

**Q: How do you prevent prompt injection?**  
A: Guardrail stage, trading policy checks, sanitized narrative context, and output validation before persisting.

**Q: How is multi-tenancy enforced?**  
A: JWT carries `org_id`; services scope queries; cross-org access returns forbidden.

**Q: What’s the hardest part you solved?**  
A: Keeping a single source of truth for trade decisions while still showing useful LLM explanations—split UI panels and validators enforce that.

**Q: What would break in production?**  
A: Redis/Qdrant availability without fallbacks configured, JWT secret rotation discipline, Binance rate limits, and conflating cost estimates with billing—documented gaps.

More Q&A: [technical_qa.md](technical_qa.md)
