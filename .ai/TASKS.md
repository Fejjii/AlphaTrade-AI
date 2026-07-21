# AlphaTrade AI — Tasks

Persistent backlog. IDs: `AT-XXX`. Fields: Priority, Status, Dependencies, Risk,
Validation, Recommended model. Gap-analysis items (Phase 7) are **not implemented** here.

Legend — Priority: P0 (critical) … P3 (low). Status: TODO / IN_PROGRESS / DONE / BLOCKED.

---

## AT-000 — Bootstrap + install Master Workflow v2.0
- Priority: P1 · Status: DONE · Dependencies: none · Risk: Low
- Validation: `.ai/MASTER_WORKFLOW.md` tracked and authoritative; five-status model; normalized
  self-hash; `.gitignore` ignores handoffs + `.ai/local/` + `.ai/private/`; sync validated.
  Committed `057ef11`, CI run 29669825825 success.
- Recommended model: Opus 4.8

---

## AT-009 — Staging OpenAI + Qdrant provider activation (paper-only)
- Priority: P0 · Status: DONE · Dependencies: none · Risk: Medium (ops + provider config)
- Validation: Staging OpenAI + Qdrant active (paper-only). Commit `5f2d7cf` deployed;
  `/knowledge/search` returns semantic chunks; `provider-validation --remote --ingest` OK;
  verify-safety / portfolio / exchange-demo smokes OK. Providers: `gpt-5.6-sol`,
  `text-embedding-3-large` 1536-d, Qdrant healthy; `execution_mode=paper`,
  `real_trading=false`, `EXCHANGE_MODE=paper_exchange_demo`.
- Recommended model: Opus 4.8

---

## AT-010 — Readiness audit + real-money safety architecture roadmap (design only)
- Priority: P0 · Status: DONE · Dependencies: AT-009 · Risk: Low (docs/audit only)
- Goal: Full current-version readiness audit (repo + staging read-only) and Mode D
  safety architecture roadmap without implementing or enabling live trading.
- Validation: Deliverables present — `docs/AT010_readiness_audit.md`,
  `docs/AT010_risk_register.md`, `docs/AT010_real_money_safety_roadmap.md`;
  staging `verify-safety.sh` pass; local ruff pass; local pytest exit 0;
  paper posture unchanged (`execution_mode=paper`, `real_trading=false`,
  `EXCHANGE_MODE=paper_exchange_demo`). No live-trading code.
- Recommended model: Grok 4.5
- Completion evidence: Session AT-SESSION-20260721-001203; commit baseline `e123100`;
  staging API `git_sha=5f2d7cf`.

---

## Paper hardening (from AT-010) — implement before any sandbox/live program

### AT-011 — Authz for compute surfaces (`/tools`, `/risk/*`, strategy evaluate) + gate `/docs`
- Priority: P0 · Status: DONE · Dependencies: AT-010 · Risk: Medium
- Safety classification: Security / paper-safe
- Goal: Require auth on `/tools` (incl. execute), `/risk/*`, strategy evaluate; gate
  OpenAPI `/docs` outside local; keep paper-only.
- Branch: `feat/at-011-authz-tools-risk`
- Validation: Merged PR #1 (`3217c18`). CI run 29794325773 success. Unauth → 401;
  VIEWER → 403 on trader compute; trader/owner → 200; docs gated outside local;
  `/tools/execute` binds JWT tenant. Paper defaults unchanged.
- Recommended model: Composer 2.5 (impl) · Grok 4.5 (review)
- Completion evidence: commit `6908124`, merge `3217c18`, PR https://github.com/Fejjii/AlphaTrade-AI/pull/1

### AT-012 — Fresh risk + eligibility at paper execution; bind size/price; fail-closed zero stop
- Priority: P0 · Status: DONE · Dependencies: AT-011 · Risk: Medium (safety-critical)
- Safety classification: Trading safety / paper-only
- Goal: Re-evaluate RiskEngine at `place_paper_order` with DailyRiskState + settings +
  kill switch; refuse missing risk_result; call eligibility; bind order size/price to
  proposal (or re-risk); BLOCK on zero stop distance (no `0.001` fail-open).
- Branch: `feat/at-012-paper-risk-at-execution`
- Validation: Merged PR #2 (`992e954`). CI run 29799284663 success on `ffa975e`.
  Fresh risk at place_paper_order; DailyRiskState portfolio sync; proposal binding;
  sequential exposure/daily-loss regression tests; paper-only unchanged.
- Recommended model: Grok 4.5
- Completion evidence: commit `7ebe3b0`, merge `992e954`, PR https://github.com/Fejjii/AlphaTrade-AI/pull/2

### AT-013 — RAG fail-closed (no mock embeddings into Qdrant; no split-brain ingest)
- Priority: P0 · Status: TODO · Dependencies: AT-010 · Risk: Medium (data integrity)
- Safety classification: Provider / knowledge
- Goal: Fail ingest when embeddings `fallback_used` or Qdrant degraded; never upsert mock
  vectors to remote; avoid Postgres-success / Qdrant-miss silent success; delete orphans.
- Branch: `feat/at-013-rag-fail-closed`
- Validation: Forced provider failures → ingest errors; search exposes degraded flags.
- Recommended model: Grok 4.5

### AT-014 — Server-side kill switch (persist + enforce + UI wire-up)
- Priority: P0 · Status: DONE · Dependencies: AT-012 · Risk: Medium (safety-critical)
- Safety classification: Trading safety
- Goal: Persist org kill switch; enforce in RiskEngine + execution; replace cosmetic
  frontend toggle with API-backed control.
- Branch: `feat/at-014-persistent-kill-switch` (merged via PR #3)
- Validation: Toggle → paper place refused; UI reflects server; agent cannot hardcode false.
- Recommended model: Grok 4.5

### AT-015 — Honor PROVIDER_MODE for LLM/embeddings + wire narrative quota + search opacity
- Priority: P1 · Status: TODO · Dependencies: AT-013 · Risk: Low
- Branch: `feat/at-015-provider-mode-quotas`
- Validation: `PROVIDER_MODE=mock` with key set → mock only; narrative quota enforced;
  search returns fallback/degraded flags.
- Recommended model: Composer 2.5

### AT-016 — Audit unit-of-work + baseline metrics
- Priority: P1 · Status: TODO · Dependencies: AT-010 · Risk: Low
- Branch: `feat/at-016-audit-uow-metrics`
- Validation: No mid-request audit commit splitting business txn; RED metrics scrapeable.
- Recommended model: GPT-5.4 / Sonnet 4.6

### AT-017 — Frontend auth boundary + security headers
- Priority: P1 · Status: TODO · Dependencies: AT-011 · Risk: Medium
- Branch: `feat/at-017-frontend-auth-headers`
- Validation: Unauth app routes redirect via middleware; CSP/headers present; paper banners
  follow `/health` truth (no hardcoded “paper active” when real would be on).
- Recommended model: Sonnet 4.6

### AT-018 — Proxy trust + Redis-required rate limits in staging/prod
- Priority: P1 · Status: TODO · Dependencies: AT-010 · Risk: Medium
- Branch: `feat/at-018-rate-limit-proxy-trust`
- Validation: Spoofed XFF ignored; memory fallback false outside local; denylist fail-closed.
- Recommended model: GPT-5.4

### AT-019 — Backup/restore runbook + restore drill evidence
- Priority: P1 · Status: TODO · Dependencies: AT-005 · Risk: Medium (ops)
- Branch: `feat/at-019-backup-restore-runbook`
- Validation: Documented RPO/RTO; successful restore drill recorded (no secrets in docs).
- Recommended model: Sonnet 4.6

---

## Live-trading program (design → gated implementation; do NOT start before paper Criticals)

### AT-020 — Phase 0: Mode D safety specification (docs/ADRs only)
- Priority: P1 · Status: TODO · Dependencies: AT-010, AT-011 · Risk: Low
- Safety classification: Architecture / no live code
- Branch: `docs/at-020-live-safety-spec`
- Validation: ADRs for order FSM, limits, credentials, promotion gates, incident SEVs;
  no app behavior change; paper defaults unchanged.
- Recommended model: Grok 4.5

### AT-021 — Phase 1: Execution port + sandbox/testnet adapter (no real trading)
- Priority: P2 · Status: TODO · Dependencies: AT-020, AT-007, AT-012, AT-014 · Risk: High
- Safety classification: Mode C sandbox only; `ENABLE_REAL_TRADING` stays false
- Branch: `feat/at-021-execution-port-sandbox`
- Validation: Sandbox contract tests; freshness/idempotency/partial-fill chaos; host allowlist;
  verify-safety still paper-only.
- Recommended model: Grok 4.5 / Opus 4.8

### AT-022 — Phase 2: Approval-gated sandbox execution + circuit breakers
- Priority: P2 · Status: TODO · Dependencies: AT-021, AT-008 · Risk: High
- Branch: `feat/at-022-approval-gated-sandbox`
- Validation: Dual-control E2E; breaker + kill drills; no real credentials.
- Recommended model: Opus 4.8

### AT-023 — Phase 3: Tiny-capital pilot (authorization-gated; separate program)
- Priority: P3 · Status: TODO · Dependencies: AT-022 + explicit human Mode D authorization · Risk: Critical
- Safety classification: Mode D — cannot proceed via ordinary impl task
- Branch: short-lived after written authorization (never long-lived live branch)
- Validation: Written approval; trade-only keys; tiny notional; reconcilation clean; kill proven.
- Recommended model: Opus 4.8

### AT-024 — Phase 4: Controlled scale-up (authorization-gated)
- Priority: P3 · Status: TODO · Dependencies: AT-023 · Risk: Critical
- Safety classification: Mode D ladder — each step REVIEW_REQUIRED
- Validation: Promotion checklist evidence; limit ladder tests; no auto-promote.
- Recommended model: Opus 4.8

---

## Gap analysis (Phase 7) — queued, do NOT implement in bootstrap task

Baseline: verified repo already has strong coverage (deterministic risk engine, guardrails,
provider fallbacks, auth/RBAC, audit + usage quotas, evaluation harness, CI with 6 jobs,
paper-only enforcement, staging deploy). Gaps below are incremental hardening.

### AT-001 — Type-checking (mypy --strict) in CI
- Priority: P1 · Status: TODO · Dependencies: none · Risk: Low
- Gap: `mypy` is configured (`pyproject.toml`, strict) but CI runs only ruff + pytest for backend.
- Validation: CI job runs `uv run mypy src` green; no runtime behavior change.
- Recommended model: GPT-5.4 / Sonnet 4.6

### AT-002 — LangSmith tracing / structured LLM observability
- Priority: P2 · Status: TODO · Dependencies: none · Risk: Low
- Gap: `LANGSMITH_API_KEY` exists but tracing provider is a mock placeholder (per docs).
- Validation: opt-in tracing behind env flag; disabled by default; no secrets logged.
- Recommended model: GPT-5.4

### AT-003 — Scale AI evaluation beyond deterministic fixtures
- Priority: P2 · Status: TODO · Dependencies: AT-002 · Risk: Medium
- Gap: eval harness is deterministic/mock; no scored LLM eval or regression thresholds in CI gating.
- Validation: eval runs with thresholds; env-guarded for real providers; deterministic default.
- Recommended model: Opus 4.8

### AT-004 — Supply-chain security (dependency + secret scanning, pinned actions)
- Priority: P1 · Status: TODO · Dependencies: none · Risk: Low
- Gap: no automated dependency/secret scanning or SBOM in CI; actions not SHA-pinned.
- Validation: CI adds dependency audit + secret scan; build still green; no code behavior change.
- Recommended model: GPT-5.4

### AT-005 — Deploy rollback runbook + smoke gating on deploy
- Priority: P2 · Status: TODO · Dependencies: none · Risk: Low
- Gap: rollback documented informally; no automated post-deploy smoke gate.
- Validation: documented rollback + `verify-safety.sh` gate wired into deploy checklist.
- Recommended model: Sonnet 4.6

### AT-006 — Cost/usage guardrail alerting
- Priority: P2 · Status: TODO · Dependencies: AT-002 · Risk: Low
- Gap: org quotas exist; no proactive alert when approaching token/cost thresholds.
- Validation: threshold alerts (in-app only; external delivery stays disabled); tests for limits.
- Recommended model: GPT-5.4

### AT-007 — Data freshness/degradation conservative-mode audit
- Priority: P1 · Status: TODO · Dependencies: none · Risk: Medium (safety-critical)
- Gap: confirm every consumer of market/vector data enforces conservative behavior on
  stale/degraded/conflicting inputs (Qdrant degraded fallback, Binance rate-limit fallback).
- Validation: tests asserting conservative paths; no real trading; provenance preserved.
- Recommended model: Opus 4.8

### AT-008 — Frontend E2E coverage for approval/refusal safety paths
- Priority: P2 · Status: TODO · Dependencies: none · Risk: Low
- Gap: expand Playwright coverage of real-trading refusal and approval gating in UI.
- Validation: e2e specs pass in CI; paper-only asserted.
- Recommended model: Sonnet 4.6
