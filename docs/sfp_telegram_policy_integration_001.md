# SFP Telegram Policy Integration 001 handoff

Branch: `codex/sfp_telegram_policy_integration_001`.
Exact parent: `5f4f0a467ce8f68f9c7a82d3b32307d559a9f092`.
Draft PR target: `codex/release_consolidation_wave_002`.

Canonical SFP Brain setup/event history now feeds the existing Watcher scan
notification hook, Telegram paper agent, Candidate alert gateway, Telegram Policy
V2, recipient binding and durable security outbox. No notification store,
delivery service, migration, credential, activation flag or execution path was
added. The hook runs after the setup transaction commits. It remains optional
and is installed only through the existing activation configuration.

| Event type | Existing severity | Phase |
| --- | --- | --- |
| `SFP_SWEEP_DETECTED` | `WATCH` | `FORMING` |
| `SFP_RECLAIM_FORMING` | `WATCH` | `FORMING` |
| `SFP_CONFIRMED` | `ACTION` | `CONFIRMED` |
| `SFP_INVALIDATED` | `INFO` | none |
| `SFP_EXPIRED` | `INFO` | none |
| `SFP_BLOCKED_BY_RISK` | `WATCH` | none |

`ACTION` requests attention to confirmed evidence; it grants no action or
execution authority. All six messages are informational, without Candidate
action intents, nonces, confirmation buttons, or a second footer. The generic
Candidate alert path refuses SFP so it cannot inadvertently offer action buttons.
Risk-blocked events use the stored account decision and its reason codes. They
honor the existing `risk_alerts` toggle and are not mandatory-risk bypasses.

Each message includes paper mode, symbol, venue, timeframe, direction, structural
level type/price, sweep extreme, reclaim state, immutable strategy-version ID,
tenant-scoped setup ID, original evidence timestamp, event timestamp, quality
coverage, missing/unsupported evidence, and risk state/reasons. Clock expiry
retains the original evidence time, including during missing evidence.

A closed candle can reveal the sweep and reclaim together. The sweep projection
uses the canonical sweep receipt time and proof; it does not invent an earlier
intrabar receipt or a separate lifecycle. Events outside the authored evidence
age horizon and future events are excluded from replay projection. Fresh stored
facts recover notification admission after worker/gateway restart.

The existing policy accepts all six exact `event_types`. Strategy subscriptions
use canonical strategy-version UUIDs, as existing Candidate subscriptions do.
Symbol, severity, phase, risk toggle, minimum quality, quiet hours, cooldown,
duplicate suppression, recipient isolation and delivery-time rechecks remain
owned by Policy V2. SFP has component measurements but no aggregate 0–100 quality
score. Coverage is displayed, never converted into a score: every configured
minimum quality threshold, including zero, fails with `POLICY_QUALITY_MISSING`.

Semantic duplicate identity is tenant/version/setup/event type. Exact outbox
identity also binds user, binding, bot and chat. Repeated observations and replay
produce one outbox row per semantic event per recipient, even when temporal
suppression is disabled. Existing cooldown and temporal history use the same
scoped security store and persisted notification facts; suppression remains
terminal and retries cannot suppress themselves.

Focused tests cover both directions, all six types, canonical Watcher/risk
projection, file-backed setup replay, PostgreSQL outbox replay, policy filters,
missing quality, original expiry timestamps, binding/tenant gates, cooldown,
delivery-time suppression and disabled protocol behavior. Transport is fake.
The SFP PostgreSQL fixture now fixes daily-risk accounting to its synthetic
candle date, making its existing risk-lock assertions independent of today.

Telegram network delivery remains unarmed. No credentials, runtime environment,
deployed database, strategy approval, risk rules, order execution, or live trading
settings were changed. Merge, deployment and runtime activation are deferred to
the release owner.

Validation used a disposable local PostgreSQL 16 database:

- 272 passed, no skips, across `test_sfp_telegram_policy_integration.py`,
  `test_sfp_strategy_brain_runtime.py`, `test_sfp_detector.py`,
  `test_telegram_notification_policy_v2.py`, `test_phase6_candidate_telegram_alerts.py`,
  `test_telegram_paper_agent.py`, `test_telegram_evaluation_integration.py`, and
  `test_watcher_paper_runtime.py`.
- Final focused integration rerun: 18 passed, no skips.
- Ruff passed for all changed Python files. Mypy passed for the two new source
  modules with `--follow-imports=silent`. `git diff --check` passed.
- One existing Starlette/httpx deprecation warning. The full backend suite was
  not run. No migration was applied to a deployed environment.
