# Phase 5 market source contracts

Read-only perpetual evidence foundations for the first BTCUSDT vertical slice.
This is not a profitability claim and does not enable trading.

## Scope

Implemented:

- typed market identities (venue, market type, instrument, timeframe, source, provider)
- closed OHLCV contracts and forming-candle rejection
- ordered perpetual `TradeEvent` with versioned aggressor semantics
- trade-stream cursor, reconnect epochs, and fail-closed gap detection
- freshness policy (first-slice latest trade ≤ 10 seconds)
- provider provenance (`fallback_used` cannot be true)
- deterministic quote-volume CVD and signed quote flow
- Binance USD-M public REST adapter (GET-only)
- replay fixtures (no network)

Not implemented here: watcher orchestration, Telegram, candidates, fusion predicates,
execution, BloFin submission, or journal automation. Canonical read HTTP and the
`/decision/market` honesty surface are implemented in AT-064. Watcher remains off.

## Canonical first slice

| Field | Value |
|---|---|
| Instrument | Binance USD-M linear perpetual `BTCUSDT` |
| Trigger | final 15m bars (minimum 100) |
| Context | final 4h bars (minimum 30) |
| Pattern name | Bearish Liquidity Sweep with CVD Divergence and Aggressive Sell Imbalance at 4h Resistance |
| Preferred live source | `https://fapi.binance.com` `/fapi/v1/klines` and `/fapi/v1/aggTrades` |
| Default runtime source | `PERPETUAL_EVIDENCE_SOURCE=replay` |

Spot `/api/v3/*` and Coin-M `dapi.binance.com` cannot satisfy this contract.
The legacy `binance-public` spot adapter is unchanged and is not an evidence source
for the slice.

## Finality

A kline is `FINAL` only when the provider row is complete and
`evaluated_at >= interval_end + grace`. Forming candles may be parsed but cannot
enter `ClosedOhlcvSeries` or confirm a setup.

## Trades, CVD, and signed flow

Binance aggTrade `m=true` means the buyer was the maker, so the aggressor is the
seller (`binance-usdm-aggtrade/buyer-is-maker/v1`).

For linear USD-M:

- `quote_quantity = price * quantity * contract_multiplier`
- buyer aggressor contributes `+quote_quantity`
- seller aggressor contributes `-quote_quantity`
- arithmetic is unrounded Decimal

First-slice CVD window is half-open
`[open(T-32 15m), end(T))` with baseline `0` at the window start.
CVD completeness is derived from a `TradeStreamSnapshot` containing an immutable
`TradeWindowCoverageProof`. The proof binds the exact market/source identity,
retrieval or connection lineage, requested and actual half-open bounds, gap and
completeness state, first/last trade identities, ordered trade-set hash, and its
own canonical content hash. Caller-supplied COMPLETE/NONE flags and event counts
cannot establish coverage. The proof's actual bounds must cover the entire CVD
window, including quiet prefixes and suffixes.

Trigger-bar signed flow is `signed_quote_delta_T / total_quote_volume_T`.
It consumes the same proven snapshot and requires complete trigger-bar coverage,
exact identity and lineage, no gap, the versioned aggressor convention, and a
terminal trade no older than 10 seconds. Missing prefixes/suffixes, zero total
volume, stale evidence, and mismatched markets fail closed.

## AggTrades retrieval

Live `GET /fapi/v1/aggTrades` uses policy `binance-usdm-aggtrades/time-chunk-fromid/v1`:

- `startTime`/`endTime` are inclusive and must span less than one hour
- `fromId` is never combined with `startTime`/`endTime`
- a full 1000-row page continues with `fromId` only
- boundary trades are deduped by aggregate id
- incomplete chunks or sequence holes fail closed

## Cursor and reconnect

States: `INITIAL -> CONTINUOUS -> RECONNECTING -> RECOVERED`.
Every reconnect starts a new connection epoch. Current CVD is unusable until
contiguous backfill proves coverage from the pre-disconnect watermark and warm-up
completes. An unresolved gap is `UNRECOVERABLE` and fails closed. Cross-connection
CVD windows are not supported in V1. Raw stream ingestion produces only PARTIAL
coverage; COMPLETE coverage enters through a verified retrieval-bound
`OrderedTradeBatch`.

## Freshness

Policy `first-slice-btc-usdt-usdm-freshness/v1`: latest trade event must be no more
than 10 seconds old at evaluation. Time passing beyond `valid_until` fails closed
without requiring a new market event.

## Network safety

The live adapter:

- sends GET only over HTTPS
- allowlists host `fapi.binance.com` only (plain HTTP and unknown hosts fail closed)
- allowlists `/fapi/v1/ping`, `/time`, `/exchangeInfo`, `/klines`, `/aggTrades`
- never sends API keys
- never calls order, position, or account endpoints
- reports regional HTTP 401/403/418/451 and connect failures as unavailable
  without falling back to spot or mock

## Replay

`ReplayPerpetualSource` and `canonical_first_slice_fixture()` reproduce the 100/30
closed-bar series and the CVD-window trades without network access so later phases
can hash-compare identical inputs.

## Health

Default registry registers `binance-usdm-perpetual-replay` (explicit mock).
`PERPETUAL_EVIDENCE_SOURCE=binance_usdm` selects the live read-only adapter.
Live unavailability does not substitute spot data.

## Canonical live read-only pipeline (AT-064)

`app.evidence_pipeline` assembles existing USD-M contracts into
`CanonicalEvidenceWindowV1` without enabling Watcher, Telegram, or execution.

| Piece | Behavior |
|---|---|
| Catalog | BTCUSDT enabled by default; additional USD-M symbols can be registered without rewriting the assembler |
| Assembler | Closed 15m/4h OHLCV, CVD `[T-32 open, T end)`, trigger-bar signed quote flow, source identity, completeness |
| Current price | Last contracted perpetual trade in the 10s freshness window. Empty windows fail closed. No fabricated prices |
| Usable live mark | `is_live` and not mock, `fallback_used=false`, not replay, freshness `fresh` or `aging` |
| Replay | Default `PERPETUAL_EVIDENCE_SOURCE=replay`. Fixture prices are `replay_fixture`, never `live_mark` |
| HTTP | Authenticated `GET /canonical/evidence`. 200 fail-closed envelope (`price=null` when unusable). 422 unknown symbol |
| Identity | Canonical window hash is deterministic. `organization_id` is in the preimage, so tenants fork hashes |
| Watcher | `AssemblingWatcherScanEvidence` exists but is not wired into the worker. `watcher_activated` stays false |

Canonical UI (`/decision/market`) reads this GET path. Compatibility
`POST /market/analyze` snapshots are not canonical current prices.

