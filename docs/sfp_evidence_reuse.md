# SFP persisted candle reuse

The focused reproducer on main `c70d4bd` reaches `remember_observation`
through the real SFP assembler and Watcher wrapper. Reusing a candle encoded
as `102.00000000` after storing `102` raises
`DuplicateDataError("Canonical receipt must preserve its original OHLCV payload.")`.
The wrapper exposes `canonical_contract_invalid_contract`. Both decimal values
and their canonical content hashes are identical; the old raw JSON comparison
mistakes serialization differences for a conflicting immutable receipt.

Compare the complete validated `OhlcvBar` values when reusing a receipt. Preserve
the original JSON and receipt clocks. This permits equivalent decimal encodings
without changing any market value, binding, finality, revision or content hash.
An actual same-revision change remains a conflict. An explicit higher revision
appends a separate receipt; returning an older revision remains forbidden.

The tests persist observations for both approved SFP directions, roll overlapping
256-candle windows, repeat evaluations and reopen storage with another engine.
They cover SQLite and PostgreSQL, unchanged original rows/clocks, true value
conflicts, explicit revisions and older-revision refusal. Existing SFP detector
and runtime regressions cover closed candles, known-at causality, tenant binding,
canonical assessment, candidate linkage and execution refusal.

## Attribution and supervising acceptance

This proves a local defect with the reported wrapper code. It does **not** prove
that decimal formatting caused the October 5 21:30–21:45 UTC live failures.
Live logs and persisted observations were unavailable because the Render
connector requires a confirmed workspace selection. Unchanged rolling reuse
succeeds locally. Actual immutable conflicts and provider revisions remain
distinct hypotheses until live diagnostics or rows establish the failing check.

After review and deployment through the normal CI gate, verify fresh successful
evaluations for both BTCUSDT 15m SFP scopes and continued Nested evaluations.
If a refusal persists, inspect these bounded events:

- `canonical_evidence_contract_rejected`: allowlisted failure category only.
- `canonical_ohlcv_receipt_conflict` / `canonical_observation_receipt_conflict`:
  public observation UUID and finite conflicting field names.
- `canonical_ohlcv_revision_regressed`: public observation UUID and integer
  retained/incoming revisions.

No event includes raw exception text, provider URLs, credentials or candle values.
Use the public receipt UUID for read-only comparison with provider evidence.
Keep true conflicts refused; never overwrite/delete evidence, invent a provider
revision or backdate a receipt. No execution activation is part of acceptance.

## Focused local checks

Use a disposable local PostgreSQL database through `PHASE1_POSTGRES_URL`;
the existing fixture resets its test schema. Keep paper/mock mode and all demo
activation flags disabled. Run only:

```sh
pytest tests/test_sfp_receipt_reuse.py tests/test_sfp_strategy_brain_runtime.py tests/test_sfp_detector.py -o addopts='' -q
pytest tests/test_live_evidence_pipeline.py -k watcher_port -o addopts='' -q
```

Scoped Ruff lint/format applies to the changed source and regression file.
The two commands pass 117 and 4 cases respectively (121 total, no skips),
including all seven new SQLite/PostgreSQL/diagnostic cases.
Strict mypy passes for the receipt DAO. The assembly/watcher modules have 38
pre-existing strict mypy errors; comparison with untouched main finds identical
messages after ignoring shifted line numbers. Do not claim those modules pass.
Use the PR's automatic CI as the consolidated integration gate; do not restart
PR206 or manually rerun the complete backend suite.
