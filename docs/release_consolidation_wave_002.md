# AlphaTrade paper release consolidation wave 002

> **Historical / release-specific record.** Original decisions, procedures and results below are preserved for their stated date/base. They are not current runtime observations or complete MVP acceptance. Read the [current status and pending acceptance](current_status.md), [architecture](architecture.md) and [deployment entry point](deployment.md) first; recheck commit-specific environment, migration and activation values before using older procedures.


Branch: `codex/release_consolidation_wave_002`.
Exact base: `78635e60e4f745fd50d6dc181b555a6948562077` (green PR160).
Finalization baseline: `fed937fe11fb4656ad4ad0be750bd7c03975250f` (green PR176).
Repository verified from the supplied PRs and SHAs: `Fejjii/AlphaTrade-AI`.

## Accepted scope and provenance

PR160 already contains PR154–PR158. Its existing history is inherited once.
The initial consolidation cherry-picked twenty-two unique commits from thirteen
feature heads. Finalization continues that same branch and adds seven unique commits
from PR171, PR174, PR175, and PR177, in that order: twenty-nine source commits across
seventeen accepted heads. Every source head was verified against its fetched PR ref
and a completed successful GitHub CI run before integration. Every pick carries
`-x` provenance; inherited feature history is not replayed.

| PR | Accepted feature | Exact green source SHA |
| --- | --- | --- |
| #159 | Brain Orchestrator V2: governed Agent action registry and domain proposals | `42b9803aee5111e7c5708285afc8614f315411dd` |
| #161 | Simplify Settings into a trader workspace | `95c4659f155a48f6cf7ed4f6dbca24408d8b2a77` |
| #162 | Voice Agent V1: add voice transport to the existing Agent workspace | `6cd6f1283f8072bc1c51310aa90e5cb442e5fea2` |
| #163 | Knowledge workspace: trader categories over canonical sources | `f647e2e240c4e3f7074ea8a005d3a57459bf057d` |
| #164 | Add Telegram trader notification policy v2 | `285798773fac867fd3f9991ad7295fa56e2d377e` |
| #165 | Expose tenant-scoped Strategy Analytics API V2 | `9f6e2edd16b43dfc5a6585462ba77919a0c5a6fc` |
| #166 | Simplify primary trader navigation to six destinations | `e3cb00bffb769c7aa57d2a89a6d79500f1b05f96` |
| #167 | Agent Action Application V3: confirmed canonical writes and paper pretrade | `7df8bcc6e42ba68ab2194b980de1792abeceabcc` |
| #168 | SFP Full Vertical 002: canonical Strategy Brain runtime and durable lifecycle | `c29bc3e91ba3fbff0bc63807e437664936171628` |
| #169 | Add deterministic source-linked Daily Review service | `315ddd875567b60d3956f5f60ae6754f124642b1` |
| #170 | Add verified read-only perpetual open interest and funding evidence | `3fc730347e450f537a9fdd708b4a0570555cd794` |
| #172 | Expose Daily Review as a tenant-scoped dashboard feature | `3e491561ac8ccddb795f8c6d3a04d39fdf7afa1d` |
| #173 | Strategy replay and experiments 001: deterministic Nested replay | `dff0f619a4afe5de9e9bf94dc4c900bc2b857200` |
| #171 | Agent Paper Execution V4 | `34a93110841ee75f061be58efa63ec56b49d2400` |
| #174 | Agent Daily Review | `255ef43320b27c80b12b6488fc4340adb2ab1f84` |
| #175 | Agent Strategy Analytics | `a8b0986b77c3bf00d878b24a940d9f0cb5c44482` |
| #177 | Verified CVD and five-minute order flow | `c91f283274c5a630dc34f8fa157584ddd83201a3` |

Source-only ranges use each PR's accepted base, rather than replaying all history
since main. In particular, PR167 excludes inherited PR159, PR168 excludes inherited
PR158, PR169 excludes inherited PR167, and PR172 excludes inherited PR169.
Finalization excludes PR171's inherited PR167, PR174's inherited PR169,
PR175's inherited PR165, and PR177's inherited PR170. Their unique ranges contain
three, one, one, and two commits respectively. All 29 source commits occur exactly
once in the branch's provenance trailers.
Source refs remain unchanged.

## Finalization conflict resolutions

- PR171 and PR177 conflict in `HANDOFF.md`: replace independent current summaries
  with the canonical release handoff; retain all dedicated feature documentation.
- PR174 conflicts in `interactive_agent/actions.py`: retain both typed
  `PaperExecutionInput` and `DailyReviewInput` contracts.
- PR174 conflicts in `interactive_agent/service.py`: retain paper preparation and
  Daily Review routing, with deterministic replies bypassing the narrative model.
- PR175 conflicts in `interactive_agent/contracts.py`: retain both typed action
  requests and analytics filters, and both structured Daily Review and analytics
  result fields.
- PR175 conflicts in `interactive_agent/service.py`: keep governed action routing,
  membership checks, canonical paper proposal/confirmation handling, Daily Review
  reads, analytics gathering, both structured transcript fields, and both result
  fields. Analytics also bypasses model prose. Reject analytics filters combined
  with a typed action before writing a transcript, preventing filters from
  reinterpreting an authorized action.
- PR177's automatic family dispatch merge leaves SFP outside the shared required
  print gate. SFP now uses the same `require_bound_order_flow` helper as Nested.
  Required CVD/flow must bind to the venue, instrument, trigger close, and selected
  hashed public observations. Missing or substituted candle evidence cannot
  confirm SFP. Optional flow retains the inherited SFP assessment behavior.

The resulting Agent retains governed journal, Knowledge, Watcher and strategy
research actions; paper pretrade and canonical execution; Daily Review and Strategy
Analytics reads; voice transport; live trading refusal; hash-protected confirmations;
tenant isolation; and final Risk/ActionEligibility decisions. The new combined
regression performs both reads between a paper proposal and its confirmation, then
proves one fill and one canonical journal despite repeated confirmation.

## Initial consolidation conflict resolutions

- `HANDOFF.md` conflicted in PR161, PR162, PR163, PR166, PR170, and PR173 because
  independent branches replace the current task summary. Each source's dedicated
  handoff/documentation remains available; the final current handoff describes this release.
- PR166 conflicted in the Settings and Knowledge pages and their component tests.
  Retain PR161's five Settings sections and PR163's five Knowledge categories,
  canonical reads, source/provenance details, and missing-document behavior.
  Keep PR166's six primary destinations, shared desktop/mobile/command navigation,
  route catalog, and retained specialist routes. Settings links retain 44px targets;
  Knowledge retains direct lesson-review access. Update the navigation browser fixture
  to the integrated section IDs and category links while preserving query/document checks.
- PR168 conflicted with PR164's generic migration-head expectations in
  `test_watcher_paper_activation.py`, `test_journal_trades_alembic_empty_tenant.py`,
  `test_phase2_4_alembic_postgres.py`, and `test_phase8_learning_persistence.py`.
  The final generic expectation is the merge head. Historical revision assertions
  check ancestry and original parent links.
- PR172 conflicted in `TraderDashboardView.tsx` and the Dashboard page test.
  Add Daily Review to the polished inherited Dashboard, retaining its portfolio
  metrics, risk/daily status, open-position detail, and source-failure handling.
  Keep PR172's missing-review refusal assertions.
- An automatic merge in `strategy_brain/assembly.py` combined PR155's Nested-only
  Telegram summary with PR168's SFP paper linkage. PostgreSQL runtime checks exposed
  an attempted read of Nested-only `confirmed_index` on an SFP detection. SFP now
  persists its canonical paper linkage and exits before the Nested adapter.
  Nested summaries remain intact; no SFP Telegram producer is added.

## Migration reconciliation

Exactly one repository head: `a3release002`.

The no-op merge revision has exactly these parents:
`("a2tgpolicy002", "a2sfp002")`. Both original revisions still descend from
`a1brain001` and are byte-for-byte identical to their accepted source files.
All older migration files remain unchanged.
Finalization adds no migration and leaves `a3release002` as the only head.

The initial focused PostgreSQL migration regression covered upgrade from each accepted
branch, convergence on the merge, preservation of original SFP receipt content,
an explicit-parent downgrade that removes only the merge, reupgrade, downgrade
through both branches to `a1brain001`, and another reupgrade. Relative `-1`
is ambiguous at a merge; use an explicit parent or common ancestor.
Existing empty-tenant journal and historical Phase 2–4/8 upgrade/downgrade/reupgrade
checks also run against the disposable database.

## Authority and operational limits

Paper execution only. The inherited configuration keeps `ENABLE_REAL_TRADING=false`.
CandidateLifecycleService remains canonical, and RiskEngine and ActionEligibility
remain final. PR171 delegates sizing to PositionSizingService and execution to the
existing canonical paper authorities, rechecking risk and eligibility at confirmation.
Agent does not mint Candidates or invent sizing. Accepted canonical paper fills now
participate in the shared risk accounting and loss cooldown. Five-market Watcher,
accepted Nested/SFP detectors, environment examples, deployment and CI configuration
remain preserved.

No alternative execution engine, synthesized production market data, Telegram
network arming, worker activation, shared database migration, deployment, or merge.
The replay implementation uses the accepted existing backtest authorities.
SFP execution remains refused with `sfp_execution_plan_not_authorized`.
Test payloads/clocks are explicit fixtures and are not claims of live market evidence.

PR170's OI and Funding remain present. PR177 adds real trade-print aggressive buy
and sell base/quote volume, five-minute delta and imbalance, print counts, freshness
and availability, plus bounded ten-minute rolling CVD/change/slope. The signed sum
starts at zero for each window and venue switch; it is not absolute provider CVD.
Unproven trade coverage remains unavailable/incomplete. Failover discards earlier
venue facts; candle volume never substitutes for prints.

## Finalization verification

- **742 distinct focused backend cases passed, zero skipped**, using each case's
  latest result once. The 738-case matrix passed 737 and exposed the new combined
  test's fixture registration issue when its source module was also collected.
  Local fixture registration fixed it; all three combined Agent regressions then
  passed against disposable PostgreSQL. Four new SFP required-print cases passed
  for both directions and both roles; affected SFP runtime cases passed again.
- **189 focused frontend cases passed across 20 files**, covering Agent/voice,
  Daily Review Dashboard, Knowledge, Settings, and six-destination navigation.
  Full frontend TypeScript checking passed. No frontend code changed in finalization.
- Scoped backend Ruff lint/format and targeted Agent/SFP mypy checks passed.
  One-head verification passed: `a3release002`. No migration files changed.
- Disposable PostgreSQL **17.11**, loopback port 55432 and task-owned database,
  exercised Agent action application, canonical paper execution, concurrent and
  repeated confirmations, tenant/hash/risk refusals, and SFP runtime integration.
  All PostgreSQL runs explicitly selected the disposable URL and safe paper,
  Telegram and worker settings. The server was stopped after verification.
- No full local repository suite, new migration cycle, deployment, activation,
  or merge. The unchanged migration graph already passed the initial upgrade,
  downgrade and reupgrade checks below. GitHub CI is allowed to run and is not awaited.

Finalization backend selection (relative to backend):

```text
tests/test_agent_action_application.py
tests/test_agent_action_application_postgres.py
tests/test_agent_action_orchestration.py
tests/test_agent_paper_execution_v4.py
tests/test_agent_daily_review.py
tests/test_agent_strategy_analytics.py
tests/test_interactive_agent_foundation.py
tests/test_release_wave002_agent_finalization.py
tests/test_strategy_brain_nested.py
tests/test_sfp_strategy_brain_runtime.py
tests/test_strategy_replay_001.py
tests/test_market_intelligence_oi_funding.py
tests/test_market_intelligence_cvd_orderflow.py
tests/test_phase5_cvd_flow.py
tests/test_canonical_evidence_http.py
tests/test_watcher_bybit_continuity.py
tests/test_at067_canonical_strategy_evaluation_policy.py
tests/test_telegram_notification_policy_v2.py
tests/test_daily_review.py
tests/test_daily_review_api.py
tests/test_strategy_analytics_api_v2.py
tests/test_phase2_4_alembic_postgres.py::test_alembic_single_head
tests/test_at012_paper_risk_at_execution.py
tests/test_automated_paper_loop.py
tests/test_strategy_slice_33.py
tests/test_phase7_eligibility_postgres.py
```

## Initial consolidation verification

- **938 distinct focused backend cases passed, zero skipped.** The initial 905-case
  matrix passed 899 and exposed four SFP/Nested adapter failures plus two ambiguous
  downgrade test calls. After the corrections, all 78 affected SFP/Nested/migration
  cases passed. Another 33 existing AT034 backtest engine/API/integration cases passed.
  The aggregate counts each case once and uses its latest result.
- **189 focused frontend cases passed across 20 files.** After the contextual
  lesson-review link reconciliation, all 26 Knowledge page cases passed again.
- Full frontend TypeScript check and scoped ESLint with zero warnings passed.
  Scoped backend Ruff lint and formatting passed on 104 affected Python files,
  with final checks on the repaired assembly and migration/runtime tests.
- Exact base/provenance, exact fetched source refs, accepted migration content,
  historical migration preservation, protected-path comparisons, and diff checks passed.
- Disposable PostgreSQL **17.11** ran exclusively on loopback port 55432 with a
  task-owned database. It exercised migration cycles, both branch upgrades, SFP
  Candidate/restart/risk refusal, Agent concurrent confirmations, Telegram policy
  history, empty-tenant journal reads, watchlist persistence, and historical migrations.
  Docker Hub rate-limited its image, so verified Debian packages were extracted
  under /tmp and used without modifying the host installation. The temporary
  server was stopped after verification.
- The initial npm install could not write its default cache; setting an explicit
  /tmp cache made installation succeed without dependency or lockfile changes.

All backend test commands explicitly used the disposable local database and safe
paper/Telegram/worker settings. No shared runtime database URL was used. Existing
source fixtures remain isolated from production market data.

No full repository suite, production build, or browser/device validation was run
locally. The updated navigation browser fixture is typechecked/linted but its new
combined context was not browser-executed. Real microphone/provider connectivity
and production migrations remain unverified. GitHub CI will run from the draft
pull request; it is not awaited. No deployment, activation, or main merge.

Focused backend files (paths relative to backend):


```text
tests/test_agent_action_application.py
tests/test_agent_action_application_postgres.py
tests/test_agent_action_orchestration.py
tests/test_daily_review.py
tests/test_daily_review_api.py
tests/test_journal_trades_alembic_empty_tenant.py
tests/test_market_intelligence_oi_funding.py
tests/test_nested_candidate_alerts.py
tests/test_notifications_slice_46.py
tests/test_phase2_4_alembic_postgres.py
tests/test_phase8_learning_persistence.py
tests/test_sfp_strategy_brain_runtime.py
tests/test_strategy_analytics_api_v2.py
tests/test_strategy_replay_001.py
tests/test_telegram_alert_delivery.py
tests/test_telegram_automatic_delivery.py
tests/test_telegram_notification_policy_v2.py
tests/test_telegram_postgres_store.py
tests/test_watcher_paper_activation.py
tests/test_release_wave002_migrations.py
tests/test_interactive_agent_foundation.py
tests/test_sfp_detector.py
tests/test_watcher_five_symbol_watchlist.py
tests/test_watcher_tenant_watchlist.py
tests/test_phase6_action_eligibility.py
tests/test_phase6_action_eligibility_adversarial.py
tests/test_telegram_paper_activation.py
tests/test_deployment_safety.py
tests/test_config.py
tests/test_strategy_brain_nested.py
tests/test_strategy_analytics_foundation.py
tests/test_watcher_paper_runtime.py
tests/test_watcher_stack_integration.py
tests/test_at034_engine.py
tests/test_at034_api.py
tests/test_at034_integration.py
```

Focused frontend files (paths relative to frontend):

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
```
