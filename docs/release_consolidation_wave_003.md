# AlphaTrade paper release consolidation wave 003

Repository: `Fejjii/AlphaTrade-AI`.
Branch: `codex/release_consolidation_wave_003`.
Exact base: `5f4f0a467ce8f68f9c7a82d3b32307d559a9f092` (accepted PR176 candidate).
Draft target: `codex/release_consolidation_wave_002`; the review diff contains only wave 003.

## Accepted sources and unique history

All seven source branches descend directly from the exact base. Integrate eleven
unique commits in PR178–PR184 order with `-x` provenance. The complete PR176 history,
including its seventeen accepted feature heads, is inherited once.

| PR | Accepted work | Exact supplied source head |
| --- | --- | --- |
| #178 | Expose Telegram Policy V2 in trader notification Settings | `7ae08cd09ea399d951b14d435601f9640390510c` |
| #179 | Connect canonical SFP events to Telegram Policy V2 | `36d53221ccac6ec967d91a14189856da0c55f78d` |
| #180 | Add canonical analysis-only Confluence Intelligence V2 | `af2aef1aa10f866cf12a9a24747cc1051f7e593a` |
| #181 | SFP replay adapter 001: canonical lifecycle research without trade returns | `c9ad31cd4522c83e7986ed7ce550bfb7ce9a870b` |
| #182 | Proactive attention queue 001: deterministic paper review | `04483f3f0cd98bec3f9984fba5b7e043fe11ed49` |
| #183 | Complete governed paper strategy learning and promotion | `55f2d540aef6e195729bfa9cad8245d7602528ff` |
| #184 | Runtime stability: canonical SFP risk clock and paper-worker memory diagnostics | `a9d8aa61d1f186855bcbff6b3c6cc31341b8431e` |

Unique ranges contain one, two, two, one, two, one, and two commits respectively.
Every supplied fetched ref matches its exact SHA. Source branches remain unchanged.

At intake, GitHub CI snapshots reported success for PR179 and PR184 and failure
for PR176, PR178, PR180, PR181, PR182 and PR183. The exact base's backend log has
two failing SFP daily-risk cases and 3,600 passes. PR184 corrects that canonical
clock defect. These are the user's explicitly accepted exact inputs; this record
does not relabel failed source snapshots green. New consolidation CI is not awaited.

## Semantic conflict resolutions

- PR181 conflicts in `HANDOFF.md` with PR180's current summary. PR182 conflicts
  in `HANDOFF.md` and `CHANGELOG_SESSION.md` with the earlier source summaries.
  Replace these ephemeral summaries with the canonical release handoff while
  retaining dedicated feature documentation and complete source commit history.
- PR183 conflicts in `services/strategy_replay_service.py`: retain PR181's
  non-null snapshot guard and SFP evidence/adapter identity comparisons, plus
  PR183's exact immutable version/content validation. Replay comparisons retain
  matching datasets, windows, assumptions, risk limits, receipt/evidence hashes,
  config/result hashes and report/version identities. Explicit type narrowing
  preserves those existing guards in the combined implementation.
- PR179 and PR184 automatically merge the SFP runtime test fixture, retaining
  PR179's temporary `resolve_day` override. Remove that obsolete override so
  PR184's leap-day, release-day, midnight and future-year tests exercise the
  actual injected canonical risk clock. Keep the original blocked-risk assertions,
  one Candidate/one locked row, and zero plans/fills. Nested's locked fixture
  remains aligned to its existing injected evaluation date.
- PR181's SFP structural replay has null PnL/R and zero execution trades.
  Governed learning now reports the absence of authorized trade-return evidence
  explicitly; structural observations remain unable to satisfy promotion gates.
  A combined regression records real SFP baseline/candidate replay comparisons,
  preserves null return differences/no improvement claim, refuses an explicit
  human promotion attempt even with review text, and preserves the selected
  baseline with zero trades/journals.
- PR178's form/API event union and browser assertion predate PR179's SFP producer.
  Add all six accepted SFP lifecycle event identifiers to the frontend union and
  replace stale unavailable-producer/phase/quality wording with current semantics.
  A selected Nested stage filter excludes SFP events, which have no stage.
  SFP component coverage is not an aggregate score; any configured quality
  threshold fails closed. Dedicated SFP controls remain unavailable in this UI.
  A full-replacement PATCH regression preserves saved SFP event allowlists when
  editing shared phase preferences. Saving preferences never arms network delivery.
- The combined Agent also retains explicit action validation and structured
  learning-status reads alongside Daily Review, analytics, voice, journal,
  Knowledge, Watcher, strategy research, paper pretrade and canonical execution.
  Narration never promotes a strategy or confirms an execution.

## Resulting release behavior and boundaries

Six primary workspaces remain unchanged. Attention joins the existing Dashboard
and Daily Review; it is a bounded, tenant-scoped SELECT-only queue with stable
identity, source provenance, expiry, deduplication and risk-first ordering.
It cannot launch jobs, execute trades, promote strategies or send Telegram.

Confluence Intelligence stays a typed Python analysis foundation without HTTP/UI/
runtime wiring. Hard requirements, optional coverage, research quality points,
historical expectancy and canonical risk eligibility remain separate. Scores do
not express win probabilities or override trading decisions.

Nested and SFP operational detectors remain canonical. Nested deterministic replay
is preserved. SFP replay uses the existing replay/backtest authorities and canonical
detector/receipt proofs, with lifecycle/structure research and null trade returns.
It creates no operational Candidate, Brain episode, fill, journal or account state.

Governed promotion binds immutable versions, exact replay comparisons, separate
completed paper validation and explicit human approval, preserving rollback and
idempotency. Agent only reads bounded status. CandidateLifecycleService remains
canonical; Risk and ActionEligibility remain final. Agent does not mint Candidates
or invent sizing. SFP execution still has no authorized plan.

OI, funding, real-print CVD and five-minute aggressive order flow remain present.
No candle volume replaces print evidence. Venue/window reset and availability/
freshness semantics are preserved.

SFP notices reuse the Candidate alert gateway, recipient binding, Telegram Policy
V2 and durable outbox after setup facts commit. Sweep, reclaim forming, confirmation,
invalidation, expiry and risk blocking remain informational, with no action buttons
or nonces. Candidate facts are refreshed before post-commit scan projection.

PR184 keeps the canonical evaluation clock authoritative for automated eligibility
and equity accounting, including user timezone boundaries and UTC fallback.
Worker memory diagnostics remain opt-in and disabled by default: sampled cycle
peak, cleanup RSS, bounded trends, cgroup/thread/retained-structure information.
Sampling is a lower bound, not proof of long-term staging capacity.

## Migrations and operational safety

Exactly one Alembic head: `a3release002`.
Parents remain `a2tgpolicy002` and `a2sfp002`. No migration is added or changed.
All history is inherited. The unchanged graph already passed disposable PostgreSQL
upgrade/downgrade/reupgrade checks in wave 002; wave 003 verifies the head and
unchanged migration diff without repeating those cycles.

Paper only; `ENABLE_REAL_TRADING=false`. Telegram network and paper activation
remain disarmed. No alternative execution engine, fabricated production market
data, shared database migration, deployment or main merge.

## Focused verification

Backend: **1,056 distinct cases passed, zero skipped** across the focused matrix.
The 77 affected replay/governed-Agent cases passed again after explicit type
narrowing was added; the aggregate counts every case once using its latest result.
Frontend: **213 cases passed across 24 files**, including Notifications, SFP replay,
Attention/Dashboard/Daily Review, six destinations, Settings, Knowledge and Voice.
Frontend TypeScript and scoped ESLint on 16 affected TS/TSX files passed.
Ruff lint/format passed on 69 affected Python files; focused mypy passed on
26 new/combined source modules. The React component checklist was applied to the
changed Settings, replay and Dashboard components.

PostgreSQL tests explicitly use the task-owned local database on loopback port
55432, PostgreSQL 17.11, with paper/Telegram/worker safety overrides. Test candles,
trade prints, clocks and Telegram transports are declared isolated fixtures.
No assertion of live provider/microphone connectivity or long-term staging
memory acceptance is made.
The 40-cycle five-market mocked regression retained bounded inspected structures;
its warmed cleanup RSS slope was about 2.3 KB/cycle. Pytest process RSS is not
staging worker steady state. The disposable server was stopped after validation.

The initial consolidation ran no full local repository suite, browser/device run,
production build, repeated unchanged-architecture audit, deployment, activation
or merge. Push a draft and allow GitHub CI; do not wait for its outcome.

## Executed focused selections

Backend paths, relative to backend:

```text
tests/test_agent_action_application.py
tests/test_agent_action_application_postgres.py
tests/test_agent_action_orchestration.py
tests/test_agent_paper_execution_v4.py
tests/test_agent_daily_review.py
tests/test_agent_strategy_analytics.py
tests/test_interactive_agent_foundation.py
tests/test_release_wave002_agent_finalization.py
tests/test_governed_learning_promotion_001.py
tests/test_strategy_brain_nested.py
tests/test_sfp_detector.py
tests/test_sfp_strategy_brain_runtime.py
tests/test_strategy_replay_001.py
tests/test_sfp_replay_adapter_001.py
tests/test_confluence_intelligence_v2.py
tests/test_attention_queue.py
tests/test_daily_risk_clock.py
tests/test_at012_paper_risk_at_execution.py
tests/test_automated_paper_loop.py
tests/test_telegram_notification_policy_v2.py
tests/test_sfp_telegram_policy_integration.py
tests/test_nested_candidate_alerts.py
tests/test_market_intelligence_oi_funding.py
tests/test_market_intelligence_cvd_orderflow.py
tests/test_daily_review.py
tests/test_daily_review_api.py
tests/test_watcher_paper_runtime.py
tests/test_watcher_stack_integration.py
tests/test_watcher_bybit_continuity.py
tests/test_watcher_tenant_watchlist.py::test_repeated_worker_cycles_release_history_and_keep_compositions_bounded
tests/test_watcher_tenant_watchlist.py::test_database_revision_restart_and_stale_worker_fence
tests/test_watcher_tenant_watchlist.py::test_normal_production_composition_probes_all_five_without_candidates
tests/test_watcher_tenant_watchlist.py::test_runtime_summary_is_shared_tenant_scoped_and_freshness_fenced
tests/test_watcher_tenant_watchlist.py::test_foreign_target_is_rejected_before_evidence_and_candidate_creation
tests/test_worker_memory_diagnostics.py
tests/test_paper_worker_memory.py
tests/test_paper_worker_supervisor.py
tests/test_paper_validation_run_session_slice_82.py
tests/test_strategy_conversation_foundation.py
tests/test_at034_engine.py
tests/test_at034_api.py
tests/test_at034_integration.py
tests/test_at067_canonical_strategy_evaluation_policy.py
tests/test_phase2_4_alembic_postgres.py::test_alembic_single_head
```

Frontend paths, relative to frontend:

```text
src/app/(app)/knowledge/page.test.tsx
src/app/(app)/page.fallback.test.tsx
src/app/(app)/page.test.tsx
src/app/(app)/settings/advanced/page.test.tsx
src/app/(app)/settings/page.test.tsx
src/components/NotificationSettingsPanel.test.tsx
src/components/WatcherWatchlistSection.test.tsx
src/components/agent/AgentVoiceControls.test.tsx
src/components/agent/AgentWorkspace.test.tsx
src/components/dashboard/DailyReviewCard.test.tsx
src/components/knowledge/KnowledgeRelatedContext.test.tsx
src/components/knowledge/KnowledgeSemanticSearch.test.tsx
src/components/knowledge/knowledgeWorkspace.test.ts
src/components/layout/AppShell.test.tsx
src/components/layout/CommandMenu.test.tsx
src/components/layout/DesktopSidebar.test.tsx
src/components/layout/TopBar.test.tsx
src/components/layout/navigation-config.test.ts
src/lib/api/daily-review.test.ts
src/lib/voice/browser-voice-provider.test.ts
src/components/settings/TelegramPolicyForm.test.tsx
src/components/dashboard/AttentionCard.test.tsx
src/lib/api/attention.test.ts
src/app/(app)/backtests/[id]/page.test.tsx
```

## PR185 final Notification Settings V2 E2E auth fix

Starting branch: `codex/release_consolidation_wave_003`, exact parent
`c8153ef6d7fc32474192d62eab095a3994813d07`.

The middleware did recognize the smoke session marker. A local reproduction of
the failing 390px spec with `CI=true` and tracing showed the initial `/settings`
document returning **200**, with `Cookie: alphatrade_session=1`. The helper installs
the shared non-sensitive marker on `PLAYWRIGHT_BASE_URL` (default
`http://localhost:3000`), with frontend hostname, root path and SameSite=Lax, before
navigation in the same per-test browser context. Its init script supplies the
access token in sessionStorage. CI uses the same base URL; its retry/server-reuse
settings do not change cookie origin or context lifetime.

The notification fixture's unavailable-read matcher omitted
`GET /watcher/watchlist` and `GET /watcher/watchlist/status`. These Settings reads
reached the real API with the synthetic fixture token and returned **401**.
`POST /auth/refresh` also returned 401. The API client's existing fail-closed path
then cleared the access token and marker and assigned
`/login?next=%2Fsettings`. Response timing explains why CI sometimes reached the
form before redirecting and why retry outcomes varied.

The fix adds those two exact watchlist paths to the fixture's unavailable **503**
responses. It does not fabricate watchlist/runtime evidence. Production middleware,
session handling, backend authorization, the shared smoke installer and Playwright
configuration are unchanged. No timeout increase or authentication bypass was added.

Browser assertions now verify the marker's shared value, frontend domain, `/` path,
SameSite=Lax and non-HttpOnly contract; the fixture access token in sessionStorage;
the bearer header on mocked `/auth/me`; and the fixture user/organization displayed
in Settings. The successful mobile save/reload checks repeat the session assertions.
The direct edge auth spec explicitly checks `/settings#notifications` redirects to
login without a marker and renders no policy form. Existing stale-marker-without-token,
login, logout/back navigation, public-route and security-header checks still pass.

Final focused results, all without retries:

- Notification Settings V2 browser spec: **3 passed** (390px, 320px, unsupported V2).
- Direct auth boundary browser spec: **6 passed**.
- Existing primary navigation smoke: **1 passed** (desktop/mobile six destinations,
  navigation and retained routes).
- Direct auth/session/API-client and Settings unit selections: **46 passed in 8 files**.
- Scoped ESLint on the two changed browser specs and `git diff --check`: passed.

Final notification traces show `/settings` 200 before/after reload, `/auth/me` 200,
both watchlist reads 503, and no 401 or refresh request. Local browser validation used
the existing executable override with system Chromium; GitHub's bundled Chromium
result remains for CI to establish. Tests used the existing disposable SQLite/mock
API setup. No production database, migration or deployment changed.

Executed commands, relative to `frontend`:

```bash
# Shared local browser environment; CI still uses its existing workflow/config.
export CI=true
export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
export UV_CACHE_DIR=/tmp/alphatrade-pr185-uv-cache
export SIMPLIFIED_UI_SHOTS=/tmp/alphatrade-pr185-navigation-shots

# Auth and navigation passed here. A new email assertion initially matched both
# shell and Settings; it was scoped to Settings, then the notification spec passed.
npm run test:e2e -- e2e/notification-settings-v2.spec.ts e2e/auth-boundary.spec.ts e2e/simplified-ui-smoke.spec.ts --retries=0 --output=/tmp/alphatrade-pr185-e2e-results
npm run test:e2e -- e2e/notification-settings-v2.spec.ts --retries=0 --trace=on --output=/tmp/alphatrade-pr185-notification-results

npm run test -- src/lib/auth/boundary.test.ts src/lib/auth/session.test.ts src/contexts/AuthContext.test.tsx src/lib/api/client.test.ts 'src/app/(app)/settings/page.test.tsx' 'src/app/(app)/settings/advanced/page.test.tsx' src/components/NotificationSettingsPanel.test.tsx src/components/settings/TelegramPolicyForm.test.tsx
npx eslint e2e/notification-settings-v2.spec.ts e2e/auth-boundary.spec.ts
```

Publish one focused commit to the existing PR185 branch, allow GitHub CI, and STOP.
Do not wait for CI, deploy, merge, or activate Telegram/trading.
