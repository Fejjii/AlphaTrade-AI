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

## AT-ADR-019 — TradingView signed intake + BloFin demo read-only sync (AT-037)
- **Date:** 2026-07-25
- **Status:** Accepted
- **Context:** TradingView alerts need a secure multi-tenant intake path into the
  paper-first workflow, and operators need BloFin **demo** account/position
  visibility without any order mutation. Existing paper-validation candidates
  require non-null alert/draft FKs (AT-035 synthetic scaffold pattern). Billing
  webhooks prove HMAC+timestamp+idempotency patterns but lack tenant signal
  lifecycle and public rate limits.
- **Decision:**
  1. **Signed public webhook.** `POST /webhooks/tradingview` with
     `X-AT-Timestamp` + `X-AT-Signature` (HMAC-SHA256 over `{timestamp}.{body}`),
     skew window, fail-closed when disabled/secret missing, public IP rate limit.
  2. **Dedicated `tradingview_signals` table.** Org-scoped lifecycle
     (`received`/`validated`/`rejected`/`duplicate`/`candidate_created`),
     unique `(org, idempotency_key)` and `(org, alert_id)`, redacted payload
     storage, optional links to setup/strategy/journal/backtest/candidate.
  3. **Optional paper candidate only.** Explicit trader confirm
     (`CREATE_TRADINGVIEW_PAPER_CANDIDATE`) creates synthetic alert+draft+queued
     candidate with `promotion_source=tradingview_signal`. Auto-create off by
     default. Never creates live orders or executable proposals.
  4. **BloFin sync is read-only demo.** Persist bounded snapshots via
     `get_demo_account_provider` only; provenance + health + stale marking;
     no execution provider calls; secrets never logged.
  5. **Frontend.** Signal inbox + exchange BloFin sync panel with loading/empty/
     stale/error states.
- **Alternatives considered:** Reuse billing `webhook_events` only (rejected:
  no signal lifecycle/links); make alert FK nullable on candidates (rejected:
  breaks Slice 80 invariants — use synthetic scaffold); auto-queue every alert
  (rejected: opt-in confirm / setting); live BloFin sync (rejected: Mode D /
  safety).
- **Safety impact:** Paper/demo only; real trading stays disabled; no order
  placement/cancel/modify; rate limits/denylist/kill-switch unchanged.
- **Consequences:** Migration `o1d2e3f4a5b6`; docs in
  `docs/tradingview_blofin_sync.md`; tests in `test_at037_tradingview_blofin.py`
  + frontend page/panel tests.
- **Validation:** Targeted backend + frontend tests on feature branch; no deploy.

## AT-ADR-020 — Automated paper-signal orchestration (AT-038)
- **Date:** 2026-07-25
- **Status:** Accepted
- **Context:** AT-037 delivers signed TradingView intake and optional manual
  paper-candidate creation. Operators need a deterministic, reviewable bridge from
  validated signals into paper-validation candidates/run plans and (optionally)
  approval-gated paper proposals — without any live or autonomous execution path.
- **Decision:**
  1. **Dedicated decision table.** `paper_signal_orchestration_decisions` with
     unique `(org, tradingview_signal_id)` idempotency, status state machine,
     eligibility/risk evidence JSON, transition history, and links to signal /
     setup / strategy / journal / backtest / candidate / run plan / proposal.
  2. **Configurable human modes only.** `observe_only` | `candidate_only` |
     `approval_required`. No autonomous live mode. Default disabled + observe_only.
  3. **Reuse existing paper pathways.** Candidates via AT-037
     `_create_candidate_internal`; run plans via Slice 81 confirm pathway;
     paper proposals via `ProposalService.create(approval_required=True)`.
     Never call `place_paper_order` or exchange mutation APIs.
  4. **Fail-closed gates.** Freshness, timeframe, direction, confidence, setup/
     strategy linkage when configured, level consistency, conflicting-signal
     window, market-context (when BloFin demo enabled), kill switch, daily-loss
     lock, cooldown after loss, `execution_mode=paper`, `enable_real_trading=false`.
  5. **Explicit proposal confirm.** `APPROVE_PAPER_SIGNAL_PROPOSAL` required in
     `approval_required` mode; re-validate eligibility before proposal create.
- **Alternatives considered:** Auto-place paper orders from signals (rejected:
  bypasses approval/risk); extend TradingView signal status instead of a decision
  table (rejected: conflates intake lifecycle with orchestration); live mode
  (rejected: Mode D / safety).
- **Safety impact:** Paper-only; real trading stays disabled; kill switch /
  cooldown / daily-loss / approval controls remain authoritative.
- **Consequences:** Migration `p2e3f4a5b6c7`; docs in
  `docs/paper_signal_orchestration.md`; tests in
  `test_at038_paper_signal_orchestration.py` + frontend page tests.
- **Validation:** Targeted backend + frontend tests on feature branch; no deploy.

## AT-ADR-021 — Phase 5 Binance USD-M perpetual evidence contracts (no spot fallback)
- **Date:** 2026-09-16
- **Status:** Accepted (implemented on PR #80, draft; do not merge pending independent review)
- **Context:** The first BTCUSDT vertical slice requires closed perpetual 15m/4h OHLCV,
  ordered USD-M aggregate trades, quote-volume CVD, and signed quote flow. The existing
  `binance-public` adapter uses spot `/api/v3/klines` and may silently fall back to mock
  data. Architecture §17/§25 forbid forming-candle confirmation, spot substitution, and
  unresolved reconnect gaps.
- **Decision:**
  1. **Separate perpetual evidence package** (`app.market_contracts`) with typed venue,
     market, instrument, source, provider, interval, finality, revision, timestamps,
     freshness, content hash, and provenance. Phase 1 execution modules are not modified.
  2. **Preferred source is Binance USD-M public REST** (`fapi.binance.com` klines +
     aggTrades). GET-only path allowlist. No API keys. No order/position/account paths.
  3. **No spot fallback and no mock substitute** for live USD-M evidence. Regional
     unavailability fails closed (`RegionalProviderFailureError`) and reports
     `using_fallback=false`.
  4. **FINAL candles only.** Forming klines are represented but cannot enter a
     `ClosedOhlcvSeries`. First slice requires 100 final 15m and 30 final 4h bars.
  5. **Trade stream cursor** is `INITIAL -> CONTINUOUS -> RECONNECTING -> RECOVERED`.
     Every reconnect starts a new epoch. Unresolved sequence gaps are
     `UNRECOVERABLE` and fail closed. Cross-connection CVD windows are not supported.
  6. **CVD** is unrounded Decimal quote volume: buyer aggressor `+price*qty*multiplier`,
     seller aggressor negative. Baseline is 0 at the open of the 32nd 15m bar before
     trigger T. Signed flow is `signed_quote_delta / total_quote_volume` on the trigger
     bar. Binance aggressor convention is `m=true` ⇒ seller aggressor (`buyer-is-maker/v1`).
  7. **Default runtime source is replay fixtures** (`PERPETUAL_EVIDENCE_SOURCE=replay`)
     so local/CI never require Binance reachability. Replay is explicitly mock, not a
     silent live fallback.
  8. **AggTrades retrieval** chunks `startTime`/`endTime` to < 1 hour and paginates
     further pages with `fromId` only. Mixed time+fromId queries are forbidden.
     Incomplete pages or sequence holes fail closed.
  9. **CVD completeness** is derived from a `TradeStreamSnapshot` plus immutable
     `TradeWindowCoverageProof`. The proof binds exact market/source identity,
     lineage, requested/actual half-open bounds, gap/completeness state, terminal
     trade identities, ordered trade-set hash, and content hash. It must cover the
     entire T-32 through trigger-end window. Count and internal continuity alone
     are insufficient. First-slice action eligibility also requires terminal trade
     freshness ≤10s.
  10. **Live evidence hosts** are explicit approved USD-M HTTPS identities
      (`fapi.binance.com`). Arbitrary hosts and `http://` are rejected.
  11. **End-to-end identity** requires every normalized trade to exactly match the
      stream market/instrument and represented source fields. CVD/flow identity must
      exactly equal the authoritative snapshot identity.
  12. **Signed quote flow** consumes the same proven stream as CVD and requires
      complete trigger-bar coverage, no gap, matching lineage/aggressor convention,
      and fresh terminal evidence. Raw trade lists are not accepted.
- **Alternatives considered:** Relabel the existing spot kline adapter as perpetual
  (rejected: incompatible market); fall back to spot or mock when USD-M is blocked
  (rejected: false evidence); persist observations in this phase (rejected: no migration
  unless unavoidable; later phases own candidate/observation storage).
- **Safety impact:** Read-only market evidence only; no execution path change;
  `ENABLE_REAL_TRADING=false` and `EXECUTION_MODE=paper` unchanged.
- **Consequences:** Docs in `docs/market_source_contracts.md`; tests in
  `test_phase5_*.py`. Pattern/fusion/watcher remain out of scope.
- **Validation:** Targeted Phase 5 pytest, full backend pytest, ruff, scoped mypy.

## AT-ADR-022 — Isolated watcher orchestration foundation (typed persistence)
- **Date:** 2026-09-16
- **Status:** Accepted
- **Context:** Phase 7 watcher work is split across parallel agents. This agent
  owns worker orchestration (leases, fencing, lineage, retry, health, scheduling)
  without market semantics, candidates, Telegram, execution, journal, or ORM
  migrations. Agent 1 later supplies source freshness and evidence validity.
- **Decision:**
  1. New isolated package `app.watcher` with typed persistence ports and a
     deterministic in-memory repository for this wave.
  2. Manual and worker callers share one `WatcherOrchestrator.evaluate` boundary
     (`PREVIEW | PERSIST_EVIDENCE | PERSIST_AND_NOTIFY`). Notify stays blocked.
  3. One fenced worker owns a tenant-scoped scan key `(organization_id, scan_scope)`;
     stale fence holders cannot publish. `scan_scope` strings are not a tenant boundary.
  4. Every scan has an immutable lineage; attempts are append-only; retries are
     idempotent; failures cannot be rewritten as successes.
  5. Health is exclusive `healthy | degraded | blocked | stale`.
  6. `WATCHER_ORCHESTRATION_ENABLED` defaults false and is not wired into the
     live worker loop. No shared ORM model or Alembic changes.
  7. WatcherStore methods take `organization_id` explicitly and reject organization
     mismatch. Lease, fence, heartbeat, health, latest-attempt-by-scope, and
     lineage-by-scope are keyed by `(organization_id, scan_scope)`.
- **Alternatives considered:** Extend `MarketWatcherService` / SQLAlchemy models
  now (rejected: collides with parallel agents and premature PostgreSQL binding);
  process-local locks only (rejected: architecture requires monotonic lease
  epochs on every worker-caused write).
- **Safety impact:** Watcher stays disabled; no automatic trading or candidate
  creation; real trading remains disabled.
- **Consequences:** Later integration review binds the ports to PostgreSQL after
  all three parallel PRs land.
- **Validation:** `backend/tests/test_watcher_orchestration_foundation.py`.

## AT-ADR-023 — Isolated Telegram security protocol; APPROVE never executes (AT-043)
- **Date:** 2026-09-16
- **Status:** Accepted
- **Context:** Agentic redesign §10 requires verified private-chat enrollment,
  opaque action nonces, receipts, replay protection, and a RemoteActionGateway
  that is not a second mutation stack. Agent 3 owns the isolated security
  foundation only. Telegram must remain disabled and must not connect to
  execution. CLOSE stays unavailable. EXECUTE_PAPER_PLAN is out of scope.
- **Decision:**
  1. **Isolated package.** `app.telegram_security` holds enrollment, binding,
     message/callback identity, nonce, receipt, rate-limit, outbox, delivery
     acknowledgement, transport, and the action authorization boundary.
  2. **Persistence interfaces only.** `TelegramSecurityStore` + deterministic
     `InMemoryTelegramSecurityStore`. No shared ORM models, no Alembic.
  3. **Disabled by default.** `telegram_interaction_enabled=false`. No FastAPI
     webhook. Fake transport for tests; no live Telegram API calls.
  4. **Private chat only.** Group/channel chats and chat-id-only enrollment fail.
  5. **Opaque one-time nonces** bind org, user, account, Telegram identity, resource,
     revision/content hash, one action, expiry, and single-use state.
  6. **APPROVE** records a protocol-level authorization intent (`executes=false`).
     It never calls ExecutionService. EXECUTE_PAPER_PLAN is not in the Telegram
     vocabulary.
  7. **CLOSE** is a known name but unavailable (issue and apply both fail).
  8. Duplicate `update_id` / `callback_query_id` / outbox idempotency keys
     converge only when the inbound semantic fingerprint is identical. Same
     transport lookup identity with changed update/message/callback identity,
     Telegram user, chat, chat type, bot, nonce or enrollment-token hash,
     action, organization, AlphaTrade user, account, resource, revision,
     content hash, or payload hash fails closed as `REPLAY_CONFLICT`.
  9. Inbound type and size validation precede receipt lookup. Exact persisted
     replay convergence and conflicting replay rejection precede rate-limit
     charging; only genuinely new semantic inbound actions consume budget.
  10. `MAX_INBOUND_UPDATE_BYTES` is enforced against
     `TelegramInboundUpdate.body_size` (raw Telegram request payload), never
     nonce or enrollment-token length. Webhook wiring remains out of scope.
  11. Delivery is at-least-once via durable claim.
- **Alternatives considered:** Wire inbound webhook now (rejected: later
  integration); persist via Alembic in this slice (rejected: later PostgreSQL
  binding); allow APPROVE to call execution (rejected: CRITICAL-03).
- **Safety impact:** Telegram stays off. Live trading stays disabled. Approval
  cannot execute. CLOSE cannot close.
- **Consequences:** Docs in `docs/telegram_security_protocol.md`. Tests in
  `backend/tests/test_telegram_security_protocol.py`.
- **Validation:** Targeted protocol tests, full backend pytest, ruff, mypy on
  `app.telegram_security`, GitHub CI. No merge in the implementing PR's agent
  instructions.

## AT-ADR-024 — Phase 6 canonical signal-fusion contract freeze
- **Date:** 2026-09-17
- **Status:** Accepted (contracts only; evaluator/persistence not in this slice)
- **Context:** Parallel Phase 6 implementation needs one typed identity and hash
  layer so observations, fusion, assessment, candidates, eligibility, adapters,
  and PostgreSQL persistence cannot invent competing schemas.
- **Decision:**
  1. Canonical package is `app.signal_fusion`. Phase 5
     `PublicMarketObservation` and market identities are reused, not duplicated.
  2. Freeze immutable contracts: `FusionPolicy`, `SetupAssessment`,
     `ActionEligibility`, `Candidate`, `CandidateTransition`, and
     `CanonicalEvidenceWindowV1`.
  3. Setup truth lifecycle is `NO_SETUP -> WATCH -> PARTIAL_MATCH ->
     CONFIRMED_SETUP` or market-only `INVALIDATED`/`EXPIRED`. Risk/account
     state cannot occupy `SetupAssessment`.
  4. Confirmed candidates start `ACTIVE`. Terminal `REJECTED`/`SKIPPED`/
     `EXPIRED`/`INVALIDATED` cannot resurrect to `ACTIVE`.
  5. Candidate uniqueness is the §5 tuple; `setup_definition_id` is a
     tenant-owned `CompiledSetupDefinition` only.
  6. `CanonicalEvidenceWindowV1` hashes the §26 semantic preimage with
     canonical Decimal/datetime serialization and deterministic ordering.
     Transport metadata and presentation evidence are excluded.
  7. This slice does not implement the fusion evaluator, candidate repository,
     Alembic, watcher/Telegram/TradingView adapters, risk evaluation, alerts,
     outbox, execution, or frontend.
- **Alternatives considered:** New observation identity in fusion (rejected:
  Phase 5 already owns public observations); persist candidates now (rejected:
  contract freeze only); let adapters keep source-specific candidate keys
  (rejected: equivalent watcher/detector/TradingView evidence must converge).
- **Safety impact:** Paper mode unchanged. No network, execution, watcher,
  Telegram, or BloFin calls.
- **Consequences:** Later Phase 6 agents implement evaluator, persistence, and
  adapters against this package.
- **Hardening (2026-09-17, PR #84):** Fail-closed selected-observation
  venue/market/instrument matching; role-aware timeframes (trigger vs context
  may differ); tenant assertions enter CanonicalEvidenceWindowV1 only when
  required or explicitly selected by FusionPolicy; duplicate semantic set
  members are canonicalized; Phase 5 `observation_id_for` is revision-aware
  (`source_event_id|finality|revision`) so FORMING, FINAL, and corrected
  revisions are distinct immutable appends. No evaluator, persistence, or
  live trading.


## AT-ADR-025 — Phase 6 deterministic first-slice fusion evaluator
- **Date:** 2026-09-17
- **Status:** Accepted (setup-truth evaluator only)
- **Context:** PR 84 froze identities. Setup truth still had no deterministic
  evaluator. Parallel agents must not invent a second identity or let risk
  rewrite pattern presence.
- **Decision:**
  1. `evaluate_setup(policy, command, evidence, evaluated_at)` is the sole
     first-slice setup-truth function. It reuses PR 84 contracts and Phase 5
     payloads; it does not create `Candidate` or `ActionEligibility`.
  2. Canonical pattern name remains **Bearish Liquidity Sweep with CVD
     Divergence and Aggressive Sell Imbalance at 4h Resistance**. The first
     slice makes no exhaustion claim.
  3. States are only `NO_SETUP`, `WATCH`, `PARTIAL_MATCH`, `CONFIRMED_SETUP`,
     `INVALIDATED`, `EXPIRED`. Risk, account, leverage, balance, portfolio,
     and execution availability cannot alter `SetupAssessment`.
  4. Confirmation requires every mandatory Boolean predicate (equal weight,
     threshold `1.0`): identity, finality, freshness ≤ 10s, no gap, warmup,
     Wilder ATR14, confirmed L2/R2 swing `S`, nearest versioned 4h resistance
     `R` with `abs(S-R) <= 0.50 ATR4h`, sweep/close, volume ≥ 1.50, bearish
     quote-volume CVD divergence, aggressive sell imbalance ≤ -0.10.
  5. Invalidation is `T.high + max(0.10 ATR15m, 2 * tick)`; expiry is two
     additional final 15m bars. Fail closed on wrong market/instrument/venue,
     forming/stale/missing evidence, unresolved gap, wrong perpetual identity,
     incomplete warmup, missing/invalid manual resistance, incompatible policy.
  6. Evidence order and adapter kind (watcher vs detector) must not change
     the assessment. Equivalent semantic evidence hashes identically via
     `CanonicalEvidenceWindowV1`.
- **Alternatives considered:** Interpret a generic AST VM now (rejected: first
  slice is one compiled pattern); persist candidates in this slice (rejected:
  evaluator owns truth only); let account/risk fields veto setup (rejected:
  eligibility is a later contract).
- **Safety impact:** Paper only. No exchange, execution, Telegram, watcher, or
  deployment calls.
- **Consequences:** Candidate persistence and action eligibility remain later
  Phase 6 slices against the same frozen identities.

## AT-ADR-026 — Phase 6 candidate lifecycle service (in-memory authority)
- **Date:** 2026-09-17
- **Status:** Accepted (application service; PostgreSQL/Alembic not in this slice)
- **Context:** PR #84 froze Candidate / CandidateUniquenessTuple / transitions.
  Parallel persistence work must not invent a second candidate authority.
  PaperValidationCandidate remains a downstream queue (§26).
- **Decision:**
  1. Canonical candidate authority is `CandidateLifecycleService`.
  2. Creation requires SetupAssessment `CONFIRMED_SETUP` plus the exact
     `CanonicalEvidenceWindowV1` plus the tenant-owned
     `CompiledSetupDefinition` identity. NO_SETUP / WATCH / PARTIAL_MATCH /
     EXPIRED / INVALIDATED cannot mint ACTIVE candidates.
  3. Uniqueness is exactly `CandidateUniquenessTuple`. Duplicate semantic
     confirmations converge, including concurrent inserts. Distinct org,
     strategy version, compiled setup, fusion policy version, direction,
     venue, market, instrument, timeframe, or evidence-window hash do not
     converge.
  4. Initial state is ACTIVE. Descendants are PLAN_CREATED and terminal
     REJECTED / SKIPPED / EXPIRED / INVALIDATED. Terminal states cannot
     resurrect. History is append-only.
  5. Persistence is a typed `CandidateRepository` port with deterministic
     `InMemoryCandidateRepository` only. No SQLAlchemy models, no Alembic,
     no fusion evaluator, no watcher/Telegram/execution wiring.
  6. Legacy `PaperValidationCandidate` cannot create canonical identity.
  7. **Idempotency (integration hardening):** organization-scoped creation
     `idempotency_key` binds to the canonical uniqueness fingerprint. Exact
     retries converge; same key with a different payload fails closed.
     Transition idempotency is candidate-scoped: exact key+payload replay
     returns the original record; key reuse with a changed payload fails
     closed. A different key requesting an already-applied state converges
     only when the semantic fingerprint matches the original transition.
- **Alternatives considered:** Persist PostgreSQL in this slice (rejected:
  separate durable-persistence agent); derive candidates from PVC or
  TradingView signals (rejected: competing authority).
- **Safety impact:** Paper only. No network, execution, feature flags, or
  live trading.
- **Consequences:** Later Phase 6 agents bind PostgreSQL to the same port
  without changing uniqueness or lifecycle rules.

## AT-ADR-027 — Phase 6 evaluator + candidate runtime foundation integration
- **Date:** 2026-09-17
- **Status:** Accepted (in-memory runtime foundation only)
- **Context:** Main already contains Phase 6 contracts, compatibility audit,
  and the golden first-slice fixture corpus. PR #87 owns setup truth. PR #86
  owns candidate authority. They must share one package without rewriting
  frozen contracts or restoring removed fixture-specific semantic hashing.
- **Decision:**
  1. Integrate evaluator and candidate lifecycle additively onto current
     main. Do not change CanonicalEvidenceWindowV1, SetupAssessment,
     Candidate, or the golden fixture corpus.
  2. Canonical strategy name remains **Bearish Liquidity Sweep with CVD
     Divergence and Aggressive Sell Imbalance at 4h Resistance**.
  3. Evaluator never creates candidates. Combined flow is composition:
     evidence → `evaluate_setup` → CONFIRMED_SETUP → exactly one ACTIVE
     candidate. Duplicate semantic evaluation converges.
  4. Golden fixtures remain the authoritative corpus in
     `backend/tests/fixtures/phase6_first_slice/`. Evaluator/candidate
     tests adapt to current support APIs; they do not overwrite fixtures.
  5. No PostgreSQL, Alembic, watcher, Telegram, eligibility, TradePlan,
     execution, frontend, or live trading.
- **Alternatives considered:** Merge PR 86/87 fixture support over the
  corpus (rejected: corpus on main is authoritative); couple evaluator to
  candidate creation (rejected: separate authorities).
- **Safety impact:** Paper only. No external calls, execution, or deployment.
- **Consequences:** Independent integration review is the next gate. Draft
  PR only; do not merge in the implementing agent instructions.

## AT-ADR-028 — Phase 6 deterministic ActionEligibility service
- **Date:** 2026-09-17
- **Status:** Accepted (in-memory eligibility authority only)
- **Context:** Frozen `ActionEligibility` binds identity and state but does not
  evaluate. SetupAssessment is market truth. A confirmed Candidate still must
  not proceed toward paper TradePlan creation until account, risk, safety,
  configuration, stale action evidence, and first-slice cross-venue basis are
  checked without rewriting setup history.
- **Decision:**
  1. `ActionEligibilityService.evaluate` is the sole first-slice action gate.
     It consumes a canonical Candidate, SetupAssessment lineage, account,
     portfolio, risk snapshot, safety snapshot, market-action evidence, and
     paper execution configuration. It does not create Candidates, mutate
     SetupAssessment, create TradePlanRevision, reserve risk, consume
     approval, or call venues.
  2. Frozen `ActionEligibilityState` remains `ELIGIBLE | BLOCKED | EXPIRED`.
     Finer distinctions are `EligibilityReasonCode` values. Kill switch maps
     to `BLOCKED_KILL_SWITCH` and always dominates. Daily loss and weekly loss
     use Phase 1 `check_daily_loss_lock` / `check_weekly_loss`. Capacity uses
     `RiskEngine.limits.max_position_pct_of_equity`. Account/tenant isolation
     maps to `BLOCKED_ACCOUNT_STATE`. Stale required action evidence maps to
     `BLOCKED_DATA_QUALITY`. Cross-venue basis above 20 bps maps to
     `BLOCKED_BASIS` and never changes SetupAssessment. Live/real-trading
     configuration maps to `BLOCKED_CONFIGURATION`. Non-confirmed setup maps
     to `BLOCKED_SETUP_NOT_CONFIRMED`.
  3. First-slice cross-venue basis threshold is 20 bps (`>` blocks; `<=`
     eligible). Basis is an eligibility gate only.
  4. Identical semantic evaluation converges on one immutable record.
     Changed risk snapshot identity or safety epoch appends a distinct
     evaluation revision without mutating history.
  5. `live_executable` is always false. `paper_actionable` is true only for
     `ELIGIBLE` under paper configuration. Persistence remains in-memory.
- **Alternatives considered:** New ActionEligibilityState values such as
  `BLOCKED_SAFETY` (rejected: frozen contract already has ELIGIBLE/BLOCKED/
  EXPIRED); evaluating eligibility inside `evaluate_setup` (rejected: setup
  truth must stay independent); constructing TradePlan to probe risk size
  (rejected: this slice ends at eligibility truth).
- **Safety impact:** Paper only. Kill switch remains the Phase 1 authority.
  Real trading cannot become executable. No network, Telegram, watcher,
  Alembic, or deployment.
- **Consequences:** Later slices may bind PostgreSQL and feed ELIGIBLE results
  into paper TradePlan creation. Draft PR only; do not merge.

## AT-ADR-029 — Watcher orchestration wires to Phase 6 fusion (first slice)
- **Date:** 2026-09-17
- **Status:** Accepted (orchestration wiring only)
- **Context:** PR #88 integrated `evaluate_setup` and `CandidateLifecycleService`
  on frozen contracts. Watcher orchestration still used a scripted evaluation
  boundary that forbade all candidate IDs. Manual and worker scans must consume
  the same deterministic evidence and evaluator without a second identity.
  Wave B integration assigned this ADR `AT-ADR-029` because PR 90 already
  occupied `AT-ADR-028` for ActionEligibility.
- **Decision:**
  1. One typed service, `WatcherFusionEvaluationService`, implements
     `WatcherEvaluationBoundary`. Watcher does not implement trading predicates.
  2. Flow is scan evidence → `evidence_window_from_assessment_command` →
     `evaluate_setup` → `SetupAssessment` → `CandidateLifecycleService` only
     when state is `CONFIRMED_SETUP` and mode is `PERSIST_EVIDENCE`.
  3. Watcher does not compute a second evidence hash and does not mint
     candidate IDs. CanonicalEvidenceWindowV1 and CandidateLifecycleService
     remain identity authorities.
  4. NO_SETUP, WATCH, PARTIAL_MATCH, INVALIDATED, and EXPIRED do not create
     an ACTIVE candidate. Duplicate semantic scans converge. Organization
     isolation remains `(organization_id, scan_scope)` plus the candidate
     uniqueness tuple.
  5. SetupAssessment stays market truth only. Balance, portfolio, risk,
     leverage, execution availability, and account state are not inputs.
     Action eligibility, TradePlan, Telegram, execution, Alembic, and a
     second WatcherStore adapter are out of scope.
  6. Persistence remains the existing WatcherStore port (in-memory now;
     PostgreSQL owned by PR #85). `WATCHER_ORCHESTRATION_ENABLED` and
     `MARKET_WATCHER_ENABLED` stay false. No scheduler activation.
  7. Orchestrator honesty still rejects unverified candidate IDs. Canonical
     publication requires SUCCEEDED, reason `confirmed_setup`, a 64-hex
     `evidence_validity_token`, and exactly one candidate id.
- **Alternatives considered:** Put predicates in WatcherOrchestrator
  (rejected: second evaluator); mint watcher-scoped candidate IDs (rejected:
  competing identity); create candidates on PREVIEW (rejected: dry-run);
  mix ActionEligibility into SetupAssessment (rejected: setup vs action).
- **Safety impact:** Watcher remains disabled. Paper only. No live trading,
  exchange mutation, Telegram, or deployment.
- **Consequences:** Draft PR only; do not merge. Later work may bind a live
  market-evidence adapter and PostgreSQL WatcherStore without changing this
  evaluation boundary.

## AT-ADR-030 — Phase 6 Candidate Telegram alert foundation
- **Date:** 2026-09-17
- **Status:** Accepted (composition foundation; Telegram remains disabled)
- **Context:** Canonical Candidate authority (AT-ADR-026/027) and the isolated
  Telegram security protocol (AT-ADR-023) both exist. Alerts must not treat
  PaperValidationCandidate, PaperSignal, SetupDetection, or TradingViewSignal
  as independent candidate authorities. APPROVE must never execute. Wave B
  integration assigned this ADR `AT-ADR-030` because `AT-ADR-028` is
  ActionEligibility and `AT-ADR-029` is watcher fusion wiring.
- **Decision:**
  1. New package `app.candidate_alerts` composes Candidate -> deterministic
     `CandidateAlertIntent` -> existing Telegram outbox -> secured actions.
  2. Identity binds organization, user, account, candidate ID, candidate
     content hash, strategy version, compiled setup identity, fusion policy
     version, evidence window hash, lifecycle revision, alert kind, and
     Telegram channel. Duplicate semantic events converge. Revision/content
     changes produce a distinct identity.
  3. Structured alert facts are canonical only. No profitability claims.
     No LLM-authored setup truth.
  4. APPROVE stays authorization intent (`executes=false`). REJECT/SKIP map
     to `CandidateLifecycleService` through the gateway. REDUCE_RISK emits
     typed intent and does not mutate Candidate. EXPLAIN/SHOW_CHART/STATUS
     are read-only. CLOSE remains unavailable. EXECUTE_PAPER_PLAN is absent.
  5. Reuse `TelegramSecurityStore` / in-memory protocol store. No new
     PostgreSQL adapter, no Alembic, no webhook, no Telegram network call.
     PR 85 remains durable Telegram persistence owner.
  6. `TELEGRAM_INTERACTION_ENABLED=false`, `ENABLE_REAL_TRADING=false`,
     `EXECUTION_MODE=paper`.
- **Alternatives considered:** Alert from PaperValidationCandidate or
  TradingViewSignal (rejected: competing authority); extend TelegramSecurityStore
  with alert tables (rejected: second persistence model); let APPROVE call
  execution (rejected: CRITICAL-03).
- **Safety impact:** Telegram stays off. Live trading stays disabled. Approval
  cannot execute. Candidate immutability is preserved for REDUCE_RISK and
  read-only actions.
- **Consequences:** Docs in `docs/phase6_candidate_telegram_alerts.md`. Tests in
  `backend/tests/test_phase6_candidate_telegram_alerts.py`.
- **Validation:** Candidate alert tests, Telegram protocol tests, Phase 6
  Candidate tests, full backend pytest, ruff, mypy `--strict` on the new
  package plus `app.telegram_security` and `app.signal_fusion`, GitHub CI.
  Draft PR only; do not merge in the implementing agent instructions.

## AT-ADR-031 — Phase 6 canonical Candidate PostgreSQL persistence
- **Date:** 2026-09-18
- **Status:** Accepted (PostgreSQL adapter; not wired into staging/production)
- **Context:** AT-ADR-026 froze CandidateLifecycleService as the only Candidate
  authority with an in-memory `CandidateRepository`. Durable uniqueness,
  append-only transitions, and the remaining Watcher persist-after-lease-loss
  race require a PostgreSQL adapter that cannot become a second authority.
- **Decision:**
  1. `PostgresCandidateRepository` implements the existing
     `CandidateRepository` port. `CandidateLifecycleService` remains the only
     Candidate authority. In-memory remains the unit-test default.
  2. Projections persist in `canonical_candidates`. Creation idempotency,
     append-only transitions, and transition-key aliases are separate tables
     with uniqueness constraints matching in-memory semantics.
  3. Worker-originated writes bind Watcher lease identity. The Candidate
     persist transaction `SELECT ... FOR UPDATE` locks
     `watcher_worker_leases (organization_id, scan_scope)` and proves current
     owner, epoch, fencing token, and a non-expired lease before committing
     Candidate authority. A stale worker cannot persist after losing its lease.
  4. One Alembic revision from head `3ec264f9aaa8`. Adapters are constructed
     explicitly and are not imported by FastAPI, workers, or feature flags.
  5. `WATCHER_ORCHESTRATION_ENABLED`, `MARKET_WATCHER_ENABLED`,
     `TELEGRAM_INTERACTION_ENABLED`, and live trading remain disabled.
- **Alternatives considered:** Check fence then persist in a later transaction
  (rejected: TOCTOU); put Candidate identity in WatcherStore (rejected: second
  authority); change TradePlan / ActionEligibility / SetupAssessment (out of
  scope).
- **Safety impact:** Paper only. No Watcher, Telegram, or live-trading
  activation.
- **Consequences:** Tests in `backend/tests/test_phase6_candidate_postgres.py`.
  Migration `4fd8c1a90b27`.

## AT-ADR-032 — Phase 7 canonical TradePlanRevision application layer
- **Date:** 2026-09-18
- **Status:** Accepted (application layer; durable PostgreSQL binding follows)
- **Context:** Phase 6 froze Candidate and ActionEligibility as in-memory
  authorities. Phase 1 `TradePlanRevision` is hash-stable and immutable, but
  `ProposalService.create_revision` is fail-closed and
  `trade_plan_revisions.candidate_id` still foreign-keys
  `paper_validation_candidates`. PR 93 owned the application layer. Source PR
  claimed `AT-ADR-031`, already used by Candidate PostgreSQL, so this ADR is
  `AT-ADR-032`.
- **Decision:**
  1. `CanonicalTradePlanService.create` is the sole first-slice plan authority.
  2. Creation loads Candidate and ActionEligibility from those services. Only
     `ACTIVE` + currently paper-actionable `ELIGIBLE` may insert. Lineage
     (org/user/account, candidate identity/hash/revision, assessment, evidence
     window, strategy/setup, venue/market/instrument/timeframe/side) must match
     exactly. Plan `candidate_id` is the canonical Candidate id.
  3. Phase 1 `TradePlanRevisionSemantic` / `CanonicalTradePlanContentV1` stays
     hash-stable. Canonical binding is `CanonicalTradePlanLineage` beside that
     preimage, not new semantic fields.
  4. Identical semantic requests converge (presentation/correlation first-write
     wins). Conflicting organization-scoped idempotency fails closed. One plan
     per (org, user, account, candidate) in this slice.
  5. `CandidateState.PLAN_CREATED` is applied only after a successful store
     insert; failed creates do not transition. Transition identity is derived
     from plan uniqueness so retries converge.
  6. `PaperValidationCandidate` and `ProposalService.create_revision` cannot
     mint canonical plan authority. Approval may bind revision id + content
     hash only and cannot change executable semantics. Execution is absent.
  7. Application persistence is `CanonicalTradePlanStore`. Source PR used an
     unbound SQLAlchemy adapter because the PVC FK was still in place. Phase 7
     integration owns the durable remap after Candidate migration `4fd8c1a90b27`.
- **Alternatives considered:** Add lineage fields to `TradePlanRevisionSemantic`
  (rejected: would break existing Phase 1 content-hash verification); write
  canonical UUID5 ids into the PVC FK (rejected: competing identity, FK
  violation).
- **Safety impact:** Paper only. Live trading cannot become executable. No
  network, Watcher, Telegram, Journal, execution dispatch, frontend, or
  deployment changes.
- **Consequences:** Docs in `docs/phase7_canonical_trade_plan_binding.md`.
  Tests in `backend/tests/test_phase7_canonical_trade_plan.py`.
- **Validation:** Focused canonical plan tests, Phase 1 planning/approval
  tests, Phase 6 candidate/eligibility tests, full backend pytest, ruff,
  mypy `--strict`, GitHub CI. Draft PR only; do not merge.

## AT-ADR-033 — Phase 7 learning attribution reuses journal projector
- **Date:** 2026-09-18
- **Status:** Accepted (application service; PostgreSQL/Alembic not in this slice)
- **Context:** Phase 4 already converges one execution lifecycle to one
  `JournalTrade`. Phase 6 froze SetupAssessment/Candidate/TradePlan identity.
  Learning analytics still summarize the older paper-validation funnel. This
  wave must connect canonical lifecycle to learning without a second trading
  authority or competing migration. Source PR 95 claimed `AT-ADR-031`, already
  used by Candidate PostgreSQL, so this ADR is `AT-ADR-033`.
- **Decision:**
  1. `JournalLifecycleProjector` remains the only JournalTrade writer.
  2. `LearningAttributionService` / `JournalLifecycleLearningService` are
     record-only consumers. They copy lineage; they do not evaluate setups,
     create candidates, authorize plans, or dispatch execution.
  3. Lineage rides on append-only `payload.lineage`. First-seen values are
     sticky. Duplicate source identity converges. Conflicting identity and
     cross-tenant attribution fail closed.
  4. REJECT/SKIP never create executed trade outcomes. Quality axes are
     planned setup vs execution vs trader behavior. PnL cannot rewrite
     SetupAssessment hashes. LLM narrative is excluded from `facts_hash`.
  5. Lesson/analytics/RAG adapters consume facts. Lessons are suggestions
     only. RAG is a renderer only. No shared schema changes in this wave.
- **Alternatives considered:** New journal trade writer for learning (rejected:
  competing authority); Alembic columns in this wave (rejected: Candidate and
  TradePlan migrations already occupy the Alembic head); auto-persisting
  lessons or RAG ingest (rejected: review workflow and market-truth integrity).
- **Safety impact:** Paper only. No live trading, Watcher, Telegram, frontend,
  or execution-dispatch changes.
- **Consequences:** Docs in `docs/phase7_learning_attribution.md`. Tests in
  `backend/tests/test_learning_attribution.py` and
  `backend/tests/test_journal_lifecycle_lineage.py`.
- **Validation:** Targeted attribution/journal/learning pytest, full backend
  pytest, ruff, mypy `--strict` on the new package plus journal lifecycle
  modules, GitHub CI. Draft PR only; do not merge.

## AT-ADR-034 — Phase 7 canonical TradePlan / ActionEligibility PostgreSQL binding
- **Date:** 2026-09-19
- **Status:** Accepted (PostgreSQL adapter; not wired into staging/production)
- **Context:** AT-ADR-032 froze CanonicalTradePlanService as the only first-slice
  plan authority with an in-memory store. `trade_plan_revisions.candidate_id`
  still foreign-keyed `paper_validation_candidates`. ActionEligibility was
  in-memory only. Candidate PostgreSQL (AT-ADR-031 / Alembic `4fd8c1a90b27`)
  landed first.
- **Decision:**
  1. Next Alembic revision is `c9e2b4a1d078` after `4fd8c1a90b27`.
  2. `PostgresActionEligibilityStore` implements `ActionEligibilityStore`.
     Evaluations are immutable and keyed by uniqueness hash. Identity bindings
     fail closed. Candidate rows are locked so revision history is append-safe.
  3. `trade_plan_revisions` keeps `candidate_id` as an unconstrained UUID for
     legacy PVC-backed rows. Discriminator `plan_authority` is
     `paper_validation` (canonical_candidate_id NULL) or `canonical`
     (canonical_candidate_id = candidate_id, FK canonical_candidates).
     Legacy PVC ids are never reinterpreted as canonical Candidate ids.
  4. Canonical rows bind `compiled_setup_definition_id` to tenant-owned
     `compiled_setup_definitions`. Global SetupDefinition FK is dropped.
  5. `canonical_trade_plan_lineage` stores Candidate/eligibility hashes beside
     unchanged `semantic_payload`. Uniqueness hash is unique. Idempotency keys
     are organization-scoped.
  6. Canonical `plan_id` remains UUID5(org, user, account, candidate_id). A
     compatibility TradeProposal with `plan_root_kind=canonical_plan_root`
     satisfies the existing composite FK without restoring ProposalService as
     plan authority.
  7. Plan insert locks the canonical Candidate and runs `PLAN_CREATED` in the
     same transaction via `on_inserted`. Adapters are not imported by FastAPI,
     workers, or feature flags. Execution remains a later slice.
- **Alternatives considered:** Backfill PVC ids as canonical Candidate ids
  (rejected: competing identity); put lineage fields into
  TradePlanRevisionSemantic (rejected: would break Phase 1 hashes); delete
  canonical rows on Alembic downgrade automatically (rejected: fail closed if
  canonical rows exist).
- **Safety impact:** Paper only. Watcher, Telegram, and live trading stay
  disabled. No exchange mutation. No deployment.
- **Consequences:** Docs in `docs/phase7_canonical_trade_plan_binding.md`.
  Tests in `backend/tests/test_phase7_eligibility_postgres.py` and
  `backend/tests/test_phase7_trade_plan_postgres.py`. Migration `c9e2b4a1d078`.

## AT-ADR-035 — Phase 8 learning attribution PostgreSQL persistence
- **Date:** 2026-09-19
- **Status:** Accepted (PostgreSQL adapter; FastAPI/runtime wiring owned by later Phase 8 slices)
- **Context:** AT-ADR-033 froze record-only learning attribution on
  `JournalLifecycleProjector` with an in-memory store. Canonical trade outcomes
  still could not be queried as durable strategy/pattern intelligence. Agent 1's
  persistence contract lived in `AGENT_1_ATTRIBUTION_INTEGRATION`.
- **Decision:**
  1. Next Alembic revision is `d4f7a2c8e901` after `c9e2b4a1d078`.
  2. `learning_attribution_records` is the candidate-scoped aggregate
     (`UNIQUE(organization_id, candidate_id)`). Partial unique
     `(organization_id, execution_lifecycle_id)` when set. Events are append-only
     and unique on the same source identity as journal projection receipts.
  3. `PostgresAttributionStore` implements `AttributionStore` on the caller's
     session. Duplicate source identity converges. Conflicting identity, sticky
     lineage, and cross-tenant access fail closed.
  4. Quality axes remain separate: setup quality, execution quality, risk
     adherence, trader behavior, and outcome. REJECT/SKIP cannot become executed
     outcomes. PnL cannot rewrite SetupAssessment or evidence-window hashes.
  5. `learning_venue_mode` is `paper_internal` or `paper_exchange_demo` so future
     demo trade learning does not mix with internal paper stats. Live/real is
     not a venue.
  6. `LearningQueryService` is the read API for strategy/pattern stats,
     human-versus-system comparison, lesson suggestions (`persist=false`), and
     RAG evidence documents. Narrative is labeled `NARRATIVE_NOT_FACT` and is
     excluded from `facts_hash`. RagService is not called.
  7. Optional `journal_trades` lineage columns are projector-stamped query
     helpers. The projector remains the only JournalTrade writer. Slice 84
     paper-validation learning analytics is not replaced.
- **Alternatives considered:** Materialized stats table as a second authority
  (rejected: derive stats from records); auto-ingest learning narrative to Qdrant
  (rejected: market-truth and lesson-review integrity); FastAPI/worker wiring
  (rejected: out of scope for this slice).
- **Safety impact:** Paper only. No live trading, Watcher, Telegram, frontend, or
  execution-dispatch changes in this slice.
- **Consequences:** Docs in `docs/phase8_learning_persistence.md`. Tests in
  `backend/tests/test_phase8_learning_persistence.py`. Migration `d4f7a2c8e901`.
- **Validation:** Attribution/idempotency/tenant/RAG-boundary tests, Alembic
  upgrade/downgrade/reupgrade and single head, full backend pytest, ruff, mypy
  `--strict`, GitHub CI. Source PR #97; integrated on
  `cursor/phase8_final_integration`.

## AT-ADR-036 — Phase 8 canonical PAPER runtime execution
- **Date:** 2026-09-19
- **Status:** Accepted (runtime composition; paper execution only)
- **Context:** AT-ADR-034 bound Candidate, ActionEligibility, and canonical
  TradePlanRevision to PostgreSQL without FastAPI or worker wiring. Phase 1
  `EXECUTE_PAPER_PLAN` already claims `paper_validation` plans. Canonical plans
  must not become ProposalService trading authority. Source PR #99 claimed
  `AT-ADR-035`, already used by learning persistence, so this ADR is
  `AT-ADR-036`.
- **Decision:**
  1. `ProductionCanonicalRuntime` is the production composition for PostgreSQL
     Candidate, ActionEligibility, and CanonicalTradePlan adapters.
     `CandidateLifecycleService` remains the only Candidate authority.
  2. FastAPI lifespan stores the runtime on `app.state`. Request handlers bind
     the caller's Session. The worker constructs the same runtime and never
     starts Watcher or Telegram. Flags default false.
  3. `ExecutionService.execute_paper_plan` routes `plan_authority=canonical` to
     `CanonicalPaperExecutionService`. That path re-verifies Candidate,
     eligibility, plan hash, approval, and account lineage immediately before
     the existing `PaperPlanClaimService` claim transaction. Kill switch and
     `evaluate_claim_predicate` remain final. Authorization is not consumed on
     `BLOCKED`.
  4. Canonical execution is PAPER only. `live_executable` stays false. No
     exchange mutation. Duplicate idempotency keys converge across restarts.
     Stale, rejected, expired, mismatched, or modified plans fail closed.
  5. Compatibility `canonical_plan_root` TradeProposal rows remain FK-only.
     ProposalService create always writes `analysis_proposal`. List omits
     canonical roots. Get/update paths raise `TradingPolicyError`.
  6. Journal lifecycle receives deterministic `approved_plan` / `fill` events
     with `source_system=canonical_paper_execution` via
     `JournalLifecycleProjector`. Exact replay converges.
  7. HTTP `POST /execution/paper-plan` accepts only identity + idempotency.
     Executable fields are forbidden. Legacy `POST /execution/paper` stays
     fail-closed and must not mint canonical Candidate or TradePlan authority.
- **Alternatives considered:** Making ProposalService the canonical plan
  authority (rejected: competing authority); enabling Watcher/Telegram with
  this wave (rejected: explicitly out of scope); new Alembic (rejected: Phase 7
  schema plus PR97 learning migration are sufficient).
- **Safety impact:** Paper only. Watcher, Telegram, and live trading stay
  disabled. No real exchange mutation. No deployment.
- **Consequences:** Docs in `docs/phase8_runtime_execution.md`. Tests in
  `backend/tests/test_phase8_runtime_composition.py` and
  `backend/tests/test_phase8_canonical_paper_execution.py`.
- **Validation:** Adversarial execution pytest, full backend pytest, ruff,
  scoped `mypy --strict` on Phase 8 modules, deployment-safety, relevant HTTP
  E2E, GitHub CI. Source PR #99; integrated on
  `cursor/phase8_final_integration`.

## AT-ADR-037 — Canonical paper decision frontend (user-facing workflow)
- **Date:** 2026-09-19
- **Status:** Accepted (frontend composition; no backend authority invented)
- **Context:** Redesign architecture §14/§15 Phase 12 consolidates surfaces.
  Backend Phase 6/7 Candidate, ActionEligibility, TradePlanRevision, and
  ExecutionReceipt exist as services/stores. Source PR #98 claimed
  `AT-ADR-035`, already used by learning persistence, so this ADR is
  `AT-ADR-037`.
- **Decision:**
  1. Plan landing is `/decision`. Legacy `/workspace`, `/proposals`,
     `/approvals`, and `/paper-validation/*` stay reachable.
  2. Market quality and action eligibility are separate cards. Setup quality
     never grants permission to act.
  3. Canonical TradePlan execution binds to `POST /execution/paper-plan`
     with identity + idempotency only. Legacy `POST /execution/paper` remains
     compatibility-only and must not execute a canonical TradePlan.
  4. Canonical reads reuse existing authorities: candidates, setup
     assessment, action eligibility, execution receipt, and
     `LearningQueryService` strategy/pattern statistics. Missing HTTP is
     added as a thin read adapter, not a second domain model.
  5. PaperValidationCandidate is a compatibility projection, not
     CandidateLifecycleService. `canonical_plan_root` stays invisible to
     ProposalService trading authority.
  6. Human approval records authorization only. AI copy cannot claim to
     approve or execute. No live execution control is rendered.
  7. Kill switch and paper/real-trading posture are on every decision screen.
     LLM never becomes deterministic authority.
- **Alternatives considered:** Treat PVC as canonical Candidate (rejected:
  AT-ADR-026); keep `POST /execution/paper` as the decision-hub execute path
  (rejected: AT-ADR-036 fail-closed); hide legacy Plan routes (rejected: keep
  functional until telemetry justifies deprecation).
- **Safety impact:** Paper only. Watcher, Telegram, and live trading stay
  disabled. No real exchange mutation. No deployment.
- **Consequences:** Docs in `docs/redesign/phase8_canonical_frontend.md`.
  Frontend module `frontend/src/lib/canonical-decision/`.

## AT-ADR-038 — Phase 8 release-candidate integration
- **Date:** 2026-09-19
- **Status:** Accepted (integration; draft PR only; do not merge or deploy)
- **Context:** PR97, PR99, and PR98 landed independently on `main@cd9087a`.
  All three claimed AT-ADR-035 / AT-055. Canonical frontend executed through
  legacy `POST /execution/paper`. Runtime learning used in-memory attribution.
- **Decision:**
  1. Integration order is PR97 → PR99 → PR98. Do not merge `main`.
  2. ADR/task IDs remap to AT-ADR-035/AT-055 (learning), AT-ADR-036/AT-056
     (runtime), AT-ADR-037/AT-057 (frontend).
  3. Alembic remains a single head: `d4f7a2c8e901` after `c9e2b4a1d078`.
  4. Canonical frontend execution binds to `POST /execution/paper-plan`.
  5. Thin `/canonical/*` read APIs reuse Candidate, ActionEligibility,
     ExecutionReceipt, and `LearningQueryService`. No duplicate domain models.
  6. Runtime paper execution attributes through `PostgresAttributionStore`.
  7. Paper only. Watcher and Telegram stay disabled. Kill switch and risk
     BLOCK stay final. Human approval is mandatory. LLM is never authority.
- **Alternatives considered:** Merge into `main` in this wave (rejected);
  create another Alembic revision (rejected: not required).
- **Safety impact:** Paper only. No deploy. No real exchange mutation.
- **Consequences:** Branch `cursor/phase8_final_integration`. Tests in
  `backend/tests/test_phase8_canonical_workflow.py`.

## AT-ADR-039 — Final backend hardening fail-closed attribution and deployment pins
- **Date:** 2026-09-19
- **Status:** Accepted
- **Context:** After Phase 8 integration (`main@c39dca6`), ALLOW journal projection
  could silently skip learning when Candidate or ActionEligibility lookup returned
  `None`. `PaperExecutionRiskGate` remains unused on `EXECUTE_PAPER_PLAN`. Staging
  deployment safety logged Telegram flags but did not reject Watcher/Telegram enablement.
- **Decision:**
  1. Missing Candidate, eligibility, or required assessment lineage after ALLOW
     raises `LearningAttributionIncompleteError` and rolls back the claim/journal
     unit of work. Learning evidence is never silently skipped.
  2. Claim-time final risk authority remains `evaluate_claim_predicate` under
     locked safety-epoch and `AccountRiskAccountingState`, plus canonical lineage
     revalidation including persisted ActionEligibility TTL. Do not integrate
     unused `PaperExecutionRiskGate` as a competing claim authority.
  3. `POST /execution/paper-plan` commits replay requests without double-metering
     usage so healing writes persist.
  4. Canonical fill projection fails closed when the command/plan is missing or
     the production canonical runtime is unbound on a canonical plan.
  5. Staging/production reject Watcher and Telegram enablement flags. Accidental
     real trading remains impossible via existing paper/deployment/exchange
     invariants (`real_trading_enabled` is permanently false).
- **Alternatives considered:** Persist a separate attribution-failure row while
  committing ALLOW (rejected for this slice: would split execution from learning);
  wire `PaperExecutionRiskGate` into claim (rejected: second risk authority).
- **Safety impact:** Paper only. Watcher, Telegram, and live trading stay disabled.
  No deploy.
- **Consequences:** Branch `cursor/final_backend_hardening`. Tests in
  `backend/tests/test_phase8_backend_hardening.py`. Draft PR
  https://github.com/Fejjii/AlphaTrade-AI/pull/102 (do not merge). GitHub CI run
  35462467663 success.
