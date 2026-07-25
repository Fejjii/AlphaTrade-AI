# Human vs System v3 (Slice 36)

Compares journaled trades, linked proposals, backtest context, and system recommendations. Paper mode only — real trading remains disabled.

## API

- `GET /human-vs-system/{trade_id}` — journal or proposal id (per-trade analyzers)
- `POST /human-vs-system/{trade_id}/analyze` — full discipline pass
- `GET /journal/entries/{id}/discipline-analysis` — journal-focused breakdown with lesson candidates
- `GET /journal/comparison` — **aggregate** human-vs-system cohort/scorecard comparison
  with decision-quality metrics over closed journal trades (AT-036); record-only,
  does not invoke per-trade `HumanVsSystemService` orchestration. Frontend:
  `/journal/comparison`.

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

## Runner analysis (Slice 37)

Fetches post-exit candles when available via historical candle service. Computes MFE/MAE after exit, TP2/TP3 hit flags, runner invalidation, and capped missed-profit estimate (50% of MFE). Returns limitations when candles missing — no fake estimates.

## Lesson review workflow

See [lesson_workflow.md](lesson_workflow.md). API: `/lessons/candidates`, accept/reject/archive, `/lessons/accepted`.

## Agent

- Did I exit too early?
- What would the system have done?
- Did I respect my stop?
- How much did I lose by not following the plan?

Routes to `human_vs_system_tool`.
