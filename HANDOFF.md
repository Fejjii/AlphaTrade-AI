Status: REVIEW_REQUIRED
Task: ALPHATRADE CVD AND 5 MINUTE ORDER FLOW INTELLIGENCE 001
Phase: Implementation committed and pushed; draft PR opened; handoff recorded; STOP
Updated: 2026-10-01T22:14:28+02:00 (Europe/Berlin)

Draft PR: https://github.com/Fejjii/AlphaTrade-AI/pull/177
Branch: `codex/market_intelligence_cvd_orderflow_001`
Exact PR170 base: `3fc730347e450f537a9fdd708b4a0570555cd794`
Implementation: `dd5313c72487c359889c627972e97b8d443c3afe`
PR target: `codex/market_intelligence_oi_funding_001`, verified at the exact base.
Repository: `Fejjii/AlphaTrade-AI` (the requested underscore spelling does not resolve).

The existing canonical provider/evidence pipeline now exposes verified real-print
five-minute aggressive base/quote volumes, deltas, print counts, imbalance,
bounded rolling base/quote CVD, change/slope and deterministic directional states.
CVD is an internal ten-minute signed-volume sum, explicitly zero at each window
start or venue switch. No candle-volume input or absolute provider-CVD claim.
Required `CVD_5M`/`ORDER_FLOW_5M` roles bind to the canonical command/window and
fail closed, including Strategy Brain family dispatch. Optional evidence preserves
setup identity. Flow-triggered failover discards all earlier venue facts.

Validation: final affected-code matrix **528 passed, 3 skipped**; the three existing
governed paper integration cases require local PostgreSQL. **74 new tests passed**
independently. Scoped Ruff lint/format pass; mypy passes for seven contract and
integration modules. Tests use deterministic mocked public payloads and recorded
fixtures; no live venue connectivity claim. HTTP tests require the sandbox's local
socket/network permission and pass with that permission. No full-suite/type-debt
claim is made.

Semantics and limits: `docs/market_intelligence_cvd_orderflow_001.md`.
Bybit returns INCOMPLETE whenever its bounded recent tail cannot prove the full
prefix/end/overlap. Divergence is explicitly two public-print close points;
undefined comparison states stay null. No profitability probabilities.

No live trading changes, execution changes, deployment, activation or merge.
CI was not awaited. Human review is the only next step. Agent STOP.
