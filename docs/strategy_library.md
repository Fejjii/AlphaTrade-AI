# Strategy Library (Slice 33-36)

Tenant-scoped user strategy cards with versioning, Strategy Lab UI, **backtest engine v1**, paper validation metrics, and optional RAG ingest. **Paper only** — no real exchange execution.

## Lifecycle

| Stage | `validation_status` | Meaning |
|-------|---------------------|---------|
| Draft | `draft` | Card editable; not validated |
| In review | `in_review` | Awaiting human review |
| Validated | `validated` | Eligible for RAG ingest and paper validation tracking |
| Archived | `archived` | Read-only historical version |

Version bumps create a new `user_strategy_versions` row; the parent strategy points at the latest card. `paper_eligible` (Slice 35) flags strategies that pass **conservative backtest promotion** — **does not enable live trading**.

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/strategies` | Create strategy + v1 card |
| GET | `/strategies` | List user strategies |
| GET | `/strategies/{id}` | Get strategy with latest card |
| PATCH | `/strategies/{id}` | Update metadata or new card version |
| POST | `/strategies/{id}/versions` | Create explicit version |
| GET | `/strategies/{id}/versions` | List versions |
| POST | `/strategies/{id}/backtests` | Run backtest v1 (historical simulation) |
| GET | `/strategies/{id}/backtests` | List backtest runs with metrics |
| GET | `/backtests/{id}` | Backtest run detail |
| GET | `/backtests/{id}/trades` | Simulated trades for a run |
| POST | `/strategies/{id}/paper-validation/start` | Start / refresh paper validation metrics |
| GET | `/strategies/{id}/paper-validation` | List paper validation runs |
| GET | `/strategies/{id}/paper-validation/{run_id}` | Single validation run with metrics |
| POST | `/market/history/ingest` | Ingest historical OHLCV candles |
| GET | `/market/history/candles` | Query stored candles (debug) |
| GET | `/strategies/modules` | List deterministic code modules (unchanged) |
| POST | `/strategies/evaluate` | Evaluate code module (unchanged) |

Manual levels: see [pre_trade_analysis.md](pre_trade_analysis.md) (`/manual-levels` CRUD).

## Strategy Lab UI (Slice 34–35)

Frontend routes:

- `/strategy-lab` — list strategies with validation status and paper eligibility
- `/strategy-lab/new` — create strategy card (`StrategyCardForm`)
- `/strategy-lab/[id]` — detail, version history, **BacktestPanel** (form, metrics, trades) and **PaperValidationPanel**
- `/strategy-lab/[id]/edit` — edit metadata and bump card version

All pages show paper-only messaging. Backtest v1 runs deterministic candle replay; paper validation aggregates metrics from linked paper positions.

## Strategy card fields

`strategy_name`, `market_type`, `asset_universe`, `timeframes`, `entry_conditions`, `confirmation_conditions`, `invalidation`, `stop_loss`, `take_profit_plan`, `runner_plan`, `position_sizing`, `add_rules`, `no_trade_rules`, `backtest_rules`, `success_criteria`, `validation_status`.

## Agent routing

Workspace questions about strategy cards, validation status, backtest runs, or paper eligibility route through `strategy_workflow_tools` and `backtest_tool` (see [agent_workflow.md](agent_workflow.md)). Deterministic tool output is labeled **SOURCE OF TRUTH**; LLM narrative cannot override card facts or invent metrics.

## RAG

Validated or in-review cards ingest as `STRATEGY_TEMPLATE` documents. Analytics summaries are not auto-ingested.

## Backtest & paper validation (Slice 35)

See dedicated docs:

- [backtesting.md](backtesting.md) — historical candle storage, replay engine, metrics, promotion rules
- [paper_validation.md](paper_validation.md) — paper trade aggregation, recommendations

**Natural language rules:** vague card text returns `needs_structured_rules` — the engine does not fake trades. Use setup defaults (e.g. `htf_trend_pullback`) or structured tokens (`pullback`, `ema`, `breakout`, `stop`, `tp1`, etc.).

**Promotion:** at most `backtested`, `paper_eligible`, or `needs_review` — never auto-promotes to live. Real trading remains disabled.

## Migration (staging)

Apply both migrations before using library APIs in staging:

```bash
cd backend && uv run alembic upgrade head
```

Revisions:

1. `k1l2m3n4o5p6` — user strategies, manual levels, loss acceptance on proposals
2. `l2m3n4o5p6q7` — backtest runs, paper validation runs, `paper_eligible` on user strategies
3. `m3n4o5p6q7r8` — historical candles, backtest trades, paper validation metrics
4. `n4o5p6q7r8s9` — structured rules on strategy versions, lesson candidates

Head should be **`n4o5p6q7r8s9`**.

## Structured rules (Slice 36–37)

Strategy Lab includes a **rich structured rule editor** with add/edit/remove for entry, exit, and no-trade blocks.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/strategies/{id}/testability` | Score 0-100, missing fields, suggested edits |
| PATCH | `/strategies/{id}/structured-rules` | Save machine-testable rule blocks |
| POST | `/strategies/{id}/structured-rules/validate` | Deterministic validation |
| POST | `/strategies/{id}/structure-from-text` | Keyword draft from plain English |

Testability UI shows ready-for-backtest badge, unsupported types, ambiguous conditions, and suggested next edits.

Accepted lessons may propose rule updates — see [lesson_workflow.md](lesson_workflow.md).

Migration head: **`o5p6q7r8s9t0`** (Slice 37).
