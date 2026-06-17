# Market Watcher (Slice 41–42)

Read-only market scanning foundation for paper validation prep. **No orders, no broker or exchange execution.**

## Defaults

| Env flag | Default |
|----------|---------|
| `MARKET_WATCHER_ENABLED` | `false` |
| `MARKET_WATCHER_BRIDGE_ENABLED` | `false` |
| `MARKET_WATCHER_BRIDGE_AUTO_TICK` | `false` |

When disabled, manual scan or bridge tick returns a clear disabled result without side effects.

## Watcher responsibilities

1. Load watchlist symbols (or `MARKET_WATCHER_DEFAULT_SYMBOLS`)
2. Fetch read-only ticker snapshots via market data provider
3. Check data freshness
4. Persist observations for eligible paper validation scan decisions
5. Never place orders or call exchange trading endpoints

## Bridge (Slice 42)

`MarketWatcherBridgeService` connects fresh observations to eligible paper validation runs:

1. Load recent observations
2. Find active paper validation runs
3. Match symbol, exchange, timeframe
4. Skip stale data and blocked strategies (eligibility gates)
5. Trigger **paper validation scan only** via runtime service
6. Record decisions in `market_watcher_bridge_decisions`
7. Create in-app alerts with source `market_watcher_bridge`

**Manual bridge tick only** by default (`POST /market-watcher/bridge/tick`, owner). Optional auto tick is gated by `MARKET_WATCHER_BRIDGE_AUTO_TICK=true` (not enabled in production defaults).

Bridge never calls exchange trading APIs or opens real trades.

## Observations

Stored in `market_watcher_observations`:

- symbol, exchange, timeframe, observed_at, price, volume
- `data_freshness`, `status` (`fresh`, `stale`, `unavailable`)
- optional links to strategy, paper validation run, or alert

Bridge decisions stored in `market_watcher_bridge_decisions` with decision type, reason, blockers, optional triggered scan and alert ids.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/market-watcher/status` | Env flag, watched symbols, last scan |
| POST | `/market-watcher/scan` | Manual read-only scan (owner) |
| GET | `/market-watcher/history` | Recent scan summaries |
| GET | `/market-watcher/observations` | Persisted observations |
| GET | `/market-watcher/bridge/status` | Bridge env flags and last tick summary |
| POST | `/market-watcher/bridge/tick` | Manual bridge tick (owner, paper scan only) |
| GET | `/market-watcher/bridge/history` | Bridge decision history |

## UI

**Market Watcher** (`/market-watcher`) — watcher status, bridge status, observations, bridge decisions, manual scan and bridge tick (when enabled), paper-only disclaimer.

## Agent

Deterministic tools answer: watcher running?, symbols watched?, data fresh?, bridge enabled?, bridge skip reason?, triggered scans?, linked runs?, run bridge tick (with confirmation).

Paper only — no live trading path.

## Smoke test

```bash
./scripts/market-watcher-smoke.sh   # requires running backend (Docker or local)
```

Verifies watcher status, manual scan/disabled response, bridge status/tick, bridge history, observations, alerts summary, and `real_trading_enabled=false`.
