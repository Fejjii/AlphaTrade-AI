# Knowledge workspace 001 handoff

Status: REVIEW_REQUIRED
Branch: `codex/knowledge_workspace_001`
Exact base: `94954e7d243be0c03ce667403964adb6e4e2b850` (`codex/trader-interface-polish`, PR #157)

## Result

The existing `/knowledge` area is now a single trader workspace with Trading Rules, Playbook, Lessons, Strategy Research, and Market Observations navigation. All knowledge preserves access to other document types. These are frontend views of existing source types, not persisted categories or a new knowledge system.

| Workspace view | Existing source types |
| --- | --- |
| Trading Rules | `risk_policy` |
| Playbook | `trading_playbook` |
| Lessons | `review_note`, `mistakes_database` |
| Strategy Research | `strategy_template` |
| Market Observations | `general_note`, `trade_journal` |

Category reads reuse `GET /knowledge/documents`, paginated at 50 records per source. Loading keeps navigation and search visible while hiding previous-category records. Failed sources have retry controls, and multi-source views show partial results without claiming complete counts. Legacy `source`, `q`, and `document` URLs remain supported. Legacy title/reference filtering is explicitly scoped to the document page.

One content search reuses `POST /knowledge/search`, including category source filters, ranked passages, canonical document links, passage provenance, and degraded/fallback warnings. Query or category changes discard prior and in-flight results. Search links open the exact requested document. Because no document-by-ID endpoint exists, direct links outside the loaded page resolve through canonical document pages, bounded to 4,000 records with an explicit limit error.

Cards reuse the existing UI tokens, controls and document/chunk components. Full URI, document ID, source hash, version and timestamps are available in expandable provenance details; full URIs wrap on mobile. Stored `strategy://`, `lesson://`, and `journal://` identifiers provide canonical links. Expanded lesson documents read the existing candidate API for their strategy/journal references. Strategy and journal documents match accepted lessons by their stored `related_strategy_id` or `related_journal_entry_id`. The accepted-lesson read is currently the API client's first 50 records; incomplete coverage is disclosed. Trade IDs and strategy tags are never treated as journal-entry or strategy IDs. `journal-trade://` remains visible as provenance because there is no verified frontend destination for an individual canonical trade.

Add note stays collapsed until requested. Creation of Trading Rules, Playbook and Market Observations notes uses only existing `POST /knowledge/ingest` source types. The active rules/observations view selects the appropriate initial source. Empty title/content and repeated busy submissions are blocked; errors retain the draft; success refreshes canonical documents. No edit, delete, review/promotion, or strategy attachment action was added. The Knowledge API has no edit endpoint.

## Reused infrastructure and boundaries

Inspected the existing Knowledge routes/schemas/client, document and chunk views, URI helpers, accepted-lesson RAG producer, strategy-library RAG synchronization, journal RAG synchronization, lesson candidate APIs, and the trader polish handoff/design components.

No backend, API/data contracts, database migrations, storage layer, dependencies, execution behavior, Telegram, Agent orchestration, Strategy Brain detectors, active Strategies, Strategy Lab, or shared shell/navigation was changed. The trader polish branch is the exact parent, rather than cherry-picked UI changes.

## Validation

Commands run from `frontend/`:

```sh
npm run test -- 'src/app/(app)/knowledge/page.test.tsx' src/components/knowledge
npm run typecheck
```

- Focused Vitest: **47 passed across 6 files**. Existing URI/query/display tests remain included. Page tests exercise actual async loading with API mocks and replace obsolete multi-panel hub assertions with workspace behavior assertions.
- Full frontend TypeScript check passed.
- ESLint passed with zero warnings on changed/new TypeScript and TSX files.
- Frontend contract fixture Playwright: **4 passed**, covering desktop 1440×1000, iPhone portrait 390×844, and landscape 844×390. Checks category reads, lazy chunks, typed lesson/journal links, search request payload and exact result destination, canonical note ingestion and refresh, full provenance URI expansion, loading/unavailable/retry/empty states, document overflow, child clipping, and 16px mobile controls. Browser page errors were checked in the three populated flows.

```sh
XDG_CONFIG_HOME=/tmp/alphatrade-browser-config \
XDG_CACHE_HOME=/tmp/alphatrade-browser-cache \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
KNOWLEDGE_SCREENSHOTS=1 \
npx playwright test --config playwright.knowledge.config.ts
```

Agent-browser independently confirmed the dev server's sign-in page rendered interactive controls and no framework error overlay. The authenticated Knowledge story was then checked through Playwright using frontend-only API fixtures. Fixture requests are validated against the existing backend route/schema and client contracts; no live backend or account was used.

`git diff --check` passed. Protected-scope comparison from repository root passed:

```sh
git diff --exit-code 94954e7d243be0c03ce667403964adb6e4e2b850 -- \
  backend 'frontend/src/app/(app)/strategies' 'frontend/src/app/(app)/agent' \
  'frontend/src/app/(app)/strategy-lab' frontend/src/components/strategy \
  frontend/src/lib/api frontend/package.json frontend/package-lock.json
```

## Evidence and limits

[Desktop and iPhone fixture screenshots](screenshots/knowledge-workspace/README.md) are watermarked **FRONTEND TEST FIXTURE · NOT LIVE DATA**. Google Fonts could not be fetched in this environment, so browser captures use existing fallback fonts. Chromium at iPhone dimensions was verified; Safari, the iOS keyboard and a physical iPhone were not.

Expanded document content retains the existing 50-chunk read and explicitly marks truncation. Related lessons show loaded coverage rather than full-corpus conclusions. No full frontend suite, production build or backend tests were needed or run for this frontend change. No CI results were awaited or polled.

## Review handoff

Review the draft PR against `codex/trader-interface-polish` at the exact base above. Confirm the source mapping and empty states with real tenant data when reviewing; physical iPhone/Safari verification remains a reviewer option. This task stops after its draft PR and handoff. Nothing is merged or deployed, and no follow-up automation is started.
