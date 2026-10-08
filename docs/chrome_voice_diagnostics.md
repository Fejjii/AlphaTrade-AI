# Chrome voice diagnostic repair

## Evidence and scope

On 8 October 2026 the user verified recording on iPhone Safari and on Safari on
the affected Mac. Chrome on that Mac failed despite enabled Chrome site and macOS
microphone permissions. Both speech recognition and basic capture were reported
to fail with permission errors; capture reports `NotAllowedError`. The affected device is inaccessible
from this cloud task; actual post-deployment Chrome/macOS acceptance remains pending.

A demonstrated application cause is the global Next.js response header
`Permissions-Policy: camera=(), microphone=(), geolocation=()`, defined in
`frontend/src/lib/security-headers.ts` and applied to every path by
`frontend/next.config.ts`. Chrome enforces this document policy independently of
site/macOS permission toggles. It is changed to `microphone=(self)`. Camera and
geolocation remain denied, and CSP `frame-ancestors` plus `X-Frame-Options` still
refuse embedding. `frontend/vercel.json` defines no separate policy override.

The provider now checks `document.permissionsPolicy` or Chrome
`document.featurePolicy` before starting capture/recognition. A detected denial
explains the deployed header/iframe issue and directs the user to open the app in
a top-level HTTPS tab. Browsers without either API use the existing capture path.

Two real Chromium tests against the running Next.js app passed with a synthetic
microphone: the actual repaired response permits capture and every track ends; a
control document with the former header produces `NotAllowedError` despite the
allowed device. This isolates the application policy cause; it does not verify the
affected Mac's microphone, Chrome speech service, Safari, or current deployment.
The deployed-header fetch was blocked by automatic approval review because the
Vercel tool may create a temporary authentication-bypass link and follow redirects.
No bypass was created, and current deployment headers remain unverified.

The previous provider conflated `not-allowed` and `service-not-allowed` and claimed
microphone denial. Recognition rejection alone does not establish capture denial.
The repair retains allowlisted browser error codes and safe synchronous DOMException
names, separates service rejection,
network, unavailable audio capture and unsupported language, and offers an explicit
local microphone capture check after failure. Recognition `not-allowed` remains an
ambiguous access failure; only a separate capture result establishes whether capture
works. Raw browser messages and unknown error strings are discarded.

## Behavior and lifecycle

Recognition still starts synchronously inside the recording button click, using
standard or prefixed SpeechRecognition, `navigator.language` (fallback `en-US`),
continuous recognition and interim results. There is no Chrome-specific block, new
transcription service, automatic retry, or language substitution. A rejected language
produces guidance to review browser language settings. Changing browser/site settings
can require a page reload; retry is explicit and creates a fresh recognition instance.

The separate **Check microphone capture** button calls `getUserMedia({audio: true,
video: false})` directly from its click, stops every returned track immediately, and
records/uploads no audio. It does not call recognition or send a transcript. The
12-second bounded wait cannot dismiss a browser permission prompt; users can dismiss
it themselves. Late capture resolutions after timeout, cancellation or disposal still
stop all tracks and cannot update the UI. Clear, hidden-page, conversation-change,
disabled-control and unmount paths cancel the diagnostic as well as recognition.
Normal recognition may send audio to the browser's speech service as before.

Final transcripts remain visible for review and require explicit **Send transcript**.
Partial/canceled/failed recognition never sends. A synchronous send lock additionally
prevents two clicks before React updates from creating duplicate sends.

## Focused automated verification

Run from `frontend/`:

```sh
npm run test -- src/lib/voice/browser-voice-provider.test.ts src/components/agent/AgentVoiceControls.test.tsx
npx eslint src/lib/voice/types.ts src/lib/voice/browser-voice-provider.ts src/lib/voice/browser-voice-provider.test.ts src/components/agent/AgentVoiceControls.tsx src/components/agent/AgentVoiceControls.test.tsx
npm run typecheck
```

The original PR227 voice suite contained 49 mocked cases. This repair adds policy
refusal coverage and a separate real Chromium policy/capture test. The complete
focused form/header/voice selection passed 74 unit tests; scoped ESLint and frontend
TypeScript checks passed. The two Chromium policy checks passed. No full backend
CI was dispatched.

Run the browser checks against a local Next.js server (no backend or exchange
submission is needed):

```sh
PLAYWRIGHT_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
npx playwright test e2e/microphone-policy.spec.ts --project=chromium --workers=1
```

Set the executable path only when using a system Chromium; otherwise use the
Playwright-installed browser. The device is synthetic, and speech recognition is
not exercised by these browser checks.

Tests mock recognition, synthesis, capture and React interactions. They cover safe
error classification, fresh-session recovery, final transcription, prefixed API,
insecure/unsupported recognition, timeout, cancellation and late callbacks, immediate
track cleanup and delayed capture after cancel/dispose/timeout, transcript review and
duplicate sends. They cannot verify Chrome's actual speech service, network policy,
operating-system permissions, selected input device or Safari recognition behavior.

## Required real-device acceptance after review and deployment

1. After deployment, open the deployed Agent page directly over HTTPS in Chrome.
   In DevTools Network, reload and inspect the **document** response (not the API).
   Require one effective `Permissions-Policy` with `microphone=(self)` and no
   additional denying header. In Console, record `window.isSecureContext`,
   `window.top === window.self`, and
   `(document.permissionsPolicy ?? document.featurePolicy)?.allowsFeature("microphone")`.
   An iframe/parent policy can further restrict the document and cannot be repaired
   by site permission toggles. Then record
   Chrome/macOS versions, page origin, browser language, selected microphone and whether
   the profile is managed (`chrome://management`). Record only non-sensitive metadata.
2. Click **Start recording**, say “Review my strategy risk”, then **Stop recording**.
   If it fails, record the complete safe displayed message and **Browser code**, without
   transcripts containing private information. Confirm failure never submits a message.
3. Click **Check microphone capture**. Record its result and safe browser code, if any.
   Verify the microphone indicator stops immediately on completion. The diagnostic must
   produce no audio upload and no Agent request; inspect Network if necessary.
4. If capture passes but recognition fails, report those two independent results. For
   `service-not-allowed`, inspect browser policy (`chrome://policy`) and service
   availability. For `network`, compare with VPN/network policy using only an authorized
   network. For `language-not-supported`, record the configured language. Do not infer a
   root cause merely from these possibilities. For `not-allowed`, inspect both capture
   permissions/policy and speech-service restrictions. For capture denial/device errors,
   confirm the effective document policy first. If it allows capture in a top-level
   secure document but `NotAllowedError` persists, inspect `chrome://policy` for
   `AudioCaptureAllowed` and `AudioCaptureAllowedUrls`, and `chrome://management`.
   Record the actual policy values and origins, then compare a clean Chrome profile
   with extensions disabled and the same selected microphone. These are remaining
   diagnostics, not a claim that external policy is the cause.
5. Retry by clicking **Start recording** again after addressing the observed cause
   (reload if browser settings require it). Verify final text appears only for review,
   **Send transcript** sends once, and repeated clicks do not send duplicates. Use a
   harmless analysis message; do not request or confirm exchange orders.
6. Record then **Clear voice**; record then switch conversations or hide the tab. Verify
   no late transcript appears or sends, and the microphone indicator stops. Start a
   capture check and clear or navigate away before resolving its prompt; dismiss the
   prompt if needed and confirm any late-opened capture immediately closes.
7. Repeat recording, stopping, review, explicit Send and Clear on the same Mac's Safari
   and iPhone Safari. Verify the existing working behavior and read-reply playback.

Acceptance is pending until these real-device outcomes are recorded. A passing local
capture check proves only capture access for that request, not speech recognition.
