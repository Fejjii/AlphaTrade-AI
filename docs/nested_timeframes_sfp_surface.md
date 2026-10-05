# Nested timeframe scope and SFP frontend surface

Nested Continuation remains one structural strategy family using the existing
`detect_nested` implementation. The frontend offers every canonical `Timeframe`.
Every draft binds an explicit symbol, direction and trigger timeframe; creation
and approval use the existing immutable strategy-version workflow. Provisional
Nested parameters are unchanged. No 5m-specific detector or parameter tuning was
introduced. D Line / Break of Trend remains one future family and is not implemented.

## Verified timeframe support

| Timeframe | Nested spec / compile / assembly / Watcher evidence | Binance native acquisition | Bybit native acquisition |
| --- | --- | --- | --- |
| 1m | Verified | Verified | Verified |
| 3m | Verified | Verified | Verified |
| 5m | Verified | Verified | Verified |
| 15m | Verified | Verified | Verified |
| 30m | Verified | Verified | Verified |
| 1h | Verified | Verified | Verified |
| 2h | Verified | Verified | Verified |
| 4h | Verified | Verified | Verified |
| 6h | Verified | Verified | Verified |
| 12h | Verified | Verified | Verified |
| 1d | Verified | Verified | Verified |
| 3d | Verified | Verified | Unsupported; fails closed before fetching |
| 1w | Verified | Verified | Verified |

Verification uses deterministic native-shaped HTTP fixtures through the real
provider adapters. No live exchange responses or provider availability are claimed.
Binance's interval map needed expansion for every interval except 15m and 4h.
Bybit's map needed expansion for its other ten native intervals. The spec, canonical
detector, evidence assembly, assessment and Watcher code needed no interval-specific
changes. Bybit has no native 3d interval; no aggregation or interval substitution
was added.

The same detector's bullish and bearish N1/N2/N3/N4+ progression and causal replay
are tested for 5m, 15m, 1h, 4h, 1d and 1w. Prefix decisions match full-history
decisions at the same closed-candle cutoff. Future, forming, incomplete, gapped
and mismatched-timeframe evidence cannot confirm. Live canonical assessment stops
confirming when the evidence ages past one trigger interval.

Sequence identity includes instrument, direction and timeframe. Stored episode
identity also includes tenant and immutable strategy version. A persistence test
advances a 15m N2 while 1h and 4h N2 payloads and states remain unchanged. A changed
parameter set creates a different version and leaves the original spec intact.

## SFP frontend

The Strategies page now has separate Nested and SFP panels backed by shared
creation/review UI. SFP creation calls the existing authenticated
`POST /strategy-brain/templates/sfp` endpoint. All research parameters are explicitly
authored; no parameter defaults or optimization were added. Decimal inputs retain
their string precision, and an omitted optional maximum sweep depth becomes null.

Creation only creates a draft. A separate review action compiles the selected
immutable version, then calls the existing explicit approval endpoint only when
compilation succeeds. Errors remain visible. Family filtering prevents SFP versions
or lifecycle conditions from being displayed as Nested stages. SFP setup details
show the condition, timeframe and version without inventing an execution plan.
The existing SFP backend and detector are preserved.

## Limits and safety

- Structural support does not establish equal behavior or profitability. Replay
  creation requires matching dataset, assumptions and strategy timeframes; replay
  comparison already requires matching timeframe, dataset, assumptions and windows.
  Tests also reject using 15m validation data for 5m, 1h, 4h, 1d or 1w instances.
- Nested live acquisition still requires 256 complete final contiguous candles.
  Newly listed markets, particularly at daily/weekly intervals, may lack enough
  history and must fail closed. No warmup, freshness, continuity, completeness,
  finality, risk or execution gate was weakened.
- Bybit 3d is unavailable. Provider outages, region restrictions and contract
  availability still use the existing conservative failure path. Live availability
  was not tested.
- The bundled `ReplayPerpetualSource` first-slice fixture only contains 15m and 4h
  candles. Dataset-backed historical strategy replay accepts other canonical
  intervals when correctly bound closed candle data is supplied. No fixture data
  was fabricated to pretend that a missing provider dataset exists.
- SFP approval authorizes governed structural research scans and lifecycle alerts;
  the existing foundation has no authorized SFP execution plan.
- `ENABLE_REAL_TRADING=false`, `EXECUTION_MODE=paper`, and
  `EXCHANGE_MODE=paper_internal` are preserved. No deployment or activation occurs.
- Only focused tests and checks are run. PostgreSQL-dependent governed paper-fill
  integration requires an available local PostgreSQL database.

## Files changed

- `backend/src/app/market_contracts/adapters/binance_usdm.py`
- `backend/src/app/market_contracts/adapters/bybit_usdt_perpetual.py`
- `backend/tests/test_nested_timeframes.py`
- `backend/tests/test_strategy_brain_nested.py`
- `backend/tests/test_strategy_replay_001.py`
- `frontend/src/lib/api/types.ts`
- `frontend/src/lib/api/brain-types.ts`
- `frontend/src/lib/api/index.ts`
- `frontend/src/lib/api/strategy-brain.test.ts`
- `frontend/src/components/strategies/StrategyBrainPanel.tsx`
- `frontend/src/components/strategies/NestedContinuationPanel.tsx`
- `frontend/src/components/strategies/NestedContinuationPanel.test.tsx`
- `frontend/src/components/strategies/SfpPanel.tsx`
- `frontend/src/components/strategies/SfpPanel.test.tsx`
- `frontend/src/components/strategies/SfpParameterFields.tsx`
- `frontend/src/app/(app)/strategies/page.tsx`
- `frontend/src/app/(app)/strategies/setups/[id]/page.tsx`
- `frontend/src/app/(app)/strategies/setups/[id]/page.test.tsx`
- `.ai/TASKS.md`
- `docs/nested_timeframes_sfp_surface.md`

## Focused validation

Backend suites: `test_nested_timeframes.py`, `test_strategy_brain_nested.py`,
`test_strategy_replay_001.py`, `test_sfp_strategy_brain_runtime.py`,
`test_phase5_perpetual_adapter.py`, and `test_bybit_usdt_perpetual_evidence.py`.

Frontend suites: `NestedContinuationPanel.test.tsx`, `SfpPanel.test.tsx`,
`strategies/setups/[id]/page.test.tsx`, and `api/strategy-brain.test.ts`.

Checks: frontend TypeScript, ESLint on changed frontend production files, Ruff
lint/format on changed Python files, and `git diff --check`. Full-suite tests and
build/deployment checks are excluded by the task's focused-test scope.

Final results: **173 backend passed, 14 skipped** (local PostgreSQL unavailable),
and **25 frontend passed** across four files. All listed checks pass. The replay API
integration needed sandbox network permission for local TestClient event-loop
communication; it passed in isolation and in the final focused run. Nothing was
deselected in the final run.

Backend command, from `backend/`:

```sh
ENABLE_REAL_TRADING=false EXECUTION_MODE=paper EXCHANGE_MODE=paper_internal \
  ../.venv/bin/python -m pytest \
  tests/test_strategy_brain_nested.py tests/test_nested_timeframes.py \
  tests/test_strategy_replay_001.py tests/test_sfp_strategy_brain_runtime.py \
  tests/test_phase5_perpetual_adapter.py tests/test_bybit_usdt_perpetual_evidence.py \
  -q -r s -o addopts=''
```

Frontend command, from `frontend/`:

```sh
npm run test -- \
  src/components/strategies/NestedContinuationPanel.test.tsx \
  src/components/strategies/SfpPanel.test.tsx \
  'src/app/(app)/strategies/setups/[id]/page.test.tsx' \
  src/lib/api/strategy-brain.test.ts
```
