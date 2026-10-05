# Trader interface polish screenshots

These are **synthetic frontend test fixtures, not live account or market data**. Each image carries a fixture watermark. Chromium captured desktop (1440 × 1000) and iPhone portrait dimensions (390 × 844). Landscape (844 × 390) also passed layout checks. These are viewport checks, not a physical iPhone or Safari validation.

The local environment blocked Google Fonts; the captures use the application's existing fallback fonts.

| Surface | Desktop | iPhone portrait |
| --- | --- | --- |
| Dashboard | [Screenshot](desktop-dashboard-fixture.png) | [Screenshot](iphone-dashboard-fixture.png) |
| Agent | [Screenshot](desktop-agent-fixture.png) | [Screenshot](iphone-agent-fixture.png) |
| Journal | [Screenshot](desktop-journal-fixture.png) | [Screenshot](iphone-journal-fixture.png) |
| Journal statistics | [Screenshot](desktop-journal-statistics-fixture.png) | [Screenshot](iphone-journal-statistics-fixture.png) |
| Journal empty state | — | [Screenshot](iphone-journal-empty-fixture.png) |
| Journal unavailable state | — | [Screenshot](iphone-journal-unavailable-fixture.png) |

Regenerate from `frontend/` with:

```sh
POLISH_SCREENSHOTS=1 npx playwright test --config playwright.polish.config.ts
```

If using system Chromium, also set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to its executable path. The fixture suite intercepts the existing API contracts and never starts a backend or uses an external account.
