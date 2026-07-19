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
