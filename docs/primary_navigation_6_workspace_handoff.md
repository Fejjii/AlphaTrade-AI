# AlphaTrade six-destination navigation handoff

Status: COMPLETE — draft review handoff; stop here.

- Draft PR: https://github.com/Fejjii/AlphaTrade-AI/pull/166
- Branch: `codex/primary_navigation_6_workspace_001`
- Exact base: `94954e7d243be0c03ce667403964adb6e4e2b850`
- Stack parent: #157, `codex/trader-interface-polish`, above #153.
- Implementation commit: `036965cf1c9747f402a973ef5e6d12ec879abd3f`
- Last updated: 2026-10-01 16:46 UTC.

## Result and changed surfaces

Desktop navigation, the collapsed sidebar, mobile tabs, and command-menu primary
results expose exactly six destinations in this order:

| Destination | Existing route | Role |
| --- | --- | --- |
| Dashboard | `/` | Main observational view; existing paper portfolio and status presentation |
| Agent | `/agent` | Conversational operating interface; persistent navigation accent |
| Journal | `/journal` | Trade review, statistics, and learning; existing contextual access retained |
| Strategies | `/strategies` | Existing active strategy intelligence and setup implementation |
| Knowledge | `/knowledge` | Rules, playbook, lessons, and recorded notes/research |
| Settings | `/settings` | Markets, strategy setup, notifications, risk, and system parameters |

Knowledge is promoted from a specialized Strategies link to its own destination.
Lessons select Knowledge in the shell and remain reachable from Journal and
Knowledge. Knowledge section links reuse the existing `source` filter contract
and preserve `document` and `q` when changing library views. Research notes use
the existing general-note filter; no research data or capability is invented.

Settings links to the existing Watcher watchlist and notification panels with
anchors, strategy setup at `/strategy-lab`, risk settings at `/risk`, and runtime
posture/build configuration via the system anchor. Account and Advanced remain
the Settings secondary links. Specialized pages remain in Advanced settings and
the command menu; all 47 original navigation/catalog paths are retained.

The mobile bar uses six columns, complete labels, safe-area padding, and touch
targets of at least 44px. The active tab has a top marker and background; the
Agent icon keeps its accent when another destination is selected. Desktop Agent
has a persistent accent border. Collapsed links keep their accessible names.

Changed production files are the shared navigation configuration/catalog,
DesktopSidebar, MobileBottomNavigation, optional navigation props on the existing
JournalHubChrome, Knowledge page chrome, and Settings contextual links/anchors.
No pages are duplicated or removed. Backend files, API contracts, redirects,
active Strategies from #153, Telegram, dependencies, and business behavior are
unchanged. Existing unavailable/error states and paper posture remain explicit.

## Validation

- 120 focused Vitest tests passed in 10 files.
- All changed/new TypeScript files passed ESLint with `--max-warnings=0`.
- `npm run typecheck` passed.
- Five frontend-only Playwright tests passed: desktop 1440×1000, iPhone-sized
  portrait 390×844, narrow portrait 320×740, landscape 844×390, and contextual
  access/deep links. All six links were clicked in every viewport. Checks cover
  selection, label fit, minimum touch targets, collapsed desktop access,
  Knowledge query preservation, Settings anchors, and retained routes.
- `git diff --check`, exact-base comparison, retained-path comparison, and
  protected-scope comparison passed.

Focused unit command, from `frontend`:

```sh
npm test -- src/components/layout/navigation-config.test.ts src/components/layout/DesktopSidebar.test.tsx src/components/layout/AppShell.test.tsx src/components/layout/CommandMenu.test.tsx src/components/layout/TopBar.test.tsx 'src/app/(app)/knowledge/page.test.tsx' 'src/app/(app)/settings/page.test.tsx' 'src/app/(app)/settings/advanced/page.test.tsx' 'src/app/(app)/journal/page.test.tsx' src/components/knowledge/knowledgeContext.test.ts
```

Browser command, from `frontend`:

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium NAVIGATION_SCREENSHOTS=1 node_modules/.bin/playwright test --config playwright.navigation.config.ts
```

The new browser configuration reuses the frontend fixture configuration and
requires one Next.js server on port 3000. Session and paper posture are fixture
values; workspace sources return explicit unavailable responses. Navigation
checks assert API requests are reads. Retained pages may show their existing
error state before a header when a source fails; this behavior is preserved.
The existing backend-integrated simplified-UI smoke expectations were updated
to six destinations, but that integrated suite was not run.

## Screenshots and verification limits

Six watermarked desktop/iPhone-sized captures are committed with reproduction
instructions in [screenshots/primary-navigation-6](screenshots/primary-navigation-6/README.md).
They show Agent, Knowledge, and Settings with unavailable workspace sources and
are not live trading results. Google Fonts were blocked locally; screenshots use
existing fallback fonts. Browser checks use Chromium, not physical iPhone/Safari.
Full backend integration, full repository test suite, and production build were
outside this navigation change.

## Review handoff

Review draft #166 as the delta above #157. No CI was awaited, no PR was merged,
and no deployment was performed. No further implementation is pending. Stop.
