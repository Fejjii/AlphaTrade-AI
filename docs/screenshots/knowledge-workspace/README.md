# Knowledge workspace frontend fixtures

These captures use synthetic API responses and are labeled **FRONTEND TEST FIXTURE · NOT LIVE DATA**. They show the Knowledge category navigation, search, document provenance, exact linked lesson context, and stored market observations after canonical note creation.

| Viewport | Capture |
| --- | --- |
| Desktop, 1440×1000 | [Desktop](desktop-fixture.png) |
| iPhone portrait, 390×844 | [Portrait](iphone-fixture.png) |
| iPhone landscape, 844×390 | [Landscape](iphone-landscape-fixture.png) |

Regenerate from `frontend/`:

```sh
XDG_CONFIG_HOME=/tmp/alphatrade-browser-config \
XDG_CACHE_HOME=/tmp/alphatrade-browser-cache \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
KNOWLEDGE_SCREENSHOTS=1 \
npx playwright test --config playwright.knowledge.config.ts
```

An installed Playwright Chromium can run without the executable override. Google Fonts were unavailable here; captures use the application's fallback fonts. These are Chromium screenshots at iPhone dimensions, not physical iPhone or Safari verification.
