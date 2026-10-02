# Proactive attention queue 001

Exact base: `5f4f0a467ce8f68f9c7a82d3b32307d559a9f092`.
Branch: `codex/proactive_attention_queue_001`.

`GET /dashboard/attention` returns `AttentionQueue/v1` for the authenticated
membership's organization and user. It accepts no tenant/user override, uses
Reader RBAC and the dashboard read rate limit, and returns
`Cache-Control: private, no-store`. There is no write endpoint.

The Dashboard displays five ordered items, reasons, recommended review, source
IDs/timestamps, symbol and strategy references, expiry, existing acknowledgement
state and limitations. Unavailable differs from empty. The browser removes
expired notices without another request; refresh fetches current stored state.
Agent integration is deferred; Agent implementations are untouched.

## Recorded inputs and lifetime

| Input | Ownership | Attention and removal |
| --- | --- | --- |
| `strategy_brain_setups` | Organization | Forming, confirmed, risk-blocked, missing required evidence, stale required market evidence. Active states only; excluded at recorded `expires_at`. |
| `paper_evaluation_observations` | Organization | Latest non-replayed scan/assessment/eligibility per recorded lineage. Explicit provider outage/unreachable, unavailable/stale evidence, blocks, forming/confirmed setups and failed scans. Fifteen-minute TTL; recovery replaces failure. Brain projections take precedence over fallback setup notices for represented versions. |
| `watcher_health_snapshots`, `watcher_symbol_status` | Organization | Unhealthy enabled Watcher, explicit outages and stale symbol evidence. Fifteen-minute TTL. Symbol revision must match the current watchlist. |
| `risk_events` | Organization + user | Blocks and warnings; ALLOW produces no notice. Twenty-four-hour TTL. Repeated rule/context merges provenance. |
| `kill_switch_states`, `daily_risk_states` | Organization kill switch; user daily lock | Persisted active kill switches stay visible until state changes. Recorded daily locks expire at midnight in the user's stored risk timezone (UTC default). No risk rule is recomputed or bypassed. |
| `journal_trades` | Organization + user | Open `paper_execution` or `paper_validation` positions until closure. Legacy positions without explicit paper provenance are excluded. |
| `backtest_runs`, `paper_validation_runs` | Organization + user | Job status and terminal replay result review. Active jobs remain; terminal results expire after seven days. Cancelled jobs produce no notice. Results confer no approval or profitability claim. |
| `strategy_conversation_proposals` | Organization + user | Drafts awaiting human confirmation. Identical content/target/parent merges references. Confirmed/rejected/superseded records disappear. |
| Daily Review lessons, `lesson_candidates` | Organization + user | Current UTC-day lessons and pending candidates. Whitespace-normalized text merges provenance. Candidate status changes remove pending notices. Reflections are observations, not independently verified facts. |
| `telegram_security_outbox`, `paper_validation_alerts` | Organization + user; explicitly organization-owned alerts may be shared | RETRYABLE/DEAD_LETTER outbox and failed Telegram alerts. Sent/recovered records disappear. Alert `read_at` projects acknowledgement; outbox acknowledgement is unsupported. Chat IDs, message bodies, tokens and raw transport errors are excluded. |

Required closed OHLCV/volume or explicit `required_evidence` status produces a
Brain missing-evidence notice. Optional MA, HTF, CVD and quality components are
not silently declared required. Closed-bar freshness uses the existing Brain
timeframe/SFP maximum-age rule, bounded by setup expiry. Absent records produce
no invented failure. Journal lesson symbols resolve only through scoped sources.

## Determinism and authority

UUIDv5 identity binds organization, user, category and semantic key; it excludes
the request clock and mutable wording. Semantic duplicates merge sorted, unique
provenance. The newest signal supplies wording and expiry; canonical hashes break
equal-time ties. Future sources and expired signals are excluded. Expiry is
half-open: an item disappears at `now >= expires_at`.

Category order: risk blocks, risk events, provider outages, missing evidence,
stale evidence, Telegram failures, Watcher health, confirmed setups, forming
setups, paper positions, proposals, validation jobs, replay results and lessons.
Severity then stable identity break category ties. An empty queue has null
`recommended_next_action`.

The adapter suppresses autoflush and performs SELECTs only. It does not persist
items/acknowledgements, evaluate risk, launch jobs, acquire market data, invoke
providers/LLMs, call Agent actions, deliver Telegram, approve strategies or
execute trades. Global runtime rows without tenant ownership are excluded.
Unknown symbol/strategy references remain null. Every response fixes paper mode
and `executes_trades`, `approves_strategies`, `bypasses_risk`, `telegram_delivery`
to false. Existing risk and approval workflows remain authoritative.

No migration, worker activation, live trading, Telegram send or deployment.
Acknowledgement writes and Agent integration require separate work. Validation
results are in the branch root `HANDOFF.md` and `CHANGELOG_SESSION.md`.
