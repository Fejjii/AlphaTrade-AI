# Pre-Trade Analysis (Slice 33)

Deterministic pre-trade engine — **not LLM authority**. LLM may explain results later.

## API

- `POST /pretrade/analyze` — full analysis output
- `POST /risk/size` — position sizing v2 only
- `POST /risk/loss-acceptance` — loss acceptance gate

## Inputs

Symbol, exchange, direction, optional strategy library id, manual level ids, account size, max risk %, daily loss state, open positions.

## Outputs

Bullish/bearish factors, regime, trend/volume/funding/setup scores, R:R, entry zone, stop, invalidation, TP levels, runner logic, sizing recommendation, leverage recommendation, final recommendation (`no_trade`, `watch`, `small_probe`, `normal_size`, `high_conviction`), limitations.

## Confidence bands (sizing)

| Score | Band |
|-------|------|
| &lt; 40 | No trade |
| 40–59 | Watch / tiny probe |
| 60–79 | Small to normal |
| 80–100 | High quality (max ~1R unless strongly validated) |

## Formula

`position_size = maximum_acceptable_loss / stop_loss_distance`

Breakeven win rate: `1 / (1 + risk_reward_ratio)`

Paper only — no live execution.
