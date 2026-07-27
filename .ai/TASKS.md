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

### AT-040 — Premium design-system foundation (Phase A) + navigation/app shell (Phase B) + Phase C daily workflows
- Priority: P1 · Status: IN_PROGRESS (Phase A + B + C1 + C2 + C3A + C3B1 DONE) · Dependencies: AT-039 · Risk: Low (frontend-only)
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
- Phase C remaining: Phase C3B2+ Knowledge redesign (unstarted);
  Portfolio/risk split; analytics/charts (Phase D+).

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
