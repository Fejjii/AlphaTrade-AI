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
