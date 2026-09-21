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
  replay (AT-032), human-vs-system journal endpoint, backtesting integration.

### AT-031 — Journal Statistics & Setup Analytics v1 (journal domain, slice 2)
- Priority: P1 · Status: DONE · Dependencies: AT-030 · Risk: Low (read-only aggregates, no execution path)
- Safety classification: Paper-safe / record-only / read-only endpoint
- Goal: Deterministic tenant-scoped statistics over canonical `journal_trades`, grouped and
  filterable by setup/setup version, strategy/strategy version, symbol, timeframe, market
  regime, source, rule compliance (worst-assessment classification), and human-vs-system
  execution; metrics: trade count, W/L/BE, win rate, expectancy, average R, average
  winner/loser, profit factor, net PnL, fees/funding/slippage impact, MFE/MAE aggregates
  (recorded values only), available-vs-realized profit; per-family sample counts,
  confidence labels, warnings, date-range filter, bucket pagination, bounded scans
  (`journal_stats_max_rows`).
- Branch: `cursor/at-031-journal-statistics-fea2` (merged)
- Deliverables: `schemas/journal_statistics.py`; statistics queries on
  `repositories/journal_trades.py`; `services/journal_statistics_service.py`;
  `GET /journal/statistics` (ReaderDep); migration `j6e7f8a9b0c1` (indexes only);
  frontend `/journal/statistics` page + API client/types + nav entry;
  `tests/test_at031_journal_statistics.py` (19 tests); docs section + roadmap update.
- Validation: migration `j6e7f8a9b0c1` upgrade/downgrade/upgrade on Postgres 16 (scratch DB);
  `tests/test_at031_journal_statistics.py` (19 tests); full backend suite exit 0; ruff clean;
  strict mypy clean on new modules; frontend lint/typecheck/tests/build green.
- Recommended model: Fable 5
- ADR: AT-ADR-013 · Docs: `docs/journal_intelligence_foundation.md` (§4)
- Completion evidence: commits `2412c56`, `99d7f7f` (CI flake fix), merge `8020558`, PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/17; CI run 30092110777 success (backend
  1242 passed / 1 skipped; deployment-safety, frontend, evaluation, e2e-smoke,
  docker-build all green). No deploy.
- Follow-up slices: replay (AT-032 DONE), journal completion (import/backfill/auto-journal),
  human-vs-system journal endpoint, backtesting integration (see docs roadmap §6).

### AT-032 — Journal Excursion Replay (deterministic MFE/MAE from HistoricalCandle)
- Priority: P1 · Status: DONE · Dependencies: AT-030, AT-031 · Risk: Low
  (record-only replay; no execution path)
- Safety classification: Paper-safe / record-only
- Goal: Deterministic in-trade MFE/MAE, available profit, and profit-capture for
  canonical `journal_trades` from read-only `HistoricalCandle`;
  `excursion_source="replay"` with data-source/freshness provenance; never overwrite
  manual/system without explicit `overwrite_policy=force`; optional post-exit runner
  analysis via `RunnerAndMissedProfitAnalyzer`; feed AT-031 statistics; handle missing
  candles, gaps, incomplete windows, invalid trade windows safely; tenant isolation +
  RBAC + audit; bounded candle/batch queries.
- Branch: `feat/at-032-journal-excursion-replay` (merged)
- Deliverables: migration `k7f8a9b0c1d2`; calculator + replay service; schemas; routes
  `POST /journal/trades/{id}/replay-excursions` and batch
  `POST /journal/trades/replay-excursions`; config bounds; tests; docs §5; ADR-014.
- Validation: migration `k7f8a9b0c1d2` upgrade/downgrade/upgrade on Postgres 16 (scratch DB);
  `tests/test_at032_journal_excursion_replay.py` (17 tests); ruff clean; strict mypy clean
  on new modules; AT-030/031 regression green; CI run 30105918952 success (backend 1259
  passed / 1 skipped; deployment-safety, frontend, evaluation, e2e-smoke, docker-build all
  green). No deploy.
- Recommended model: Fable 5
- ADR: AT-ADR-014 · Docs: `docs/journal_intelligence_foundation.md` (§5)
- Completion evidence: commits `460a994`, `e237d96` (ruff format), merge `b164c14`, PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/18; CI run 30105918952 success. No deploy.
- Follow-up slices: journal completion (import/backfill/auto-journal), human-vs-system
  journal endpoint, backtesting integration (see docs roadmap §6).

### AT-033 — Journal Completion (bulk import, backfill, auto-journal, attachments)
- Priority: P1 · Status: DONE · Dependencies: AT-030, AT-031, AT-032 · Risk: Low
  (record-only; no execution path; new flags default off)
- Safety classification: Paper-safe / record-only
- Goal: Bulk journal import (`source=imported`, `entry_method=import`) with
  `(org, external_ref)` dedup via partial unique index + deterministic fingerprints;
  dry-run/commit modes with per-row reconciliation and all-or-nothing commits;
  `TradeJournal` → `journal_trades` backfill CLI (idempotent, dry-run default);
  opt-in auto-journal hooks on paper position / paper-validation close (default off,
  savepoint-isolated, never blocks the close); DB-backed attachment storage behind
  `AttachmentStorage` with size/MIME/quota caps and evidence auto-link;
  `entry_method` human-vs-system statistics dimension; frontend `/journal/import`
  with CSV mapping, dry-run preview, and batch history; tenant isolation + RBAC +
  audit throughout.
- Branch: `feat/at-033-journal-completion`
- Deliverables: migration `l8a9b0c1d2e3`; `journal_import_service` +
  `journal_backfill_service` + `journal_attachment_service`/`_storage`;
  `scripts/backfill_journal_entries.py`; routes `POST /journal/trades/import`,
  `GET /journal/imports[/{id}]`, attachment endpoints; auto-journal hooks in
  `position_service` + `paper_validation_runtime_service`; settings flags + limits;
  frontend import page + api client + tests; docs §6; ADR-015.
- Validation: migration `l8a9b0c1d2e3` upgrade/downgrade/upgrade round-trip on
  disposable Postgres 16 (docker) clean; partial unique index verified on Postgres
  (duplicate rejected, NULL refs unconstrained); 44 new backend tests
  (`test_at033_journal_import.py` 14, `test_at033_journal_backfill.py` 6,
  `test_at033_journal_attachments.py` 12, `test_at033_auto_journal.py` 9,
  `test_at033_integration.py` 3); AT-030/031/032 regression green (49 tests);
  frontend 267 passed + lint + typecheck + build green; ruff check/format clean.
  Full-suite result recorded in the PR. No deploy; no live trading.
- Recommended model: Fable 5
- ADR: AT-ADR-015 · Docs: `docs/journal_intelligence_foundation.md` (§6)
- Completion evidence: commits `a2e09a0`…`1e65185`, merge `ad66dca`, PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/19; CI run 30114440476 success
  (backend, frontend, deployment-safety, docker-build, evaluation, e2e-smoke,
  Vercel preview green). No deploy; auto-journal flags remain default off.
- Follow-ups: attachment upload UI (needs trades detail page), per-user auto-journal
  preference, failed/dry-run import batch persistence, human-vs-system endpoint.

### AT-034 — Deterministic Backtesting v2 (engine, orchestration, frontend, tests/docs)
- Priority: P1 · Status: DONE · Dependencies: AT-030, AT-031, AT-032, AT-033,
  Slice 35 · Risk: Low (record-only; no execution path; advisory tiers only)
- Safety classification: Paper-safe / record-only
- Goal: Deterministic backtest v2 with frozen config/dataset snapshots,
  `result_hash` reproducibility, walk-forward holdout/rolling splits, long+short
  entry modes (pullback_ema/breakout/liquidity_sweep), funding accrual, in-loop
  MFE/MAE/capture, bounded orchestration (sync vs queued, cancel, idempotency,
  active-run cap), bulk journal-from-backtest, journal comparison cohorts, advisory
  setup evidence tiers, frontend backtest UI, integration tests and v2 docs.
- Branches: `feat/at-034-backtest-domain-engine`, `feat/at-034-backtest-api-orchestration`,
  `feat/at-034-backtest-frontend`, `feat/at-034-backtest-tests-docs`
- Deliverables: migration `m9b0c1d2e3f4`; `backtest_engine_service` (v2),
  `backtest_dataset_service`, `backtest_hashing`, `backtest_service`,
  `backtest_journal_service`, `setup_evidence_service`; routes
  `POST/GET /strategies/{id}/backtests`, `GET/POST /backtests/{id}/*`,
  `GET /journal/comparison`, `GET /journal/setup-evidence`; settings `backtest_*`;
  frontend backtest pages; `tests/test_at034_engine.py`, `tests/test_at034_api.py`,
  `tests/test_at034_integration.py`; `docs/backtesting.md` v2; ADR-016.
- Validation: `tests/test_at034_integration.py` green; full backend pytest + ruff
  clean; frontend tests/typecheck/build (WS3); Status DONE after final merge. No deploy; no live trading.
- Recommended model: Grok 4.5 (WS1/WS2) + Composer 2.5 (WS3/WS4)
- ADR: AT-ADR-016 · Docs: `docs/backtesting.md`
- Completion evidence: merged PR #20 (`095e490`, CI 30126077064), PR #21
  (`a46d863`, CI 30126107532), PR #22 (`fb26dea`, CI 30130869273), PR #23
  (`8f9a84b`, CI 30130870524) → `main` @ `8f9a84b` (governance tip `79971fa`). Post-merge local validation:
  AT-034 + slice-35 pytest 43 passed; frontend page tests 7 passed; ruff clean.
  No deploy; paper posture unchanged.

### AT-035 — Research validation loop (backtest evidence → paper candidate queue)
- Priority: P1 · Status: DONE · Dependencies: AT-034, Slice 80
  (paper validation candidate queue) · Risk: Low (advisory only; no execution path)
- Safety classification: Paper-safe / record-only
- Goal: Advisory promotion of completed backtest evidence (tier1/tier2) into the
  existing paper-validation candidate queue with frozen provenance, synthetic
  research-origin alert/draft scaffolding, idempotent per org+backtest run,
  tenant isolation, and RBAC (reader GET, trader POST promote).
- Branch: `feat/at-035-research-validation-loop`
- Deliverables: migration `n0c1d2e3f4a5`; `research_validation_service`,
  routes `/research-validation/*`; candidate provenance fields on
  `PaperValidationCandidateItem`; frontend `/research-validation` page;
  `tests/test_at035_research_validation.py`; `docs/research_validation.md`; ADR-017.
- Validation: disposable Postgres 16 migration upgrade/downgrade/upgrade cycle;
  partial unique index `uq_pvc_org_backtest_active` verified; duplicate active
  promotion blocked at DB layer; targeted `test_at035_research_validation.py` (10)
  green; integrated AT-035 + slice80/81 + at034_api (46) green; ruff + strict mypy
  on touched modules; frontend lint/typecheck/research-validation tests (8) green.
  No deploy; no live trading; risk/execution unchanged.
- Recommended model: Grok 4.5 (WS1) + Composer 2.5 (WS2/WS3)
- ADR: AT-ADR-017 · Docs: `docs/research_validation.md`
- Completion evidence: PR https://github.com/Fejjii/AlphaTrade-AI/pull/24 merged
  (`2f46111`, CI run 30136769341 all green: backend, frontend, deployment-safety,
  docker-build, evaluation, e2e-smoke, Vercel preview). Disposable Postgres 16
  migration upgrade/downgrade/upgrade verified; partial unique index
  `uq_pvc_org_backtest_active` and duplicate active promotion blocked at DB layer.
  No deploy; paper posture unchanged.

### AT-036 — Human-vs-system decision quality (aggregate journal comparison)
- Priority: P1 · Status: DONE · Dependencies: AT-034, AT-031 ·
  Risk: Low (advisory only; no execution path)
- Safety classification: Paper-safe / record-only
- Goal: Extend `GET /journal/comparison` with AT-036 decision-quality metrics,
  human/system actor scorecards, dimension buckets, setup/regime breakdowns, and
  frontend `/journal/comparison` page. Backward compatible with AT-034 three-cohort
  response. Tenant isolation + `ReaderDep` RBAC unchanged.
- Branch: `feat/at-036-human-vs-system-decision-quality` (merged)
- Deliverables: extended `journal_statistics_service.compare_cohorts`; schemas in
  `backtest.py` / `journal_statistics.py`; frontend comparison page + nav;
  `tests/test_at036_journal_comparison.py`; `journal/comparison/page.test.tsx`;
  docs + ADR-018.
- Validation: PR #25 CI run 30139404763 success (backend, frontend,
  deployment-safety, docker-build, evaluation, e2e-smoke, Vercel preview green).
  Local pre-merge targeted: AT-036 + AT-031 + AT-034 API pytest 47 passed;
  frontend comparison + backtest page tests 9 passed. No deploy; no live trading;
  risk/execution unchanged. Per-trade `/human-vs-system/{id}` remains Slice 36.
- Recommended model: Grok 4.5 (WS1) + Composer 2.5 (WS2/WS3)
- ADR: AT-ADR-018 (Accepted) · Docs: `docs/journal_intelligence_foundation.md` §7,
  `docs/human_vs_system.md`, `docs/backtesting.md`, `docs/limitations_roadmap.md`
- Completion evidence: commit `847d85d`, merge `3ff1eb3`, PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/25; CI run 30139404763 success.
  No deploy; paper posture unchanged.

### AT-037 — TradingView Signal Intake and BloFin Read-Only Synchronisation v1
- Priority: P1 · Status: DONE · Dependencies: AT-035, Slice 80, BloFin demo
  account provider · Risk: Medium (webhook surface; exchange read path)
- Safety classification: Paper-safe / demo read-only (no order mutation)
- Goal: Secure TradingView signed webhook intake with idempotent signal lifecycle,
  optional paper-validation candidate routing, plus BloFin demo read-only
  account/position/market-context sync. No order placement.
- Branch: `feat/at-037-tradingview-blofin-sync` (merged)
- Deliverables: migration `o1d2e3f4a5b6`; `tradingview_signals` +
  `blofin_demo_sync_snapshots`; `tradingview_signal_service`, `blofin_sync_service`,
  signature helper; routes `POST /webhooks/tradingview`,
  `GET/POST /tradingview/signals*`, `POST/GET /exchange/blofin/sync*`;
  frontend `/tradingview-signals` + BloFin sync panel; tests
  `test_at037_tradingview_blofin.py` + frontend tests; `docs/tradingview_blofin_sync.md`;
  ADR-019.
- Validation: disposable Postgres 16 migration upgrade/downgrade/upgrade cycle for
  `o1d2e3f4a5b6` verified; PR #26 CI run 30144938569 all green (backend 1371 passed,
  1 skipped; frontend, deployment-safety, docker-build, evaluation, e2e-smoke, Vercel
  preview). Local pre-merge: `test_at037_tradingview_blofin.py` (9) + integrated
  AT-035/blofin (71) + frontend vitest (9) + mypy strict on AT-037 modules. No deploy;
  no live trading.
- Recommended model: Cursor Grok 4.5
- ADR: AT-ADR-019 (Accepted) · Docs: `docs/tradingview_blofin_sync.md`
- Completion evidence: PR https://github.com/Fejjii/AlphaTrade-AI/pull/26 merged
  (`1d52cb3`, CI run 30144938569). Commits `650097a`, `9e09a85`. No deploy; paper
  posture unchanged.

### AT-038 — Automated Paper-Signal Orchestration v1
- Priority: P1 · Status: DONE · Dependencies: AT-037, Slice 80/81,
  ProposalService, KillSwitchService · Risk: Medium (orchestration surface;
  must remain paper-only)
- Safety classification: Paper-safe (no order mutation; no live mode)
- Goal: Connect validated TradingView signals to paper-validation candidates/run
  plans and optional approval-gated paper proposals through a deterministic,
  reviewable orchestration workflow with observe_only / candidate_only /
  approval_required modes.
- Branch: `cursor/at-038-paper-signal-orchestration`
- Deliverables: migration `p2e3f4a5b6c7`; `paper_signal_orchestration_decisions`;
  eligibility + orchestration service; routes under `/paper-signal-orchestration/*`;
  frontend `/paper-signal-orchestration`; tests
  `test_at038_paper_signal_orchestration.py` + frontend page tests;
  `docs/paper_signal_orchestration.md`; ADR-020.
- Validation: PR #27 CI run 30160911227 success (backend, frontend, docker-build,
  deployment-safety, evaluation, e2e-smoke). Frontend flake fix: await
  `paper-draft-candidate-link` inside `waitFor` after draft queue
  (`4c2e49d`). No deploy; `PAPER_SIGNAL_ORCHESTRATION` not enabled on staging;
  paper posture unchanged.
- Recommended model: Cursor Grok 4.5
- ADR: AT-ADR-020 (Accepted) · Docs: `docs/paper_signal_orchestration.md`
- Completion evidence: PR https://github.com/Fejjii/AlphaTrade-AI/pull/27 merged
  (`05b79ea`, CI run 30160911227). Head commit `4c2e49d`.

### AT-043 — Telegram security and interaction protocol foundation
- Priority: P1 · Status: IN_PROGRESS · Dependencies: agentic redesign Phase 8 design
  (`docs/redesign/agentic_redesign_target_architecture.md` §10) · Risk: Medium
  (security-critical; must remain disconnected from execution)
- Safety classification: Security / paper-safe / Telegram disabled
- Goal: Isolated Telegram enrollment, verified private-chat identity, nonce,
  receipt, replay, rate-limit, outbox, delivery-ack, and action-authorization
  contracts. Telegram stays disabled. APPROVE never executes. CLOSE unavailable.
  No FastAPI webhook, no ORM/Alembic, no execution wiring.
- Branch: `cursor/telegram-security-foundation-5bf5`
- Deliverables: `app.telegram_security`; in-memory store; fake transport;
  `docs/telegram_security_protocol.md`; tests
  `test_telegram_security_protocol.py`; `TELEGRAM_INTERACTION_ENABLED=false`.
  Final hardening (PR 79): exact-replay fingerprint +
  `TelegramInboundUpdate.body_size`; closure binds full transport identity and
  resolves exact/conflicting replay before rate-limit charging.
- Validation: targeted protocol tests + full backend pytest + ruff + mypy on
  the new package + GitHub CI. No merge in this task.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-023

### AT-039 — Premium UI/UX blueprint + screen inventory (planning only)
- Priority: P1 · Status: DONE · Dependencies: AT-038 · Risk: Low (docs only)
- Safety classification: Product/design planning; no runtime change
- Goal: Author AlphaTrade-specific premium UI/UX blueprint and full frontend
  screen inventory to guide Phases A–F redesign without changing app behavior.
- Branch: `plan/at-039-premium-ui-ux-blueprint-cloud`
- Deliverables: `docs/product/at039_premium_ui_ux_blueprint.md`,
  `docs/product/at039_screen_inventory.md` (53 routes audited).
- Validation: Docs-only PR #28; no frontend/backend/API/migration/dependency
  changes. Paper-first invariants encoded in blueprint (risk BLOCK final, no UI
  override; provenance/freshness required).
- Recommended model: Cursor Grok 4.5
- Completion evidence: PR https://github.com/Fejjii/AlphaTrade-AI/pull/28 merged
  (`853d96b`). Head commit `7ebc8df`.

### AT-040 — Premium design-system foundation (Phase A) + navigation/app shell (Phase B) + Phase C daily workflows + Phase D analytics planning
- Priority: P1 · Status: IN_PROGRESS (Phase A + B + C1 + C2 + C3A + C3B1 + C3B2 DONE; Portfolio/Risk command centre DONE; Phase D Analytics & Charts blueprint DONE) · Dependencies: AT-039 · Risk: Low (frontend-only / docs)
- Safety classification: UI foundation / shell IA / daily workflow UX; no trading/execution/risk-authority change
- Goal: Introduce dark-first semantic tokens, typography utilities, shared UI
  primitives (incl. PageHeader, FreshnessPill, StatusBadge, Skeleton, Empty/Error/
  Stale/Blocked states, RiskBlock with no UI override, PaperModeIndicator,
  DataNumber), and adopt them on a small representative set of screens without
  route or nav IA changes (Phase A). Then implement AT-039 Phase B navigation and
  app shell (eight destinations, desktop sidebar, mobile bottom nav + Menu sheet,
  StatusStrip advice/execution/risk truth, TopBar page identity + freshness shell
  interface + account control, Settings Billing & Usage consolidation). Phase C1
  implements Dashboard attention queue, Signals inbox, and Plan hub daily loop.
  Phase C2 redesigns Validate as one coherent pipeline (Draft → Candidate →
  Run plan → Run session → Observation → Outcome).
- Branch (Phase A): `feat/at-040-premium-design-system-foundation`
- Branch (Phase B): `cursor/at040-phase-b-nav-shell-ae93`
- Branch (Phase C1): `feat/at040-phase-c1-daily-decision-loop`
- Branch (Phase C2): `cursor/at040-phase-c2-validate-pipeline-53f5`
- Branch (Phase C3A): `cursor/at040-phase-c3a-journal-quick-entry-a54b`
- Deliverables (Phase A): `frontend/src/styles/tokens.css`, tokenized Tailwind + globals,
  `frontend/src/components/ui/*` primitives, states updates, representative page
  adoption (Dashboard, TradingView signals, paper-signal orchestration, journal
  statistics, portfolio), guide `docs/product/at040_design_system_foundation.md`,
  vitest `design-system.test.tsx`.
- Deliverables (Phase B): centralized `navigation-config.ts`, DesktopSidebar /
  MobileBottomNavigation / MobileMenuSheet / SecondaryNavigation / StatusStrip /
  TopBar / CommandMenu / `ShellFreshnessContext`, Billing & Usage at
  `/settings/billing`, Portfolio ownership of `/risk`, session-dismissible advice
  truth, e2e logout via account menu.
- Validation: PR #29 CI run 30165820718 success (backend, frontend, docker-build,
  deployment-safety, evaluation, e2e-smoke). No `package.json` dependency adds;
  no routes removed; `nav-items.ts` unchanged; zero backend/API/migration files.
  Phase A hardening PR #30 CI run 30174563899 success; post-merge main CI run
  30178168238 success (backend, frontend, docker-build, deployment-safety,
  evaluation, e2e-smoke). Phase B PR #31 CI run 30200035610 success; post-merge
  main CI run 30201145776 success (frontend, backend, docker-build,
  deployment-safety, evaluation, e2e-smoke). No deploy; live trading unchanged.
- Recommended model: Cursor Grok 4.5
- Completion evidence: PR https://github.com/Fejjii/AlphaTrade-AI/pull/29 merged
  (`c414378`, CI run 30165820718). Head commit `34135be`. Phase A hardening PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/30 merged (`d988576`, CI run
  30174563899; post-merge main CI 30178168238). Hardening head `e9e930c`
  (TabsRoot shared id prefix + fail-closed paper-mode / limitations hardening).
  Phase B PR https://github.com/Fejjii/AlphaTrade-AI/pull/31 merged (`fc148ff`,
  pre-merge head `7f7818c`, CI run 30200035610; post-merge main CI 30201145776).
  Phase C1 PR https://github.com/Fejjii/AlphaTrade-AI/pull/32 merged
  (`f7fafd4`; pre-merge head `95d669a`; validated implementation commit
  `7e42fe8`; pre-merge CI 30211212052 success; post-merge main CI 30212388146
  success — frontend, backend, docker-build, deployment-safety, evaluation,
  e2e-smoke). Correction pass recorded: SourceResult availability, runtime
  safety-truth matrix (`isPaperModeConfirmed`), conservative shell freshness
  aggregation (available sources with missing/invalid/future timestamps
  contribute unavailable; live + unknown cannot yield page-level Live), signal
  deep-link honesty, Plan signal context query, and session-only dismiss
  labeling. Phase C1 complete; Phase C2 Validate pipeline complete; Phase C3A Journal
  hub + quick-entry complete.
- Phase C1 deliverables: Dashboard attention queue; Signals inbox on
  `/tradingview-signals`; Plan hub on `/workspace`; `WorkflowFreshnessAdapter`;
  unknown-route identity `AlphaTrade`; account-menu Escape focus restore;
  SourceResult partial-data honesty; confirmed-paper-only safety badges;
  conservative multi-source shell freshness with unknown-timestamp contribution.
- Phase C2 deliverables: Validate hub at `/paper-validation`;
  pipeline components (`ValidationPipeline`, stage/summary cards, attention queue,
  source availability, `OutcomeSummary`); SourceResult honesty on stage lists;
  preserved detail routes with related-stage links; confirmed-paper posture;
  Risk BLOCK no override; no auto-promote/start; no backend/API/migration changes.
  Honesty correction pass: independent session observation/outcome SourceResult
  loads (404 = not recorded; other failures = unavailable); Setup Alert Review
  `?alert=` deep-link highlight/focus without mutation; candidate→run-plan
  active preference + accessible plan links with partial-data Retry when run
  plans fail. Final coverage/freshness pass: typed outcome coverage statuses
  (`not_applicable` / `complete` / `partial` / `unavailable`) with separate
  `renderable` / `fullyAvailable` / `errorCount`; partial Outcomes in
  partial-data warning without Live freshness; session outcome UI states
  (`loading` / `recorded` / `confirmed_not_recorded` / `unavailable`) gate the
  recording form. Loading-versus-unavailable pass: explicit observation source
  states (`loading` / `available` / `unavailable`) and outcome source states in
  `OutcomeSummary`; initial load shows neutral loading copy (no premature
  unavailable/Retry/zero); retry shows retrying/refreshing without unavailable;
  completed sessions use historical missing-outcome wording.
  Phase C2 PR https://github.com/Fejjii/AlphaTrade-AI/pull/33 merged
  (`cd77790`; pre-merge head `0e0a1af`; validated implementation commit
  `921929e`; pre-merge CI 30224234541 success; post-merge main CI 30225088594
  success — frontend, backend, docker-build, deployment-safety, evaluation,
  e2e-smoke). Phase C2 complete.
- Phase C3A deliverables: Journal hub at `/journal`; needs-journaling queue with
  `journalCoverage`/`positionsCoverage` honesty; recent entries; quick-entry using
  existing journal create/prefill fields; prefill relationship reset on context
  change/loading/invalid/cleared; SourceResult multi-source honesty; confirmed-PAPER
  posture; preserved Import/Lessons/Knowledge/Statistics/Comparison reachability;
  no backend/API/migration changes.
  Phase C3A PR https://github.com/Fejjii/AlphaTrade-AI/pull/34 merged
  (`dc19bc8`; pre-merge head `8b57a68`; validated implementation commit
  `d2aa71e`; pre-merge CI 30229681876 success; post-merge main CI 30231014521
  success — frontend, backend, docker-build, deployment-safety, evaluation,
  e2e-smoke). Phase C3A complete.
- Phase C3B1 deliverables (review hub only — no Knowledge redesign):
  Lessons review hub at `/lessons`; attention queue (`pending_review` only);
  recently reviewed (accepted + rejected); source context + next-action guidance;
  SourceResult multi-source honesty; preserved accept/reject mutations + typed
  confirmations; journal/strategy/validation relationship links from stored fields only;
  `?candidate=` deep-link verification; coaching source filter; confirmed-PAPER posture;
  correction passes: pagination coverage honesty (complete/truncated), all-status
  deep-link rendering, global mutation lock, confidence 0 display, deep-link +
  coaching-filter visibility, corrected truncated count wording;
  no backend/API/migration changes.
  Phase C3B1 PR https://github.com/Fejjii/AlphaTrade-AI/pull/35 merged
  (`edbc038`; pre-merge head `7ccc005`; validated implementation commit
  `219f2c8`; pre-merge CI 30257024612 success; post-merge main CI 30258584822
  success — frontend, backend, docker-build, deployment-safety, evaluation,
  e2e-smoke). Phase C3B1 complete.
- Phase C3B2 deliverables (Knowledge hub only — no Portfolio/Risk/Analytics):
  Premium Knowledge hub at `/knowledge`; list documents/chunks via existing APIs;
  loaded-page library search + semantic search; source_type filters; recently added
  (created_at desc); category honesty (definitive totals only for unfiltered complete
  coverage); source context; `source_uri` relationship links only
  (`journal://` / `lesson://` / `strategy://…/vN`); `?document=` deep-link verification
  within loaded coverage; chunk detail retry; confirmed-PAPER posture; correction pass
  for category/search/URL-sync/deeplink/retry/lockfile/mobile wrap;
  no backend/API/migration changes.
  Phase C3B2 / Knowledge Hub PR https://github.com/Fejjii/AlphaTrade-AI/pull/36 merged
  (`041f0c4`; pre-merge head / implementation head
  `a4aed6fc9913ae2c5bc6cf8d300ff56eab4b2495`; pre-merge CI 30264373051 success;
  post-merge main CI 30267507921 success — frontend, backend, docker-build,
  deployment-safety, evaluation, e2e-smoke). Phase C3B2 / Knowledge Hub DONE.
- Portfolio/Risk command centre deliverables:
  `/portfolio` owns paper account overview, exposure, history, and risk posture
  (daily discipline + kill-switch fail-closed); `/risk` remains configuration-only.
  Honesty corrections: unresolved/stale kill-switch never means clear; cached BLOCK
  remains authoritative after refresh failure; drawdown/daily P&L wording distinguishes
  today vs selected-range; journal `?entry=` deep links; empty equity is confirmed empty
  (not truncated); positions link labeled "View positions"; separate Daily discipline /
  Kill switch source rows. Frontend-only; no Knowledge/nav/backend changes.
  Portfolio/Risk command centre PR https://github.com/Fejjii/AlphaTrade-AI/pull/37
  merged (`7788320`; pre-merge / implementation head
  `0a2fcad698b7997b74ef3402006e73cedbf1a35a`; pre-merge CI 30277821355 success;
  post-merge main CI 30279764094 success — frontend, backend, docker-build,
  deployment-safety, evaluation, e2e-smoke). Portfolio/Risk command centre DONE.
- Critical data-honesty and Portfolio RiskBlock fixes deliverables:
  `/settings/audit` loading/error honesty (EmptyState only after successful empty
  response); `/settings/team` explicit loading/loaded/failed list state (empty wording
  only after successful empty response; create/revoke preserved); Portfolio
  `buildRiskPosture` kill-switch BLOCK precedence when Daily discipline is
  loading/absent, failed, or missing snapshot (`showRiskBlock=true`, stored reason,
  discipline values unavailable, limitations explain source condition). Frontend-only;
  no `/analytics`, `useAsyncData.ts`, Knowledge, nav, backend, API, migration, or
  deployment changes.
  Critical data-honesty / RiskBlock fixes PR https://github.com/Fejjii/AlphaTrade-AI/pull/44
  merged (`aaa33f4`; pre-merge / implementation head
  `0ab606984edab99550d70d77b70a51111f8a861d`; pre-merge CI 30287687997 success;
  post-merge main CI 30291493531 — frontend, backend, docker-build, deployment-safety,
  evaluation, e2e-smoke). Critical data-honesty / RiskBlock fixes DONE.
- Analytics PR 1 deliverables (foundation, filters, Overview + Performance):
  `/analytics` with Overview + Performance tabs; URL-synced filters; honest SourceResult
  loading per widget; Overview stats with journal/portfolio provenance; Performance charts
  (daily P&L, cumulative realised P&L) via lazy-mounted Recharts; freshness gating;
  ISO-week roll-up; chart transforms with malformed-value honesty; no changes to audit,
  invitations, portfolio, or `useAsyncData.ts`.
  Analytics PR 1 PR https://github.com/Fejjii/AlphaTrade-AI/pull/43 merged
  (`257f3a2`; pre-merge / implementation head
  `82202e6fd7d3c527b958b6622dc3ec8f2a58c60e`; pre-merge CI 30294572981 success;
  post-merge main CI 30296686361 success — frontend, backend, docker-build,
  deployment-safety, evaluation, e2e-smoke). Analytics PR 1 DONE.
- Analytics PR 2 deliverables (Setup and Strategy Analytics):
  `/analytics?tab=setups` with win-rate and expectancy charts, paged bucket table,
  grouping toggle, URL-synced journal setup_id deep links, setup-identity integrity
  (journal UUIDs never routed to portfolio), Setups journal source filter, honest
  setup-evidence provenance, and compact chart labels; no reopen of Portfolio/Risk
  or Analytics PR 1 scope.
  Analytics PR 2 PR https://github.com/Fejjii/AlphaTrade-AI/pull/47 merged
  (`1c3077b03737fa8f60c15cb673ff58e6d14b58ea`; pre-merge / implementation head
  `e4bfdacd90c9965f738f7c13c88d14d523d4c642`; pre-merge CI 30313626587 success —
  frontend, backend, docker-build, deployment-safety, evaluation, e2e-smoke;
  post-merge main CI 30315387747 success — same six jobs). Analytics PR 2 DONE.
- Analytics PR 3 deliverables (Behaviour and human-versus-system comparison):
  `/analytics?tab=behaviour` with rule-compliance chart, dual discipline score cards
  (proposal-flow vs validation-session, distinctly labeled and linked), risk-behaviour
  warning counts (counts, not performance), independent per-widget source slots and
  freshness presentation; `/analytics?tab=comparison` with human-vs-system paired bars
  and decision-quality tiles; all five Analytics tabs functional; no backend/API changes;
  no reopen of Portfolio/Risk, Analytics PR 1, or Analytics PR 2 scope.
  Analytics PR 3 PR https://github.com/Fejjii/AlphaTrade-AI/pull/46 merged
  (`8fffc0ff0e861f4b553f4ae3babd384d006f3b83`; pre-merge / implementation head
  `1ae5b3e43297ba4cbffb881a897315fe6ae1a564`; pre-merge CI 30350773804 success —
  frontend, backend, docker-build, deployment-safety, evaluation, e2e-smoke;
  post-merge main CI 30352734328 success — same six jobs). Analytics PR 3 DONE.
- Phase D Analytics & Charts blueprint deliverables (documentation only — no
  frontend/backend/chart implementation): authoritative implementation plan at
  `docs/product/at040_analytics_and_charts_blueprint.md`; verified capability
  inventory + metric availability matrix; six-tab Analytics IA; chart specs;
  filter model with setup-identity integrity; currency-agnostic monetary display;
  App Router URL-history contract (`router.push` for committed actions;
  `router.replace` only for cleanup/canonicalisation); four-PR sequence;
  complete-CI merge evidence; Composer 2.5 for PRs 1–4.
  Analytics & Charts Blueprint PR https://github.com/Fejjii/AlphaTrade-AI/pull/38
  merged (`ee7cf9d`; pre-merge / implementation head
  `e82d4fc3287a693ea755901e01e2b5d868ee8ecb`; pre-merge CI 30271331488 success;
  post-merge main CI 30273039335 success — frontend, backend, docker-build,
  deployment-safety, evaluation, e2e-smoke). Analytics & Charts blueprint DONE.
  Governance record PR https://github.com/Fejjii/AlphaTrade-AI/pull/40 merged
  (`9d42d10`).
- Phase C remaining: none (Portfolio/Risk merged).
- Analytics implementation roadmap: Analytics PR 1 complete; Analytics PR 2 complete;
  Analytics PR 3 complete; **Analytics PR 4** (validation analytics and final chart polish)
  is the immediate next implementation — fresh Composer 2.5 agent chat from latest `main`;
  do not reopen Portfolio/Risk or Analytics PRs 1–3 scope in that chat. Final readiness
  audit follows Analytics PR 4 and final polish (see blueprint §8 PR 4 and
  `docs/product/at040_final_polish_and_readiness_audit.md` when merged).

### AT-042 — Watcher orchestration foundation (Phase 7 worker; isolated)
- Priority: P1 · Status: IN_PROGRESS · Dependencies: agentic redesign Phase 7
  contracts; Agent 1 source freshness later · Risk: Medium
- Safety classification: Paper-safe; watcher remains disabled; no execution,
  journal, Telegram, candidates, or ORM/migrations
- Goal: Isolated worker architecture — scan request / watchlist policy contracts,
  leases, fencing, retry, scan lineage, dedupe, idempotent scheduling, manual
  and worker evaluation-boundary parity, health, failure reporting, observability,
  and deterministic test repositories.
- Branch: `cursor/watcher-orchestration-foundation-4364`
- Validation: Targeted foundation tests plus full backend, ruff, mypy, GitHub CI.
  Tenant isolation: two organizations with identical `scan_scope` acquire independent
  leases/fences/heartbeats/health/lineage. `WATCHER_ORCHESTRATION_ENABLED` default
  false; no Alembic migrations.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-022

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

---

## Agentic redesign — market evidence

### AT-041 — Phase 5 market source contracts and evidence foundations
- Priority: P0 · Status: DONE · Dependencies: Phases 1–4 on `main` · Risk: Medium
- Safety classification: Paper-safe / read-only market evidence; no execution path
- Goal: Contract-test Binance USD-M perpetual OHLCV and aggregate trades for the first
  BTCUSDT 15m/4h slice; freeze identity, finality, freshness, cursor/gap, CVD, signed
  quote flow, provenance, and replay fixtures. No watcher, Telegram, candidates,
  execution, or frontend.
- Branch: `cursor/phase5-market-contracts-852a`
- PR: https://github.com/Fejjii/AlphaTrade-AI/pull/80 (draft; do not merge)
- Validation: 62 Phase 5 tests cover closed/forming candles, wrong market/instrument/source,
  immutable full-window coverage, missing prefix/suffix, gap/duplicate/out-of-order/cursor
  recovery, freshness/stale, CVD exact arithmetic, proven signed quote flow, aggressor
  semantics, content-hash stability, replay determinism, provider provenance, regional
  failure, HTTPS host binding, aggTrades pagination, and no spot fallback. Local Ruff clean;
  mypy `--strict` on `src/app/market_contracts` Success (23 files). Full backend and all
  GitHub CI jobs passed on closure revision `d73ed26602e01f438707717d184be0b798c74ea9`
  (1723 backend tests; run 35146515639). Final exact provider/source-boundary hardening is
  included in the follow-up PR #80 HEAD validation. Paper posture unchanged.
- Recommended model: Grok 4.6
- ADR: AT-ADR-021 · Docs: `docs/market_source_contracts.md`

### AT-044 — Phase 6 contract freeze (observations, fusion, candidates)
- Priority: P0 · Status: DONE · Dependencies: AT-041 Phase 5 market
  contracts; Phase 3 compiled setup identity · Risk: Medium (identity authority)
- Safety classification: Paper-safe / contracts only; no evaluator, persistence,
  watcher, Telegram, execution, or live trading
- Goal: Freeze typed immutable Phase 6 domain contracts and
  `CanonicalEvidenceWindowV1` hashing so parallel agents share one identity
  system. Reuse Phase 5 `PublicMarketObservation` and Phase 3
  `CompiledSetupDefinition` / `TradeDirection` / `Timeframe`.
- Branch: `cursor/phase6-contract-freeze`
- Deliverables: `app.signal_fusion`; tests in
  `backend/tests/test_phase6_signal_fusion_contracts.py` and
  `backend/tests/test_phase6_contract_hardening.py`. Hardening covers
  market-identity integrity, policy-selected tenant assertions, canonical
  set semantics, and revision-aware observation identity. No Alembic, no
  evaluator, no adapter implementations.
- Validation: Merged to `main` via PR #84 (`d8193ec`) and golden fixture
  corpus PR #82 (`addf5ef`). Paper posture unchanged.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-024

### AT-045 — Phase 6 deterministic fusion evaluator (setup truth only)
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-044 Phase 6 contract
  freeze · Risk: Medium (setup-truth authority)
- Safety classification: Paper-safe / evaluator only; no PostgreSQL, Alembic,
  watcher, Telegram, execution, or live trading
- Goal: Implement the deterministic first-slice fusion evaluator that consumes
  frozen `FusionPolicy`, `AssessmentCommand`, `CanonicalEvidenceWindowV1`, and
  Phase 5 evidence and emits authoritative `SetupAssessment` for
  “Bearish Liquidity Sweep with CVD Divergence and Aggressive Sell Imbalance
  at 4h Resistance” on BTCUSDT perpetual 15m/4h.
- Branch: `cursor/phase6-deterministic-evaluator-0069` (source PR #87);
  integrated on `cursor/phase6-evaluator-candidate-integration`
- Deliverables: `app.signal_fusion.evaluator.evaluate_setup`; synthetic matrix
  in `backend/tests/test_phase6_fusion_evaluator.py`. No Candidate persistence,
  no PR 84 contract semantic changes.
- Validation: evaluator suite + Phase 5 + Phase 6 contract tests; full backend
  pytest; ruff; mypy `--strict` on `src/app.signal_fusion`; GitHub CI.
  Draft integration PR only; do not merge.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-025

### AT-046 — Phase 6 candidate lifecycle service (in-memory authority)
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-044 Phase 6 contract
  freeze · Risk: Medium (identity authority)
- Safety classification: Paper-safe / in-memory application service; no
  PostgreSQL, Alembic, watcher, Telegram, execution, or live trading
- Goal: Implement canonical Candidate authority: idempotent creation from
  CONFIRMED_SETUP + exact CanonicalEvidenceWindowV1 + tenant-owned
  CompiledSetupDefinition; uniqueness via CandidateUniquenessTuple;
  append-only transitions; terminal non-resurrection; tenant isolation;
  organization-scoped creation idempotency and candidate-scoped transition
  idempotency. PaperValidationCandidate remains a downstream consumer only.
- Branch: `cursor/phase6-candidate-lifecycle-service-1c4d` (source PR #86);
  integrated on `cursor/phase6-evaluator-candidate-integration`
- PR: https://github.com/Fejjii/AlphaTrade-AI/pull/86 (source; do not merge)
- Deliverables: `app.signal_fusion.lifecycle`, `ports`, `memory`; tests in
  `backend/tests/test_phase6_candidate_lifecycle.py`. No fusion evaluator
  coupling, no Alembic, no PostgreSQL adapter.
- Validation: lifecycle tests + Phase 6 contract tests; full backend pytest;
  ruff; mypy `--strict` on `src/app.signal_fusion`; GitHub CI.
  Draft integration PR only; do not merge.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-026

### AT-047 — Phase 6 evaluator + candidate runtime foundation integration
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-044, AT-045, AT-046,
  golden fixture corpus on `main@addf5ef` · Risk: Medium (identity composition)
- Safety classification: Paper-safe / in-memory runtime foundation; no
  PostgreSQL, Alembic, watcher, Telegram, eligibility, TradePlan, execution,
  frontend, or live trading
- Goal: Produce one clean Phase 6 runtime foundation containing deterministic
  setup evaluation, canonical candidate lifecycle authority, and the already
  merged golden fixtures. Combined flow: canonical evidence → CONFIRMED_SETUP
  → exactly one ACTIVE candidate; duplicate semantic evaluation converges.
- Branch: `cursor/phase6-evaluator-candidate-integration`
- Deliverables: integrated `app.signal_fusion` evaluator + lifecycle; combined
  tests in `backend/tests/test_phase6_evaluator_candidate_flow.py`. Do not
  overwrite `backend/tests/fixtures/phase6_first_slice/`.
- Validation: golden fixture suite, Phase 5 market suite, Phase 6 contract
  suite, evaluator suite, candidate lifecycle suite, combined flow tests,
  full backend pytest, ruff, mypy `--strict` on `src/app.signal_fusion`,
  GitHub CI. Draft PR only; do not merge.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-027

### AT-048 — Phase 6 deterministic ActionEligibility (paper action gate)
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-047 evaluator +
  candidate runtime foundation · Risk: Medium (safety-critical gating)
- Safety classification: Paper-safe / in-memory application service; no
  PostgreSQL, Alembic, watcher, Telegram, TradePlan, execution, or live trading
- Goal: Implement the deterministic ActionEligibility service. SetupAssessment
  remains market truth. Eligibility decides whether a confirmed canonical
  Candidate may proceed toward paper TradePlan creation from account, portfolio,
  risk, safety, stale action evidence, paper configuration, and a first-slice
  20 bps cross-venue basis gate. Kill switch dominates. Live trading cannot
  make a result executable.
- Branch: `cursor/phase6-action-eligibility-078e`
- Deliverables: `app.signal_fusion.action_eligibility`; tests in
  `backend/tests/test_phase6_action_eligibility.py`. Frozen
  `ActionEligibilityState` remains `ELIGIBLE | BLOCKED | EXPIRED`. No TradePlan,
  no venue APIs, no Alembic.
- Validation: Phase 1 risk/safety regressions, Phase 6 contracts, evaluator,
  candidate lifecycle, new ActionEligibility tests, full backend pytest, ruff,
  mypy `--strict` on `src/app.signal_fusion`, GitHub CI. Draft PR to main;
  do not merge.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-028

### AT-049 — Watcher to Phase 6 fusion wiring (first slice)
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-042, AT-047 / PR #88
  head `046929cbe612e1bafc2e87ebe794d9b59300ec35` · Risk: Medium
  (orchestration identity)
- Safety classification: Paper-safe / orchestration wiring only; watcher
  remains disabled; no scheduler, Telegram, TradePlan, execution, Alembic,
  or live trading
- Goal: Connect Watcher scan → canonical market evidence →
  CanonicalEvidenceWindowV1 → evaluate_setup → SetupAssessment → canonical
  Candidate only when CONFIRMED_SETUP. Manual and worker evaluation must
  converge for identical semantic evidence. First slice: Bearish Liquidity
  Sweep with CVD Divergence and Aggressive Sell Imbalance at 4h Resistance,
  BTCUSDT perpetual, 15m trigger, 4h context.
- Branch: `cursor/phase6-watcher-fusion-wiring`
- Deliverables: `WatcherFusionEvaluationService` as the single evaluation
  boundary; integration tests for parity, gating, fencing, tenant isolation,
  and crash/retry convergence. Do not redesign WatcherStore, Phase 5/6
  contracts, the evaluator, or candidate lifecycle authority.
- Validation: watcher tests, Phase 5, Phase 6 contracts/evaluator/lifecycle,
  new integration tests, full backend pytest, ruff, mypy `--strict` on
  `src/app/watcher` and `src/app/signal_fusion`, GitHub CI. Draft PR only;
  do not merge.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-029
  Wave B integration note: original source PR claimed `AT-048` / `AT-ADR-028`;
  those IDs were already used by ActionEligibility, so this task is `AT-049`.

### AT-050 — Phase 6 Candidate Telegram alert foundation
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-043 Telegram security
  protocol; AT-046/AT-047 canonical Candidate · Risk: Medium (identity +
  authorization boundary)
- Safety classification: Paper-safe / Telegram disabled; no webhook, no
  execution, no PostgreSQL adapter, no Alembic
- Goal: Bind canonical Candidate events to deterministic CandidateAlertIntent
  identity and the existing Telegram outbox/security contracts. APPROVE is
  authorization intent only and never executes. REJECT/SKIP use typed
  Candidate transitions. REDUCE_RISK must not mutate Candidate. CLOSE stays
  unavailable. EXECUTE_PAPER_PLAN stays outside Telegram.
- Branch: `cursor/phase6-telegram-candidate-alerts-0960`
- Deliverables: `app.candidate_alerts`; tests in
  `backend/tests/test_phase6_candidate_telegram_alerts.py`; docs
  `docs/phase6_candidate_telegram_alerts.md`.
- Validation: Candidate alert tests, Telegram protocol tests, Phase 6
  Candidate tests, full backend pytest, ruff, mypy `--strict`, GitHub CI.
  Draft PR to main only; do not merge.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-030
  Wave B integration note: original source PR claimed `AT-048` / `AT-ADR-028`;
  those IDs were already used, so this task is `AT-050`.

### AT-051 — Phase 6 canonical Candidate PostgreSQL persistence
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-046/AT-047 Candidate
  authority; AT-049 Watcher fusion wiring; PR #92 remaining fencing race
  · Risk: Medium (identity + fencing)
- Safety classification: Paper-safe / PostgreSQL adapter only; Watcher,
  Telegram, and live trading remain disabled; not wired into FastAPI or workers
- Goal: Production-grade PostgreSQL `CandidateRepository` matching the existing
  port. Persist canonical Candidate projections and append-only transitions.
  Preserve deterministic identity, uniqueness, tenant isolation, idempotency,
  terminal non-resurrection, replay convergence, and conflict detection.
  Worker-originated Candidate persistence must be protected by current lease
  and fencing authority in the same database transaction.
- Branch: `cursor/phase7-candidate-persistence-5115`
- Deliverables: `app.persistence.candidate_postgres`, Candidate ORM,
  Alembic `4fd8c1a90b27`, Watcher persist fence bind, tests in
  `backend/tests/test_phase6_candidate_postgres.py`.
- Validation: focused Candidate/Postgres/fencing tests; full backend pytest;
  ruff; mypy `--strict`; Alembic upgrade/downgrade and single head; GitHub CI.
  Draft PR only; do not merge.
- Recommended model: Cursor Grok 4.6
- ADR: AT-ADR-031

### AT-052 — Phase 7 canonical TradePlanRevision application layer
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-046/AT-047 Candidate
  authority; AT-048 ActionEligibility; AT-051 Candidate PostgreSQL; Phase 1
  TradePlanRevision hash contract
  · Risk: Medium (plan identity + immutability)
- Safety classification: Paper-safe / application service; Watcher, Telegram,
  Journal, execution dispatch, frontend, and live trading remain disabled
- Goal: Canonical flow Candidate → ActionEligibility → TradePlanRevision →
  approval → paper execution, with this slice owning plan creation only. Only
  ACTIVE + ELIGIBLE may insert; lineage and tenant scope must match; semantic
  content immutable; identical requests converge; conflicting idempotency
  fails closed; PLAN_CREATED only after successful insert; PVC cannot mint
  canonical plans; approval cannot change executable semantics.
- Branch: `cursor/phase7_tradeplan_canonical` (source PR #93); integrated on
  `cursor/phase7_integration`
- Deliverables: `CanonicalTradePlanService`, `CanonicalTradePlanStore`,
  lineage envelope. Source PR claimed `AT-051` / `AT-ADR-031`; those IDs were
  already used by Candidate PostgreSQL, so this task is `AT-052`.
- Validation: focused canonical tests, Phase 1 planning/approval tests,
  Phase 6 candidate/eligibility tests, full backend pytest, ruff, mypy
  `--strict`, GitHub CI. Draft PR to main; do not merge.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-032

### AT-053 — Phase 7 learning attribution (canonical lifecycle → learning)
- Priority: P0 · Status: IN_PROGRESS · Dependencies: Phase 4 canonical journal
  projector; Phase 6 Candidate / SetupAssessment contracts · Risk: Medium
  (lineage / learning integrity)
- Safety classification: Paper-safe / record-only; no execution, Watcher,
  Telegram, frontend, Alembic, or live trading
- Goal: Connect SetupAssessment → Candidate → TradePlan → paper execution →
  JournalTrade → outcome → strategy/pattern stats → learning evidence without a
  second trading authority. Reuse `JournalLifecycleProjector`. REJECT/SKIP never
  create executed trade outcomes. Distinguish planned setup quality from
  execution quality and trader behavior. LLMs may explain, not rewrite facts.
- Branch: `cursor/phase7_learning_attribution` (source PR #95); integrated on
  `cursor/phase7_integration`
- Deliverables: `app.learning_attribution`;
  `JournalLifecycleLearningService`; sticky `payload.lineage`; lesson/analytics/RAG
  adapters; tests in
  `backend/tests/test_learning_attribution.py` and
  `backend/tests/test_journal_lifecycle_lineage.py`; docs
  `docs/phase7_learning_attribution.md`. Source PR claimed `AT-051` /
  `AT-ADR-031`; those IDs were already used by Candidate PostgreSQL, so this
  task is `AT-053`.
- Validation: attribution tests, journal lifecycle tests, learning tests, full
  backend pytest, ruff, mypy `--strict` on the new package plus journal lifecycle
  modules, GitHub CI. Draft PR only; do not merge.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-033

### AT-054 — Phase 7 canonical TradePlan / ActionEligibility PostgreSQL binding
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-051 Candidate PostgreSQL;
  AT-052 canonical TradePlan application layer
  · Risk: Medium (identity, FKs, append-only history)
- Safety classification: Paper-safe / PostgreSQL adapter only; Watcher, Telegram,
  and live trading remain disabled; not wired into FastAPI or workers
- Goal: Close the PR 93 persistence gap after Candidate migration `4fd8c1a90b27`.
  Durable ActionEligibility with deterministic identity and append-safe revision
  history. Bind canonical TradePlanRevision to canonical Candidate authority
  without reinterpreting legacy PaperValidationCandidate ids. Bind setup identity
  to tenant-owned CompiledSetupDefinition. Persist canonical lineage without
  changing CanonicalTradePlanContentV1. Organization-scoped uniqueness and
  idempotency. Deterministic candidate-based plan root. Approval still binds
  exact immutable revision + content hash. Execution remains outside this wave.
- Branch: `cursor/phase7_integration`
- Deliverables: Alembic `c9e2b4a1d078`, `PostgresActionEligibilityStore`,
  `PostgresCanonicalTradePlanStore`, discriminator columns, lineage side table,
  tests in `backend/tests/test_phase7_*_postgres.py`.
- Validation: focused eligibility/plan/alembic tests; full backend pytest; ruff;
  mypy `--strict`; Alembic upgrade/downgrade/reupgrade and single head; GitHub CI.
  Draft PR only; do not merge.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-034

### AT-055 — Phase 8 learning persistence (canonical attribution → queryable intelligence)
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-053 Phase 7 learning
  attribution; Phase 4 canonical journal projector
  · Risk: Medium (lineage / learning integrity / schema)
- Safety classification: Paper-safe / PostgreSQL adapter and query services;
  FastAPI/runtime wiring owned by later Phase 8 slices
- Goal: Persist canonical learning attribution in PostgreSQL. Preserve immutable
  lineage SetupAssessment → Candidate → TradePlan → paper execution →
  JournalTrade → outcome. Duplicate facts converge; conflicting identities and
  cross-tenant writes fail closed. REJECT/SKIP never become executed outcomes.
  Separate setup quality, execution quality, risk adherence, trader behavior,
  and outcome. Produce deterministic strategy/pattern statistics and
  human-versus-system comparison. Support future demo trade learning as a
  separate venue cohort. Learning never rewrites historical market truth. LLM
  narrative remains explanation only. Facts are consumable by analytics and RAG
  without competing journal/lesson authorities.
- Branch: `cursor/phase8_learning_persistence-843e` (source); integrated on
  `cursor/phase8_final_integration`
- Deliverables: Alembic `d4f7a2c8e901`, `PostgresAttributionStore`,
  `LearningQueryService`, journal lineage query columns, tests in
  `backend/tests/test_phase8_learning_persistence.py`, docs
  `docs/phase8_learning_persistence.md`.
- Validation: Migration cycle, idempotency, conflicts, tenant isolation,
  attribution correctness, strategy aggregation, RAG fact boundaries; full
  backend pytest; ruff; mypy `--strict`; GitHub CI. Source PR #97.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-035

### AT-056 — Phase 8 canonical PAPER runtime execution
- Priority: P0 · Status: IN_PROGRESS · Dependencies: AT-051 Candidate PostgreSQL;
  AT-052 canonical TradePlan application layer; AT-054 PostgreSQL binding;
  AT-055 learning persistence
  · Risk: Medium (execution safety, lineage, idempotency)
- Safety classification: Paper-safe / runtime wiring; Watcher, Telegram, and
  live trading remain disabled; no real exchange mutation
- Goal: Wire Phase 7 PostgreSQL Candidate, ActionEligibility, and canonical
  TradePlan adapters into FastAPI and workers. Complete the canonical PAPER
  lifecycle: Evidence → SetupAssessment → Candidate → ActionEligibility →
  TradePlanRevision → approval → EXECUTE_PAPER_PLAN → journal. CandidateLifecycleService
  remains sole Candidate authority. Execution requires the exact approved
  immutable TradePlanRevision. Duplicate requests converge. Stale/rejected/
  expired/mismatched/modified plans fail closed. Risk engine BLOCK and kill
  switch stay final. `canonical_plan_root` is never ProposalService trading
  authority.
- Branch: `cursor/phase8_runtime_execution` (source); integrated on
  `cursor/phase8_final_integration`
- Deliverables: `app.runtime.canonical`, `CanonicalPaperExecutionService`,
  `POST /execution/paper-plan`, ProposalService filter, journal projection
  source `canonical_paper_execution`, tests
  `backend/tests/test_phase8_*.py`, docs `docs/phase8_runtime_execution.md`.
  No Alembic.
- Validation: adversarial execution tests (restart/idempotency, tenant
  isolation, stale state, kill switch, risk rejection, duplicates, journal);
  full backend pytest; ruff; scoped `mypy --strict`; GitHub CI. Source PR #99
  claimed AT-055; remapped to AT-056 on the RC branch.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-036

### AT-057 — Canonical paper decision frontend
- Priority: P1 · Status: DONE · Dependencies: AT-040 design system;
  AT-055 learning persistence; AT-056 runtime execution · Risk: Medium
  (UX honesty vs unbound canonical HTTP)
- Safety classification: Frontend / paper-only; no live execution control
- Goal: User-facing canonical decision workflow: market assessment → candidate
  → eligibility → TradePlan → human approval → paper execution → outcome →
  learning. Reuse design system. Do not invent backend authority. Bind
  canonical TradePlan execution to `POST /execution/paper-plan`.
- Branch: `cursor/phase8_canonical_frontend` (source); integrated on
  `cursor/phase8_final_integration`
- Deliverables: `/decision` screens, typed contracts for canonical HTTP,
  frontend API clients for paper-plan + canonical reads + learning queries,
  tests, docs `docs/redesign/phase8_canonical_frontend.md`.
- Validation: frontend lint, typecheck, unit tests, build, relevant e2e,
  GitHub CI. Source PR #98 claimed AT-055; remapped to AT-057 on the RC
  branch.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-037

### AT-058 — Phase 8 final integration release candidate
- Priority: P0 · Status: DONE · Dependencies: AT-055, AT-056, AT-057
  · Risk: Medium (execution binding, learning durability, authority isolation)
- Safety classification: Paper-only integration; Watcher, Telegram, and live
  trading remain disabled; no deploy
- Goal: Independently review and integrate PR97 + PR99 + PR98. Bind frontend
  canonical TradePlan execution to `POST /execution/paper-plan`. Wire durable
  Postgres learning attribution and canonical read/query APIs. Keep one Alembic
  head. Do not merge `main`. Do not deploy.
- Branch: `cursor/phase8_final_integration`
- Deliverables: remapped governance IDs, `/canonical/*` reads,
  `PostgresAttributionStore` runtime hook, frontend paper-plan binding,
  `backend/tests/test_phase8_canonical_workflow.py`.
- Validation: full backend pytest, frontend tests, lint, typecheck, build,
  ruff, scoped mypy, Alembic cycle, deployment-safety, evaluation, e2e,
  Docker build, GitHub CI.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-038

### AT-059 — Final backend hardening (release residues)
- Priority: P0 · Status: DONE · Dependencies: AT-058 Phase 8 final integration
  · Risk: Medium (learning integrity, claim-time risk, deployment safety)
- Safety classification: Paper-only; Watcher, Telegram, and live trading remain disabled;
  no deploy
- Goal: Close remaining medium backend residues before release. Canonical learning
  attribution must not silently skip after ALLOW. Claim-time risk stays
  `evaluate_claim_predicate` plus persisted ActionEligibility (do not wire unused
  `PaperExecutionRiskGate` as a second authority). Approval/execution/journal/learning
  stay one unit of work under failure. Restart/duplicate converge. Canonical reads stay
  tenant-safe. Paper-only runtime and deployment safety keep accidental real trading
  impossible.
- Branch: `cursor/final_backend_hardening` (source); integrated on
  `cursor/final_release_integration-c461`
- Validation: adversarial hardening tests; source GitHub CI run 35464006608
  success at `60d5ef9` (backend, frontend, deployment-safety, evaluation,
  docker-build, e2e-smoke). Draft source PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/102 — do not merge.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-039

### AT-060 — Finish canonical decision UX (bind GET APIs, paper-plan only)
- Priority: P0 · Status: DONE · Dependencies: AT-057, AT-058 · Risk: Medium
  (UX honesty / tenant isolation)
- Safety classification: Frontend + ProposalService firewall; paper-only
- Goal: Bind `/decision` to canonical GET APIs (candidates, setup assessments,
  eligibility, execution receipts, learning records, strategy stats). Remove
  stale unbound copy. Canonical decision execution uses
  `POST /execution/paper-plan` only. PVC/legacy proposals stay compatibility
  views. ProposalService checks tenant scope before `canonical_plan_root`
  rejection (no existence oracle).
- Branch: `cursor/final_canonical_ux-1b0c` (source); integrated on
  `cursor/final_release_integration-c461`
- Validation: frontend lint/typecheck/1155 tests/build; Chromium e2e 24 passed /
  13 skipped; source PR #101 exact-head CI run 35462481756 success at `3fd8a0a`.
  Integrated on `cursor/final_release_integration-c461`. Source PR #101 claimed
  AT-059; remapped to AT-060. Draft PR only; do not merge.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-037

### AT-061 — Final synthetic staging readiness
- Priority: P0 · Status: DONE · Dependencies: AT-058 Phase 8 RC on `main@c39dca6`
  · Risk: Medium (ops + safety locks)
- Safety classification: Paper-only staging readiness; Watcher, Telegram, and live
  trading remain disabled; no real exchange credentials; no merge
- Goal: Confirm the canonical architecture can deploy to paper staging. Document
  required env vars. Enforce paper mode, Watcher off, Telegram off, real trading
  impossible. Add synthetic HTTP smoke for auth, Candidate reads, eligibility,
  TradePlan approval, paper execution, journal, learning, strategy stats, decision
  frontend, kill switch, risk BLOCK, and cross-tenant rejection. Deploy only if
  cloud credentials already exist; otherwise stop at the human boundary.
- Branch: `cursor/final_staging_readiness` (source); integrated on
  `cursor/final_release_integration-c461`
- Deliverables: staging safety locks, `/health` posture flags, canonical smoke
  script + pytest, `docs/RELEASE_READINESS.md`, rollback chain notes.
- Validation: source PR #103 exact-head CI run 35465464233 success at `24133a1`.
  Staging deploy remains an operator/credential step, not this task. Source PR
  #103 claimed AT-059 / AT-ADR-039; remapped to AT-061 / AT-ADR-040. Draft PR
  only; do not merge.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-040

### AT-062 — Final paper-release candidate integration
- Priority: P0 · Status: DONE · Dependencies: AT-059, AT-060, AT-061
  · Risk: Medium (overlap of safety locks, UX binding, staging smoke)
- Safety classification: Paper-only integration; Watcher, Telegram, and live
  trading remain disabled; no deploy; no merge to main
- Goal: Independently review and integrate PR102 + PR101 + PR103 on
  `main@c39dca6`. Preserve fail-closed learning, canonical GET/paper-plan UX,
  and synthetic staging smoke. Resolve overlapping `deployment_safety` and
  governance IDs semantically. Produce `docs/FINAL_RELEASE_READINESS.md`.
- Branch: `cursor/final_release_integration-c461`
- Validation: backend pytest 2271 collected, exit 0; ruff check/format 765 files;
  mypy `--strict` 29 affected files; Alembic single head `d4f7a2c8e901` with
  upgrade/downgrade/reupgrade; evaluation 16/16 + 5/5 + 7/7; frontend lint/
  typecheck/1155 tests/build; Chromium e2e 24 passed / 13 skipped; canonical
  smoke self-check + focused 3 smoke tests; GitHub CI run 35466201940 success
  (backend, frontend, deployment-safety, evaluation, docker-build, e2e-smoke).
  Draft PR https://github.com/Fejjii/AlphaTrade-AI/pull/104 — do not merge;
  do not deploy. Report `docs/FINAL_RELEASE_READINESS.md`.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-041

### AT-063 — Intelligence integration of PR109, PR110, and PR111
- Priority: P0 · Status: IN_PROGRESS · Dependencies: PR #109, PR #110, PR #111
  on `main@20d2cac` · Risk: High (evaluation, evidence identity, confirmation)
- Safety classification: Paper-only integration; Watcher, Telegram, and live
  trading remain disabled; no deploy; no merge to main
- Goal: Independently review and integrate PR109 (canonical strategy policy),
  PR110 (canonical evidence pipeline), and PR111 (strategy conversations).
  Close verified correctness gaps: evidence identity, Watcher
  `executable_policy`, freshness vs candle close, conversation-to-pattern
  preview, confirmation safety. Keep one Alembic head. Preserve journal
  `account_id` from PR #106.
- Branch: `cursor/intelligence_integration-1ea1`
- Validation: focused regressions, then full backend/frontend suites, lint,
  types, build, Alembic/PostgreSQL, safety, evaluations, relevant browser
  tests, exact-HEAD GitHub CI. Draft PR only; do not merge; do not deploy.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-046

### AT-064 — Canonical live read-only USD-M evidence pipeline
- Priority: P0 · Status: DONE · Dependencies: PR #108 market contracts on
  `main@20d2cac` · Risk: Medium (freshness honesty)
- Safety classification: Paper-only read path; Watcher, Telegram, and live
  trading remain disabled; no exchange mutation; no merge
- Goal: Assemble CanonicalEvidenceWindowV1 from existing Binance USD-M contracts
  (BTCUSDT first, multi-symbol catalog). Expose truthful current price +
  freshness on GET `/canonical/evidence`. Stop canonical UI from presenting
  frozen compatibility prices as live marks. Preserve replay fixtures.
  Do not activate Watcher.
- Branch: `cursor/live_evidence_pipeline-5b0d` (source); integrated on
  `cursor/intelligence_integration-1ea1`
- Deliverables: `app.evidence_pipeline`, catalog, canonical evidence HTTP,
  `/decision/market` honesty, fail-closed tests (fresh/stale/partial/outage/
  wrong-symbol/duplicate/restart/source/CVD/tenant).
- Validation: source PR #110 exact-head CI run 35527904094 SUCCESS at `afd4d2a`.
  Draft source PR https://github.com/Fejjii/AlphaTrade-AI/pull/110 — do not merge.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-042
- Note: Source PR #110 claimed AT-064 / AT-ADR-042; kept. Source PR #111 also
  claimed AT-064 / AT-ADR-042; remapped to AT-065 / AT-ADR-043.

### AT-065 — Persistent strategy conversation + discussion context
- Priority: P0 · Status: DONE · Dependencies: PR #107 audit · Risk: Medium
  (transcript vs strategy authority)
- Safety classification: Paper-only; no Watcher, Telegram, live trading, or
  autonomous activation
- Goal: Durable tenant-scoped conversations and messages. History survives
  restart. Chat must not become a second memory authority. Discussions may
  reference strategies, versions, journal, lessons, learning attribution, and
  statistics via existing services + RAG.
- Branch: `cursor/strategy-conversation-foundation-5d46` (source); integrated on
  `cursor/intelligence_integration-1ea1`
- Validation: `backend/tests/test_strategy_conversation_foundation.py`;
  persistence + restart + tenant 404; RAG source-type boundary tests.
  Source PR #111 exact-head CI run 35529286291 SUCCESS at `057b89b`.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-043
- Note: Source PR #111 claimed AT-064 (persistence) and AT-065 (discussion
  context); remapped to AT-065 on integration because AT-064 is the evidence
  pipeline.

### AT-066 — Structured proposals stay drafts until explicit confirmation
- Priority: P0 · Status: DONE · Dependencies: AT-065 · Risk: High
  (silent mutation of strategy authority)
- Safety classification: Confirmation-gated version fork; no compile/activation
  on confirm
- Goal: AI may explain, challenge, compare, and propose. Every mutation needs
  explicit confirmation. Provenance links conversation → proposal → version.
  Strategy Lab conversational UI + API. Confirmation safety must check proposal
  identity, content hash, target strategy, and captured parent version.
- Branch: `cursor/strategy-conversation-foundation-5d46` (source); integrated on
  `cursor/intelligence_integration-1ea1`
- Validation: confirm, reject, duplicate confirm, lineage, prompt-injection
  mutation attempts; concurrent confirmation races.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-044
- Note: Source PR #111 claimed AT-066 / AT-ADR-042; ADR remapped to AT-ADR-044.

### AT-067 — Canonical strategy evaluation policy (first-slice adapter)
- Priority: P0 · Status: DONE · Dependencies: AT-066, PR #107, PR #108
  · Risk: High (evaluation authority)
- Safety classification: Paper-only; no Watcher enablement; no Telegram; no live trading
- Goal: One deterministic evaluation policy boundary: approved immutable
  `UserStrategyVersion` → `CompiledSetupDefinition` → canonical evidence →
  `evaluate_canonical_strategy` → `SetupAssessment`. `evaluate_setup` remains
  sole market-truth function. First-slice predicates become a compatibility
  adapter. Drafts and unsupported rules fail closed. Watcher (disabled) and
  paper-validation canonical entry call the same boundary. No Candidate mint
  from read-projection placeholder IDs.
- Branch: `cursor/canonical-strategy-policy-82f1` (source); integrated on
  `cursor/intelligence_integration-1ea1`
- Validation: 18 AT-067 tests (determinism, version change, unsupported rule,
  stale evidence, strategy/evidence mismatch, duplicate evaluation, lineage,
  compatibility parity, tenant isolation, no-LLM, Watcher/paper boundary).
  Source PR #109 exact-head CI run 35528565992 SUCCESS at `872f5de`. Draft PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/109 — do not merge independently.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-045
- Completion evidence: feat commit `4d5bfb9`; source PR #109; remapped from
  source AT-ADR-043. Source PR #111 left AT-067 as TODO; closed by integrating
  PR #109.

### AT-069 — Live read-only perpetual market monitoring
- Priority: P0 · Status: DONE · Dependencies: AT-064, Phase 5 contracts
  · Risk: Medium (freshness honesty + stream identity)
- Safety classification: Paper-only read path; Watcher, Telegram, and live
  trading remain disabled; no exchange mutation; no merge
- Goal: Continuously provide trustworthy Binance USD-M perpetual evidence
  (BTCUSDT first, catalog-extensible) with current price, OHLCV, trade stream,
  CVD, coverage, freshness, source identity, provider status, reconnect/backoff,
  rate-limit handling, and gap detection. Never present replay, demo-seed, or
  compatibility snapshots as the current live price.
- Branch: `cursor/live-market-monitoring-cc4d`
- Deliverables: `app.market_monitor`, `GET /canonical/market-status`,
  decision/market + /market honesty, fail-closed stream tests.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-048
- Completion evidence: HEAD `69371ee` on `cursor/live-market-monitoring-cc4d`;
  draft PR https://github.com/Fejjii/AlphaTrade-AI/pull/118. Local: monitor
  25/25; full backend 2219 passed / 181 skipped; frontend lint/typecheck;
  1171 unit tests; Next build; E2E 26 passed / 13 skipped. Watcher, Telegram,
  and live trading stay off. Do not merge or deploy.

### AT-068 — Durable setup lifetime + canonical AUTO_PAPER authority
- Priority: P1 · Status: IN_PROGRESS · Dependencies: AT-067, intelligence
  acceptance review P1s · Risk: High (lifetime identity + paper mint authority)
- Safety classification: Paper-only; no Watcher enablement; no Telegram; no live trading
- Goal: Persist setup-lifetime pins so restart reconstructs the same trigger
  and expiry; remove `PaperBotEngine` as AUTO_PAPER minting authority. Automated
  paper trades consume persisted APPROVED/ACTIVE compiled policy → canonical
  evidence → `evaluate_canonical_strategy` → `CONFIRMED_SETUP` only.
- Branch: `cursor/intelligence-acceptance-final-fix-5138`
- Validation: PostgreSQL restart/migration tests; non-vacuous CONFIRMED_SETUP
  paper mint; fail-closed draft/stale/expired/wrong-tenant/wrong-hash; ruff;
  mypy; full backend; frontend; e2e; exact-head CI. Draft PR only; no merge.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-047

### AT-070 — Paper-only continuous Watcher runtime
- Priority: P0 · Status: DONE · Dependencies: AT-042, AT-064, AT-067, AT-068, AT-069
  · Risk: High (continuous worker, leases, Candidate persist)
- Safety classification: Paper monitoring only; staging/production Watcher flags stay
  false; no Telegram; no live orders; no real exchange credentials
- Goal: Wire the missing continuous worker: tenant-scoped approved compiled strategy
  → live read-only market evidence → `WatcherOrchestrator` scan →
  `evaluate_canonical_strategy` → persist Candidate only on `CONFIRMED_SETUP`.
  Reuse existing orchestrator, Postgres store, leases/fencing, canonical assembler,
  `resolve_executable_strategy_policy`, CandidateLifecycleService, and durable
  setup lifetime. BTCUSDT first; configurable symbols; bounded polling; single
  active worker per scan scope.
- Branch: `cursor/watcher_paper_runtime-5455` (source); remapped from source AT-069
- Validation: 22 paper-runtime tests (concurrent, lease takeover, restart replay,
  duplicate scan, stale, outage, wrong tenant, wrong lineage, CONFIRMED_SETUP,
  WATCH/NO_SETUP, expiry, kill switch); ruff check/format; full backend pytest
  exit 0 (Postgres-backed tests skipped locally — no local Postgres; GitHub CI
  has the service); frontend lint/typecheck/test/build; evaluation 16/16, 5/5,
  7/7. Draft PR only; do not merge or deploy.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-049
- Note: Source PR #120 claimed AT-069 / AT-ADR-048; remapped because AT-069 is
  the live market monitor (PR #118).
- Completion evidence: feat `1de8b60`; draft PR #120. GitHub CI run 35614998968
  failed on `test_concurrent_workers_single_lease` (StaticPool SQLite shared
  across worker threads). Follow-up isolates that test from SQLite and surfaces
  ThreadPoolExecutor exceptions; do not merge until that head is green.

### AT-071 — Watcher PAPER MONITORING operator UX + observability
- Priority: P1 · Status: DONE · Dependencies: AT-ADR-040, AT-ADR-022,
  AT-067, AT-070 · Risk: Medium (honesty of runtime status; no authority change)
- Safety classification: Paper-only observability; no Watcher enablement; no
  Telegram; no live trading; no evaluator/strategy-authority change
- Goal: Operator-facing Watcher paper-monitoring surface showing runtime
  status (`RUNNING`/`STOPPED`/`DEGRADED`/`STALE`/`BLOCKED`), symbols,
  approved strategies, last/next scan, market freshness, provider health,
  SetupAssessment lineage, candidates, block reasons, lease/worker health,
  recent errors, and paper-only posture. Typed API only; never infer
  RUNNING from frontend config; no fake activity/prices/candidates.
- Branch: `cursor/watcher_monitoring_ux-c026` (source); remapped from source AT-069
- Validation: backend projection + `/market-watcher/monitoring` 27 tests passed;
  frontend lint+typecheck+1189 tests+build pass; Watcher monitoring E2E 4/4;
  full Chromium E2E 30 passed / 13 skipped; mypy on new modules clean.
  Draft PR https://github.com/Fejjii/AlphaTrade-AI/pull/119 — do not merge
  or deploy.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-050
- Note: Source PR #119 claimed AT-069 / AT-ADR-048; remapped because AT-069 is
  the live market monitor (PR #118) and AT-070 is the paper runtime (PR #120).
- Completion evidence: feat `6572f71`, fix `9d36ee1`; Watcher stays disabled.

### AT-072 — Integrate paper Watcher stack (live market → runtime → monitoring UX)
- Priority: P0 · Status: DONE · Dependencies: AT-069, AT-070, AT-071 · Risk: High
  (evidence authority, worker safety, monitoring honesty)
- Safety classification: Paper-only integration; Watcher/Telegram/live trading stay off;
  no deploy; no source-PR merge; no Watcher activation
- Goal: Reconcile PR #118 live monitor, PR #120 paper runtime, and PR #119 monitoring UX
  onto `main@b4244f0` without merging those PRs. One evidence authority (monitor gate +
  canonical assembler). One evaluator path to CONFIRMED_SETUP Candidates. Monitoring
  reports real heartbeat/lease evidence. Freshness clocks stay separated. Fail closed on
  stale, outage, wrong tenant, wrong lineage, expired setup, and in-memory policy.
- Branch: `cursor/watcher_integration-b74b`
- Validation: focused stack 115 passed; full backend with PostgreSQL 2464 passed / 0 skipped;
  frontend lint+typecheck+1193 tests+build; Ruff check/format; strict mypy on affected
  modules; Alembic single head `c8d9e0f1a2b3`; evaluation 16/16, 5/5, 7/7; Chromium E2E
  30 passed / 13 skipped; deployment safety 60 passed; Docker image build; GitHub CI
  run 35627618727 success on `cc226f7`. Draft PR only; do not merge or deploy.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-051
- Completion evidence: feat `2bb9c40`, fix `cc226f7`; draft PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/121. Watcher, Telegram, and live trading
  stay off. Do not merge, deploy, or activate Watcher.

### AT-073 — Telegram paper interaction layer
- Priority: P0 · Status: DONE · Dependencies: AT-043, AT-072, candidate-alert
  foundation · Risk: High (Telegram must never become trading authority)
- Safety classification: Paper-only interaction; Telegram stays disabled by default;
  no webhook; no Watcher activation; no live trading; no deploy; no merge
- Goal: Watcher meaningful event → durable notification → Telegram alert → bound
  discussion of evidence/strategy/Candidate/risk. Mutating paper actions stay
  identity-bound confirmation gated. Support Watcher alerts, Candidate alerts,
  strategy discussion, market context, paper trade status, journal outcome, and
  learning summary. Deduplicate, persist delivery, retry safely, isolate tenants,
  rate-limit, audit, recover after restart.
- Branch: `cursor/telegram_paper_agent-aac1` (cloud suffix; requested
  `cursor/telegram_paper_agent`)
- Validation: focused Telegram/paper-agent + protocol + Candidate-alert tests
  passed; full backend pytest 2497 passed / 0 skipped; ruff check/format;
  strict mypy 21 affected files; frontend lint+typecheck+1193 tests+build;
  evaluation 16/16, 5/5, 7/7; Chromium E2E 30 passed / 13 skipped;
  deployment-safety 60 passed; smoke-gate self-checks; GitHub CI run
  35658947838 success on `aa75c04`. Alembic single head `d9e0f1a2b3c4`.
  Draft PR only; do not merge or deploy.
- Recommended model: Cursor Grok 4.6 Extra High
- ADR: AT-ADR-052
- Completion evidence: feat `aa75c04`; draft PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/124. Telegram, Watcher, and live
  trading stay off. Do not merge, deploy, or enable Telegram.
- Note: Does not enable `TELEGRAM_INTERACTION_ENABLED`, Watcher
  `PERSIST_AND_NOTIFY`, or live trading. `EXECUTE_PAPER_PLAN` remains unavailable
  on Telegram.


