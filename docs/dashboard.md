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
| `open_paper_trades` / `open_paper_trades_summary` | Proposal-flow positions + paper-validation `PaperTrade` OPEN rows, counts by source |
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

Includes both:

1. **Proposal-flow** open `Position` rows (unrealized PnL when available)
2. **Paper-validation** open `PaperTrade` rows (strategy name when linked)

Limitations explain missing unrealized marks for validation trades.

## Paper-only behavior

- No broker or exchange data
- Real trading remains disabled by default
- Developer diagnostics (usage, providers, audit) stay collapsed

See also [risk_management.md](risk_management.md) for settings and PnL source details.
