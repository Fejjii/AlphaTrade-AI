# Strategy Library (Slice 33–39)

Tenant-scoped user strategy cards with versioning, Strategy Lab UI, **backtest engine v1**, **paper validation runtime**, and optional RAG ingest. **Paper only** — no real exchange execution.

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
| GET | `/strategies/{id}/paper-eligibility` | Gates, blockers, accepted vs pending lessons |
| POST | `/strategies/{id}/paper-validation/start` | Start paper validation run (`runtime_mode`, optional `config`) |
| GET | `/strategies/{id}/paper-validation` | List paper validation runs |
| GET | `/strategies/{id}/paper-validation/{run_id}` | Single validation run with metrics |
| POST | `/paper-validation/{run_id}/scan` | Scan for paper signals (Slice 39) |
| POST | `/paper-validation/{run_id}/tick` | Monitor / close open simulated trades |
| GET | `/paper-validation/{run_id}/signals` | Paper signals from scan |
| GET | `/paper-validation/{run_id}/trades` | Simulated paper trades |
| GET | `/paper-validation/{run_id}/positions` | Open simulated positions |
| GET | `/paper-validation/{run_id}/metrics` | Current validation metrics |
| POST | `/paper-validation/{run_id}/stop` | Stop active run |
| POST | `/market/history/ingest` | Ingest historical OHLCV candles |
| GET | `/market/history/candles` | Query stored candles (debug) |
| GET | `/strategies/modules` | List deterministic code modules (unchanged) |
| POST | `/strategies/evaluate` | Evaluate code module (unchanged) |

Manual levels: see [pre_trade_analysis.md](pre_trade_analysis.md) (`/manual-levels` CRUD).

## Strategy Lab UI (Slice 34–35)

Frontend routes:

- `/strategy-lab` — list strategies with validation status and paper eligibility
- `/strategy-lab/new` — create strategy card (`StrategyCardForm`)
- `/strategy-lab/[id]` — detail, version history, **BacktestPanel**, **PaperValidationPanel** (eligibility, scan/tick, signals, trades)
- `/strategy-lab/[id]/edit` — edit metadata and bump card version

All pages show paper-only messaging. Backtest v1 runs deterministic candle replay; paper validation runs a **paper bot** (scan/tick) that simulates trades locally — no exchange orders.

## Strategy card fields

`strategy_name`, `market_type`, `asset_universe`, `timeframes`, `entry_conditions`, `confirmation_conditions`, `invalidation`, `stop_loss`, `take_profit_plan`, `runner_plan`, `position_sizing`, `add_rules`, `no_trade_rules`, `backtest_rules`, `success_criteria`, `validation_status`.

## Agent routing

Workspace questions about strategy cards, validation status, backtest runs, paper eligibility, or paper validation runtime route through `strategy_workflow_tools`, `backtest_tool`, and `paper_validation_tool` (see [agent_workflow.md](agent_workflow.md)). Deterministic tool output is labeled **SOURCE OF TRUTH**; LLM narrative cannot override card facts or invent metrics.

## RAG

Validated or in-review cards ingest as `STRATEGY_TEMPLATE` documents. Analytics summaries are not auto-ingested.

## Structured rules (Slice 36–37)

Strategy Lab includes a **rich structured rule editor** with add/edit/remove for entry, exit, and no-trade blocks.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/strategies/{id}/testability` | Score 0-100, missing fields, suggested edits |
| PATCH | `/strategies/{id}/structured-rules` | Save machine-testable rule blocks |
| POST | `/strategies/{id}/structured-rules/validate` | Deterministic validation |
| POST | `/strategies/{id}/structure-from-text` | Keyword draft from plain English |

Testability UI shows ready-for-backtest badge, unsupported types, ambiguous conditions, and suggested next edits.

## Lesson → version flow (Slice 37–38)

Accepted lessons may update strategy cards — **never silently**:

1. **Accept lesson only** — reviewed memory; no card change
2. **Accept + attach rule** — patches latest version `structured_rules` (explicit confirmation)
3. **Accept + new version** — bumps `current_version`; stores `lesson_source_metadata` on the new row

Pending lesson candidates are **observations only** — they block paper promotion when critical but are not treated as rules. Only **accepted** lessons affect eligibility and RAG. See [lesson_workflow.md](lesson_workflow.md).

Strategy Lab lists versions created from lessons; `/lessons` shows pending vs accepted queue.

## Paper eligibility (Slice 38)

`GET /strategies/{id}/paper-eligibility` returns conservative gates:

| Status | Meaning |
|--------|---------|
| `needs_structure` | Structured rules or testability below threshold |
| `needs_backtest` | No completed backtest |
| `needs_more_sample` | Backtest sample or promotion metrics insufficient |
| `needs_lesson_review` | Critical pending lesson observations |
| `paper_eligible` | Passed backtest gates — may start paper validation |
| `paper_validation_running` | Active simulated run |
| `paper_validated` | Paper validation passed — **still paper only** |
| `restricted` | Poor backtest metrics (expectancy, drawdown) |

Response includes `blockers`, `reasons`, `accepted_lessons`, `unresolved_lesson_observations`, and `real_trading_enabled: false`.

## Backtest & paper validation (Slice 35–39)

See dedicated docs:

- [backtesting.md](backtesting.md) — historical candle storage, replay engine, metrics, promotion rules
- [paper_validation.md](paper_validation.md) — paper bot runtime, scan/tick, signals, simulated trades, promotion

**Natural language rules:** vague card text returns `needs_structured_rules` — the engine does not fake trades. Use setup defaults (e.g. `htf_trend_pullback`) or structured tokens (`pullback`, `ema`, `breakout`, `stop`, `tp1`, etc.).

**Promotion:** at most `backtested`, `paper_eligible`, `paper_validated`, or `needs_review` — never auto-promotes to live. Real trading remains disabled.

## Smoke scripts

```bash
./scripts/strategy-smoke.sh          # Slice 38 — card, rules, backtest, eligibility, lessons
./scripts/paper-validation-smoke.sh  # Slice 39 — start, scan, tick, metrics
```

Both assert `real_trading_enabled` is false.

## Migration (staging)

Apply all migrations before using library APIs in staging:

```bash
cd backend && uv run alembic upgrade head
```

Revisions (through Slice 39):

1. `k1l2m3n4o5p6` — user strategies, manual levels, loss acceptance on proposals
2. `l2m3n4o5p6q7` — backtest runs, paper validation runs, `paper_eligible` on user strategies
3. `m3n4o5p6q7r8` — historical candles, backtest trades, paper validation metrics
4. `n4o5p6q7r8s9` — structured rules on strategy versions, lesson candidates
5. `o5p6q7r8s9t0` — lesson review, runner analysis fields (Slice 37)
6. `p6q7r8s9t0u1` — lesson accept paths, `lesson_source_metadata` (Slice 38)
7. `q7r8s9t0u1v2` — paper signals, paper trades, runtime scan/tick (Slice 39)
8. `r8s9t0u1v2w3` — paper scheduler, runtime history, alerts (Slice 40)
9. `s9t0u1v2w3x4` — alert dedup indexes, lesson gate hardening (Slice 40C)
10. `t0u1v2w3x4y5` — alert delivery fields, market watcher observations (Slice 41)

Head should be **`t0u1v2w3x4y5`**.
