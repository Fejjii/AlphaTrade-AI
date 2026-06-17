# Backtesting (Slice 35-36)

Deterministic **backtest engine v1** replays stored historical OHLCV candles. Historical simulation only — **not** a profit guarantee. Real trading remains disabled.

## What v1 supports

- Historical candle storage (`historical_candles` table) with uniqueness on symbol + exchange + timeframe + open_time
- Ingestion via `POST /market/history/ingest` (mock deterministic data in tests; Binance public when configured)
- Backtest replay with fees (`fees_bps`) and slippage (`slippage_bps`)
- Simple machine-readable rule adapters:
  - `htf_trend_pullback` — EMA pullback reclaim
  - `liquidity_sweep_reversal` — sweep and reclaim
  - Generic cards with keywords (pullback, EMA, RSI, TP1, stop %, etc.)
- Simulated stop, TP1/TP2/TP3, optional runner trail
- Full metrics: win rate, profit factor, expectancy, drawdown, fees, slippage, equity curve
- Simulated trade log (`backtest_trades` + `GET /backtests/{id}/trades`)
- Conservative promotion: `needs_structured_rules`, `needs_more_sample_size`, `paper_eligible`, `restricted`, etc.

## What v1 does not support

- Full natural-language rule parsing (vague rules return `needs_structured_rules`)
- Walk-forward optimization, monte carlo, or live order execution
- Funding cost modeling beyond a neutral assumption label
- Multi-symbol portfolios in one run
- Guaranteed statistical significance on small samples

## Fees and slippage

- **Fees:** applied on entry and exit notional: `fees_bps / 10000 × price × size`
- **Slippage:** adverse fill adjustment: `slippage_bps / 10000 × price` on entry and exit

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/strategies/{id}/backtests` | Run backtest v1 |
| GET | `/strategies/{id}/backtests` | List runs with metrics |
| GET | `/backtests/{id}` | Run detail |
| GET | `/backtests/{id}/trades` | Simulated trades |
| POST | `/market/history/ingest` | Store candles |
| GET | `/market/history/candles` | Debug listing |

## Migration

Apply through head **`n4o5p6q7r8s9`** after Slice 35:

```bash
cd backend && uv run alembic upgrade head
```

## Structured rules priority (Slice 36)

Backtest engine resolves rules in order:

1. **structured** — saved rule blocks on strategy version
2. **adapter** — keyword parser on text card
3. **default_setup** — known setup type defaults
4. **unsupported** — returns `needs_structured_rules`

## Post-exit runner analysis (Slice 37)

Human-vs-system runner analysis may fetch historical candles after exit time to compute MFE/MAE, TP2/TP3 hit flags, and capped missed-profit estimates. When candles are missing, analysis returns explicit limitations — no fabricated hindsight PnL.

Result includes `rule_engine_source` in the backtest payload.

## Safety

- Backtest results are labeled historical simulation only
- Small sample sizes produce strong warnings
- Incomplete or gappy data marks results `unreliable_data`
- No API path executes real exchange orders

See also: [strategy_library.md](strategy_library.md) · [paper_validation.md](paper_validation.md)
