# Screenshot provenance and reproduction

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
