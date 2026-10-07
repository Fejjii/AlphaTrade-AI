# Dashboard

The trader-first dashboard composes deterministic, paper-only backend summaries.

## Summary endpoint

`GET /dashboard/summary` (Slice 44–45) returns:

| Section | Description |
| --- | --- |
| `safety` | Execution mode; real trading disabled flag |
| `daily_discipline` | Timezone-aware snapshot: trades today, paper PnL, protective signals, limits, `risk_settings_source`, `pnl_sources` |
| `discipline_score` | Latest deterministic analytics score, band (`strong` / `good` / `caution` / `review_needed`), contributors — no LLM |
| `strategy_readiness` | Counts and top strategies needing action |
| `active_paper_validations` | Running paper validation runs |
| `open_paper_trades` / `open_paper_trades_summary` | Canonical `JournalTrade` OPEN paper execution/validation rows, counts by source and bounded details |
| `alerts_lessons` | Unread alerts and pending lessons |
| `market_watcher` / `bridge` | Optional automation status |
| `next_recommended_action` | Priority-ranked trader guidance |

## Daily discipline card

Shows:

- Discipline status (`calm`, `caution`, `locked`)
- Discipline score band when available
- Configured daily loss limit, target, max trades
- Loss / green-day / frequency protective signals
- Limitations in a collapsed details section

## Open paper trades

Uses the same owner-private canonical `JournalTrade` sources as Attention:
`paper_execution` and `paper_validation`, with status `open`. All accounts, venues
and dates are included. Manual demo tests and non-paper/manual/imported sources
are excluded from this count; recent trades deliberately show all Journal sources.

Counts cover all matching rows. Details include at most ten rows in the summary
(eight on the Dashboard), ordered by recorded entry time with creation time as a
fallback. `journal_trade_id` links to `/journal?trade_id=…`; account and exchange
identify each record's scope. `proposal_flow_count` remains as a compatibility
alias for `paper_execution_count`. Linked legacy position/paper IDs remain available.
The summary does not fall back to a different store after a canonical read failure.

Current unrealized PnL and open exposure are unavailable from these recorded facts.
They are null, never inferred from absolute unrealized PnL or manufactured as zero.

## Different scopes on the same Dashboard

Recent trades use `/journal/trades`, ordered by creation time, with no date,
source, account or status filter. This replaces the legacy journal-note list.
Recorded `net_pnl` and canonical trade links are used; open trades show Open.

Portfolio value and closed-trade metrics still cover proposal/validation history
through `Position` and `PaperTrade`. Daily discipline retains its existing
user-timezone day window and sources. Both scopes are labeled in the UI; an older
canonical open trade does not imply a trade opened today or a closed performance
sample. No history backfill or execution-record rewrite is performed.

See [the presentation repair handoff](presentation_repairs_20261007.md) for the
source trace, focused verification and deployment acceptance steps.

## Paper-only behavior

- Recorded venue attribution only; Dashboard reads never contact an exchange
- Real trading remains disabled by default
- Developer diagnostics (usage, providers, audit) stay collapsed

See also [risk_management.md](risk_management.md) for settings and PnL source details.
