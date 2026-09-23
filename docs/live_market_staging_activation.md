# Staging live USD-M market evidence activation

Controlled, read-only Binance USD-M market evidence for staging.
This page is step 3 of the package in `docs/controlled_paper_activation.md`.
Applying it does not by itself activate Watcher or Telegram, and it does not
place, cancel, or authenticate exchange requests.

Public REST only: `GET https://fapi.binance.com` `/fapi/v1/klines` and
`/fapi/v1/aggTrades` (plus ping, time, and exchangeInfo). No API key is read
or sent. Spot and Coin-M hosts are rejected. Missing, stale, gapped, or
wrong-source evidence fails closed. The live quote rule stays 10 seconds.
BTCUSDT is the default catalog symbol.

The process default remains `PERPETUAL_EVIDENCE_SOURCE=replay` so local and CI
tests stay deterministic and offline. Replay is also the rollback value.

## Exact staging environment changes

Apply these on the staging **API** and **worker** services together. Do not
add Binance or other exchange credentials.

| Variable | Previous intended value | Activation value |
|---|---|---|
| `PERPETUAL_EVIDENCE_SOURCE` | `replay` | `binance_usdm` |
| `MARKET_DATA_FUTURES_BASE_URL` | unset (code default `https://fapi.binance.com`) | `https://fapi.binance.com` |
| `PERPETUAL_EVIDENCE_TIMEOUT_SECONDS` | `10` | `10` |

Leave these unchanged:

| Variable | Required value |
|---|---|
| `ENVIRONMENT` | `staging` |
| `EXECUTION_MODE` | `paper` |
| `ENABLE_REAL_TRADING` | `false` |
| `EXCHANGE_MODE` | `paper_internal` |
| `BLOFIN_DEMO_ENABLED` | `false` |
| `BLOFIN_API_KEY` | empty |
| `BLOFIN_API_SECRET` | empty |
| `BLOFIN_API_PASSPHRASE` | empty |
| `MARKET_WATCHER_ENABLED` | `false` |
| `MARKET_WATCHER_BRIDGE_ENABLED` | `false` |
| `MARKET_WATCHER_BRIDGE_AUTO_TICK` | `false` |
| `WATCHER_ORCHESTRATION_ENABLED` | `false` |
| `TELEGRAM_ALERTS_ENABLED` | `false` |
| `TELEGRAM_INTERACTION_ENABLED` | `false` |
| `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED` | `false` |
| `ALERT_DELIVERY_ENABLED` | `false` |

Do not set `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `BINANCE_FUTURES_API_KEY`,
`BINANCE_FUTURES_API_SECRET`, `FAPI_API_KEY`, or `FAPI_API_SECRET`.
`MARKET_DATA_PROVIDER=binance` is the legacy spot reader. It is not the
perpetual evidence source and is not a fallback when USD-M is down.

`render.yaml` and `.env.staging.example` already carry the activation values.
Production (`.env.production.example`) stays `replay`. The process refuses
`binance_usdm` when `ENVIRONMENT=production`.

## Activation steps

1. Merge and deploy this revision only when a human intends to activate.
   This repository change does not edit the live platform environment and
   does not deploy.
2. Set the activation variables above on both staging services. Remove any
   Binance or BloFin credential if one is present. Confirm Watcher and
   Telegram flags stay false.
3. Restart both services so `Settings` reloads. Startup fails closed if the
   futures host, credentials, Watcher, Telegram, or trading posture is unsafe.
4. Validate without writing environment variables:

```bash
# Offline wiring check (CI)
./scripts/validate-live-market-staging.sh --self-check

# After the human restart, against the running API
BASE_URL=https://YOUR-API.onrender.com \
  ./scripts/validate-live-market-staging.sh --remote --require-active
```

5. Confirm `GET /health`:
   - `perpetual_evidence_source` = `binance_usdm`
   - `perpetual_evidence_activation` = `active`
   - `live_quote_freshness_seconds` = `10`
   - `first_perpetual_symbol` = `BTCUSDT`
   - `exchange_credentials_used_for_market_evidence` = `false`
   - `spot_fallback_permitted` = `false`
   - `fabricated_fallback_permitted` = `false`
   - `execution_mode` = `paper`
   - `real_trading_enabled` = `false`
   - Watcher and Telegram flags = `false`
6. Authenticated `GET /canonical/market-status?symbol=BTCUSDT` must show
   `activation.state=active`, source family `binance_usdm_futures_public`,
   and `fallback_used=false`. A fresh last trade inside 10 seconds may be
   `live_mark`. Outage, gap, stale evidence, wrong symbol, and wrong source
   return no usable price.

## Rollback steps

1. Set `PERPETUAL_EVIDENCE_SOURCE=replay` on both staging services.
2. Leave `ENABLE_REAL_TRADING=false`, `EXECUTION_MODE=paper`, and the Watcher
   and Telegram flags false. Do not add credentials while rolling back.
3. Restart both services.
4. Confirm:

```bash
BASE_URL=https://YOUR-API.onrender.com \
  ./scripts/validate-live-market-staging.sh --remote --expect inactive
```

5. `GET /health` shows `perpetual_evidence_source=replay` and
   `perpetual_evidence_activation=inactive`.
6. `GET /canonical/market-status` shows `mode=replay`,
   `availability=replay`, and `current_price.presentation=replay_fixture`.
   That price is not a live mark.

Replay fixtures remain available for deterministic tests regardless of the
staging value. Switching staging back to replay does not delete them.
