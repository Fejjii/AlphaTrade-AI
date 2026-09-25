# Final integrated paper system (AT-076)

PR #126 Watcher remediation is the scan base. PR #125 paper evaluation and
Telegram discussion are applied on that base. This slice does not merge those
source PRs, does not deploy, and does not enable Watcher, Telegram, or live
trading. The later controlled package that may arm those paths together is
`docs/controlled_paper_activation.md`. This page does not arm that package.

## Authority map

| Decision | Authority | What it must not do |
| --- | --- | --- |
| Market evidence | Live monitor gates quote and trade-stream freshness. `FirstSliceEvidenceAssembler` is the only `CanonicalEvidenceWindowV1` producer. | A second assembler, a fabricated price, or a live mark from replay. |
| Strategy | Persisted approved compiled policy (`ExecutablePolicyAuthority.PERSISTED_APPROVED_COMPILED`). | In-memory policy minting a Candidate. Telegram or AI activating a strategy. |
| SetupAssessment | `evaluate_canonical_strategy`. | Telegram override. Manual insertion of `CONFIRMED_SETUP`. |
| Candidate | `CandidateLifecycleService`, only after a genuine `CONFIRMED_SETUP`, behind the worker fence. | Telegram mint. Persist from a stale fence or a duplicate worker. |
| Paper decision | ActionEligibility, then `CanonicalTradePlanService`, then paper execution. | Risk `BLOCK` being overridden. Telegram placing an order. |

`paper_evaluation` copies deterministic facts. `telegram_paper_agent` and
`paper_interaction` discuss them. AI refinement is a suggestion
(`activate=false`, `auto_activate=false`).

## Watcher contracts that stay authoritative

From the PR #126 remediation:

- Freshness clocks stay separate: current quote, trade stream, closed-candle
  finality, historical evidence validity, and setup lifetime.
- OHLCV availability is not closed-candle finality. Trade coverage is not
  historical evidence validity.
- Live quote stale threshold remains 10 seconds. The 60-minute scanner window
  is the legacy scanner, not the Watcher quote clock.
- Each worker process uses a unique instance id. Renewing the same owner's
  lease requires the current fencing token.
- Production assembly with `monitor=None` is `missing_monitor`.
- A live monitor in front of a replay assembler, or the reverse, is
  `wrong_source` once the monitor snapshot itself is fresh. A stale snapshot
  still fails as `stale_evidence` before that source check.
- The worker clock and the candidate-repository fence clock are the same clock.

`build_watcher_paper_runtime` leaves `scan_notification_hook` unset unless the
caller supplies one. `python -m app.workers.watcher_paper` does not supply it.

## Target loop

```
live read-only market
  → approved compiled strategy
  → Watcher
  → canonical SetupAssessment
  → Candidate
  → paper decision / TradePlan
  → paper execution lifecycle
  → Journal
  → attribution
  → evaluation facts
  → learning / refinement suggestion
```

Parallel interaction, advisory only:

```
Watcher / Candidate
  → durable Telegram notification
  → interactive AlphaTrade discussion
```

The PostgreSQL product proof assembles confirming evidence through
`FirstSliceEvidenceAssembler`. It does not insert `CONFIRMED_SETUP`.
Fail-closed proof covers stale evidence, provider outage, wrong tenant, wrong
lineage, expired setup, wrong source, missing monitor, in-memory policy,
duplicate worker, stale fence, Telegram mutation, and AI strategy activation.

## Confirmed setup continues inside the paper worker

When a scan publishes one `CONFIRMED_SETUP` Candidate, `WatcherPaperRuntime`
calls `AutomatedPaperLoop`. That sequencer uses the existing
`ActionEligibilityService`, `CanonicalTradePlanService`, hash-bound API
approval, and internal paper fill. It does not detect setups, mint Candidates,
or replace the risk engine. Risk `BLOCK` remains final.

The continuation runs only when `EXECUTION_MODE=paper`,
`ENABLE_REAL_TRADING=false`, and `EXCHANGE_MODE=paper_internal`. The fill
venue is `paper_internal`. No BloFin client is called, no exchange account is
mutated, and Telegram is not an execution channel. `WATCH`, `NO_SETUP`, replay
evidence, stale evidence, provider outage, a wrong tenant, a wrong strategy
lineage, and an active kill switch create no plan and no fill. The kill switch
still records the blocked scan. A repeated scan and a process restart converge
on the same plan, fill, and open Journal trade.

The open Journal row is the handoff to the existing paper close route and
statistics pipeline. This page does not arm Watcher, Telegram, or live trading.
`watcher_orchestration_enabled` stays false unless a later activation sets it.

## Migration chain

Single Alembic head:

`c8d9e0f1a2b3` (setup-lifetime pins)
→ `e3f4a5b6c7d8` (paper evaluation observations)
→ `d9e0f1a2b3c4` (paper Telegram notification, thread, message, confirmation)
→ `e0f1a2b3c4d5` (paper Telegram activation cursor and send ledger)
→ `f1a2b3c4d5e6` (controlled runtime status).

## Still off

`WATCHER_PAPER_STAGING_ACTIVATION`, `WATCHER_ORCHESTRATION_ENABLED`,
`MARKET_WATCHER_ENABLED`, `TELEGRAM_INTERACTION_ENABLED`,
`TELEGRAM_ALERTS_ENABLED`, `TELEGRAM_PAPER_ACTIVATION_ARMED`,
`TELEGRAM_NETWORK_PERMITTED`, and `ENABLE_REAL_TRADING` stay false in the
committed templates. `TELEGRAM_INBOUND_MODE` stays `off`. Production rejects
Watcher and Telegram flags. Staging rejects Watcher orchestration unless the
paper-monitoring arm is set with live USD-M evidence and preflight passes.
Staging still rejects Telegram arming flags. This repository does not set
those arms, does not edit a live platform environment, and does not start
the worker. Real exchange mutation stays unavailable.

The controlled procedures are `docs/live_market_staging_activation.md`,
`docs/watcher_paper_activation.md`, and `docs/telegram_paper_activation.md`.
Running them is a separate human action.
