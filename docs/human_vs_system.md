# Human vs System (Slice 33–34)

Compares actual trade behavior (journal / proposal linkage) to the system plan. Slice 34 adds structured **delta fields** for UI and agent tooling; several comparisons remain placeholders until the backtest engine lands (Slice 35+).

## API

`GET /human-vs-system/{trade_id}` — trade_id may be a journal entry id or proposal id.

Agent routing: *"Compare my trade to the system plan"* → `human_vs_system_tool`.

## Comparisons

- Entry vs suggested zone (`entry_delta_pct` when data available)
- Exit vs system TP/stop (`exit_delta`, `stop_behavior_delta`)
- Size vs recommended (`size_delta_pct`, `size_vs_recommended_pct`)
- Leverage vs allowed (`leverage_delta`)
- Stop vs invalidation
- PnL vs rule-based simulated placeholder (`pnl_vs_simulated_placeholder`)
- Emotion tags vs emotion-free baseline
- Missed runner profit (`missed_runner_profit_placeholder`)

## Plan adherence score (100)

| Component | Points |
|-----------|--------|
| Entry followed plan | 20 |
| Size respected risk | 20 |
| Stop loss respected | 20 |
| Profit taking followed | 15 |
| Emotion controlled | 15 |
| Journal completed | 10 |

## Slice 34 v2 limitations

| Field / behavior | Status |
|------------------|--------|
| Entry/size deltas | Populated when journal/proposal links exist; may be partial |
| Exit / stop behavior | Qualitative notes; not tick-level replay |
| PnL vs simulated | **Placeholder** — `"Rule-based simulated PnL placeholder — backtest engine not connected."` |
| Runner profit | **Placeholder** — live runner tracking not connected |
| Backtest-linked simulation | Future slice (depends on real backtest engine) |

Human-vs-system is **review and coaching**, not a performance guarantee. Paper execution only; no broker fills.
