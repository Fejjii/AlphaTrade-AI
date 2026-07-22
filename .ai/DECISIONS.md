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

## AT-ADR-007 — Honor PROVIDER_MODE + narrative quota + search opacity (AT-015)
- **Date:** 2026-07-22
- **Status:** Accepted (implementation pending review/commit authorization)
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
