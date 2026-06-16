# Trading analytics (Slice 31)

Deterministic trading intelligence for paper-mode workflows: setup tracking, trade review, discipline scoring, and risk behavior visibility.

## Setup tracking

Each **proposal**, **paper order**, **position**, and **journal entry** links to a `strategy_id` / setup type:

- `htf_trend_pullback`
- `liquidity_sweep_reversal`
- `countertrend_short_build`
- `passive_level_order`
- `profit_protection`
- `green_day_guard`
- `mental_capital_guard`
- `manual_review`

Paper execution copies setup type from the approved proposal onto orders and positions.

## API (tenant-scoped, auth required)

| Endpoint | Access |
|----------|--------|
| `GET /analytics/setups` | Owner, trader, viewer |
| `GET /analytics/trade-review` | Owner, trader, viewer |
| `GET /analytics/discipline` | Owner, trader, viewer |
| `GET /analytics/risk-behavior` | Owner, trader, viewer |

Mutations on trading records remain owner/trader only.

## Discipline score (deterministic)

Score 0–100 and letter grade from recent proposals/trades:

1. Stop loss present  
2. Invalidation defined  
3. Risk limits respected (no block)  
4. Approval flow followed  
5. Journal completed when executed  
6. No overtrading warnings  
7. Green-day guard respected  
8. Daily loss guard respected  
9. Paper execution matches approved proposal  

The LLM does **not** compute this score.

## Risk behavior analytics

Aggregates risk warnings, blocks, approval outcomes, paper rejections, and journal completion rate after paper fills.

## Journal learning loop

- Journal form supports setup selector, mistake/emotion tags, lessons, improvement rules.  
- `GET /journal/prefill` seeds entries from proposals or positions.  
- Lessons and rules sync to RAG via `JournalRagSyncService` (when enabled).  
- Analytics summaries are **not** auto-ingested into RAG.  
- Agent RAG retrieval prioritizes journal/mistake sources for review-style questions.

## Agent tool

`analytics_summary_tool` — inputs: `user_id`, `organization_id`, optional date range and setup type. Returns setup stats, discipline summary, repeated mistakes/emotions, and improvement suggestions. Used by the workspace graph, not direct SQL.

## Paper trading limitations

- Win/loss and PnL reflect **paper positions** and journal labels, not exchange fills.  
- Small sample sizes can skew averages.  
- Historical rows before Slice 31 may lack `strategy_id` on positions/orders (backfilled from proposal linkage when available).
- Slice 33 adds separate user strategy library analytics path; setup stats still use `StrategyId` enum on proposals/journal.

## Why deterministic

Analytics are rule-based aggregates for auditability, testability, and stable UX. Narrative LLM output may explain results but never overrides scores or risk authority.
