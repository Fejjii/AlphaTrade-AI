# AlphaTrade AI — LinkedIn Posts

Three lengths plus GitHub summary. Adjust links to your profile as needed.

---

## 1. Short LinkedIn post

I shipped **AlphaTrade AI** — a human-in-the-loop AI trading copilot for crypto.

Structured analysis, deterministic risk rules, explicit approvals, and **paper-only** execution (no live trading in this release).

Stack: FastAPI · LangGraph · PostgreSQL · Redis · Qdrant · Next.js

Repo and demo docs on GitHub. Open to feedback from engineers building safe AI products.

---

## 2. Medium LinkedIn post

Over the past months I built **AlphaTrade AI**, a portfolio-grade MVP that answers a specific question: *how do you use LLMs in trading without letting them make irreversible decisions?*

The answer in this project is layered authority:

→ LangGraph orchestrates guardrails, RAG, and tools  
→ Strategies and a **15-rule risk engine** run in deterministic Python  
→ Humans **approve or reject** before any **paper** simulation  
→ An optional LLM only polishes the explanation—it cannot change risk or approval state  

I also implemented multi-tenant auth (JWT, RBAC), audit logs, usage quotas, provider fallbacks (mock/OpenAI/Binance public read-only), journal→RAG learning, Docker + CI, and an evaluation harness.

**Intentionally not in scope:** live exchange orders, auto-trading, or live Stripe billing by default.

If you’re hiring for AI platform or copilot work, the repo includes architecture docs and a 15-minute demo script. Link in comments or featured section.

---

## 3. Technical LinkedIn post

**AlphaTrade AI** — technical snapshot for engineers:

**Agent:** LangGraph pipeline — auth/quota → guardrails → RAG (`rag_retriever` tool only) → read-only market data → 7 deterministic strategy setups → risk engine → approval decision → structured `TradingAnalysisDetail` → optional narrative validation.

**Risk:** 15 pure functions; `BLOCK` overrides paper execution.

**RAG:** Qdrant collection `alphatrade_knowledge`; mock 384-d embeddings for CI; journal auto-ingest as `trade_journal` (lessons, not signals).

**Execution:** `POST /execution/paper` gated on approval + risk + `ENABLE_REAL_TRADING=false`.

**Ops:** structlog + `X-Request-ID`, audit API, `/providers/status`, GitHub Actions (ruff, pytest, eval scripts, Playwright API smoke).

**Deploy:** Docker Compose locally; Vercel + Render + Qdrant Cloud documented.

Real trading remains disabled—this is a **safety-first copilot**, not a bot.

GitHub: [Fejjii/AlphaTrade-AI](https://github.com/Fejjii/AlphaTrade-AI)

---

## 4. GitHub project summary

> **AlphaTrade AI** — Human-in-the-loop AI trading copilot for crypto markets. LangGraph agent with guardrails, RAG (playbooks + journal lessons), deterministic strategies, 15-rule risk engine, explicit approvals, and paper-only execution. FastAPI · PostgreSQL · Redis · Qdrant · Next.js 15. Multi-tenant JWT/RBAC, audit logs, usage quotas, provider fallbacks, evaluation harness. Real trading and live billing disabled by default. [Demo script](demo_script.md) · [Architecture](architecture.md)

---

## 5. Suggested hashtags

Use sparingly (3–6 per post):

`#AIEngineering` `#LangGraph` `#FastAPI` `#RAG` `#LLM` `#FinTech` `#Python` `#NextJS` `#SoftwareArchitecture` `#ResponsibleAI` `#PortfolioProject` `#MachineLearning`

Avoid hype tags (#GetRich, #PassiveIncome) — they undermine the safety positioning.

---

## Related

- [cv_project_entry.md](cv_project_entry.md)
- [interview_pitch.md](interview_pitch.md)
