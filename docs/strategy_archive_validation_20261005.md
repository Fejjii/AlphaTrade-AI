# Binance archive Nested validation

Run date: 5 October 2026. Source month: September 2026.

20 of 20 series evaluated successfully. 14,500 final candles. 400 unique per-scope confirmed setup states and 1,280 forming setup states. These counts are not trades, independent opportunities, or profitability estimates.

Markets: BTCUSDT, ETHUSDT, TAOUSDT, HYPEUSDT and ZECUSDT. Native timeframes: 5m, 15m, 1h and 4h. Both directions use the unchanged provisional Nested detector independently.

Each archive SHA256 matched its Binance CHECKSUM file. Complete monthly candles passed continuity and finality checks before the bounded tail was selected. Each saved series reproduced identical family summaries and event records on a second offline run. Deliberate archive corruption was rejected.

| Market | Timeframe | Bars evaluated | Confirmed long | Confirmed short |
|---|---|---:|---:|---:|
| BTCUSDT | 5m | 1000 | 7 | 10 |
| BTCUSDT | 15m | 1000 | 11 | 6 |
| BTCUSDT | 1h | 720 | 11 | 5 |
| BTCUSDT | 4h | 180 | 1 | 1 |
| ETHUSDT | 5m | 1000 | 12 | 14 |
| ETHUSDT | 15m | 1000 | 13 | 13 |
| ETHUSDT | 1h | 720 | 13 | 6 |
| ETHUSDT | 4h | 180 | 2 | 1 |
| TAOUSDT | 5m | 1000 | 15 | 20 |
| TAOUSDT | 15m | 1000 | 20 | 11 |
| TAOUSDT | 1h | 720 | 9 | 13 |
| TAOUSDT | 4h | 180 | 2 | 1 |
| HYPEUSDT | 5m | 1000 | 18 | 19 |
| HYPEUSDT | 15m | 1000 | 18 | 17 |
| HYPEUSDT | 1h | 720 | 12 | 8 |
| HYPEUSDT | 4h | 180 | 1 | 3 |
| ZECUSDT | 5m | 1000 | 10 | 15 |
| ZECUSDT | 15m | 1000 | 13 | 22 |
| ZECUSDT | 1h | 720 | 10 | 11 |
| ZECUSDT | 4h | 180 | 6 | 0 |

## Limits

Retrospective structural replay only. No PnL, win rate, slippage, fees, historical delivery latency, or execution validation. No threshold optimization. No CVD, order flow, open interest or higher timeframe context was supplied. The 5m and 15m scopes use the last 1,000 candles of September; 1h uses 720 and 4h uses 180. These are different calendar spans.

SFP remains unavailable: archived OHLCV cannot establish original historical observation receipts. The live approved SFP preset is unchanged. Native daily and weekly require a longer archive window and remain unvalidated in this run.

No database writes, Candidate creation, strategy changes, orders, or Telegram messages. Real trading remains disabled. Archive provenance is explicitly non-live.

## Reproduce

From repository root with backend dependencies installed (httpx SOCKS environments additionally need socksio):

```sh
ENABLE_REAL_TRADING=false EXECUTION_MODE=paper EXCHANGE_MODE=paper_internal PYTHONPATH=backend/src python backend/scripts/validate_archive_history.py --month 2026-09 --output-dir var/archive-history-202609
```

Saved evidence bundle contains original ZIPs, CHECKSUM files, canonical series, detector events, full report and the runner. Full CI is not claimed for this research-only addition; focused integrity, replay, lint and format checks passed. PR197 remains draft.
