# AT-041 PR4 — Readiness validation checklist

Source of truth: PR #41 audit (`docs/product/at040_final_polish_and_readiness_audit.md` @ `ce4bd04e…`).

This checklist separates **automated browser validation** (CI / local Playwright) from **pending physical / staging** work. Do not mark staging or iPhone rows as done from CI alone.

## A. Automated browser validation

Run:

```bash
bash scripts/readiness-browser-validation.sh
# or full suite:
cd frontend && npm run test:e2e
```

| Check | Automation | Spec / script |
|---|---|---|
| Representative 390 px overflow | Automated | `e2e/readiness-validation.spec.ts`, `e2e/analytics-hub.spec.ts` |
| Console errors | Automated | `e2e/readiness-validation.spec.ts`, `e2e/analytics-hub.spec.ts` |
| Failed requests (5xx) | Automated | same |
| One `h1` per route | Automated | `e2e/readiness-validation.spec.ts` + page tests |
| Deep links `?signal=` `?entry=` `?document=` `?tab=` | Automated | `e2e/deep-link-contracts.spec.ts`, `e2e/readiness-validation.spec.ts` |
| Paper posture visible | Automated | readiness + analytics + paper-close specs |
| Kill-switch BLOCK visibility | Automated (mocked status) | `e2e/readiness-validation.spec.ts` |
| Close-paper flow | Automated (UI + mocked API) | `e2e/paper-close.spec.ts` + `positions/page.test.tsx` |
| Analytics six tabs + URL state | Automated | `e2e/analytics-hub.spec.ts` |

## B. Pending staging validation (manual)

- [ ] Staging env: `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `PROVIDER_MODE=fallback`, non-live `EXCHANGE_MODE`
- [ ] Full CI green on the PR HEAD (all six jobs)
- [ ] Kill-switch activate → BLOCK on shell + portfolio → deactivate
- [ ] Seeded paper cycle: proposal → approval → paper execution → close with typed exit price → journal/portfolio
- [ ] Deep links from a message app resolve on staging

## C. Pending physical iPhone validation (manual)

- [ ] Safari: register/login, daily loop (Dashboard → Signals → Plan → Validate → Journal)
- [ ] Close a paper trade with explicit exit price on phone
- [ ] Review Portfolio + two Analytics tabs
- [ ] Safe-area insets, keyboard on journal/login, pinch-zoom
- [ ] Kill-switch drill from phone
- [ ] Deep links from Messages; back/forward never opens a wrong record
- [ ] No console errors under remote inspection

## D. Coverage matrix notes (FP2-129 after PRs #50–#54)

| Route | Before PR4 | PR4 action |
|---|---|---|
| `/positions` | Covered (#50/#54) | Audited; not duplicated |
| `/strategy-lab/[id]` | Covered (#51) | Audited; not duplicated |
| `/proposals` | Missing | Added `page.test.tsx` |
| `/approvals` | Missing | Added honesty fix + `page.test.tsx` |
| `/market` | Missing | Added `page.test.tsx` |
| Settings composites | Partial | Shim tests for audit/team/exchange/usage; billing already covered |
| FP2-221 liquidated rows | Open | Fetch/merge + status cell + tests |
| FP2-226 analytics freshness | Open | Hub-managed shell pill + adapter feed |
| FP2-212 / FP2-213 | Open | Deferred (not low-risk in this PR) |
