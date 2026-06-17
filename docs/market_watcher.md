# Market Watcher (Slice 41)

Read-only market scanning foundation for paper validation prep. **No orders, no broker or exchange execution.**

## Defaults

| Env flag | Default |
|----------|---------|
| `MARKET_WATCHER_ENABLED` | `false` |

When disabled, manual scan returns a clear disabled result without fetching data.

## Responsibilities

1. Load watchlist symbols (or `MARKET_WATCHER_DEFAULT_SYMBOLS`)
2. Fetch read-only ticker snapshots via market data provider
3. Check data freshness
4. Persist observations for eligible paper validation scan decisions later
5. Never place orders or call exchange trading endpoints

## Observations

Stored in `market_watcher_observations`:

- symbol, exchange, timeframe, observed_at, price, volume
- `data_freshness`, `status` (`fresh`, `stale`, `unavailable`)
- optional links to strategy, paper validation run, or alert

Scan history (last 20 runs) is kept in-memory per process for lightweight status; persisted observations survive restarts.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/market-watcher/status` | Env flag, watched symbols, last scan |
| POST | `/market-watcher/scan` | Manual read-only scan (owner) |
| GET | `/market-watcher/history` | Recent scan summaries |
| GET | `/market-watcher/observations` | Persisted observations |

## UI

**Market Watcher** (`/market-watcher`) — status, disabled copy, manual scan button.

## Agent

Deterministic tools answer: watcher running?, symbols watched?, data fresh?, setup signals?, run scan (with confirmation).

Paper only — no live trading path.
