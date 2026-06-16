# Human vs System (Slice 33)

Compares actual trade behavior (journal / proposal linkage) to the system plan.

## API

`GET /human-vs-system/{trade_id}` — trade_id may be a journal entry id or proposal id.

## Comparisons

- Entry vs suggested zone
- Exit vs system TP/stop
- Size vs recommended
- Leverage vs allowed
- Stop vs invalidation
- PnL vs rule-based simulated placeholder
- Emotion tags vs emotion-free baseline

## Plan adherence score (100)

| Component | Points |
|-----------|--------|
| Entry followed plan | 20 |
| Size respected risk | 20 |
| Stop loss respected | 20 |
| Profit taking followed | 15 |
| Emotion controlled | 15 |
| Journal completed | 10 |

Groundwork only — full backtest-linked simulation is a future slice.
