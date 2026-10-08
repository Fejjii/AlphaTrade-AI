# Manual BloFin demo policy repair and acceptance evidence

Baseline: main `e6bd9b07` (merged PR227), 8 October 2026. One implementation
agent; no delegation, full backend CI dispatch, branch-protection changes,
deployment, credential/activation changes, or live exchange order submission.
No `AGENTS.md` was present in the repository or its workspace parents; the remote
main lookup also returned 404 for that file. Current implementation was traced
before editing.

## Root causes and complete path

The reported `max_position_size` refusal came from
`ManualDemoService._risk`: `DailyRiskAccounting.sync_from_portfolio` supplied
simulator equity, open exposure, PnL and trade count, and these were combined with
previewed venue balances and the shared strategy engine. Green day protection
appeared because the same engine applied strategy discipline to a connectivity
test. Confirmation also reused saved account balances instead of refreshing them.
A second possible blocker was the claim predicate: its account ledger limits,
daily lock, actual exposure and trade slots can originate in internal paper
execution, even though the approved manual plan has no strategy lineage.

PR227 already implemented the explicit manual exception to minimum 1R at the
reward/risk, approval, claim and dispatch boundaries. This repair preserves that
exception and directional geometry validation; it does not relax strategy 1R.

| Stage | Authority, repair and preserved guards |
| --- | --- |
| Form / instrument | Owner-only read-only `/execution/manual-demo/instrument`; venue minimum, lot, tick, multiplier, indicative BTC/notional. Exact decimal validation before preview. Values are held stable during pending requests. |
| Preview | Demo credentials and organization/user/account pins; fresh executable side/depth plus account-wide position/order/protection reads; canonical manual plan. Explicit venue policy replaces combined simulator risk. No authorization or order. |
| Plan | Immutable revision/hash, no strategy/setup/Candidate. Contract quantity and executable entry range, unchanged stop/target, cost-inclusive maximum loss. Manual minimum notional and geometry errors are identified separately from exchange increments. |
| Authorization | Existing exact-hash WEB confirmation and expiry requirements; generic approval/execution cannot bypass manual confirmation. No simulator policy evaluation here. |
| Reservation / claim | Existing idempotency, revision lock, account safety epoch, unresolved-demo-history hold and ledger. Manual capacity callback is mandatory and runs under the epoch; only same-account BloFin demo reservations consume manual capacity. Simulator ledger limits/daily counters are not read as manual policy. Existing automatic predicate is unchanged. |
| Dispatch | Committed reservation and single-use effect/fence. Replays read/reconcile, never resend. Principal/hash/venue/TTL/kill/epoch checks remain. No combined portfolio predicate here. |
| Native POST | Fresh provider preflight reuses the manual policy, instrument and executable-range checks. Quote and account-read freshness are checked again after the safety callback and transport throttle. One demo entry POST, with attached full SL/TP. Real venue/account-setting mutations remain refused. |
| Exchange response | Acknowledgment is an order receipt, never fill or protection proof. Empty/uncertain responses retain identity and reservation; subsequent confirmation only reads. |
| Protection / reconciliation | Native fills and linked protection are read independently. Unique fill facts and fees cannot be overwritten or duplicated. Missing protection preserves actual fills, activates the operator hold, and can later be reverified without another entry POST. The kill switch is not automatically cleared. |
| Journal | An unfilled submitted order has its native audit receipt and no fabricated trade. Verified fills create/update the same `manual_demo_test` trade with actual quantity/price/fees and explicit protection state. Protection revalidation updates that trade; no strategy or learning attribution. Shared automated accounting retains actual history. |

The manual policy requires a flat demo account, including no pending normal or
TPSL orders on other instruments. This is a conservative actual-capacity gate,
not invented zero exposure. Malformed or potentially truncated account responses
produce actionable refusal. Unknown account state never falls back to simulator
funds or zero positions.

Test notional plus unreleased demo reservations must be at most 5%, and planned
loss plus unreleased demo loss allocations at most 1%, of the lesser of fresh demo
USDT equity and available funds. Funds must also cover entry plus fees. The existing
5 USDT test minimum and 1x/NET/cross isolation remain. Account-read freshness has
its own timestamp so a fresh quote cannot conceal old account reads. These limits
apply during preview, fresh confirmation, locked claim and final provider preflight.

A server error tagged `submission: not_started` permits a fresh preview. Other
errors, including generic 403s, retain the exact confirmation for recovery.
Historical manual ALLOW commands without audited lifecycle resolution continue to
hold the account; this repair does not add exit/outcome or repeat-entry release.
No history or reservations are erased to obtain capacity.

## Chrome application cause and limits of the proof

The application's global Next.js header was `Permissions-Policy: microphone=()`.
Chrome document policy can deny `getUserMedia` with `NotAllowedError` even when
site/macOS permissions are enabled. It is changed to `microphone=(self)`; camera,
geolocation and frame restrictions remain. The provider now identifies policy
refusal through `permissionsPolicy`/`featurePolicy` before invoking capture or
recognition. Unsupported policy APIs use the existing capture path, preserving
Safari compatibility. Recognition starts on the button gesture; capture stops all
tracks immediately, including late resolutions after cancellation/timeout/disposal.

A running local Next.js app was tested with a real Chromium engine and synthetic
microphone. The old policy reproduced `NotAllowedError`; the repaired document
header allowed capture, and every track ended. This is application-policy evidence,
not actual Mac/iPhone acceptance or speech-service proof. The deployment-fetch tool
was rejected by automatic approval review because it may create an authentication
bypass link and follow redirects. No bypass was created; actual deployed headers
remain unverified. See `chrome_voice_diagnostics.md` for exact remaining checks.

## Focused verification

Run from `backend/`, against the disposable local PostgreSQL database:

```sh
.venv/bin/pytest -o addopts='' -q \
  tests/test_manual_blofin_demo.py tests/test_demo_order_book.py \
  tests/test_planned_reward_risk.py tests/test_planned_reward_risk_postgres.py \
  tests/test_risk_engine.py \
  tests/test_phase8_canonical_paper_execution.py::test_risk_capacity_blocks_canonical_execution \
  tests/test_phase8_canonical_paper_execution.py::test_kill_switch_blocks_without_consuming_authorization
```

Result: **143 passed**, no skips, one existing FastAPI/httpx deprecation warning,
69.00 seconds. The final account-error category adjustment was additionally verified
by its 10 native capacity/unknown-state cases. Venue IO uses realistic native
provider fixtures and a real database, including concurrent confirmations. Tests
cover the reported unrelated paper exposure and restrictive simulator state, actual
venue positions/pending orders/funds, fractional contracts, geometry, consistent
preview/confirmation limits, stale account/quotes, missing claim evidence, concurrent
claims, uncertain submit/cancel responses, fill integrity, and protection/Journal
recovery. Automatic strategy daily loss, trade-frequency and green day rules, shared
capacity/kill predicates and minimum 1R remain tested.

Run from `frontend/`:

```sh
npm run test -- src/components/settings/ManualDemoTest.test.tsx \
  src/lib/security-headers.test.ts src/lib/voice/browser-voice-provider.test.ts \
  src/components/agent/AgentVoiceControls.test.tsx
npm run typecheck
PLAYWRIGHT_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
npx playwright test e2e/microphone-policy.spec.ts --project=chromium --workers=1
```

Result: **74 unit tests passed**, **2 Chromium policy/capture tests passed**.
TypeScript and scoped ESLint passed. Scoped backend Ruff checks/format checks and
mypy on the four execution/provider policy files passed. No full backend suite or
release workflow was dispatched. Provider fixtures do not prove exchange execution.

## Changed files

- Backend policy/execution: `services/manual_demo_policy.py` (new),
  `manual_demo_service.py`, `manual_demo_plan.py`, `execution_claim.py`,
  `providers/exchange/governed_blofin.py`, `demo_preflight.py`,
  `schemas/manual_demo.py`, `api/routes/execution.py`.
- Backend regressions: `tests/test_manual_blofin_demo.py`, `test_demo_order_book.py`,
  `test_risk_engine.py`.
- Form: `components/settings/ManualDemoTest.tsx` and its tests,
  `lib/api/manual-demo.ts`, `lib/manual-demo-validation.ts` (new).
- Microphone: `lib/security-headers.ts` and its tests,
  `lib/voice/browser-voice-provider.ts` and its tests,
  `e2e/microphone-policy.spec.ts` (new).
- Evidence/runbooks: this report, `manual_blofin_demo_acceptance.md`,
  `chrome_voice_diagnostics.md`.

## Short live acceptance after review and deployment

1. Review the PR and deploy disarmed. Verify real trading remains disabled and the
   selected existing demo account/owner pins and read/trade-only permissions match.
2. After an authorized acceptance window, load the manual form. Verify current
   minimum/lot, BTC conversion and notional; invalid `0.001` contracts or invalid
   geometry must refuse before submission. A valid small plan must not mention
   internal paper exposure, daily lock or green day strategy discipline.
3. Refresh and inspect the exact preview: side, contracts, BTC, executable range,
   stop, target, planned loss, expiry and hash. Obtain explicit confirmation for
   **one** demo order before clicking submit; no autonomous exchange submission.
4. Record durable command/client/venue order IDs, native fills and verified linked
   stop/target IDs. Compare BloFin demo UI with actual Journal fill/fee/protection
   facts. Acknowledgment alone is not success. Uncertainty requires recovery of the
   same plan; protection failure requires venue/operator action and read-only
   reconciliation. Do not clear a hold or erase history merely to pass acceptance.
5. In Chrome on the affected Mac, inspect the actual document header and effective
   policy in a top-level HTTPS tab, then test capture and recognition separately.
   Repeat on Mac Safari and iPhone Safari. If Chrome still reports `NotAllowedError`
   with a permissive document policy, record managed audio policies, profile and
   extension diagnostics as specified in `chrome_voice_diagnostics.md`.

Live exchange evidence, deployed headers, actual Mac Chrome recognition and Safari
regression acceptance are pending. Review → deploy → explicit one-order confirmation
is the next gate.
