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
- Priority: P0 · Status: DONE · Dependencies: AT-010 · Risk: Medium (data integrity)
- Safety classification: Provider / knowledge
- Goal: Fail ingest when embeddings `fallback_used` or Qdrant degraded; never upsert mock
  vectors to remote; avoid Postgres-success / Qdrant-miss silent success; delete orphans.
- Branch: `feat/at-013-rag-provider-fail-closed` (merged via PR #4)
- Validation: Forced provider failures → ingest errors; search exposes degraded flags.
- Recommended model: Grok 4.5
- Completion evidence: merge `b523c70`, commit `92d48bf`, PR https://github.com/Fejjii/AlphaTrade-AI/pull/4

### AT-013B — GPT-5.6 Sol Responses API + staging chat reliability
- Priority: P0 · Status: DONE · Dependencies: AT-013 · Risk: Medium (provider)
- Safety classification: Provider / chat
- Goal: Route `gpt-5.6-sol` through OpenAI Responses API; generation health probe must
  reflect real generation; `/chat/message` must not 503 on staging.
- Branch: `feat/at-013b-gpt56-sol-responses-api` (merged via PR #5)
- Validation: PR #5 CI run 29922248754 success; merged `19d53a4`; post-merge main CI
  29930805870 success; staging deploy `4956aa4`; `/health/ready` ready=true;
  LLM `openai-llm` healthy via responses (no mock); embeddings + Qdrant healthy;
  provider-validation `--remote` + `--remote --ingest` OK; verify-safety / portfolio /
  validate-exchange-demo-staging OK; chat HTTP 200 (5/5 flake retest); paper posture
  preserved (`execution_mode=paper`, `real_trading_enabled=false`,
  `EXCHANGE_MODE=paper_exchange_demo`, `LLM_MODEL=gpt-5.6-sol`).
- Recommended model: Composer 2.5
- Completion evidence: merge `19d53a4`, PR https://github.com/Fejjii/AlphaTrade-AI/pull/5;
  follow-up main commits `5c7c9a7`, `d71bd20`, `4956aa4` (probe + usage-tracking token
  budgets for reasoning models); staging API `git_sha=4956aa4`.

### AT-014 — Server-side kill switch (persist + enforce + UI wire-up)
- Priority: P0 · Status: DONE · Dependencies: AT-012 · Risk: Medium (safety-critical)
- Safety classification: Trading safety
- Goal: Persist org kill switch; enforce in RiskEngine + execution; replace cosmetic
  frontend toggle with API-backed control.
- Branch: `feat/at-014-persistent-kill-switch` (merged via PR #3)
- Validation: Toggle → paper place refused; UI reflects server; agent cannot hardcode false.
- Recommended model: Grok 4.5

### AT-015 — Honor PROVIDER_MODE for LLM/embeddings + wire narrative quota + search opacity
- Priority: P1 · Status: DONE · Dependencies: AT-013 · Risk: Low
- Branch: `feat/at-015-provider-mode-quotas` (merged via PR #6)
- Validation: `PROVIDER_MODE=mock` with key set → mock only (local); staging rejects
  `provider_mode=mock`; narrative `agent_narrative` hard block → deterministic fallback
  (`provider=quota`, no LLM); search exposes `degraded` / `fallback_used` / `vector_backend`.
- Recommended model: Composer 2.5 (impl) · Grok 4.5 (architecture/safety review)
- Completion evidence: PR #6 CI run 29944975929 success; merged `1f3dde0`; post-merge main
  CI run 29949893898 success; staging API `git_sha=1f3dde0`; `/health` + `/health/ready`
  pass; `/providers/status` openai-llm (gpt-5.6-sol), openai-embeddings, qdrant healthy
  (`is_mock=false`, no fallback); verify-safety / provider-validation `--remote` +
  `--remote --ingest` / portfolio-smoke / validate-exchange-demo-staging (17/17) OK;
  isolated staging narrative quota test (limit_agent_narrative=0 → quota fallback, restore →
  LLM path); staging RAG search `degraded=false`, `fallback_used=false`, `vector_backend=qdrant`;
  local pytest `test_at015_provider_mode_quotas.py` + `test_deployment_safety.py` +
  `test_at013_provider_fail_closed.py` pass; paper posture preserved
  (`EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `EXCHANGE_MODE=paper_exchange_demo`,
  `LLM_MODEL=gpt-5.6-sol`).

### AT-025 — Wire narrative quota for sessionless AgentRuntime
- Priority: P2 · Status: TODO · Dependencies: AT-015 · Risk: Low
- Goal: Sessionless `AgentRuntime` (no DB session) currently skips narrative quota — wire
  quota for off-session graphs or document intentional skip.
- Recommended model: Composer 2.5

### AT-026 — Expose soft narrative quota warnings in metadata/UI
- Priority: P2 · Status: TODO · Dependencies: AT-015 · Risk: Low
- Goal: Soft narrative quota warnings are audited but not exposed in `narrative_metadata`
  or workspace UI.
- Recommended model: Composer 2.5

### AT-027 — Require RAG opacity fields in frontend RagSearchResponse
- Priority: P2 · Status: TODO · Dependencies: AT-015 · Risk: Low
- Goal: Frontend `RagSearchResponse` opacity fields are optional — tighten to required
  booleans when API contract is stable.
- Recommended model: Composer 2.5

### AT-016 — Audit unit-of-work + baseline metrics
- Priority: P1 · Status: DONE · Dependencies: AT-010 · Risk: Low
- Branch: merged via PR #7 → `main` @ `bf7f78b`
- Validation: No mid-request audit commit splitting business txn; RED metrics scrapeable.
- Recommended model: Grok 4.5 (architecture/safety) · Composer 2.5 (tests/PR)
- ADR: AT-ADR-008
- Completed: 2026-07-23 — merged to main; post-merge staging validation recommended separately.
- Follow-up (usage metering on replay): **DONE** — merged via PR #8 → `main` @ `5bac87e`
  (`PaperOrderPlacementResult.created_new` gates route usage; sequential replay does not
  double-count). Concurrent first-writer unique-conflict recovery: **DONE** via AT-028.

### AT-028 — Server-side concurrent paper-order idempotency convergence (Postgres)
- Priority: P1 · Status: DONE · Dependencies: AT-016 · Risk: Medium
- Safety classification: Paper accounting / concurrency
- Goal: On concurrent identical `idempotency_key` first-writers, recover from unique
  conflicts with a bounded savepoint/unique-conflict path so the losing request converges
  to the existing order (`created_new=False`) without client retry, and never double-meters
  usage or creation audits. Target Postgres; keep SQLite test coverage honest.
- Validation: Concurrent identical requests (no client retry) → one order, one
  `PAPER_ORDER_CREATED`, one `paper_execution` usage; no service-level commits;
  AT-ADR-008 UoW preserved; paper-only posture unchanged.
- Recommended model: Composer 2.5 · Grok 4.5 (transaction review)
- Completed: 2026-07-23 — merged via PR #9 → `main` @ `1225b49` (feature commit `ee573c3`);
  CI run 30020394617 green (1173 passed, 1 skipped; PostgreSQL 16 concurrency tests pass).
- Hotfix: 2026-07-23 — concurrent-loser HTTP 500 fixed via PR #10 → `main` @ merge `9d5b7c5`
  (commit `48846cd`); quota dependency savepoint convergence + loser/replay no-commit route;
  CI run 30032319345 green (1180 passed, 1 skipped). Staging validation pending separately.

### AT-029 — Fix pre-existing mypy Depends typing on `/execution/paper` route
- Priority: P3 · Status: DONE · Dependencies: none · Risk: Low
- Goal: `backend/src/app/api/routes/execution.py` reports a pre-existing strict-mypy
  `list-item` error: `require_quota(...)` typed as `Callable[..., QuotaCheckResult]`
  where FastAPI `dependencies=` expects `Depends`. Do not suppress or broaden typing
  rules; fix the dependency typing helper / annotation properly.
- Validation: `uv run mypy --strict src/app/api/routes/execution.py` clean.
- Recommended model: Composer 2.5
- Completed: 2026-07-24 — merged via PR #12 → `main` @ merge `cfdfe48` (commit `fb33f66`);
  CI run 30050995688 green. `require_quota` now returns `fastapi.params.Depends`
  (`DependsMarker`); typing-only, no runtime change. Pre-merge: scoped strict mypy + ruff
  clean, 23 quota tests passed.

### AT-017 — Frontend auth boundary + security headers
- Priority: P1 · Status: DONE · Dependencies: AT-011 · Risk: Medium
- Branch: `feat/at-017-frontend-auth-headers`
- Validation: Unauth app routes redirect via middleware; CSP/headers present; paper banners
  follow `/health` truth (no hardcoded “paper active” when real would be on).
- Recommended model: Sonnet 4.6
- Completed: 2026-07-23 — merged via PR #11 → `main` @ merge `1946471` (commit `47f891f`);
  pre-merge CI run 30040774513 green; post-merge CI run 30042962867 green (1180 passed,
  1 skipped). Edge middleware marker-cookie auth boundary, CSP + security headers,
  health-truth paper banners, fail-closed app layout, single-flight refresh.

### AT-018 — Proxy trust + Redis-required rate limits in staging/prod
- Priority: P1 · Status: DONE · Dependencies: AT-010 · Risk: Medium
- Branch: `feat/at-018-proxy-trust-redis` (operator lane name; backlog alias was
  `feat/at-018-rate-limit-proxy-trust`)
- Validation: Spoofed XFF ignored; memory fallback false outside local; denylist fail-closed.
- Recommended model: GPT-5.4 (backlog); implemented via Fable 5 (operator assignment)
- ADR: AT-ADR-009
- Completed: 2026-07-24 — merged via PR #13 → `main` @ merge `22afcda` (commit `265348e`);
  CI run 30053223730 green. Rightmost-hops `TRUSTED_PROXY_HOPS` client-IP trust (default 0),
  uvicorn forwarded-ips no longer `*`, staging/prod reject in-memory rate-limit fallback,
  fail-closed token denylist (503 on unpersistable revocation writes). Pre-merge (after
  rebase onto `cfdfe48`): ruff + scoped strict mypy clean; full backend suite exit 0
  (includes 25 new AT-018 tests); targeted rerun 88 passed. Deploy note: staging boot now
  fails fast if `REDIS_URL` unreachable (intended; `render.yaml` carries the new flags).

### AT-019 — Backup/restore runbook + restore drill evidence
- Priority: P1 · Status: DONE · Dependencies: AT-005 · Risk: Medium (ops)
- Branch: `feat/at-019-backup-restore-drill` (operator lane name; backlog alias was
  `feat/at-019-backup-restore-runbook`)
- Validation: Documented RPO/RTO; successful restore drill recorded (no secrets in docs).
- Recommended model: Grok 4.5 (operator assignment; backlog previously Sonnet 4.6)
- ADR: AT-ADR-010 (drafted in-lane as AT-ADR-009; renumbered — AT-018 landed AT-ADR-009)
- Completed: 2026-07-24 — merged via PR #14 → `main` @ merge `a31a05c` (commit `ca4ff70`);
  CI run 30054203698 green. Runbook (RPO/RTO), inventory, drill plan + sanitized Tier A
  local Compose drill evidence (passed 2026-07-23); local-only backup/restore/drill
  scripts (`CONFIRM=yes` gate, no remote targets). RR-13 moved to Partial. Managed/staging
  Tier B restore remains approval-gated. AT-005 deploy rollback + smoke gate merged via PR #15.

---

## Journal intelligence program

### AT-030 — Journal Intelligence Foundation (canonical journal domain, slice 1)
- Priority: P1 · Status: DONE · Dependencies: none · Risk: Low (record-only, no execution path)
- Safety classification: Paper-safe / record-only
- Goal: Canonical tenant-scoped journal domain (`journal_trades` + evidence, rule-check,
  observation children) unifying manual, paper, imported, backtest, and system trades;
  links (never duplicates) positions, paper trades, proposals, orders, backtest trades,
  legacy journal entries, and immutable setup/strategy versions; plan (thesis, trigger,
  entry, invalidation, stop, targets, runner), execution (leverage, fees, funding,
  slippage), MFE/MAE + available-vs-realized profit, market regime.
- Branch: `cursor/at-030-journal-intelligence-foundation-b68a` (merged)
- Validation: migration `i5d6e7f8a9b0` upgrade/downgrade/upgrade on Postgres 16;
  `tests/test_at030_journal_trades.py` (13 tests); full backend suite exit 0; ruff clean;
  scoped strict mypy clean on new modules (`db/models.py` stays at its pre-existing
  62-error strict baseline); paper posture unchanged.
- Recommended model: Fable 5
- ADR: AT-ADR-012 · Docs: `docs/journal_intelligence_foundation.md`
- Completion evidence: commit `1674dfd`, merge `1e9f5c5`, PR https://github.com/Fejjii/AlphaTrade-AI/pull/16;
  CI run 30064982141 success (backend 1223 passed / 1 skipped; deployment-safety, frontend,
  evaluation, e2e-smoke, docker-build all green). No deploy.
- Follow-up slices (see docs roadmap): journal completion (import/backfill/auto-journal),
  statistics, replay (deterministic MFE/MAE), human-vs-system journal endpoint,
  backtesting integration.

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
- Priority: P2 · Status: DONE · Dependencies: none · Risk: Low
- Branch: `feat/at-005-deploy-rollback-smoke-gate` (merged via PR #15)
- Goal: Document exact rollback triggers/steps/verification/failure handling; automate
  post-deploy smoke gate (`verify-safety.sh` + staging smoke) wired into deploy checklists.
- Validation: `docs/deploy_rollback_runbook.md` present; `scripts/post-deploy-smoke-gate.sh`
  `--self-check` exit 0; gate wired into staging checklist/runbook/`RELEASE.md`; CI
  deployment-safety self-check; paper-only posture unchanged; no staging deploy performed.
- Recommended model: Sonnet 4.6 (backlog) · Grok 4.5 (this lane)
- ADR: AT-ADR-011
- Completed: 2026-07-24 — merged via PR #15 → `main` @ merge `f145599` (commit `4d2617c`);
  CI run 30057647347 success (backend 1210 passed, 1 skipped; deployment-safety,
  frontend, docker-build, evaluation, e2e-smoke all green). Gate profiles: safety /
  standard / extended; exit `1` documented as rollback trigger. Live staging gate run
  deferred to next authorized deploy.

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
