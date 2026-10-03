# Final staging acceptance

Base: `8147caf9c9042c5bbc944e5911ea79d0bfbb1e7b`, branch
`codex/final_product_acceptance_001`, target `codex/release_consolidation_wave_003`.
PR189 was rebased from `c81175a6039b9861427accd6f468ab5e6ff931fb` without
conflicts. The acceptance commit replayed unchanged; the current release's
accepted PR186, PR187, PR188 and PR191 behavior is preserved. Changes are scripts,
tests and documentation. No deployment, Telegram connection or
execution authority is enabled by this package.

The original acceptance campaign below is historical evidence from baseline
`8673d8f69779ea516ca97456baea7b3064daf089`. Its full-suite counts and device/network
limitations are not a new validation claim for this head. Rebase validation is
recorded separately in the evidence file's `integration_rebase` field. GitHub CI
provides the normal full gate for the rebased PR.

Focused validation on the rebased branch: 27 acceptance-harness cases passed;
five existing PostgreSQL binding cases were skipped because local PostgreSQL is
unavailable (the normal GitHub backend job supplies it). All 37 affected
Chromium fixture cases and three local paper API workspace cases passed.
Frontend typecheck, focused ESLint, Python lint/format, shell syntax and diff
checks passed. The login page rendered without a framework error overlay.
No code-integration blocker was found; merge review still requires the normal
GitHub CI gate. No full-suite campaign, production build, staging run or physical
device check was repeated.

For this integration, keep all nine flags unchanged: `EXECUTION_MODE=paper`,
`ENABLE_REAL_TRADING=false`, `EXCHANGE_MODE=paper_internal`,
`TELEGRAM_ALERTS_ENABLED=false`, `TELEGRAM_INTERACTION_ENABLED=false`,
`AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false`,
`TELEGRAM_PAPER_ACTIVATION_ARMED=false`, `TELEGRAM_INBOUND_MODE=off`,
`TELEGRAM_NETWORK_PERMITTED=false`. The separate Telegram operator procedure is
outside this finishing task and is not a prerequisite for reviewing the MVP
with Telegram disabled.

## One staging-session checklist

- [ ] Confirm the accepted backend SHA and the frontend bundle pin from the
  **same deployment artifact**. Keep `ENABLE_REAL_TRADING=false`,
  `EXECUTION_MODE=paper`, `EXCHANGE_MODE=paper_internal`,
  `TELEGRAM_NETWORK_PERMITTED=false`. No exchange execution or credentials.
- [ ] Run the read-only API package below. All eleven components must pass;
  stop on a SHA mismatch, stale heartbeat, degraded provider, missing API,
  missing contract or HTTP error. Keep its JSON report with the release evidence.
- [ ] Run the automated browser/suite package. Check desktop, portrait and
  landscape: all eight workspaces, navigation, loading/error states and clipping;
  Voice recording/transcript/send/reply/playback/cancellation and typed draft.
- [ ] Review the Telegram preparation report, intended tenant/user, private
  enrollment, effective notification policy, outbox/retry/dead-letter state and
  kill switches. Preparation reports **BLOCKED** until binding is inspected;
  **OPERATOR_REVIEW_REQUIRED** is a prerequisite report, never permission to send.
- [ ] **Human: real iPhone microphone — NOT_TESTED.** Over HTTPS, deny permission
  then allow it, record/stop, review the transcript, send to Agent, verify reply,
  typed draft, conversation switch and page-hide cancellation. Record model,
  iOS/Safari version, release SHA and result.
- [ ] **Human: Safari recognition availability — NOT_TESTED.** Check actual
  `SpeechRecognition`/`webkitSpeechRecognition`. If absent, verify the unavailable
  message and working text composer; do not claim recognition PASS.
- [ ] **Human: Safari speech output — NOT_TESTED.** Listen to Read Agent reply,
  stop speech, interrupt with recording, switch conversations and hide the page.
- [ ] **Operator/human: real Telegram message — NOT_TESTED.** Perform the separate
  enrollment/projection procedure below in an isolated paper acceptance tenant,
  observe one expected informational message and matching durable outbox receipt,
  then roll back the Telegram flags. Do not claim PASS from fake transport.

Only the four physical checks above require human device observation. WebKit
binary installation and staging API access are infrastructure prerequisites,
not physical checks. Automated speech fixtures do not establish microphone,
Safari speech-service availability or audible output.

## Read-only API package

Install existing backend/frontend dependencies. Build the accepted frontend with
its actual deployment API origin, then capture its local Agent asset pin:

```bash
python3 scripts/final-product-acceptance.py \
  --capture-frontend-contract /tmp/frontend-contract.json

# Operator supplies these values; load the token securely into the environment.
export ACCEPTANCE_API_URL=https://staging-api.example.com
export ACCEPTANCE_FRONTEND_URL=https://staging.example.com
export ACCEPTANCE_EXPECTED_SHA=<full-accepted-40-character-sha>
# SMOKE_ACCESS_TOKEN: authenticated, verified intended staging trader/admin user.
python3 scripts/final-product-acceptance.py \
  --frontend-contract /tmp/frontend-contract.json \
  --output /tmp/final-product-api.json
```

Exit 0 means every check passed; exit 1 means a named component failed; exit 2
means inputs/transport cannot be used. This package issues **GET only**, refuses
redirects, HTTP outside loopback, credential-bearing URLs and Telegram origins.
It never registers users, sends Agent turns, submits signals, starts enrollment,
changes flags or calls execution. It reports disabled Telegram separately from
an untested real message. The asset pin must come from the deployed artifact,
not an independently rebuilt artifact with different public environment values.

Coverage: health/timestamp; exact deployment SHA and staging identity; paper
safety; Watcher worker heartbeat/lease/scan when armed (explicit disabled posture
otherwise); Agent capabilities/authority; Journal and Strategies reads; actual
LLM/embedding/vector provider readiness and Knowledge documents/chunks; Signals
and orchestration read interfaces; disarmed Telegram posture and authority;
pinned frontend Voice controls and backend contract-only Voice capability.
Empty historical lists are valid; failed lists are not translated into emptiness.
Provider status is configuration/read readiness, not a new inference benchmark.
An armed worker with a missing/stale row, any recorded stale row, or an unavailable
status store blocks acceptance. Disarmed entrypoints deliberately idle without
publishing rows: their absence is reported as disabled, never running. API
liveness alone is insufficient. No staging URL or session was supplied, so a
real staging API run remains pending.

## Automated reproduction

Use a **disposable local UTF-8 PostgreSQL database ending in `_test`**. Persistence
fixtures reset its public schema. Do not point them at staging or production.

```bash
export PHASE1_POSTGRES_URL=postgresql+psycopg://alphatrade:alphatrade@127.0.0.1:5432/alphatrade_test
export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
# Install Playwright WebKit into a writable location before the complete run.
export PLAYWRIGHT_BROWSERS_PATH=/tmp/alphatrade-browsers
cd frontend
npx playwright install webkit
cd ..
bash scripts/run-final-product-tests.sh
```

The runner forces paper/disarmed flags and removes real Telegram configuration
from its child process. Backend tests reject real HTTP transports; TestClient,
MockTransport and fake Telegram transports remain available. Skips fail the run.
Frontend-only fixtures and local mock API tests are explicitly separate from
actual staging/device evidence. The Chromium mobile config reruns existing
phone specs with Chromium; it is not WebKit or physical Safari validation.

For an isolated offline font/build check only, set
`NEXT_FONT_GOOGLE_MOCKED_RESPONSES` to the absolute path of
`frontend/test-fixtures/offline-fonts.cjs`. This verifies compilation with local
fallback fonts; it does not verify real font delivery and must not be used in a
deployment. The normal build uses the repository's existing real font setup.

## Telegram: separate operator action

While networking is disabled, print the exact prerequisites without starting a
worker or changing configuration:

```bash
# Set the current safe flags exactly as shown in the checklist/report.
python3 scripts/telegram-staging-readiness.py
# From backend dependencies; secrets are configured, never printed:
PYTHONPATH=backend/src backend/.venv/bin/python scripts/telegram-staging-readiness.py --check-binding
```

`--check-binding` requires `DATABASE_URL`, `TELEGRAM_BOT_ID`, `TELEGRAM_CHAT_ID`,
`ACCEPTANCE_ORGANIZATION_ID` and `ACCEPTANCE_USER_ID`. It reads migrated PostgreSQL
using SELECT, requires exactly one non-revoked VERIFIED private binding scoped
to that tenant/user, and refuses a binding allowing CLOSE. A chat ID alone is
never enrollment. Numeric bot ID must match the secret token's numeric prefix.
Neither script contacts `api.telegram.org`.

The JSON contains the full `operator_enrollment_environment` and
`operator_projection_environment` maps derived from the existing controlled
activation interfaces. Review the deployment's existing Settings validation too;
the maps do not replace JWT/provider/database/Redis requirements.

1. **Operator only, after the offline report/tests:** configure the enrollment
   profile atomically on the existing staging Telegram process:
   `ENVIRONMENT=staging`, paper flags unchanged, public read-only
   `PERPETUAL_EVIDENCE_SOURCE=binance_usdm`, matching numeric bot ID/secret token,
   `TELEGRAM_INTERACTION_ENABLED=true`, `TELEGRAM_INBOUND_MODE=polling`,
   `TELEGRAM_NETWORK_PERMITTED=true`, `TELEGRAM_PAPER_ACTIVATION_ARMED=false`.
   Keep legacy `TELEGRAM_ALERTS_ENABLED=false`,
   `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false`, and `TELEGRAM_WEBHOOK_SECRET` empty.
   This is the first network step; preparation never performs it. Production
   and staging webhooks are not supported activation profiles.
2. As the intended authenticated staging user, call
   `POST /telegram-paper/enrollment/start` through the existing API. Treat its
   single-use token as secret. Before expiry, send `/start <token>` in the bot's
   **private** Telegram chat. Existing polling completes enrollment; group,
   wrong-user, expired and replay-conflicting challenges must fail. The API and
   Telegram process must share migrated PostgreSQL and the accepted release SHA.
3. Confirm the stored binding scope/private/VERIFIED/non-revoked state. If using
   the preparation script to inspect it, first restore disabled Telegram flags
   for that inspection; the script refuses preparation with networking enabled.
   Review `telegram_enabled=true`, effective Policy V2 subscriptions, event
   toggles, quality/severity, cooldown and quiet hours. There is no independent
   Policy V2 `enabled` property. Use an existing informational event, not an order.
4. Review the isolated tenant's outbox before projection: no unexpected pending
   backlog, retries or dead letters. Require global/tenant kill switches inactive
   for projection. Operator may then configure the projection map: exact bound
   chat, `WATCHER_ORCHESTRATION_ENABLED=true`,
   `WATCHER_PAPER_STAGING_ACTIVATION=true`,
   `TELEGRAM_PAPER_ACTIVATION_ARMED=true`; keep legacy Watcher/bridge/auto-tick and
   legacy Telegram delivery off. This retains the existing governed paper arm;
   the automation does not grant it. Existing workers handle delivery/polling.
5. Observe one expected informational message and its durable sent receipt.
   Confirm replay/deduplication and that no bare `I confirm` can authorize any
   operation. Paper mutations still require the issued exact confirmation
   identity and the existing Risk/kill-switch/tenant/revision gates.
6. Restore `TELEGRAM_NETWORK_PERMITTED=false`, interaction/arm false, inbound off;
   leave tokens and durable audit/outbox/cursor/ledger records in their approved
   secret/storage locations. Use `scripts/telegram-paper-activation-rollback.sh`
   for the existing printed rollback plan. It does not apply a deployment change.

## Preparation evidence and blockers

Recorded results are in `docs/evidence/final_product_acceptance_001.json`.
Staging API/session and physical results are not inferred from local mocks.
WebKit download was denied by the managed network policy (`Domain forbidden` for
the Playwright download hosts); installing it requires an environment with the
appropriate supported download access. All available Chromium cases are run.
The original complete acceptance verdict was **BLOCKED** by those prerequisites.
Device/message checks remain **NOT_TESTED** until observed. They do not establish
a code-integration blocker for this rebased, disarmed MVP. The supplied current
release evidence reports successful real BTCUSDT Watcher scans with
`reason_code=watch`, zero Candidates when conditions do not qualify, API health
200 and stable bounded worker memory. This task preserves that behavior and does
not repeat the staging campaign or claim new physical-device acceptance.
