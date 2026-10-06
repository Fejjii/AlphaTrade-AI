# Knowledge workspace frontend fixtures

> **Recorded frontend fixture snapshot:** retain the original capture context below; use the [current screenshot review](../../screenshots_checklist.md) and [Knowledge/retrieval guide](../../rag_system.md) for present limits. This set does not establish hosted provider or file-import acceptance.


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
