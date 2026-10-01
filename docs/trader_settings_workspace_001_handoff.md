# Trader Settings workspace 001

Status: REVIEW_REQUIRED
Date: 2026-10-01
Branch: `codex/trader_settings_workspace_001`
Exact base: `94954e7d243be0c03ce667403964adb6e4e2b850`
PR target: `codex/trader-interface-polish` (at the exact base when this work was prepared)

## Result

Settings now presents Markets, Strategies, Notifications, Risk, and Account and system together, with links to each section. The secondary navigation calls this destination Workspace. Advanced remains separate and retains operational routes, build configuration, and safety disclosures.

- Markets reuses the existing Watcher watchlist editor for symbol changes, enabled states, and ordering. It also shows the monitoring API's reported universe and market provider availability. The reported universe can include other paper-monitoring markets; it is explicitly distinguished from editable slots. Availability observations still require the matching revision, symbol, enabled state, and a fresh timestamp. Configuration remains visible if the availability request fails; missing configuration never becomes a fabricated default universe.
- Strategies shows the monitoring API's approved compiled strategy versions, distinguishes approved versions from active paper versions, and shows paper monitoring and detected setup count separately. Numeric versions come from matching the exact version ID in the existing version API, with one read per distinct strategy. A failed or incomplete version lookup leaves the version reference and lifecycle visible and explicitly labels the numeric version unavailable. Strategy activation is not a Settings control.
- Notifications shows Telegram delivery/configuration state independently of saved preferences, plus in-app, webhook, Telegram, alert-type, quiet-hour, and frequency preferences. Only the existing minimum-severity preference is editable. Telegram/webhook enable toggles and notification test sends are absent. The displayed markets and strategies describe the reported Watcher alert context, not unsupported routing filters. A configured Telegram provider is not presented as a verified connection.
- Risk displays `/risk/settings` parameters, defaults, and timezone fallback. It has no editor, defaults, calculations, mutation calls, or separate risk authority. The existing risk engine and approved risk configuration page are unchanged.
- Account and system shows account verification, organization, confirmed or unverified paper posture, real-trading status, Watcher status, freshness and observation time, Telegram runtime/permission state, and provider health. Refresh uses the existing status reads. Freshness is explicitly labeled as belonging to the last monitoring snapshot; absent source data remains unavailable.

## Existing API use

| Source | Settings use |
| --- | --- |
| `GET /watcher/watchlist` | Saved market slots and revision |
| `GET /watcher/watchlist/status` | Per-market availability observations |
| `PUT /watcher/watchlist` | Existing revisioned symbol, enablement, and order changes only |
| `GET /market-watcher/monitoring` | Reported universe, compiled strategy versions, runtime monitoring state, detections, freshness |
| `GET /strategies/{id}/versions` | Exact numeric version lookup; never infer activity from the newest version |
| `GET /notifications/preferences` | Existing alert preferences |
| `PATCH /notifications/preferences` | Minimum severity only |
| `GET /alerts/delivery-status` | Telegram delivery/configuration state |
| `GET /risk/settings` | Canonical risk parameter display only |
| Existing AppContext `/health` and `/providers/status` | System posture and provider health |

There are no new endpoints or backend execution changes. No Telegram network delivery or live trading was enabled. Missing connection verification, per-market/per-strategy notification filters, and strategy activation controls are clearly labeled as unavailable or unverified.

## Validation

From `frontend/`:

```sh
npm test -- 'src/app/(app)/settings/page.test.tsx' \
  'src/app/(app)/settings/advanced/page.test.tsx' \
  src/components/NotificationSettingsPanel.test.tsx \
  src/components/WatcherWatchlistSection.test.tsx \
  src/components/layout/navigation-config.test.ts \
  src/components/layout/AppShell.test.tsx
npm run typecheck
./node_modules/.bin/eslint 'src/app/(app)/settings/page.tsx' \
  'src/app/(app)/settings/page.test.tsx' \
  'src/app/(app)/settings/advanced/page.tsx' \
  'src/app/(app)/settings/advanced/page.test.tsx' \
  src/components/settings/*.tsx \
  src/components/NotificationSettingsPanel.tsx \
  src/components/NotificationSettingsPanel.test.tsx \
  src/components/WatcherWatchlistSection.tsx \
  src/components/WatcherWatchlistSection.test.tsx \
  src/components/layout/navigation-config.ts \
  src/components/layout/navigation-config.test.ts \
  src/components/layout/AppShell.test.tsx
```

Results: **53 tests passed across 6 files**, TypeScript passed, ESLint passed, and `git diff --check` passed. Tests cover exact version matching, absent version metadata, empty monitoring state, enabled-versus-running semantics, unverified and unsafe runtime posture, canonical read-only risk values, supported revisioned watchlist writes, supported severity-only preference writes, independent source failures and retries, and missing/empty preference values. Delivery methods are asserted unused.

Protected-scope comparison found no changes to `backend/`, `.github/`, frontend API contracts/configuration, dependency manifests, or lockfiles. React component review covered independent reads, request deduplication per strategy, accessible labels, explicit failure states, and responsive wrapping.

Verification scope is focused local frontend tests, type checking, lint, and source review. No production build, browser/device run, backend suite, or full frontend suite was performed. No CI wait, merge, or deployment.

## Review handoff

Review the Settings workspace and Advanced separation in the draft PR. Keep this branch stacked on the interface-polish branch until its parent work lands. Stop after commit, push, draft PR creation, and handoff.
