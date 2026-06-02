# AlphaTrade AI — CV Project Entry

Copy-paste friendly blocks for resumes, LinkedIn, and portfolio sites.

---

## 1. Recruiter-friendly project title

**AlphaTrade AI — Human-in-the-Loop AI Trading Copilot (Paper MVP)**

---

## 2. One sentence summary

Built a full-stack AI trading copilot with LangGraph orchestration, deterministic risk controls, human approval gates, RAG knowledge retrieval, and paper-only execution—with multi-tenant auth, audit logs, and usage quotas.

---

## 3. CV bullets (pick 4–5)

- Designed and implemented a **LangGraph** agent pipeline (guardrails → RAG → market data → strategies → risk → approval) with **deterministic structured outputs** and optional schema-validated LLM narrative.
- Built a **15-rule risk engine** in pure Python where `BLOCK` is final authority over trade proposals and paper execution.
- Delivered **human-in-the-loop workflow**: proposals, approvals (approve/reject/modify), and idempotent **paper execution** with full audit trail—real trading disabled by default.
- Implemented **RAG** over playbooks, policies, and journal lessons (Qdrant + OpenAI/mock embeddings) with tenant-scoped retrieval and journal auto-ingest loop.
- Shipped **FastAPI + Next.js 15** MVP: JWT/RBAC, Redis rate limits, provider fallbacks, usage metering, Stripe billing scaffold, Docker/CI, and offline evaluation harness.

---

## 4. Tech stack line

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic · LangGraph · PostgreSQL · Redis · Qdrant · OpenAI (optional) · Next.js 15 · TypeScript · Tailwind · Vitest · Playwright · Docker · GitHub Actions

---

## 5. Compact version (selected projects section)

**AlphaTrade AI** — AI trading copilot with LangGraph, deterministic risk engine, human approvals, RAG, and paper-only execution. FastAPI, Postgres, Redis, Qdrant, Next.js. GitHub: [Fejjii/AlphaTrade-AI](https://github.com/Fejjii/AlphaTrade-AI)

---

## 6. Stronger version (portfolio / LinkedIn featured)

### AlphaTrade AI — Human-in-the-Loop Trading Copilot

Crypto trading teams and solo traders need more than chatGPT-style advice—they need **governed decisions**. AlphaTrade AI combines read-only market data, deterministic strategy signals, a fifteen-rule risk engine, and explicit human approval before any simulated trade.

**Highlights**

- LangGraph orchestration with guardrails and provider abstractions (mock-first, OpenAI/Binance/Qdrant optional)
- RAG knowledge base (playbooks + journal lessons) with citations in the workspace
- Multi-tenant SaaS foundations: JWT auth, RBAC, audit API, organization quotas, billing scaffold
- Production-minded docs: deployment guide, security checklist, evaluation harness, 15-minute demo script
- **Safety:** `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`—no live exchange orders in this release

**Links:** Repository · [Architecture](architecture.md) · [Demo script](demo_script.md)

---

## 7. Keywords by role

### AI Engineer

LangGraph · LLM orchestration · RAG · embeddings · vector search (Qdrant) · guardrails · prompt validation · evaluation harness · structured outputs · Pydantic · agent tools

### AI Consultant

Human-in-the-loop · copilot design · risk governance · audit trail · provider fallback strategy · mock-first delivery · stakeholder demo script · safe defaults

### AI Product

Trade proposal workflow · approval UX · paper trading MVP · usage quotas · billing scaffold · roadmap / limitations documentation · PWA · RBAC personas (OWNER/TRADER/VIEWER)

### AI Platform

FastAPI · multi-tenancy · PostgreSQL · Redis · JWT refresh rotation · rate limiting · observability (structlog, request IDs) · CI/CD · Docker Compose · cloud deployment (Vercel/Render)

---

## Related docs

- [interview_package.md](interview_package.md)
- [interview_pitch.md](interview_pitch.md)
- [technical_qa.md](technical_qa.md)
