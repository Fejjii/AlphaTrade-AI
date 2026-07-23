# AT-010 — Risk register

**Date:** 2026-07-21 · **Commit:** `e123100` · **Staging SHA:** `5f2d7cf`  
**Context:** Paper-first MVP. No live trading enabled. Risks below inform hardening and the future Mode D program (design only).

Legend — Likelihood / Impact: L / M / H. Status: Open / Mitigated / Accepted / Deferred.

| ID | Title | Severity | Likelihood | Impact | Status | Owner slice | Residual notes |
|----|-------|----------|------------|--------|--------|-------------|----------------|
| RR-01 | Unauthenticated `/tools` (+ execute) | Critical | H | H | Open | AT-011 | Confirmed on staging 200 |
| RR-02 | Paper place without fresh/missing risk | Critical | M | H | Open | AT-012 | Missing `risk_result` allowed for paper_internal |
| RR-03 | Mock embeddings → live Qdrant | Critical | M | H | Open | AT-013 | Silent index pollution |
| RR-04 | Qdrant/Postgres ingest split-brain | Critical | M | H | Open | AT-013 | In-memory fallback + DB commit |
| RR-05 | Unauth `/risk/*` + strategy evaluate | High | H | M | Open | AT-011 | Abuse/compute cost |
| RR-06 | Proposal size/price/SL enforcement gap | High | M | H | Open | AT-012 | Dual-lane paper semantics |
| RR-07 | Kill switch cosmetic / unwired | High | H | H | Open | AT-014 | UI local; agent hardcodes false |
| RR-08 | Stale/degraded market data soft-only | High | H | H | Open | AT-007 | AT-007 backlog |
| RR-09 | `PROVIDER_MODE` ignored for OpenAI | High | M | M | Open | AT-015 | Unexpected live calls |
| RR-10 | Audit nested commit + no metrics | High | M | M | Open | AT-016 | Incident blindness |
| RR-11 | SPA auth / sessionStorage access JWT | High | M | H | Open | AT-017 | XSS amplifies |
| RR-12 | XFF trust + memory rate-limit fallback | High | M | H | Open | AT-018 | Multi-replica bypass |
| RR-13 | CI mypy/supply-chain + backup UNKNOWN | High | M | H | Partial | AT-001/004/019 | AT-019: local restore drill + RPO/RTO docs done; managed/staging drill + AT-001/004 still open |
| RR-14 | Narrative quota / RAG opacity | High | M | M | Open | AT-015 | Cost + silent degrade |
| RR-15 | Always-on OpenAPI `/docs` | Medium | H | M | Open | AT-011 | Surface disclosure |
| RR-16 | Idempotency race → 500 | Medium | L | M | Open | AT-012 | Unique key exists |
| RR-17 | Zero-stop size fail-open `0.001` | Medium | L | M | Open | AT-012 | Validation bot |
| RR-18 | Missing CSP / security headers | Medium | M | M | Open | AT-017 | Frontend/API |
| RR-19 | Thin default browser E2E | Medium | M | M | Open | AT-008 | Opt-in staging specs |
| RR-20 | Sync I/O in async routes | Medium | M | M | Deferred | scale program | MVP acceptable |
| RR-21 | Demo exchange account mutation | Info | H | L | Accepted | Mode C | Intended for paper_exchange_demo |
| RR-22 | No live order implementation | Info | — | — | Mitigated | safety invariants | Fail-closed in staging/prod |
| RR-23 | Staging cold start ~30s | Info | H | L | Accepted | ops | Free-tier spin-up |

## Top residual risk after paper hardening (projected)

Even after AT-011…AT-018, residual risks for any future capital program remain:

1. Exchange adapter bugs and partial-fill races (Phase 1–2 of live roadmap).
2. Credential compromise (Phase 0–1 credential isolation).
3. Human approval fatigue / rubber-stamping (Phase 2 workflow design).
4. Data-quality regime shifts (AT-007 permanent ownership).

## Risk acceptance policy (current)

| Mode | Capital | Acceptance |
|------|---------|------------|
| A — none / internal paper | $0 | Current product mode |
| B — read-only exchange | $0 | Allowed with freshness + least privilege |
| C — paper/demo | $0 demo | Current staging (`paper_exchange_demo`) |
| D — real execution | Real capital | **Rejected** until separate authorized program completes Phases 0–4 gates |

No risk in this register authorizes enabling `ENABLE_REAL_TRADING` or changing `EXECUTION_MODE`.
