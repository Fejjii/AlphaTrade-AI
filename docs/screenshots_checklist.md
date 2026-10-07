# Product screenshot capture and provenance

The current reviewer package uses rendered architecture/workflow diagrams because no suitable authenticated current-product capture was available in this documentation session. Existing images are preserved as dated fixtures; they are not used as the main showcase. This guide gives an exact handoff for obtaining authentic captures without manufacturing market or execution events.

## Current product capture plan

Use an existing authorized session on the reviewed frontend, backed by the intended API release. Before capture, record the actual frontend/API commit and capture date; if they differ from `b58beda`, state both. Use a desktop viewport of **1440 × 1000** at 100% zoom, plus a **390 × 844** portrait capture where useful. Keep the six destinations, paper label and relevant evidence/source state readable. Wait for real records to finish loading; a source outage is not a suitable hero capture.

Store new reviewed files under `docs/screenshots/reviewer/` only when they exist. The filenames below are a capture plan, not image links or placeholders.

| Capture | Route and exact view | Proposed filename | Caption and acceptance |
| --- | --- | --- | --- |
| A — product entry | `/`: paper account, daily attention and monitoring, six-workspace navigation visible. | `dashboard-current.png` | Actual UI, source/date/SHA stated. Crop account/email identifiers; retain paper and source/freshness labels. No synthetic balance presented as live. |
| B — historical decision | `/journal`: open the existing Nested BTC short; show plan entry/stop/targets beside actual recorded internal fill/venue. | `journal-nested-paper.png` | “Historical Nested BTC short — internal paper simulation.” A missing target projection stays a disclosed gap; do not repair it for capture. Hide record/account IDs. |
| C — grounded Agent | `/agent`: select the exact recorded trade; ask the two prompts in [demo script](demo_script.md). Capture summary plus readable source labels, and a separate cropped Stored evidence view if safe. | `agent-recorded-trade.png` | Identify historical context. Retain distinctions between plan, fill, current 1R policy and missing evidence. Hide raw UUIDs/hashes and private conversation content. |
| D — Knowledge | `/knowledge`: show an existing nonsensitive playbook/source. Optionally use the existing file-import form and **Preview file** on a harmless local document, then stop before **Save previewed file**. | `knowledge-preview.png` | “Extracted-text preview; not yet saved/indexed” if preview is shown. Use only content authorized for public sharing; no artificial search success. |
| E — governed context | `/settings`: **Risk**, **Notifications**, or **Account and system** section; capture meaningful public controls. | `settings-controls.png` | Settings visibility does not establish an armed worker or an order. Hide credentials, account balances/identifiers and chat/email data as needed. |
| F — actual notification, optional | Existing received Watcher notification in Telegram, only through access already authorized by the owner. | `telegram-received.png` | Historical receipt with date retained; hide chat/bot/private account identity. Do not send a new notification for capture. |

For Knowledge preview, a nonsensitive local `.txt` or `.md` file is sufficient. Preview does not save/index content; do not click Save or issue an ingest request during this observational capture. Opening Settings' manual-demo form is not proof of execution. Do not click **Preview demo entry**, **Confirm and submit demo market order**, recovery, reconciliation or cancellation controls merely to obtain a screenshot; they belong to the separately supervised [manual acceptance procedure](manual_blofin_demo_acceptance.md).

Before publishing each actual image, review the full frame for passwords, API keys, JWTs, real emails, organization/user/account/chat IDs, private document text and sensitive audit/record payloads. Crop those regions from the capture or use an owner-approved sanitized display; do not alter prices, states, receipts or results. Record provenance alongside the files: capture date/time, route, viewport/browser, actual frontend/API SHA, paper/data context, and any crop/redaction. A technical evidence panel may be unsuitable for public sharing even when it is useful during a private demo.

A received notification, account-sync panel and Journal paper fill cannot be captioned as native BloFin order execution. For that claim, only separately accepted native order/fill/protection evidence is suitable. No such acceptance capture was available here.

## Preserve historical fixture reproduction

The original guide below documents existing sets and their October 6 inspection. Its fixture commands remain useful for technical UI regression work. A fixture screenshot must retain its watermark and cannot replace an authentic current-product capture in the reviewer showcase.

### Historical screenshot provenance and reproduction

Screenshots must come from the application or its declared test fixtures. Keep source context visible: local mock/replay, synthetic frontend fixture or separately authorized live-data paper context. Do not fabricate UI, trade results or provider activity.

## Existing images reviewed on October 6, 2026

The documentation review visually inspected the original dashboard, the trader-polish dashboard, six-workspace desktop Agent and phone Knowledge, and the voice-speaking desktop capture. The listed fixture images are authentic stored captures with visible watermarks. They were not freshly recaptured or compared with a running app in this task.

| Set | Origin/source | What remains useful | Historical limit |
| --- | --- | --- | --- |
| [Original `screenshots/*.png`](screenshots/README.md) | Earlier local mock paper-MVP captures. | Original workflow/portfolio history. | Old wide navigation, legacy workspace/proposal screens and synthetic IDs/results; not the current product overview. |
| [Trader polish](screenshots/trader-polish/README.md) | Frontend API fixtures; desktop/phone dimensions. | Dashboard/Journal layout and explicit small-sample/unavailable states. | Captures show the earlier five-destination shell, no Knowledge destination; balances/PnL are synthetic. |
| [Six-destination navigation](screenshots/primary-navigation-6/README.md) | Frontend fixture/unavailable sources; handoff updated October 1, 2026. | Correct current six-workspace order and mobile labels. | Earlier Agent says voice unavailable; controls evolved after capture. Source unavailable is intentional. |
| [Voice Agent V1](screenshots/voice-agent/README.md) | Frontend and deterministic speech fixtures; October 1 handoff. | Transcript review/send, separate Confirm/Reject, reply playback controls. | Older five-workspace shell; no real microphone, speech service, Safari or physical iOS proof. |
| [Knowledge workspace](screenshots/knowledge-workspace/README.md) | Synthetic frontend fixtures; see set's reproduction notes. | Knowledge layout and declared unavailable states. | Treat as its recorded snapshot, not current import/provider acceptance. |

No private credentials were observed in the reviewed images; displayed sessions/values are declared synthetic. Do not copy raw visible audit/record identifiers into new public examples. Other images were inventoried through their existing provenance notes, not individually audited here. Original capture times are not independently established beyond the dated source handoffs.

## Reproduce a local fixture capture

Install the local frontend dependencies and an appropriate Playwright Chromium browser in an isolated checkout. Read the configuration before running; use one local dev server for that checkout, with its API origin pointing to the intended local fixture context. These suites intercept API contracts and do not require a backend or external account.

From `frontend/`:

```sh
npm ci
NAVIGATION_SCREENSHOTS=1 npx playwright test --config playwright.navigation.config.ts
POLISH_SCREENSHOTS=1 npx playwright test --config playwright.polish.config.ts
VOICE_SCREENSHOTS=1 npx playwright test --config playwright.voice.config.ts
```

An existing system Chromium can be selected with `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`. Commands may recreate the set on today's source, so record the new SHA/date rather than copying an old caption. A successful browser fixture still does not establish hosted or physical-device acceptance.

The legacy `npm run capture:screenshots` script remains available for its earlier integrated capture project; inspect its config before use. It is not the canonical six-workspace/current-capability proof.

A new application stack/capture was not launched for this documentation review; frontend dependencies are not installed in the isolated checkout. Original authentic images were retained with corrected provenance and historical captions. Current running-UI and physical-device verification therefore remain unperformed.

## For any new public capture

1. Record source SHA, date, route, viewport, browser and fixture/runtime context alongside the image.
2. Use synthetic identity/content or a separately authorized sanitized context. Keep real emails, passwords, tokens, account/chat IDs and sensitive audit data out of frame.
3. Preserve paper/data-source/freshness labels. Label synthetic balances/trades and unavailable sources explicitly; do not claim performance.
4. Capture the actual six-workspace UI, readable confirmation boundaries and supported controls. An empty/error state is legitimate evidence.
5. Check desktop/phone portrait/landscape as appropriate. Browser viewport checks do not prove physical iPhone/Safari behavior.
6. State any fallback fonts, missing hardware/provider access or earlier UI shown. Link to [current status](current_status.md) for acceptance limits.

Fresh live SFP recovery, old Journal target repair and real BloFin demo acceptance remain pending in supplied supervising evidence. No screenshot changes that status.
