# Six-destination navigation screenshots

Captured with frontend-only fixtures at desktop 1440 × 1000 and iPhone-sized
390 × 844 viewports. The session and paper posture are fixtures; workspace reads
return explicit unavailable responses. Every capture is watermarked. These are
not live trading, portfolio, or market results.

| Surface | Desktop | iPhone-sized portrait |
| --- | --- | --- |
| Agent | [Desktop Agent](desktop-agent.png) | [iPhone Agent](iphone-agent.png) |
| Knowledge | [Desktop Knowledge](desktop-knowledge.png) | [iPhone Knowledge](iphone-knowledge.png) |
| Settings | [Desktop Settings](desktop-settings.png) | [iPhone Settings](iphone-settings.png) |

The navigation browser suite additionally verifies 320 × 740 narrow portrait and
844 × 390 landscape viewports, six links in order, selection, at least 44px touch
targets, complete mobile labels, collapsed desktop access, and contextual routes.
This uses Chromium; physical iPhone and Safari behavior are unverified. Google
Fonts were unavailable locally, so captures use the application's fallback fonts.
The development-only Next.js overlay is hidden in these captures.

To recapture from `frontend` with an installed Playwright Chromium browser:

```sh
NAVIGATION_SCREENSHOTS=1 node_modules/.bin/playwright test --config playwright.navigation.config.ts
```

To use system Chromium, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium`.
The configuration starts or reuses a local Next.js server on port 3000; use one
server for this checkout.
