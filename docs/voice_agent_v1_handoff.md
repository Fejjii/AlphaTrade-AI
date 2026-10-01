# AlphaTrade Voice Agent V1

Status: REVIEW_REQUIRED · 2026-10-01 Europe/Berlin

- Branch: `codex/voice_agent_v1_001`
- Exact base: `94954e7d243be0c03ce667403964adb6e4e2b850`
- PR target: `codex/trader-interface-polish` (PR #157).

The existing `/agent` workspace supports start/stop/clear recording, permission
and transcription states, transcript review and send, optional Read Agent reply,
Stop speech, and cancellation on recording, conversation changes, page hiding,
kill-switch activation, or unmount. Cleared sessions ignore delayed callbacks.
Failed sends retain the transcript; voice preserves the independent typed draft.
The conversation displays the transcript and reply, including a fallback if the
post-turn history reload fails or times out.

Voice and text share `sendMessage` and `/agent/turns` with the same conversation,
symbol, timeframe, and strategy context. Journal, strategy, knowledge, Watcher,
trading, and risk requests follow the existing governed workflow. Speech never
calls proposal decisions, journal writes, Watcher, or order endpoints directly.
Existing Confirm/Reject buttons remain explicit. No backend authority, live
trading, active Strategies, dependency, or runtime configuration changes.

`frontend/src/lib/voice/types.ts` defines the transport-only `VoiceProvider`;
`createBrowserVoiceProvider` implements Web Speech and its prefixed API.
`AgentVoiceControls` accepts another provider factory without orchestration
changes. Browser speech uses no provider secrets; future authenticated providers
must keep credentials on the server. The UI discloses browser speech-service use.

Deadlines: permission 12s; recording 60s then finalize; transcription 8s; playback
120s; Agent turn plus history reload 45s. Permission denial, missing microphone,
unsupported/insecure input, unsupported output, network errors, and empty speech
have explicit states. Turn timeouts warn that processing may have completed and
ask users to check history before resending. There are no automatic retries.

Validation from `frontend/`:

- Focused Vitest: **38 passed**, 3 files. `npm run test -- src/lib/voice/browser-voice-provider.test.ts src/components/agent/AgentVoiceControls.test.tsx src/components/agent/AgentWorkspace.test.tsx`
- TypeScript and ESLint on all changed TypeScript files: **passed**, zero warnings.
- Voice Playwright: **6 passed**. `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npx playwright test --config playwright.voice.config.ts`
- Existing trader polish Playwright: **5 passed**. `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npx playwright test --config playwright.polish.config.ts`
- Desktop 1440×1000, phone 390×844, landscape 844×390: wrapping, no horizontal clipping, and 44px touch targets checked. [Six recording/speaking screenshots](screenshots/voice-agent/README.md).
- `git diff --check` and protected-path comparison against the exact base passed.

Browser checks use deterministic speech and frontend API fixtures, assert only
POST `/agent/turns` for voice sends, and do not contact live services. Real
microphone hardware, speech-service availability/accuracy, Safari, and physical
iOS remain unverified. Screenshots use fallback fonts because Google Fonts were
blocked. Backend/full frontend suites and production build were not run.

Next: review the draft PR relative to the trader interface base; verify physical
microphone and Safari behavior before release. No CI wait, deploy, merge, or live
trading was performed. This task is complete and stopped.
