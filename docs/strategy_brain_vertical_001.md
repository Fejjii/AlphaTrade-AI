# Strategy Brain MVP vertical 001

This increment adds an operational Nested Continuation proxy to the existing paper loop. It does not claim Elliott wave counting or statistical validation. No runtime activation flags, canonical risk limits, live permissions, deployments or Telegram recipients are changed.

## Reuse map and five layers

| Layer | Existing authority reused | Addition |
| --- | --- | --- |
| Raw evidence | Watcher configuration, exact instrument catalog, contracted Binance/Bybit source, closed OHLCV, canonical observation/window contracts | OHLCV history observation binds the complete causal series; optional quote for existing paper gates |
| Detected events | Contracted candles and deterministic analysis boundaries | Mirrored causal pivot/impulse/pullback detector; versioned provisional parameters; append-only event IDs |
| Strategy interpretation | Strategy library, immutable versions, compiled definitions, approved-policy resolution, `evaluate_canonical_strategy` → `evaluate_setup` | Typed Nested spec and family adapter; explainable rules; tenant/version scoped setup projection |
| Trading decision | Candidate lifecycle and persistence fences; ActionEligibility, RiskEngine, plans, approvals, ExecutionService | Nested structural stop/target and long/short paper terms; episode idempotency key; links to the actual eligibility decision |
| Learning outcome | Canonical journal lifecycle, paper fills and existing journal statistics | Setup → Candidate → decision → plan/fill/journal references; actual closure event and distinct user belief |

No second strategy store, Agent, Candidate authority, risk engine or execution engine is introduced. Brain tables are read projections and event histories; they grant no permissions.

## Operational definition

Default M15 is configurable through the immutable authored spec (the minimal UI also offers M30/H1). An increasing price coordinate describes both long and mirrored short continuations. Strict pivots become usable only after their configured right-hand candles close. A sufficient impulse, bounded retracement and already confirmed pullback pivot must precede a **closed** break of the impulse extreme. The breakout requires actual positive candle volume and the configured relative-volume threshold. Each completed pullback/break increments N1, N2, N3 or N4_PLUS; higher highs alone do not increment the sequence.

Structural failure, pullback duration, confirmation-window expiry and bounded episode age reset the sequence. Each impulse has a stable structural setup ID. An expired episode cannot resume confirmation. Restart/replay uses deterministic causal event hashes, scoped setup IDs and the existing Candidate idempotency authority. Changed/sliding evidence windows cannot mint another Candidate for an accepted structural episode. Journal/order deduplication stays in the existing execution services.

`nested-research/v1` centralizes provisional pivot sensitivity, impulse size, retracement bounds/duration, invalidation, confirmation window, relative-volume threshold and entry trigger. They are research defaults, not optimized values. Relative candle/volume expansion, distance, sequence maturity and vertical expansion are informational proxies. Acceleration risk never submits a short or predicts exhaustion. Stops use the controlled pullback extreme; targets use a measured impulse. 3R/4R are preferences only when structure supports them; the code does not force either target or fabricate expectancy.

## Evidence and persistence

Assembly requests 256 closed candles from the exact configured instrument/timeframe and existing source. Identity, finality, continuity, provider completeness, causal time and latest-bar age gate confirmation. Canonical observations bind both trigger and full history hashes; the adapter verifies that raw bars match those observations. Required stale/missing evidence cannot confirm. Read views publish observation, expiry and freshness deadlines, and the UI expires evidence locally even during an unresolved refresh.

`AVAILABLE`, `MISSING`, `STALE`, `UNSUPPORTED` and `INCOMPLETE` are explicit evidence states. Moving-average and higher-timeframe context are optional and currently missing. CVD, order flow, open interest and funding are unsupported for this family; candle volume is not order flow. A fresh real contracted quote is still required by the existing automated paper path. Detection itself does not require a trade/CVD monitor window.

Migration `a1brain001` adds tenant-scoped setup/event projections with bounded read indexes. The migration is supplied for normal release validation; this work does not apply it to a release database. All strategy provenance remains in the existing version and lifecycle records. Projection history distinguishes system observations, paper decisions, paper opens/closes and user beliefs. Actual PnL is read from the journal; missed or blocked trades have no realized outcome.

## Governance and usable flow

The existing Strategies destination can create an explicit configured-market research draft, inspect its versioned parameters, compile and explicitly approve those paper rules through the existing approval endpoint, then open setup details and linked Candidate/journal records. Normal Watcher activation/configuration and existing paper gates are prerequisites. No new flag is automatically enabled.

Research lifecycle supports observation → hypothesis → testing → paper_active, with approved/active, paused and retired tracked separately. Only the existing approved/active compiled-policy boundary permits executable assessment; paper_active is a research status, not approval. Approval does not allow live trading. Chat rule changes remain existing proposals and cannot rewrite immutable active rules.

Setup history enforces WATCH → FORMING → CONFIRMED → TRADE_CANDIDATE or BLOCKED_BY_RISK, with invalidation, expiry and completion. Account decisions cannot be reverted by market replay. The original Candidate lifecycle remains the authority for action/expiry. Terminal signal states do not close a paper position; only actual journal events provide outcomes.

The existing interactive Agent gains a bounded stored-record read capability: configured markets, latest/forming/confirmed/previous setups, N stage, reasons, missing evidence, version, risk decision and journal references with timestamps. It performs no provider acquisition and explicitly describes stale or absent evidence as unknown. Existing candidate notification hooks remain applicable; no new Telegram delivery or enrollment is armed. There is no separate dashboard architecture.

## Validation and limits

Focused fixtures exercise mirrored N1–N4_PLUS, forming/confirmation, structural failure/reset/expiry, causal prefixes, rolling-history identity, immutable version binding, required evidence failure, replay/restart, tenant isolation, grounded reads, belief provenance, the actual governed paper path, authoritative daily risk rejection and journal-close linkage. PostgreSQL integration uses only the local test database and scripted contracted evidence. Frontend tests cover explicit draft creation, missing-data honesty and expiry during an unresolved refresh; affected existing strategy tests, typecheck and lint are included.

Limits: bounded historical windows/read lists; no profitability validation or deterministic replay comparison service; no automated exit-monitoring change; relative volume is available only as candle-derived research context; no optional HTF/MA enrichment; existing internal-paper tick/lot simplifications are retained. A real market validation run and the supplied migration remain release tasks after CI review. No provider probes or full local CI suite are part of this wave.

## Deferred canonical roadmap

All items below are **deferred, not implemented**:

- Swing Failure Pattern: common family compatibility only; detector and SFP quality scoring deferred.
- D Line: research only, with no invented anchors or executable rules.
- Higher Timeframe Swing: research only, with no automatic ladder execution.
- Verified CVD, five-minute order flow, open interest and funding evidence sources.
- Advanced confluence, strategy analytics and deterministic replay comparisons.
- Journal-driven refinement proposals, richer approval workflow and strategy learning/promotion.
- Telegram subscription policies and screenshot example annotations.

The long-term progression remains observation → hypothesis → proposed rule → validation → paper testing → approved rule → active strategy, with immutable versions, provenance and explicit permissions at every promotion.
