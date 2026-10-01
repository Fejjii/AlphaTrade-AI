# Real-print five-minute order flow and bounded CVD

Branch: `codex/market_intelligence_cvd_orderflow_001`
Exact base: `3fc730347e450f537a9fdd708b4a0570555cd794` (PR170)

`GET /canonical/evidence` exposes `order_flow` alongside the existing OI/funding
`market_intelligence`. Acquisition uses the existing process-owned Binance USD-M
and Bybit USDT perpetual sources, contract verification, GET-only allowlisted
client, request budget, trade coverage proofs, reduction, bounded caches, and
whole-venue failover. There is no new market-data service, persistence, candle
volume inference, execution change, trading permission, or probability estimate.

## Verified provider contracts

Checked 2026-10-01 from official provider repositories:

- [Binance official public-data contract](https://github.com/binance/binance-public-data#futures): futures aggregate-print columns match `/fapi/v1/aggTrades` and explicitly include “Was the buyer the maker.” `m=true` means buyer is maker and seller is aggressor; `m=false` means buyer is aggressor. Only actual JSON booleans are accepted; strings/numbers are refused.
- [Binance official USD-M connector](https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/market.py): aggregate prints combine fills at the same time, price and order. Requests use the existing time-window/from-ID pagination contract, inclusive provider milliseconds, and half-open internal windows.
- [Bybit official recent-public-trade contract](https://github.com/bybit-exchange/docs/blob/master/docs/v5/market/recent-trade.mdx): `side` is explicitly “Side of taker”; `size` is execution quantity. Linear requests have `category=linear` and up to 1,000 records. This endpoint offers recent history, without arbitrary historical pagination.

The fetched official Binance public-data README has SHA-256
`2e133d9945a9263a02781369078e72805eff074680f305cd5460016471c6caad`;
the fetched Bybit recent-trade document has SHA-256
`e754dc9ba6dfcd8f12cd73c6210e239580ccbeb7b332dc4891d667e170b6030d`.
These are verification receipts, not runtime claims of live venue connectivity.

Both adapters verify the requested exchange contract as a trading, USDT linear
perpetual before acquisition. Delivery, inverse, spot, missing contracts, and
unverified products cannot supply usable evidence. Binance duplicate IDs with
identical contents collapse; conflicting duplicates or missing aggregate IDs
refuse coverage. Out-of-order delivery is sorted by authoritative aggregate IDs,
and event times must then be nondecreasing. Invalid maker flags cannot be hidden
by duplicate signatures or cache fingerprints.

Bybit keeps the existing execution-ID ledger and overlap watermark. An initial
page must contain a print **strictly before** the requested start, proving the
whole start millisecond bucket. Its proven tail must reach or pass the closed
end. A later page must overlap the last proven execution ID; a dropped watermark,
evicted prefix, unknown side, or unprovable end yields `INCOMPLETE`. Provider
`seq` is not treated as a per-print ID. After the existing ledger proves coverage,
the new reduction uses window-local ordinals, keeping hashes stable across
synthetic rank offsets from different poll histories. The existing ledger is
unchanged by that normalization.

## Bounds, units and calculations

Every acquisition accepts exactly two UTC-aligned, closed five-minute windows:
`[window_start, window_end)`, spanning ten minutes. Canonical optional reads end
at the latest five-minute boundary at or before observation time. Strategy-required
reads end at the selected fifteen-minute trigger close. Forming, unaligned,
wrong-timeframe and overlong requests are refused before any provider request.

Trade objects are released after reduction. The response contains at most two
five-minute aggregates. Binance streams at most 200 pages of 1,000 prints per
existing time chunk, under the existing request budget; its reduced TTL cache
remains bounded and now separates five-minute and fifteen-minute identities.
Bybit retains at most three consumer lineages (monitor, canonical setup, and new
five-minute intelligence), at most 10,000 prints per lineage and a fifteen-minute
horizon. Existing history release trims each lineage to one provider page.
Unprovable data remains incomplete, including high-volume markets where Bybit's
recent page cannot reach the requested ten-minute prefix. Reads do not fabricate
history or introduce a background polling system.

Each five-minute aggregate exposes:

| Field | Definition |
| --- | --- |
| aggressive buy/sell base volume | Sum of normalized base execution quantities by verified taker side |
| aggressive buy/sell quote volume | Sum of price × quantity × verified linear contract multiplier by side |
| signed volume delta | Buy base volume − sell base volume |
| quote volume delta | Buy quote volume − sell quote volume |
| trade count | Normalized public print count; Binance counts aggregate records, not individual fills inside an aggregate |
| buy sell imbalance ratio | (Buy quote − sell quote) / (Buy quote + sell quote); bounded to [−1, 1]; null for zero denominator |
| rolling CVD | Cumulative signed **base** volume from the declared ten-minute start through this five-minute close |
| rolling quote CVD | Cumulative signed quote volume over the same declared window |

CVD is calculated internally, **not an absolute provider-published CVD**. Its
baseline is zero at each declared window start. Rolling the observation window
rebuilds the sum rather than carrying prior values. Venue/instrument/source and
window start identify the series; venue failover or recovery rebuilds the
venue-bound series with zero baseline. Binance and Bybit never share a CVD sum.
Base/quote/CVD units, calculation/reset/state policies, window bounds, full
existing instrument/source/venue/market identity, latest real print event time,
observation time, coverage and trade-set hashes, availability, completeness,
freshness and semantic hash are included in every observation.

`cvd_change` is the final five-minute base delta. `cvd_slope_base_per_second` is
that delta divided by 300 seconds. Deterministic directional states require
nonempty prints in **both** comparison windows:

- `cvd_supportive_side`: buy for positive final base delta; sell for negative final base delta; null for zero. This describes the latest CVD change, independent of the sign of the bounded cumulative total.
- `cvd_weakening`: true when consecutive nonzero base deltas have the same sign and final absolute delta is smaller; false when the same-sign magnitude does not decrease; null on reversal/zero/insufficient data.
- `order_flow_strengthening_side`: the same nonzero side in both windows, larger final absolute base delta, aligned quote-imbalance signs and a strictly larger absolute quote imbalance. Otherwise null.
- `cvd_divergence`: `bullish_print_close_to_close` when terminal public-print price falls while final base CVD change is positive; `bearish_print_close_to_close` when price rises while that change is negative; otherwise null. These are two print-close points, explicitly **not** pivot/swing divergence. The existing fifteen-minute first-slice swing divergence remains separate.

No state is a profitability probability or trading threshold. Equal/missing
inputs cannot be promoted to directional confirmation. A proven empty five-minute
subwindow has zero print sums and an undefined ratio; comparison states remain
null. A drained Binance request with no prints at all returns `MISSING`.

## Availability and canonical input roles

| State | Meaning |
| --- | --- |
| AVAILABLE | Verified complete closed coverage, valid print sums and event age within policy |
| MISSING | Drained supported Binance history contains no prints, or transport/region/HTTP/rate-limit failure |
| STALE | Complete retained window whose latest actual print is older than the consumer limit |
| UNSUPPORTED | Unverified product or source without a verified five-minute public-print contract; replay does not invent live five-minute facts |
| INCOMPLETE | Missing coverage/prefix/end/overlap/IDs, conflicting duplicates, malformed rows, future times or inconsistent snapshots |

The versioned freshness policy is 600 seconds from the latest actual print,
with no future clock-skew allowance. The exact 600-second boundary is inclusive.
Observation time never substitutes for event time. Unavailable facts carry no
usable aggregates or directional states. Stale facts retain values for inspection,
but cannot satisfy required roles. Semantic hashes bind provider facts, policies,
units, bounds, coverage and states; receipt/observation clocks and consumer age
are excluded. Consumers independently recheck freshness, structural consistency,
identity, method/reset/units, and hashes.

New `CVD_5M` and `ORDER_FLOW_5M` required roles bind hashed public observations and
the same payload into the existing assessment command/evidence bundle/window.
The evaluator checks trigger-close and command-payload binding again, using a
shared input gate also applied to the Strategy Brain family dispatch path. A
family dispatch cannot bypass required-print validation. Every
unavailable state refuses a required role. Optional intelligence stays outside
the existing setup identity and cannot silently strengthen confirmation. No new
strategy grammar or strategy family is enabled.

An eligible upstream failure invokes the existing explicit whole-source switch.
Canonical reads discard earlier quote/setup/OI/funding/order-flow facts and
restart under the active venue. Incomplete/stale/unsupported prints are never
silently filled from another venue.

## Validation

Deterministic tests use official-shaped mocked public payloads and recorded
existing first-slice fixtures. They cover normalization/mapping, half-open
boundaries, duplicates/conflicts, out-of-order delivery/events, missing prints,
incomplete/stale windows, strict Bybit coverage, bounds/cache/retention, venue
failover/atomic restart, CVD reset/replay, semantic hashing, required refusals,
optional identity preservation and consumer binding. No live exchange connectivity
or live values are claimed. Exact test results are recorded in `HANDOFF.md`.
