# SFP detector foundation 001

This additive paper research foundation starts at exact SHA `79b76d6313c7d1a269a9e32d67f89e39eca9df96`. Its only callable boundary is the pure `app.strategy_brain.sfp.detector.detect_sfp` function. It is not registered with the Watcher, compiler, API, Candidate lifecycle, risk, execution or Telegram. No deployment, runtime activation or provider acquisition is included.

## Existing contracts inspected and reused

Nested Continuation's detector, assessment adapter, assembly, records and authored spec establish the existing architecture. `BrainSetupState` already expresses `FORMING`, `CONFIRMED`, `INVALIDATED` and `EXPIRED`, and `EvidenceAvailability` already expresses available, missing, stale, unsupported and incomplete inputs. SFP reuses those enums unchanged. All prices use canonical finite Decimal types. Every input candle remains an existing `OhlcvBar`, bound to an existing `PublicMarketObservation`, `EvidenceMarketIdentity`, revision, finality and content hash. Hashing uses the existing canonical serialization service; OHLCV observation IDs remain the existing authority.

The legacy `app.analysis.setups.detect_sfp` is a single-candle float-based analysis helper, and `app.signal_fusion.swings` only represents confirmed swing highs. Neither supplies the full symmetric structural proof, availability time or lifecycle required here. The new focused modules interpret canonical evidence without registering another strategy store, evidence acquisition system, persistence layer, Candidate authority or execution path.

## Structural references and significance

`derive_levels` produces swing highs/lows, trailing range highs/lows and equal highs/lows. Strict pivots need both configured wings to close; equal levels need at least two distinct confirmed pivots within the configured price tolerance. Range references require the complete configured historical lookback. Higher timeframe support/resistance is derived only from explicitly supplied closed contextual candles. The detector checks the actual contextual timeframe, exact instrument and source; no session data, order book, external flow or market narrative is inferred.

Each structural reference retains its canonical basis candles and observation envelopes. These are proof references supplied to a pure function, not new stored evidence. Price, anchors, availability and significance are checked against that proof. Availability includes the last necessary candle close and all observation/receive times. A level must have been known before the sweep candle opened. Historical anchor age uses the level's own timeframe and lookback; it is separate from historical validity flags and current trigger freshness. Late historical evidence can support a later sweep after arrival; it cannot backdate a previously unknown level or event. Current candle age includes its arrival delay.

Significance components remain explicit: touch count, pivot confirmation width, observed price-span prominence divided by level price, and whether the reference is an HTF reference. Version `structural-components/v1` assigns ordinal points as `touches + one confirmed-pivot point + prominence ratio + one HTF-reference point`. The minimum significance is an authored research threshold. Points are not normalized confidence, estimated win probability or validated expectancy.

## Symmetric detection and lifecycle

Long SFP uses support references, a move below the price and a strict closed reclaim above it. Short SFP mirrors the same model around resistance. The previous closed candle must be on the unswept side. A touch is not a sweep, even with a zero minimum depth. Minimum and optional maximum depth are inclusive ratios of reference price; no profitable values are supplied as defaults.

The sweep retains the original level, direction, absolute/relative depth, initial extreme, canonical event time, candle end, observation time, finality, closure flag and canonical evidence envelope. Canonical OHLCV event time is the candle's start; exact intrabar sweep time and tick ordering are unavailable. Reclaim and confirmation event times use candle closure, while observation time records when they became known.

Observed behavior is separate from the reused setup lifecycle:

| Price behavior | Setup interpretation |
| --- | --- |
| Wick through, forming candle or close exactly at the level | Forming; no closed reclaim |
| Closed excursion beyond the level within the reclaim window | Forming; temporary excursion |
| Strict closed return to the original side | Forming; confirmed reclaim |
| A later favorable-body closed candle strictly beyond the reclaim candle's high for long, or low for short | Confirmed SFP |
| Configured consecutive unreclaimed closes beyond the level | Invalidated SFP; operational successful-breakout classification |
| A closed reclaim is lost, or reclaim window elapses | Invalidated; failed reclaim |
| A later closed candle breaches the initial sweep extreme plus the configured price-relative buffer, or depth exceeds the maximum | Invalidated; structural failure |
| Confirmation window elapses or fixed sweep expiry is reached | Expired; terminal |

Reclaim and confirmation windows count subsequent candles and include their last allowed candle. Zero reclaim window permits only a same-candle closed reclaim. The fixed expiry is exclusive: reaching its exact deadline cannot confirm, and later scans never extend it. A clock expiry can reuse the last actual evidence without inventing a new closed candle. The breakout label describes the configured observed closes, not a claim about future price behavior. A sustained unreclaimed breakout takes classification precedence over a new extreme on the same terminal candle.

Forming candles cannot introduce closed reclaim, confirmation or price invalidation. They can display provisional conditions alongside a previously confirmed state; the original confirmation observation remains explicit. The initial sweep extreme stays immutable, and subsequent breaches are lifecycle observations.

Same-price swing/range/equal references select the strongest currently knowable eligible reference and share one active episode. A terminal episode cannot revive. A later episode at the same price requires new structural anchors established after the previous sweep. Exact duplicate candle observations collapse; conflicting revisions of one natural candle require a fresh explicit replay. Setup identity binds the authored configuration, natural structural anchors and sweep candle. Event identity additionally binds semantic sweep/reference evidence, current observation, state, reasons and quality. Transport/recording metadata does not mint another event. Persistent deduplication is intentionally left to the existing Brain projection authority.

## Parameters, quality and evidence limits

All numeric detector parameters must be explicitly authored through immutable `SfpParameters` version `sfp-research/v1`: level lookback, pivot width, minimum significance, minimum/optional maximum depth, equality tolerance, reclaim/confirmation windows, breakout close count, structural buffer, fixed expiry, required evidence age, quality lookback and HTF alignment tolerance. Invalid bounds, NaN, binary floats, booleans in Decimal inputs and incompatible pivot/lookback sizes are rejected. The spec follows `strategy-pattern-spec/v1`, declares the SFP family kind and fixes paper scope. Future configuration changes must use the existing immutable strategy-version workflow when integrated.

Separate quality components expose level importance, known HTF alignment, sweep depth, closed reclaim delay, the reclaim/sweep candle's directional wick fraction, relative candle volume, space to the nearest known opposing structural reference and historical directional efficiency. Directional efficiency is a candle-derived research proxy, not a market-regime classifier. Target space is measured distance, not a trade target or an executable plan. Each measured component includes units and canonical observation IDs. No aggregate quality score or winning probability is returned.

Missing baselines, HTF references and opposing levels remain unavailable; stale HTF proof is explicitly stale and cannot supply a required sweep reference. CVD, order flow and open interest remain unsupported with no invented values. Candle volume is optional research evidence and never substitutes for those sources.

Required candle/observation binding, identity, continuity, completeness, causal availability and freshness are checked before detection. An absent, stale or incomplete required series returns the corresponding scan availability with no detections. Invalid identity, hash or revision binding raises an error. One trailing provisional candle is allowed; an earlier provisional candle or unresolved gap fails closed. Future observations are filtered as of evaluation time. Price preconditions and quality baselines cannot use observations received after the emitted event; out-of-order episode evidence cannot backdate a transition. Replays are bounded by caller-supplied canonical history; no cross-scan state is stored by the detector. A clipped history that omits structural proof cannot reconstruct an episode or confirm it.

## Integration intentionally deferred to parent consolidation

The following existing files are integration points, not modifications in this branch. Several are actively changed by PR153 or PR155:

1. `schemas/setup_ast.py`, `services/setup_ast_compiler.py`, `services/compiled_setup_service.py`, `signal_fusion/strategy_evaluation_policy.py` and `services/canonical_strategy_evaluation.py`: register `SfpSpec` with the existing immutable authored-spec, compiler and approved-policy contracts. Do not introduce an independent strategy store or approval route.
2. `strategy_brain/records.py`, `strategy_brain/service.py` and existing Brain setup/event tables: generalize the existing projection adapter to retain SFP references, conditions and event IDs. Preserve tenant/version scoping, terminal transitions and existing event deduplication; do not create SFP tables or a second lifecycle authority.
3. `strategy_brain/assembly.py`, `evidence_pipeline/watcher_port.py` and the existing Watcher target/evaluation boundaries: acquire and bind canonical trigger/context evidence through the existing pipeline after consolidation. The foundation performs no provider reads and installs no worker hooks.
4. Candidate, risk, paper execution, trade plans, journal and Telegram remain outside this task. Any later activation must pass through the existing canonical assessment/Candidate/risk/approval authorities; no SFP shortcut is supplied here.

## Focused validation

The synthetic tests cover independent valid bullish and bearish paths, wick without reclaim, temporary excursion, breakout, failed reclaim, structural invalidation, expiry, exact windows/depth/buffer/significance boundaries, duplicate and alias resistance, new structural episodes, causal prefixes, future pivot/context filtering, delayed observations, provisional/incomplete confirmation, stale required evidence, missing optional evidence, HTF proof and stale context, canonical binding failures and explicit version/paper constraints.

Run from `backend`:

```sh
.venv/bin/pytest tests/test_sfp_detector.py tests/test_at067_canonical_strategy_evaluation_policy.py tests/test_strategy_brain_nested.py::test_new_family_fields_preserve_existing_compiled_hash_and_card_payload tests/test_strategy_brain_nested.py::test_library_version_binding_and_draft_not_executable
.venv/bin/ruff check src/app/strategy_brain/sfp tests/test_sfp_detector.py
.venv/bin/ruff format --check src/app/strategy_brain/sfp tests/test_sfp_detector.py
.venv/bin/mypy --follow-imports=silent src/app/strategy_brain/sfp
```

The full backend suite, provider probes, deployments and CI polling are outside this increment. No profitability or real-market validation is claimed.
