# Nested / SFP historical validation evidence

Cutoff: `2026-10-05T11:37:50+00:00`. Provider: Binance USD-M perpetual public adapter.
Live acquisition: **0/30 series**, **0 final candles**.
Safety: `ENABLE_REAL_TRADING=false`, `EXECUTION_MODE=paper`, `EXCHANGE_MODE=paper_internal`. No orders, Telegram sends or strategy approval mutations.
SFP authored spec supplied: **no**. Canonical historical receipt proofs supplied: **0 candles**.

## BTCUSDT

| Timeframe | Acquisition / final bars | Nested long / short confirmations | SFP long / short confirmations |
|---|---|---|---|
| 5m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 15m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 4h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1d | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1w | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |

## ETHUSDT

| Timeframe | Acquisition / final bars | Nested long / short confirmations | SFP long / short confirmations |
|---|---|---|---|
| 5m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 15m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 4h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1d | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1w | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |

## TAOUSDT

| Timeframe | Acquisition / final bars | Nested long / short confirmations | SFP long / short confirmations |
|---|---|---|---|
| 5m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 15m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 4h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1d | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1w | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |

## HYPEUSDT

| Timeframe | Acquisition / final bars | Nested long / short confirmations | SFP long / short confirmations |
|---|---|---|---|
| 5m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 15m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 4h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1d | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1w | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |

## ZECUSDT

| Timeframe | Acquisition / final bars | Nested long / short confirmations | SFP long / short confirmations |
|---|---|---|---|
| 5m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 15m | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 4h | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1d | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |
| 1w | unavailable / unavailable | unavailable / unavailable | unavailable / unavailable |

## Representative chart evidence

No representative detections are available. Unavailable evidence is not a zero-signal result; no timestamps or signals were invented.

## Provider limitations and evidence gaps

- `[{"type": "RegionalProviderFailureError", "message": "Preferred Binance USD-M perpetual source is unreachable."}, {"type": "ProxyError", "message": "403 Forbidden"}, {"type": "ProxyError", "message": "403 Forbidden"}]`
- Acquisition reason codes: `provider_contract_verification_failed`.
- Evaluation reason codes: `authored_sfp_parameters_missing, historical_candle_receipts_missing, provider_data_unavailable`.
- Bounded final-candle tail; shorter listing history is reported explicitly. No profitability estimate.
- SFP requires explicit authored parameters and matching canonical historical receipt proofs; REST candles do not establish past receipts.
- CVD, order flow, OI and funding are unavailable in this candle-only harness. Volume is used only as candle volume.
- Each symbol/timeframe/direction is isolated; no higher-timeframe context is injected.
- Timestamps are UTC. TradingView candle labels use candle open; decisions use close/receipt. Exact intrabar sweep time is unknown.
- Counts are unique setups reaching each lifecycle role. N stages count confirmations only; detector snapshots are retained separately.

## Exact rerun command

```sh
env ENABLE_REAL_TRADING=false EXECUTION_MODE=paper EXCHANGE_MODE=paper_internal PYTHONPATH=/workspace/validation-deps:backend/src python backend/scripts/validate_strategy_history.py --symbols BTCUSDT ETHUSDT TAOUSDT HYPEUSDT ZECUSDT --timeframes 5m 15m 1h 4h 1d 1w --bars 1000 --as-of 2026-10-05T11:37:50+00:00 --output-dir var/strategy-history-validation
```

Full counts, representative proofs and reason codes: `report.json`. Acquired canonical candles: `candles.jsonl`. Detector snapshots: `events.jsonl`.

## Files changed

- `backend/scripts/validate_strategy_history.py`: reusable CLI around the existing pure detectors; separate long/short runs for every symbol and native timeframe; lifecycle counts, representative proof timestamps, reason codes, and local evidence files.
- `backend/src/app/market_contracts/adapters/binance_usdm.py`: bounded historical tail read using the existing GET-only client, parser, post-close grace and closed-series validation. The existing live acquisition method and detector semantics are unchanged.
- `backend/tests/test_strategy_history_validation.py`: focused harness, native interval, lifecycle, evidence-gap and paper-setting tests.
- `docs/strategy_history_validation_report.md`: this report of the actual acquisition attempt and rerun instructions.

## Tests run

**145 passed**. All test prices and HTTP responses are explicitly synthetic unit fixtures; they are not historical market detections and are excluded from the live report above.

From `backend/`, the exact focused test invocation in this environment was:

```sh
env ENABLE_REAL_TRADING=false EXECUTION_MODE=paper EXCHANGE_MODE=paper_internal PYTHONPATH=/workspace/validation-deps:src python -m pytest tests/test_strategy_history_validation.py tests/test_sfp_detector.py tests/test_nested_timeframes.py::test_same_detector_progression_and_causal_replay
```

Scoped Ruff lint, Ruff formatting and `git diff --check` pass. No full test suite was run. Dependencies were installed in `/workspace/validation-deps`; the acquisition rerun command above includes that path.

## Completing the historical evidence run

The environment's enforced HTTP policy does not include `fapi.binance.com`. The adapter's exact symbol contract verification requests failed with a proxy `403 Forbidden`; this does not establish Binance's regional availability or any requested instrument's listing status. All six timeframes for each symbol therefore remain unavailable. The command returned **exit code 2**, and the local candle/event files are empty.

Enable `fapi.binance.com` in the supported environment network settings, then rerun the fixed-cutoff command above. The default request is a tail of up to 1,000 final bars per isolated series, not a common calendar span. Smaller listing histories are retained and explicitly reported; no padding or resampling occurs. Gaps, duplicates, wrong interval close times and forming candles fail closed. REST revisions can change a future rerun; saved candle and detector hashes identify this run's evidence.

SFP has no default authored parameter set. Supply an existing full `SfpSpec` JSON with `--sfp-spec PATH` and existing `SfpReplayEvidence` JSON with `--sfp-evidence PATH`. The same authored parameters are used independently for both directions and each requested series; the report saves the original spec. Receipt proofs must match the acquired candle hashes and full market/source/timeframe identity. The harness never creates past receipt clocks from candle timestamps. No authored SFP spec or historical receipt proofs were supplied for this run.

The harness passes no context levels, CVD, order flow, OI or funding into either detector. It never tunes provisional thresholds or uses candle volume as an order-flow proxy. SFP structural level, sweep, reclaim, confirmation, failed reclaim, invalidation and expiry records are emitted only when the existing detector can evaluate the supplied evidence. Nested stage counts represent completed confirmations, so a forming N2 is not counted as a completed N2.

For another installed backend environment, the portable invocation from the repository root is:

```sh
env ENABLE_REAL_TRADING=false EXECUTION_MODE=paper EXCHANGE_MODE=paper_internal PYTHONPATH=backend/src uv run --project backend python backend/scripts/validate_strategy_history.py --symbols BTCUSDT ETHUSDT TAOUSDT HYPEUSDT ZECUSDT --timeframes 5m 15m 1h 4h 1d 1w --bars 1000 --as-of 2026-10-05T11:37:50+00:00 --output-dir var/strategy-history-validation
```

Append the two SFP input flags once those artifacts are available. The CLI writes `report.md`, `report.json`, `candles.jsonl` and `events.jsonl` under the ignored `var/` directory. UTC candle opens identify TradingView labels; close, actual receipt, reference availability and expiry times are retained separately. Missing evidence produces null counts and an unavailable status, not invented zero-signal results. Exit code 2 also covers missing SFP inputs and detector/evidence failures; code 0 requires every requested family/series to be evaluated.
