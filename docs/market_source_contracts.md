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
- Bybit linear USDT perpetual public REST adapter (GET-only), used as an explicit
  secondary whole-source failover and never mixed into a Binance window
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
| Process default | `PERPETUAL_EVIDENCE_SOURCE=replay` (local, CI, production, rollback) |
| Staging intended source | `PERPETUAL_EVIDENCE_SOURCE=binance_usdm` (public read-only; see `docs/live_market_staging_activation.md`) |
| Staging secondary | `PERPETUAL_EVIDENCE_SECONDARY_SOURCE=bybit_usdt_perpetual` at `https://api.bybit.com` (`GET /v5/market/kline` and `/v5/market/recent-trade`, `category=linear` only). A Binance HTTP 418, HTTP 429, or regional failure switches the whole observation onto Bybit and opens a new connection epoch. A recent-trade buffer that does not reach the requested start fails closed. Bybit `seq` is a cross sequence, not a per-trade id. A later read that drops the last proven print fails closed. |

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
completes. An empty or incomplete backfill fails closed for that attempt and keeps
the reconnect epoch so a later bounded attempt can succeed. It does not publish a
usable price. Cross-connection CVD windows are not supported in V1. Raw stream ingestion produces only PARTIAL
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
- reports regional HTTP 401/403/451 and connect failures as unavailable
  without falling back to spot or mock
- treats HTTP 418 as a temporary IP ban: bounded retry only when Retry-After
  fits the backoff cap; a longer ban is not followed by another request

## Replay

`ReplayPerpetualSource` and `canonical_first_slice_fixture()` reproduce the 100/30
closed-bar series and the CVD-window trades without network access so later phases
can hash-compare identical inputs.

## Health

Default registry registers `binance-usdm-perpetual-replay` (explicit mock).
`PERPETUAL_EVIDENCE_SOURCE=binance_usdm` selects the live read-only adapter.
Staging's intended value is that live adapter; the process default and the
rollback value stay `replay`. Production refuses the live source. Live
unavailability does not substitute spot data. See
`docs/live_market_staging_activation.md`.

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
| Identity | Canonical window hash is deterministic. `organization_id` is in the preimage, so tenants fork hashes. CVD, signed flow, and coverage bind through `PublicMarketObservation` payload hashes — a trade/CVD correction with unchanged candles changes the window |
| Freshness | The 10s last-trade rule applies only while the post-close live confirmation window is open. Later in the next interval, closed bars are historical evidence. Current price keeps its own 10s clock. Setup expiry stays on subsequent final bars. Replay and live provenance stay separate |
| Watcher | `AssemblingWatcherScanEvidence` exists but is not wired into the worker. It returns evidence only after resolving a tenant-scoped approved compiled `ExecutableStrategyPolicy`. Read-projection placeholder IDs never mint Candidates. `watcher_activated` stays false |

Canonical UI (`/decision/market`) reads this GET path. Compatibility
`POST /market/analyze` snapshots are not canonical current prices.

## Continuous live read-only monitor (AT-069)

`app.market_monitor` ticks existing USD-M GET-only sources and the Phase 5
trade-stream assembler. It does not enable Watcher, Telegram, or execution.

| Piece | Behavior |
|---|---|
| Scope | BTCUSDT first; additional catalog symbols reuse the same runtime |
| Current price | Last contracted perpetual trade in the 10s window. Replay is `replay_fixture`. Outage, gap, conflict, and wrong-source fail closed (`price=null`) |
| Availability | `fresh` / `stale` / `degraded` / `unavailable` / `replay` — never show compatibility or demo-seed as live |
| Stream | `INITIAL -> CONTINUOUS -> RECONNECTING -> RECOVERED`. New process = new connection epoch |
| Rate limit | HTTP 429 is `RateLimitedError` with Retry-After backoff. HTTP 418 is a temporary ban (`UpstreamBanError`), not a regional block. Not a fabricated fallback |
| Gaps | Sequence holes and out-of-order trades fail closed. Incomplete backfill stays on the same reconnect epoch and can be retried after backoff. No usable price until coverage is complete |
| Identity | Semantic hash excludes connection ids, receive times, and backoff. A later trade or price correction changes the hash |
| HTTP | Authenticated `GET /canonical/market-status`. 422 unknown symbol. `watcher_activated=false` |
| Default | Process default `PERPETUAL_EVIDENCE_SOURCE=replay`. Staging intended source is read-only `binance_usdm`; rollback is `replay` |

Remaining Watcher work: wire the disabled worker to this monitor + AT-064 assembler
and an approved compiled policy. Do not enable Watcher in this layer.

