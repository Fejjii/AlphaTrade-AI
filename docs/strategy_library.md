# Strategy Library (Slice 33–34)

Tenant-scoped user strategy cards with versioning, Strategy Lab UI, backtest/paper-validation placeholders, and optional RAG ingest. **Paper only** — no real exchange execution.

## Lifecycle

| Stage | `validation_status` | Meaning |
|-------|---------------------|---------|
| Draft | `draft` | Card editable; not validated |
| In review | `in_review` | Awaiting human review |
| Validated | `validated` | Eligible for RAG ingest and paper validation tracking |
| Archived | `archived` | Read-only historical version |

Version bumps create a new `user_strategy_versions` row; the parent strategy points at the latest card. `paper_eligible` (Slice 34) flags strategies that passed placeholder paper-validation criteria — **does not enable live trading**.

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/strategies` | Create strategy + v1 card |
| GET | `/strategies` | List user strategies |
| GET | `/strategies/{id}` | Get strategy with latest card |
| PATCH | `/strategies/{id}` | Update metadata or new card version |
| POST | `/strategies/{id}/versions` | Create explicit version |
| GET | `/strategies/{id}/versions` | List versions |
| POST | `/strategies/{id}/backtests` | Request backtest run (**placeholder**) |
| GET | `/strategies/{id}/backtests` | List backtest runs |
| POST | `/strategies/{id}/paper-validation/start` | Start paper validation (**placeholder**) |
| GET | `/strategies/{id}/paper-validation` | List paper validation runs |
| GET | `/strategies/modules` | List deterministic code modules (unchanged) |
| POST | `/strategies/evaluate` | Evaluate code module (unchanged) |

Manual levels: see [pre_trade_analysis.md](pre_trade_analysis.md) (`/manual-levels` CRUD).

## Strategy Lab UI (Slice 34)

Frontend routes:

- `/strategy-lab` — list strategies with validation status and paper eligibility
- `/strategy-lab/new` — create strategy card (`StrategyCardForm`)
- `/strategy-lab/[id]` — detail, version history, backtest and paper-validation panels
- `/strategy-lab/[id]/edit` — edit metadata and bump card version

All pages show paper-only messaging. Backtest and paper-validation actions create **placeholder records** only (Slice 35 will add the real engine).

## Strategy card fields

`strategy_name`, `market_type`, `asset_universe`, `timeframes`, `entry_conditions`, `confirmation_conditions`, `invalidation`, `stop_loss`, `take_profit_plan`, `runner_plan`, `position_sizing`, `add_rules`, `no_trade_rules`, `backtest_rules`, `success_criteria`, `validation_status`.

## Agent routing

Workspace questions about strategy cards, validation status, or backtest queue route through `strategy_workflow_tools` (see [agent_workflow.md](agent_workflow.md)). Deterministic tool output is labeled **SOURCE OF TRUTH**; LLM narrative cannot override card facts.

## RAG

Validated or in-review cards ingest as `STRATEGY_TEMPLATE` documents. Analytics summaries are not auto-ingested.

## Backtest & paper validation (placeholders)

- **Backtest:** `POST /strategies/{id}/backtests` persists a `backtest_runs` row with placeholder status — no historical bar replay yet.
- **Paper validation:** `POST /strategies/{id}/paper-validation/start` records a tracking run; does not connect to exchange or change `ENABLE_REAL_TRADING`.

## Migration (staging)

Apply both migrations before using library APIs in staging:

```bash
cd backend && uv run alembic upgrade head
```

Revisions:

1. `k1l2m3n4o5p6` — user strategies, manual levels, loss acceptance on proposals
2. `l2m3n4o5p6q7` — backtest runs, paper validation runs, `paper_eligible` on user strategies

Head should be **`l2m3n4o5p6q7`**.

Optional smoke: `./scripts/strategy-smoke.sh` (requires running backend).
