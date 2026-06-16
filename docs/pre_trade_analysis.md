# Pre-Trade Analysis (Slice 33–34)

Deterministic pre-trade engine — **not LLM authority**. LLM may explain results later; agent routing sends pre-trade questions to `pretrade_analysis_tool` and sizing questions to `position_sizing_tool`.

## API

- `POST /pretrade/analyze` — full analysis output
- `POST /risk/size` — position sizing v2 only
- `POST /risk/loss-acceptance` — loss acceptance gate

Manual levels (Slice 34 UI at `/manual-levels`):

- `POST /manual-levels` — create support/resistance level
- `GET /manual-levels` — list (filter by symbol)
- `GET /manual-levels/{id}` — get one
- `PATCH /manual-levels/{id}` — update
- `DELETE /manual-levels/{id}` — delete

Pre-trade analysis accepts optional `strategy_id` and `manual_level_ids` to merge library card rules with user-drawn levels.

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

## Loss acceptance (Slice 34)

`POST /risk/loss-acceptance` returns `accepted`, `rejected`, or `needs_review` with explicit max-loss messaging. The Pre-Trade page (`/pre-trade`) and proposal flow surface `LossAcceptancePanel` — traders must acknowledge loss before paper workflows proceed where required.

Loss acceptance is a **human gate**, not execution permission. Real trading remains disabled.

## Agent examples

In Workspace, deterministic routing handles:

- *"Analyze BTC long using my strategy"* → pre-trade tool
- *"Calculate position size for this setup"* → sizing tool
- *"Is this loss acceptable?"* → loss acceptance guidance

## Safety

Paper only — no live execution. `ENABLE_REAL_TRADING=false` is enforced regardless of pre-trade recommendation.
