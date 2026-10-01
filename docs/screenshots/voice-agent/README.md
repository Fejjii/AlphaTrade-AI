# Voice Agent V1 screenshots

These captures use **frontend and speech test fixtures**, not live market data or
a real microphone. Chromium checks desktop 1440×1000, phone portrait 390×844,
and phone landscape 844×390. Fallback fonts are shown; Google Fonts were blocked.

| Layout | Recording | Speaking |
| --- | --- | --- |
| Desktop | [Recording](desktop-recording.png) | [Speaking](desktop-speaking.png) |
| Phone portrait | [Recording](phone-recording.png) | [Speaking](phone-speaking.png) |
| Phone landscape | [Recording](phone-landscape-recording.png) | [Speaking](phone-landscape-speaking.png) |

Regenerate from `frontend/`:

```sh
XDG_CONFIG_HOME=/tmp/alphatrade-browser-config XDG_CACHE_HOME=/tmp/alphatrade-browser-cache PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium VOICE_SCREENSHOTS=1 npx playwright test --config playwright.voice.config.ts
```

Omit the executable override when an installed Playwright Chromium is available.
Physical microphone access and Safari/iOS were not verified.
