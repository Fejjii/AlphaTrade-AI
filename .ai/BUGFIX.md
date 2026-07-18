# Workflow: BUGFIX

## Procedure
1. Reproduce: capture exact command, input, expected vs actual, and environment.
2. Write or identify a failing test that encodes the bug (behavior-level).
3. Find root cause; prefer the minimal, correct fix over a workaround.
4. Confirm the new test passes and no regressions appear.
5. Check safety-critical impact (risk/approval/exchange/data freshness).
6. Run full local validation; update docs/notes if needed.
7. Regenerate handoff docs; run sync.

## Rules
- No behavior change beyond the fix scope. No git mutations unless authorized.
- Never mask errors silently; fail clearly with meaningful messages.
