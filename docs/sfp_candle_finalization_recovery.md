# SFP REST candle finalization and recovery

## What the evidence establishes

The supervising live report identifies observation
`55121195-4489-5d6e-b733-6c23c2f4e618`: Binance USD-M BTCUSDT 15m,
October 5, 2026, 21:15–21:30 UTC, first received at
21:30:00.614496 UTC, marked final at revision 1. Stored base volume was
`238.970`, quote volume `20494228.80890`, and trade count `8528`. Later
worker reads conflict on those three values and `content_hash`.

This is a genuine same-revision conflict. PR207's decimal-equivalence fix correctly
refuses it. SFP remembers every candle in its overlapping history; both directions
share these public receipts and therefore fail on the same candle. Nested does
not reuse these durable SFP receipts, explaining its different observed outcome.

The old Binance REST adapter supplied no provider completion flag to
`build_ohlcv_bar`. The builder inferred completion from local time crossing the
interval end; the adapter used zero grace and ignored the native close timestamp.
Consequently, the 614 ms receipt was admitted as final without a settlement check.
The focused reproducer matches the exact observation UUID, stored volumes/count,
and all four conflicting fields. OHLC and later numeric increments in the
reproducer are synthetic: the complete original/later live responses were not
independently captured in this task. The application admission defect is confirmed;
upstream late aggregation versus a later provider correction is not independently
established. Neither provider closeTime nor two matching REST reads is a native
finality acknowledgement or an absolute guarantee against later changes.

## Correction and immutable recovery boundary

Live Binance REST adapter **v2** changes the actual acquisition contract:

- Validate the native inclusive close timestamp against the canonical half-open
  interval end minus one millisecond; require a native integer trade count.
- Refuse a just-closed row inside a five-second settlement guard, even when older
  candles could satisfy the requested minimum. Do not substitute an older trigger.
- Pin the request window with `endTime` and use at most two confirmation GETs per
  adapter invocation. Eligible closed rows must match in every typed field; normal
  decimal formatting differences compare equal. Forming rows remain ineligible.
- Mark only guarded, confirmed rows final. The five-second floor excludes the
  reported subsecond race; it does not assert a Binance settlement SLA. Further
  same-policy changes continue to fail strict immutable receipt validation.
- Stamp new SFP receipts using the injected clock after acquisition/confirmation.
  Reuse existing receipt clocks exactly on later scans and restarts.

Source and provenance explicitly identify `binance-usdm-perpetual/v2`; actual
live bar/trade normalization carries the same bundle version. Replay stays at v1,
and Bybit is unchanged. This is an application adapter policy version, **not a
fabricated provider candle revision**. Provider revision remains 1.

The existing receipt primary key is `(identity_hash, observation_id)`. Changing
the real adapter policy produces a distinct identity hash, so v2 reobservations
append beside v1 history without deleting, rewriting or reclassifying it. The
natural candle observation UUID can be identical across these policy identities:
always inspect the complete key. Historical plans, evidence windows and source
references retain their original v1 hashes and clocks.

No receipt repair SQL, revision increment, exception allowlist or automatic
same-policy conflict recovery is introduced. v2 does not merge v1 into its active
history. Its historical download is known only at the new receipt time; causal
warm-up can legitimately produce no setup or unavailable structural levels.
Past confirmation is not backdated or replayed into a new Candidate. Active
strategy versions, permissions, risk and execution activation are not changed.

## Bounded supervised staging procedure

No staging reads, deployment, repair or exchange orders were performed here.

1. Review the PR and this policy/history boundary before deploying. Capture the
   worker's later raw **public** candle values, request interval and receipt times
   in the supervising evidence record. Compare them with the reported stored v1
   row. Preserve the original row and any referencing assessments/plans. If other
   instruments, intervals, prices or provenance differ, investigate those separately.
2. Record the original full receipt key, JSON, content hashes and clocks with this
   bounded read-only query (no credentials in the evidence record):

   ```sql
   SELECT identity_hash, observation_id, payload, ohlcv
   FROM public_market_observations
   WHERE observation_id = '55121195-4489-5d6e-b733-6c23c2f4e618';
   ```

3. Through the supervising release process, deploy the exact reviewed SHA and
   restart/drain workers so a scope has one deployed adapter policy. Keep demo
   disarmed and real trading disabled. No strategy reapproval or credential change
   is needed. Verify new source/provenance reports v2; do not alter stored v1 rows.
4. Allow the existing worker poll to retry after the five-second guard. Failed
   Watcher attempts are retryable; only successful attempts replay. Check both SFP
   scopes within at most **two 15m scheduled boundaries** after worker health is
   restored. A legitimate `no_setup` or causal warm-up result is acceptable;
   `canonical_contract_invalid_contract`, mixed-version errors and repeated missing
   acquisition are not successful evidence acceptance. Verify Nested still evaluates.
5. Confirm new v2 receipts have current post-acquisition clocks, unchanged provider
   revision 1 and correct volume/count values. Re-run the read-only known-UUID query:
   the original v1 row must match its snapshot exactly. If a v2 row for this candle
   is in the bounded provider window, it has a different identity hash and a later
   receipt time. Do not require a new row once the candle ages out of that window.
6. Repeat one scope and restart once to verify receipt/key/hash stability and no
   duplicate canonical result. If v2 conflicts recur, stop acceptance, retain the
   refusal and collect UUID, full key, finite conflicting field names and separately
   reviewed public values. Do not increment revisions, delete evidence or expand
   a grace window until the new conflict is explained and reviewed.

Normal request budgets/backoff still apply. Each adapter invocation adds one
confirmation GET; the existing monitor's bounded partial-history fallback may make
another invocation. Native limits remain capped at 1500 rows per request (normal
SFP request is its existing history bound). Do not force tight manual polling.

Focused tests provide development evidence, including real local PostgreSQL and
mock HTTP confirmation. Live scheduled success remains a supervising acceptance
step. No full backend run is launched here; the existing consolidated exact-SHA
release dispatch with `full_backend=true`, evaluation and browser smoke remains
the final complete release gate.

## Development verification

248 distinct focused cases passed: the core adapter/market contracts, SFP receipt
reuse/runtime/detector, Nested, reliability and freshness batch passed 216 cases.
The extended source/native-metadata, existing adapter, governed-demo and Watcher
port batch passed 66 (34 overlap); the final 26 source cases were repeated after
clock binding and typing cleanup. This includes exact-UUID reproduction and
SQLite/PostgreSQL policy-history and both-scope restart checks. The two admission
regressions fail on untouched main before the fix.

Scoped Ruff/format passes. The three contract modules pass strict mypy with
dependency reports suppressed; shared Brain assembly has the same 36 existing
strict errors as untouched `60fed16`, with no added error after line normalization.
No production conflict guard or SFP version validation was weakened to pass tests.
