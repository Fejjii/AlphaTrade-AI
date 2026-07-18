# Workflow: LINKEDIN / DEMO packaging

Portfolio and demo packaging only — no product features, no behavior change.

## Sources of truth (already in repo)
- `docs/portfolio_positioning.md`, `docs/demo_script.md`, `docs/interview_package.md`,
  `docs/interview_pitch.md`, `docs/cv_project_entry.md`, `docs/linkedin_project_post.md`,
  `docs/technical_qa.md`, `docs/screenshots_checklist.md`.

## Messaging guardrails
- Emphasize: human-in-the-loop, deterministic risk engine, explicit approvals, paper-only,
  provider fallbacks, evaluation harness, observability, multi-tenant auth.
- Never claim guaranteed returns, autonomous profitability, or live trading capability.
- No secrets, no private URLs beyond the public staging demo.

## Demo flow (5–8 min)
Dashboard → Strategy Lab → Paper Validation → Alerts & Lessons → Risk Settings →
AI Workspace (safe prompts + refusal of real trading). See `docs/demo_script.md`.
