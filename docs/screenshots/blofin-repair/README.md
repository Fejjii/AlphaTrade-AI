# BloFin repair — synthetic browser fixtures

These screenshots contain invented account, command and trade data intercepted by Playwright. They are **not authenticated BloFin evidence**, production acceptance, or proof that the existing trade closed. No native orders or external account mutations were performed.

- `fixture-dashboard-1280.png`, `fixture-dashboard-390.png`: configured demo account as the primary Dashboard; USD equity, USDT balances, native positions, partial recorded performance, unavailable net PnL and strategy performance.
- `fixture-dashboard-stale-1280.png`, `fixture-dashboard-stale-390.png`: expired saved account snapshot; original snapshot timestamp and values remain visible.
- `fixture-manual-agent-1280.png`, `fixture-manual-agent-390.png`: compact exact attempt, verified entry, unverified exit, concise Agent answer, collapsed supporting evidence and exact Journal action.
- `fixture-journal-1280.png`, `fixture-journal-390.png`: exact linked canonical Journal trade with a separate attached personal reflection.

Reproduce from `frontend/` with the local Next dev server on port 3000 and system Chromium:

```sh
PLAYWRIGHT_SKIP_WEBSERVER=1 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npx playwright test e2e/dashboard-demo-account.spec.ts e2e/blofin-repair.spec.ts e2e/manual-demo-recovery.spec.ts --project=chromium
```

The six tests passed at 1280px and 390px where applicable. Checks include exact route identity, scoped API operations, reflection attachment, native snapshot refresh/retry, recovery confirmations, session restoration, and no horizontal overflow. Chromium mobile viewport checks do not establish Safari or physical iPhone compatibility. Captures used fallback fonts because Google Fonts requests were unavailable in this environment.
