# AlphaTrade AI — Decisions (ADR log)

Durable, append-only architecture/workflow decisions. IDs: `AT-ADR-XXX`.

---

## AT-ADR-001 — Adopt private `.ai/` collaboration + iCloud handoff workflow
- **Date:** 2026-07-19
- **Status:** Accepted
- **Context:** Standardize the ChatGPT ↔ Cursor workflow already used for OnePilot AI.
- **Decision:** Add a version-controlled `.ai/` layer and Cursor project rules, plus
  per-session `HANDOFF.md` + `CHANGELOG_SESSION.md` (gitignored) and a content-aware macOS
  iCloud sync (script + LaunchAgent) that mirrors only those generated handoff docs.
- **Consequences:** Consistent, clone-portable handoffs; no application-code or Git-history
  changes; generated handoff artifacts never committed.

## AT-ADR-002 — Version-control governance; keep generated handoffs private
- **Date:** 2026-07-19
- **Status:** Accepted
- **Context:** Durable governance (`.ai/`, `.cursor/rules/`) must reach every clone, but
  per-session handoffs contain evolving state and should not pollute Git history.
- **Decision:** Track `.ai/` and `.cursor/rules/` in Git. Keep `HANDOFF.md`,
  `CHANGELOG_SESSION.md`, and `*.local.md` gitignored. The generated handoffs are
  mirrored only to iCloud via `sync-alphatrade-ai-handoff.sh` (two lightweight docs).
- **Consequences:** A fresh clone receives the AI instructions and Cursor rules; the
  repo working tree is the source of truth for handoffs and iCloud is a verified mirror.

## AT-ADR-003 — Preserve paper-only trading posture as an invariant
- **Date:** 2026-07-19
- **Status:** Accepted (pre-existing, reaffirmed)
- **Context:** Safety-critical trading system.
- **Decision:** `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`,
  `EXCHANGE_MODE=paper_internal`, `PROVIDER_MODE=fallback` (staging) are invariants.
  Any change requires a separate, explicitly authorized task.
- **Consequences:** Enforced in `deployment_safety.py` / `exchange_safety.py` and CI.

## AT-ADR-004 — Adopt Master Workflow v2.0 as the authoritative standard
- **Date:** 2026-07-19
- **Status:** Accepted (supersedes the workflow portions of AT-ADR-001/002)
- **Context:** A consolidated v2.0 standard (`ALPHATRADE_AI_MASTER_WORKFLOW.md`) unifies the
  earlier catch-up prompt and mobile-blocker addendum into one governance document.
- **Decision:** Save it as `.ai/MASTER_WORKFLOW.md` and make it authoritative from `.ai/MASTER.md`.
  Adopt the five-status model (`IN_PROGRESS`, `REVIEW_REQUIRED`, `BLOCKED`, `FAILED`, `READY`;
  no `DRAFT`), the Mobile Status block + Schema Version 2.0 metadata, the normalized
  `Source File SHA256` self-hash (hash of the doc with its own hash line removed), mandatory
  sync at every phase/blocker/review/failure, and broker/exchange modes A–D (D disabled).
  Keep `HANDOFF.md`/`CHANGELOG_SESSION.md`/`*.local.md` and `.ai/local//.ai/private/` ignored.
- **Alternatives considered:** Keep the v1 ad-hoc handoff format (rejected: no blocker/review
  states, hardcoded timezone, body-only hash); embed private material in tracked files (rejected:
  use ignored `.ai/private/` / `.ai/local/`).
- **Safety impact:** None to application behavior; strengthens blocker/review/failure handling and
  reaffirms paper-only posture and disabled real execution (mode D).
- **Consequences:** Templates and Cursor rules updated; installation stops at `REVIEW_REQUIRED`
  before any commit until a human authorizes it.
- **Validation:** `bash -n` sync script, `plutil -lint` LaunchAgent, SHA256 + `cmp`, idempotent
  second sync, secret scan of tracked governance, no app-code changes.
- **Reaffirmation (2026-07-22, AT-000B):** Supplied
  `ALPHATRADE_AI_MASTER_WORKFLOW.md` reinstalled byte-identical
  (SHA256 `4255f52c…`) as `.ai/MASTER_WORKFLOW.md`. Governance reconciled
  (`PROJECT_CONTEXT`, `MASTER.md`, trading-safety Mode A/C wording). No app-code changes.

## AT-ADR-005 — Real-money (Mode D) requires phased program; paper Criticals first
- **Date:** 2026-07-21
- **Status:** Accepted
- **Context:** AT-010 readiness audit found paper-MVP/staging readiness with Critical/High
  gaps (unauth tools, soft data degradation, under-wired risk/kill switch). A real-money
  program must not bypass paper hardening.
- **Decision:**
  1. Keep `main` paper-first; short-lived feature branches only; no long-lived live-trading branch.
  2. Close paper Critical findings (AT-011…AT-014, AT-007) before sandbox execution work.
  3. Mode D follows Phases 0–4 in `docs/AT010_real_money_safety_roadmap.md`; Phase 3–4 require
     separate explicit human authorization beyond ordinary implementation tasks.
  4. Never merge changes that weaken `EXECUTION_MODE=paper` / `ENABLE_REAL_TRADING=false` defaults.
- **Alternatives considered:** Long-lived live branch (rejected: drift + accidental merge risk);
  implement sandbox immediately (rejected: Critical paper gaps remain).
- **Safety impact:** Strengthens fail-closed path to any future capital; no live trading enabled now.
- **Consequences:** Backlog AT-011…AT-024 added; next slice is AT-011 authz.
- **Validation:** AT-010 deliverables reviewed; staging verify-safety remains paper-only.

## AT-ADR-006 — Staging/production RAG providers fail closed (AT-013)
- **Date:** 2026-07-22
- **Status:** Accepted (implementation pending review/commit authorization)
- **Context:** Silent mock LLM/embeddings and Qdrant→in-memory substitutes created
  split-brain knowledge behavior and false readiness in non-local environments.
- **Decision:**
  1. `provider_fail_closed` for `ENVIRONMENT` in `{staging, production}`.
  2. Staging/production require configured `OPENAI_API_KEY` and hosted `QDRANT_URL`;
     reject `PROVIDER_MODE=mock`.
  3. OpenAI LLM/embeddings and Qdrant refuse silent mock/memory substitutes when
     fail-closed; ingest/search raise clear `ServiceUnavailableError` (no secrets).
  4. Readiness treats critical LLM/embeddings/vector as not ready when unavailable,
     degraded+fallback, or accidentally mock.
  5. Local (and pytest default local settings) retain explicit mocks/soft fallback.
- **Alternatives considered:** Soft degrade with warnings only (rejected: false healthy);
  ban mocks in all environments (rejected: blocks offline local/dev).
- **Safety impact:** Strengthens knowledge integrity; no trading-mode change;
  `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false` preserved.
- **Consequences:** Branch `feat/at-013-rag-provider-fail-closed`; stop at
  `REVIEW_REQUIRED` before commit/push/deploy.
- **Validation:** Scoped ruff/mypy + AT-013/provider/RAG/deployment/health tests (see handoff).

## AT-ADR-008 — Audit/usage unit-of-work + gated RED metrics (AT-016)
- **Date:** 2026-07-22
- **Status:** Accepted (implementation pending review/commit authorization)
- **Context:** AT010-H6 / RR-10 — `AuditService.record` and `UsageService.record`
  called `session.commit()` mid-request on the shared FastAPI Session, splitting
  business durability from audit/usage. No scrapeable RED metrics existed.
- **Decision:**
  1. **Caller / UoW owns commit.** Routes (or application services that already
     commit) perform the authoritative `session.commit()` after business mutation,
     audit flush, and usage flush.
  2. **Audit and usage flush only.** `record()` adds + flushes so IDs (e.g.
     `audit_event_id`) are available before commit; no hidden service-level commit.
     Flush failures that must not wipe prior business rows use a nested savepoint
     via `run_in_savepoint_when_active` — nested only when the DBAPI connection
     already has an open transaction. (SQLite: `RELEASE` of a SAVEPOINT that
     *started* the transaction would otherwise commit.)
  3. **No global auto-commit on `get_session()`** — existing explicit commits remain;
     a blanket teardown commit would surprise tool/worker paths.
  4. **Durable rejected/security events** use explicitly named
     `AuditService.record_durable_isolated()` (dedicated short-lived session +
     commit) after or outside the business transaction — rate-limit, quota block,
     paper reject, kill-switch trigger, auth security events.
  5. **Usage persistence** stays fail-open unless `observability_strict_mode`;
     strict audit flush failures raise and prevent the caller commit.
  6. **RED metrics** via `prometheus-client`: `http_requests_total`,
     `http_request_duration_seconds`, `http_requests_in_progress` with labels
     `method` / `route` (template) / `status_class` only. `METRICS_ENABLED=false`
     by default; outside local, `METRICS_SCRAPE_TOKEN` is required. `/metrics` is
     not observed recursively. Health/ready stay separate.
- **Alternatives considered:** Global commit-on-success in `get_session()` (rejected
  for this slice — too many existing commits); unrestricted public `/metrics`
  (rejected — Render scrape surface); embedding org/user labels (rejected — cardinality
  + privacy).
- **Safety impact:** Stronger atomicity for paper execution/approvals; durable
  security audits preserved; no trading-mode change.
- **Consequences:** Branch `feat/at-016-audit-uow-metrics`; stop at `REVIEW_REQUIRED`.
- **Validation:** `tests/test_at016_audit_uow_metrics.py` + audit/usage/execution/
  approval/risk/auth regressions.
- **Amendment (2026-07-23 — idempotent usage metering):** Route meters
  `paper_execution` only when `PaperOrderPlacementResult.created_new` is true.
  Sequential idempotent replay returns the existing order without a second usage
  row or creation audit. Concurrent first-writers may still race past the lookup
  and hit unique constraints; current contract is unique-conflict + client retry
  (proven in `test_concurrent_identical_requests_remain_safe`). Server-side
  Postgres convergence is AT-028 — not part of this amendment.

## AT-ADR-007 — Honor PROVIDER_MODE + narrative quota + search opacity (AT-015)
- **Date:** 2026-07-22
- **Status:** Accepted
- **Context:** AT-010 H5/H10 — factory ignored `PROVIDER_MODE=mock` for LLM/embeddings
  when a key was set; `limit_agent_narrative` was unused; search opacity needed UI/tests.
- **Decision:**
  1. Local `PROVIDER_MODE=mock` forces mock LLM/embeddings (and mock dims) even with key.
  2. Staging/production continue to reject `PROVIDER_MODE=mock` (AT-ADR-006 unchanged).
  3. Narrative polish checks `agent_narrative` quota before LLM; hard block → deterministic
     fallback (chat analysis still succeeds; no narrative LLM spend).
  4. Search continues to return `degraded`/`fallback_used`/`vector_backend`; frontend surfaces them.
- **Alternatives considered:** Hard-429 the entire chat on narrative quota (rejected: optional
  polish must not block deterministic analysis); allow mock in staging (rejected: AT-013).
- **Safety impact:** Reduces unexpected OpenAI spend in mock mode; cost control for narrative;
  no trading-mode change.
- **Consequences:** Branch `feat/at-015-provider-mode-quotas`; stop at `REVIEW_REQUIRED`.
- **Validation:** `tests/test_at015_provider_mode_quotas.py` + provider/embedding/AT-013 regressions.

## AT-ADR-009 — Proxy trust, Redis-required rate limits, fail-closed denylist (AT-018)
- **Date:** 2026-07-23
- **Status:** Accepted (implementation pending review/commit authorization)
- **Context:** AT010-H8 / RR-12 — `client_ip()` trusted the leftmost (client-supplied)
  `X-Forwarded-For` entry and uvicorn ran with `--forwarded-allow-ips="*"`, so rate-limit
  identity was spoofable. Staging allowed silent in-memory rate-limit fallback, and the
  token denylist could silently fall back to a process-local store (no cross-instance
  revocation).
- **Decision:**
  1. **Rightmost-hops proxy trust.** New `TRUSTED_PROXY_HOPS` setting (default 0). Only the
     rightmost N `X-Forwarded-For` entries — appended by our own reverse proxies — are
     trusted; entry `[-N]` is the client. 0 ignores the header entirely. Malformed or
     too-short header data falls back to the socket peer address. Staging/production
     require `>= 1` (Render sits behind exactly one proxy); local defaults to 0.
  2. **Uvicorn no longer trusts `*`.** `--forwarded-allow-ips` defaults to loopback and is
     overridable via `FORWARDED_ALLOW_IPS`; client-IP resolution happens in-app.
  3. **Redis-required rate limits outside local.** Staging/production reject
     `RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK=true` at startup. Runtime Redis errors without
     fallback keep failing closed (HTTP 429), and startup fails fast when Redis is
     unreachable.
  4. **Fail-closed denylist.** Staging/production require the denylist enabled, on Redis,
     and `ACCESS_TOKEN_DENYLIST_FAIL_CLOSED=true`. Outside local, denylist construction
     failure raises (no silent in-memory substitute), revocation writes that cannot be
     persisted raise `TokenDenylistUnavailableError` (HTTP 503), and revocation checks on
     Redis error continue to treat tokens as revoked. Local keeps developer-friendly
     fallback.
- **Alternatives considered:** CIDR allowlist for proxies (rejected: Render proxy IPs are
  not stable/published; hop count is deterministic); trusting uvicorn `--proxy-headers`
  resolution (rejected: with `*` it takes the spoofable leftmost entry); swallowing
  denylist write failures (rejected: a revoked token would silently stay valid).
- **Safety impact:** Rate-limit identity is no longer client-controlled; revocation is
  enforced or explicitly unavailable. No trading-mode change; paper posture preserved.
- **Consequences:** Branch `feat/at-018-proxy-trust-redis`; `render.yaml` staging sets
  `RATE_LIMIT_ALLOW_IN_MEMORY_FALLBACK=false`, `TRUSTED_PROXY_HOPS=1`,
  `ACCESS_TOKEN_DENYLIST_FAIL_CLOSED=true` (staging Redis must be reachable at deploy);
  stop at `REVIEW_REQUIRED`.
- **Validation:** `tests/test_rate_limit.py` (proxy trust + spoof regression),
  `tests/test_token_denylist.py`, `tests/test_deployment_safety.py` (AT-018 invariants),
  full backend suite + scoped strict mypy + ruff.

## AT-ADR-010 — Backup/restore RPO/RTO targets for paper staging (AT-019)
- **Date:** 2026-07-23
- **Status:** Accepted
- **Context:** AT010-H9 / RR-13 — backup/restore RPO/RTO was UNKNOWN; no verified restore
  drill. Postgres is the system of record; Redis is ephemeral; Qdrant is rebuildable.
- **Decision:**
  1. **Postgres RPO ≤ 24h** (stretch ≤ 1h if platform PITR enabled); **RTO ≤ 4h** for
     scratch restore + validation + cutover on staging/paper-MVP.
  2. **Qdrant RPO ≤ 24h or rebuild-from-SoR**; **RTO ≤ 4h** via snapshot or re-ingest.
  3. **Redis:** no logical backup; **RTO ≤ 15m** recreate empty instance.
  4. Local Compose drills are the default verification path; managed/staging restores
     require explicit human approval and prefer scratch DB over in-place overwrite.
  5. Evidence in git must be sanitized (sizes, hashes, durations, pass/fail only).
  6. AT-005 (deploy rollback + smoke gate) remains a separate concern — not duplicated.
- **Alternatives considered:** Require staging restore before closing AT-019 (deferred:
  approval-gated); treat Redis as SoR (rejected: intentionally ephemeral).
- **Safety impact:** Improves recovery preparedness; no trading-mode change; no live
  execution; scripts refuse non-local targets.
- **Consequences:** Runbook + inventory + drill docs under `docs/`; local helpers under
  `scripts/*postgres-local*` / `drill-backup-restore-local.sh`; dumps in `.ai/local/`.
- **Validation:** Tier A local drill passed 2026-07-23; see
  `docs/backup_restore_drill_evidence.md`.

## AT-ADR-011 — Post-deploy smoke gate + deploy rollback procedure (AT-005)
- **Date:** 2026-07-24
- **Status:** Accepted (merged PR #15 → `main` @ `f145599`)
- **Context:** Rollback was informal checklist rows; no automated fail-closed post-deploy
  gate. AT-019 covers data restore; app revision rollback and smoke gating were still open.
- **Decision:**
  1. Mandatory post-deploy command is `scripts/post-deploy-smoke-gate.sh`, which always
     runs `verify-safety.sh` and (default `GATE_PROFILE=standard`) `staging-smoke.sh`.
  2. Gate exit codes: `0` pass, `1` rollback trigger, `2` misconfiguration.
  3. Document exact triggers/steps/verification/failure handling in
     `docs/deploy_rollback_runbook.md`; wire into staging checklist/runbook/`RELEASE.md`.
  4. CI `deployment-safety` job asserts the gate is executable and `--self-check` passes
     (no network / no staging deploy from CI).
  5. The gate never deploys, never enables real trading, and never mutates platform services.
- **Alternatives considered:** Rely on manual `verify-safety` only (rejected: easy to skip);
  auto-rollback via Render API from CI (rejected: requires credentials + deploy authority
  outside ordinary impl tasks).
- **Safety impact:** Stronger fail-closed deploy acceptance; paper-only invariants unchanged.
- **Consequences:** Operators must treat gate exit `1` as a hard rollback trigger; data
  restore remains AT-019.
- **Validation:** `post-deploy-smoke-gate.sh --self-check`; unit tests in
  `tests/test_deployment_scripts.py`; docs present and cross-linked.

## AT-ADR-012 — Canonical journal trade domain links existing records (AT-030)
- **Date:** 2026-07-24
- **Status:** Accepted (merged via PR #16)
- **Context:** Trade data is fragmented across proposal-flow positions, paper-validation
  trades, backtest trades, and manual session records; the legacy `journals` table is
  reflection-only and typed to the built-in `StrategyId` enum. There was no canonical
  trade identity, no first-class MFE/MAE or available-vs-realized profit, and no
  structured rule-compliance or behavioral-observation records.
- **Decision:**
  1. **One canonical entity, `journal_trades`**, tenant-scoped, covering all sources
     (`manual`, `paper_execution`, `paper_validation`, `backtest`, `imported`, `system`)
     with plan fields (thesis, trigger, entry plan, invalidation, stop, targets, runner),
     execution fields (entry/exit, size, leverage, fees, funding, slippage, PnL), market
     regime, and excursion metrics (MFE/MAE, available vs realized).
  2. **Link, never copy.** FKs to positions, paper trades, proposals, orders, backtest
     trades, paper validation runs, and legacy journal entries; setup/strategy provenance
     via existing immutable `SetupDefinition` (name+version) and `UserStrategyVersion`.
     All links validated against the caller's organization; mismatches return 404
     (fail closed, no existence leak).
  3. **Child tables** for evidence (`journal_trade_evidence`), rule compliance
     (`journal_trade_rule_checks`), and behavioral observations
     (`journal_trade_observations`) instead of free-text lists.
  4. **Record-only.** No execution authority: never read by the engine, scheduler, or
     risk gates; excursion metrics accept deterministic inputs only (manual now, candle
     replay later) — no live market I/O in the journal path.
  5. **Legacy `/journal/entries` API and RAG sync stay unchanged**; canonical trades
     mount on the same router under `/journal/trades`.
- **Alternatives considered:** Extending `TradeJournal` in place (rejected: schema is
  reflection-shaped, enum-typed to legacy strategies, and widely consumed); a separate
  standalone journal service/app (rejected: would disconnect from tenancy, audit, RBAC,
  and existing records); computing MFE/MAE live at read time (rejected: nondeterministic,
  provider-dependent, violates freshness/conservatism rules).
- **Safety impact:** No trading-mode change; paper posture preserved; all mutations
  audited (`JOURNAL_TRADE_*` events); no new secrets or providers.
- **Consequences:** Alembic head moves to `i5d6e7f8a9b0`; follow-up slices (statistics,
  replay, human-vs-system endpoint, backtest integration, import/backfill) build on this
  domain — see `docs/journal_intelligence_foundation.md`.
- **Validation:** Migration upgrade/downgrade/upgrade on Postgres 16; 13 new API tests;
  full backend suite exit 0; ruff clean; strict mypy clean on all new modules.

## AT-ADR-013 — Journal statistics: deterministic aggregates over recorded values (AT-031)
- **Date:** 2026-07-24
- **Status:** Accepted (merged via PR #17)
- **Context:** AT-030 established canonical `journal_trades` but there were no statistics
  over it. Statistics must be trustworthy on small, partially populated samples: paper
  tenants have few trades, and MFE/MAE, planned risk, fees, and available-profit are only
  sometimes recorded.
- **Decision:**
  1. **Extend the AT-030 journal architecture** — statistics queries live on
     `JournalTradeRepository`, computation in a dedicated `JournalStatisticsService`,
     one authorized endpoint `GET /journal/statistics` on the journal router. No separate
     analytics system, no rollup tables in this slice.
  2. **Closed trades only; recorded values only.** SQL selects a bounded narrow
     projection (`journal_stats_max_rows`, default 5000, stable oldest-first ordering
     with truncation flagging); metric arithmetic runs in Python with `Decimal` for
     deterministic, dialect-independent precision (SQLite tests ≙ Postgres prod).
  3. **Per-family sample counts + confidence.** Every metric family (PnL, R, costs,
     MFE/MAE, available-vs-realized) aggregates only trades that recorded those values
     and reports its own sample count; `None` is never silently reported as zero.
     Coarse confidence labels (<5 insufficient, <20 low, <50 moderate, ≥50 high) and
     machine-readable warnings accompany every result.
  4. **Derived dimensions are conservative.** Rule compliance per trade = worst recorded
     assessment (`violated` > `partial` > `compliant`; no checks ⇒ `unassessed`, never
     compliant). Human-vs-system = decision authority mapping from `source`
     (`manual`/`imported`/`paper_execution` ⇒ human; `paper_validation`/`backtest`/
     `system` ⇒ system).
  5. **Win/loss classification**: recorded `result` wins; closed trades left at
     `result=open` fall back to the recorded `net_pnl` sign (the same arithmetic AT-030
     applies at close); win rate = wins / (wins + losses), breakeven excluded.
- **Alternatives considered:** Pure SQL conditional aggregation (rejected: float
  arithmetic on SQLite diverges from Postgres `numeric`, and per-family sample logic
  becomes unreadable); extending `UnifiedTradeLoader` (rejected for this slice: it loads
  positions/paper trades, not canonical journal trades — journal statistics must read the
  canonical table so all sources are covered uniformly); precomputed rollup tables
  (rejected: premature — bounded on-demand scans suffice at current volumes and cannot
  drift from source data).
- **Safety impact:** Read-only endpoint (`ReaderDep`), tenant-scoped (org + user); no
  execution-path changes; no live market I/O; reads not audited, mutations remain audited
  via AT-030; paper posture unchanged.
- **Consequences:** Alembic head moves to `j6e7f8a9b0c1` (index-only migration). Replay
  slice (deterministic MFE/MAE from candles) will raise excursion coverage; backtest
  integration reuses these grouping dimensions.
- **Validation:** Migration upgrade/downgrade/upgrade on Postgres 16 scratch DB; 19 new
  API tests; ruff clean; strict mypy clean on new modules; frontend tsc + eslint + page
  test green.

## AT-ADR-014 — Journal excursion replay from HistoricalCandle (AT-032)
- **Date:** 2026-07-24
- **Status:** Accepted (merged via PR #18)
- **Context:** AT-030 stored excursion columns but values were only manual; AT-031
  aggregates recorded MFE/MAE / available-profit with per-family sample counts, so
  coverage stays low until a deterministic fill path exists. Live market fetches at
  read time were rejected in AT-ADR-012.
- **Decision:**
  1. **Pure calculator + audited replay service.** In-trade MFE/MAE / available profit
     are computed from stored `HistoricalCandle` OHLC overlapping `[entry, exit)`
     (exit exclusive). Long and short use mirrored extremes. Amounts require size;
     capture percent reuses AT-030 arithmetic.
  2. **Read-only market data.** Replay never ingests or calls providers; missing
     candles / invalid windows skip safely with limitations. Gaps and incomplete
     coverage set freshness flags (`excursion_is_stale`, notes) without inventing bars.
  3. **Overwrite policy is explicit and deterministic.** Default `skip_protected`
     writes only when `excursion_source` is empty or already `replay`. `manual` and
     `system` (and any other non-replay source) require `overwrite_policy=force`.
  4. **Provenance columns** on `journal_trades` record data source, staleness, gap
     count, window completeness, and `excursion_computed_at`. Persisted source is
     always `replay`. Mutations audit as `JOURNAL_TRADE_EXCURSION_REPLAYED`.
  5. **Post-exit runner analysis** reuses `RunnerAndMissedProfitAnalyzer` in the
     response only — it does not redefine in-trade `available_profit`.
  6. **AT-031 integration** is automatic: statistics read recorded amounts; replay
     raises sample coverage without changing aggregate semantics.
- **Alternatives considered:** Computing MFE/MAE at statistics read time (rejected:
  nondeterministic if candles change; couples reads to market store); always
  overwriting manual values (rejected: human-entered coaching data must stay
  protected); provider fetch during replay (rejected: violates record-only /
  freshness rules for this slice).
- **Safety impact:** Record-only; `TraderDep` mutations; tenant-scoped; bounded
  candle/batch limits; paper posture unchanged; no live trading.
- **Consequences:** Alembic head moves to `k7f8a9b0c1d2`. Remaining journal slices:
  completion/import, human-vs-system endpoint, backtest bulk journal + full
  deterministic backtesting coverage.
- **Validation:** Migration upgrade/downgrade/upgrade on Postgres 16 scratch DB; 17 new
  API tests; ruff clean; strict mypy clean on new modules; CI run 30105918952 success
  (backend 1259 passed / 1 skipped).

## AT-ADR-015 — Journal completion: import dedup, backfill, auto-journal, attachments (AT-033)
- **Date:** 2026-07-24
- **Status:** Accepted (merged PR #19, merge `ad66dca`, CI run 30114440476 success)
- **Context:** AT-030/031/032 built the canonical journal, statistics, and excursion
  replay, but records only entered via manual API calls. The completion slice needs
  bulk history import, legacy `TradeJournal` migration, automatic journaling on paper
  closes, and a storage answer for screenshots/evidence — with idempotency, tenant
  isolation, audit, and human-vs-system analytics preserved.
- **Decision:**
  1. **DB-enforced dedup via partial unique index.** `(organization_id, external_ref)
     WHERE external_ref IS NOT NULL` on `journal_trades`. App-level checks give
     friendly per-row `duplicate` outcomes; the index is the race-proof backstop.
     Import rows without a ref get a deterministic `fp-sha256:` fingerprint over
     normalized identity fields, so re-imports are idempotent either way.
  2. **All-or-nothing import commit as the recovery model.** `mode=dry_run` previews
     per-row outcomes; `mode=commit` persists nothing when any row is invalid
     (single unit of work). Recovery is "fix and re-run" — duplicates skip safely.
     Committed batches persist to `journal_import_batches` for reconciliation
     history and audit (`JOURNAL_IMPORT_COMPLETED`).
  3. **`entry_method` column for human-vs-system analytics.**
     `manual|auto|import|backfill`, orthogonal to `source` (a human from-position
     record and an auto-hook record share `source=paper_execution` but differ in
     entry_method). First-class AT-031 filter + `group_by` dimension.
  4. **Backfill is a CLI script, dry-run by default.**
     `scripts/backfill_journal_entries.py` maps legacy rows to
     `source=imported`/`entry_method=backfill` with
     `external_ref='legacy-journal:<id>'` + `linked_journal_entry_id`; legacy rows
     are never mutated (link-never-copy, AT-ADR-012 upheld).
  5. **Auto-journal hooks are opt-in global Settings flags, fail-safe for the
     close.** `journal_auto_from_position_close` /
     `journal_auto_from_paper_validation`, both default false. Hooks reuse the
     idempotent `create_from_*` prefills inside a savepoint and swallow all errors
     after a warning log — journaling can never block or roll back a close.
     Paper-validation records attribute to the run owner.
  6. **Attachments are DB-backed behind an interface.** Bytes live in
     `journal_trade_attachments.content` (Postgres) with strict caps (5 MiB, MIME
     whitelist, 20/trade) because no durable object store exists and Render disks
     are ephemeral; existing DB backups cover them. `AttachmentStorage` keeps an
     S3-style swap schema-free. Uploads auto-link `JournalTradeEvidence`
     (`ref='attachment:<id>'`).
- **Alternatives considered:** Per-row partial import commits (rejected: ambiguous
  recovery semantics; idempotent re-run is simpler); per-user auto-journal preference
  (rejected for now: no preferences model exists — would be scope creep; global flags
  documented as deferred work); local-filesystem or S3 attachment storage (rejected:
  ephemeral Render disk loses data / no object store provisioned; interface keeps the
  door open); making `external_ref` globally unique across sources only for
  `imported` (rejected: org-wide partial index gives idempotency to backfill and
  future integrations too).
- **Safety impact:** Record-only throughout; no execution-path change; new flags
  default off; mutations `TraderDep`, reads `ReaderDep`; org-scoped fail-closed
  lookups; attachment validation fail-closed; paper posture unchanged; no live
  trading.
- **Consequences:** Alembic head moves to `l8a9b0c1d2e3`. Deferred: attachment upload
  UI (needs a trades detail page), per-user auto-journal opt-in, persisting
  failed/dry-run batches (enum values reserved).
- **Validation:** Migration upgrade/downgrade/upgrade round-trip on disposable
  Postgres 16 (docker); partial unique index verified on Postgres (duplicate
  rejected, NULLs unconstrained); 44 new backend tests (import 14, backfill 6,
  attachments 12, auto-journal 9, integration 3) plus AT-030/031/032 regression
  green; frontend 267 tests + typecheck + build green; ruff clean. No deploy.

## AT-ADR-016 — Deterministic backtesting v1: snapshot+hash reproducibility, conservative intra-bar rule, evidence tiers, bounded orchestration without new queue infra (AT-034)
- **Date:** 2026-07-24
- **Status:** Accepted (merged via PRs #20–#23 → `main` @ `8f9a84b`)
- **Context:** AT-030–033 established canonical journal trades, statistics, excursion
  replay, and bulk import. Slice 35 introduced a simpler backtest engine. AT-034
  needs reproducible historical simulation that journals into the canonical trade
  store, supports walk-forward evaluation, and surfaces advisory evidence — without
  new async infrastructure, live trading paths, or parameter-optimization loops.
- **Decision:**
  1. **Frozen config + dataset snapshots.** On create, persist `config_snapshot`,
     `config_hash`, and link an immutable `backtest_datasets` row by `dataset_hash`.
     Candles are hash-referenced, not copied per run.
  2. **Pure engine + `result_hash`.** `BacktestEngineService` (v2,
     `ENGINE_VERSION=at034-2.0.0`) is deterministic; `result_hash` is canonical JSON
     SHA-256. `POST /backtests/{id}/verify` re-runs with `persist=False` and
     compares hashes after dataset integrity check.
  3. **Conservative intra-bar rule.** When stop and TP both touch in one bar, stop
     wins.
  4. **Walk-forward v1 only.** Holdout and rolling splits evaluate independent
     segments with per-split and OOS metrics — no parameter optimization across
     windows.
  5. **Bounded orchestration.** Sync path when `total_bars <= backtest_sync_max_bars`;
     otherwise `QUEUED` with existing worker loop (1 run/cycle) plus BackgroundTasks
     fallback when worker disabled. Refuse `total_bars > backtest_max_bars` (no
     truncation). Cancel every 2000 bars; idempotency keys; active-run cap per org.
  6. **Bulk journal + comparison + advisory tiers.** `POST /backtests/{id}/journal-trades`
     creates `source=backtest` rows with dedup `external_ref`. `GET /journal/comparison`
     exposes human/paper_system/backtest cohorts. `GET /journal/setup-evidence` assigns
     tier1/tier2/tier3 from configurable OOS and confirmation thresholds — advisory
     only, never execution authority.
- **Alternatives considered:** Celery/dedicated queue (rejected: existing worker +
  BackgroundTasks suffice for bounded workloads); storing full candle copies per run
  (rejected: immutable hash-referenced datasets); parameter-optimizing walk-forward
  (rejected for v1: windowed evaluation only); using backtest tiers to gate live
  trading (rejected: record-only, risk engine untouched).
- **Safety impact:** Record-only throughout; paper posture unchanged; advisory tiers
  never feed execution or risk; mutations `TraderDep`; tenant-scoped; no live orders.
- **Consequences:** Alembic head moves to `m9b0c1d2e3f4`. Docs rewritten in
  `docs/backtesting.md`. Integration tests in `test_at034_integration.py`.
- **Validation:** Merged PRs #20–#23 (CI runs 30126077064, 30126107532,
  30130869273, 30130870524 all success). Post-merge on `main` @ `8f9a84b`:
  AT-034 + slice-35 pytest 43 passed; frontend page tests 7 passed; ruff clean.
  No deploy.

## AT-ADR-017 — Research validation loop: extend candidate provenance + synthetic alert/draft vs parallel queue (AT-035)
- **Date:** 2026-07-25
- **Status:** Accepted
- **Context:** AT-034 delivers deterministic backtests, OOS metrics, and advisory
  setup evidence tiers. Slice 80 established the paper validation candidate queue
  (alert → draft → candidate). Users need a paper-safe path to promote strong
  backtest evidence into that queue without bypassing FK constraints or creating a
  parallel promotion system.
- **Decision:**
  1. **Reuse existing candidate queue.** Promotion enters `paper_validation_candidates`
     via the same queue model — no separate research queue or execution shortcut.
  2. **Synthetic research-origin alert + draft.** Create
     `PaperAlertType.RESEARCH_VALIDATION_PROMOTION` alert and a `ready_for_validation`
     draft to satisfy non-null `source_alert_id` / `draft_id` FKs; mark
     `promotion_source=research_validation`.
  3. **Eligibility via `SetupEvidenceService`.** Tier1/tier2 eligible; tier3 hard
     blocked. Missing OOS metrics or incomplete runs blocked. Soft warning
     `insufficient_confirm_sample` when confirm trades below tier1 threshold.
  4. **Frozen provenance on candidate.** Persist `backtest_run_id`, strategy/version
     FKs, dataset/config/result hashes, `evidence_tier`, and `evidence_snapshot`
     JSON at promotion time. Legacy alert-draft rows keep nullable provenance.
  5. **Idempotency.** Partial unique index on
     `(organization_id, backtest_run_id)` for active (`queued`/`reviewing`) candidates.
  6. **Confirm phrase.** `PROMOTE_RESEARCH_VALIDATION_CANDIDATE` required on POST.
  7. **Paper-only.** Advisory endpoints; never feed execution or risk; tenant-scoped;
     `ReaderDep` for evidence/status, `TraderDep` for promote.
- **Alternatives considered:** Parallel research-only queue (rejected: duplicates
  review UX and splits paper validation); nullable alert/draft FKs (rejected: breaks
  existing schema invariants); auto-start paper runtime on promote (rejected: exceeds
  advisory scope and weakens human review).
- **Safety impact:** Record-only; paper posture unchanged; no risk/execution module
  changes; promotion does not authorize live trading.
- **Consequences:** Alembic head moves to `n0c1d2e3f4a5`. Docs in
  `docs/research_validation.md`. Tests in `test_at035_research_validation.py`.
- **Validation:** Disposable Postgres 16 migration upgrade/downgrade/upgrade cycle;
  partial unique index verified; duplicate active promotion blocked at DB layer;
  targeted pytest + ruff + frontend research-validation tests; CI on merge PR.

## AT-ADR-018 — Aggregate journal comparison decision quality vs per-trade HumanVsSystemService (AT-036)
- **Date:** 2026-07-25
- **Status:** Accepted
- **Context:** AT-034 delivers three-cohort journal comparison (`human`,
  `paper_system`, `backtest`) over closed canonical trades. Users need aggregate
  decision-quality metrics (entry timing, early exits, missed profit, capture) and
  human-vs-system actor scorecards without invoking per-trade
  `HumanVsSystemService` orchestration on every list request. Slice 36
  `/human-vs-system/{id}` remains the per-trade analyzer surface.
- **Decision:**
  1. **Extend existing endpoint.** Add AT-036 fields to `GET /journal/comparison`
     — backward compatible; preserve AT-034 `cohorts` with three keys.
  2. **Recorded fields only.** Decision quality computed from journal columns
     (`planned_entry_price`, `entry_price`, `direction`, `available_profit`,
     `net_pnl`, `realized_vs_available_pct`) — no live market I/O, no proposal
     linkage required for aggregates.
  3. **Actor scorecards.** `human` = manual + imported + paper_execution;
     `system` = paper_validation + backtest + system (decision-authority mapping
     from AT-031).
  4. **Dimension buckets.** `by_entry_method`, `by_source`, `rule_compliance`
     (worst-assessment), plus capped setup/regime `breakdowns`.
  5. **Warnings.** Reuse AT-031 confidence thresholds; add `PARTIAL_TIMING_DATA`
     and `PARTIAL_MISSED_PROFIT_DATA` when subsamples are partial.
  6. **Frontend paths in `links`.** Echo filters for journal statistics and
     comparison; link to research-validation and paper-validation candidates.
  7. **Paper-only / ReaderDep.** Advisory record-only; never feeds execution or
     risk; tenant-scoped like AT-034.
- **Alternatives considered:** New dedicated endpoint (rejected: fragments
  comparison UX and duplicates filters); invoke `HumanVsSystemService` per trade in
  list (rejected: heavy, needs proposal links, exceeds aggregate scope); replace
  Slice 36 per-trade API (rejected: different granularity and analyzer depth).
- **Safety impact:** Record-only; paper posture unchanged; no risk/execution
  module changes.
- **Consequences:** No migration required (reuses AT-031/034 indexes and journal
  columns). Docs in `docs/journal_intelligence_foundation.md` §7,
  `docs/human_vs_system.md`, `docs/backtesting.md`. Tests in
  `test_at036_journal_comparison.py` and frontend comparison page tests.
- **Validation:** Targeted backend + frontend tests on feature branch; no deploy.
