# Human vs System v3 (Slice 36)

Compares journaled trades, linked proposals, backtest context, and system recommendations. Paper mode only — real trading remains disabled.

## API

- `GET /human-vs-system/{trade_id}` — journal or proposal id
- `POST /human-vs-system/{trade_id}/analyze` — full discipline pass
- `GET /journal/entries/{id}/discipline-analysis` — journal-focused breakdown with lesson candidates

## Outputs (v3)

| Output | Notes |
|--------|-------|
| Entry/size/leverage/stop deltas | Partial when linkage missing |
| Early exit flag | From runner analyzer |
| Missed runner estimate | Conservative — labeled estimate |
| Stop loss discipline | Stop refusal analyzer |
| Plan adherence score | 0–100 breakdown |
| System would have done | From linked proposal |
| Limitations | Explicit when data missing |

## Runner analysis

Conservative post-exit MFE estimate (50% cap). No hindsight shaming. Confidence `low` without candle data.

## Stop loss refusal

Detects actual loss above planned, missing stop, rejected loss acceptance. Avoidable loss is an estimate.

## Lesson candidates

Early exits and stop violations create `lesson_candidate` rows for review — not auto-promoted to permanent rules.

## Agent

- Did I exit too early?
- What would the system have done?
- Did I respect my stop?
- How much did I lose by not following the plan?

Routes to `human_vs_system_tool`.
