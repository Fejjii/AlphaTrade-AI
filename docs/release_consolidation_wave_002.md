# AlphaTrade paper release consolidation wave 002

Branch: `codex/release_consolidation_wave_002`.
Exact base: `78635e60e4f745fd50d6dc181b555a6948562077` (green PR160).
Repository verified from the supplied PRs and SHAs: `Fejjii/AlphaTrade-AI`.

## Accepted scope and provenance

PR160 already contains PR154–PR158. Its existing history is inherited once.
Twenty-two unique commits from the following thirteen feature heads are cherry-picked
in this dependency order with `-x` source provenance. Every source head was verified
against its fetched PR ref and a completed successful GitHub CI run before integration.
PR171, PR174, and PR175 are excluded regardless of later CI status.

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

Source-only ranges use each PR's accepted base, rather than replaying all history
since main. In particular, PR167 excludes inherited PR159, PR168 excludes inherited
PR158, PR169 excludes inherited PR167, and PR172 excludes inherited PR169.
All 22 source commits occur exactly once in the branch's provenance trailers.
Source refs remain unchanged.

## Conflict resolutions

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

The focused PostgreSQL migration regression covers upgrade from each accepted
branch, convergence on the merge, preservation of original SFP receipt content,
an explicit-parent downgrade that removes only the merge, reupgrade, downgrade
through both branches to `a1brain001`, and another reupgrade. Relative `-1`
is ambiguous at a merge; use an explicit parent or common ancestor.
Existing empty-tenant journal and historical Phase 2–4/8 upgrade/downgrade/reupgrade
checks also run against the disposable database.

## Authority and operational limits

Paper execution only. The inherited configuration keeps `ENABLE_REAL_TRADING=false`.
CandidateLifecycleService remains canonical, and RiskEngine and ActionEligibility
remain final. Their implementation/persistence paths, execution eligibility gates,
Watcher workers, five-market defaults, accepted Nested and SFP detectors, environment
examples, deployment configuration, and CI configuration are unchanged from PR160.

No alternative execution engine, synthesized production market data, Telegram
network arming, worker activation, shared database migration, deployment, or merge.
The replay implementation uses the accepted existing backtest authorities.
SFP execution remains refused with `sfp_execution_plan_not_authorized`.
Test payloads/clocks are explicit fixtures and are not claims of live market evidence.

## Verification

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
