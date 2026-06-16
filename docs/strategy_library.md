# Strategy Library (Slice 33)

Tenant-scoped user strategy cards with versioning, validation placeholders, and optional RAG ingest.

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/strategies` | Create strategy + v1 card |
| GET | `/strategies` | List user strategies |
| GET | `/strategies/{id}` | Get strategy with latest card |
| PATCH | `/strategies/{id}` | Update metadata or new card version |
| POST | `/strategies/{id}/versions` | Create explicit version |
| GET | `/strategies/{id}/versions` | List versions |
| GET | `/strategies/modules` | List deterministic code modules (unchanged) |
| POST | `/strategies/evaluate` | Evaluate code module (unchanged) |

## Strategy card fields

`strategy_name`, `market_type`, `asset_universe`, `timeframes`, `entry_conditions`, `confirmation_conditions`, `invalidation`, `stop_loss`, `take_profit_plan`, `runner_plan`, `position_sizing`, `add_rules`, `no_trade_rules`, `backtest_rules`, `success_criteria`, `validation_status`.

## RAG

Validated or in-review cards ingest as `STRATEGY_TEMPLATE` documents. Analytics summaries are not auto-ingested.

## Migration

Apply `k1l2m3n4o5p6` before using library APIs in staging.
