# AlphaTrade AI Codex operating contract

Use the repository as the implementation source of truth. Applicable safety and workflow policies in .ai/MASTER_WORKFLOW.md and .ai/RELEASE.md take precedence over this document. Consult .ai/DECISIONS.md and .ai/TASKS.md when task requirements need context. For current PR237 integrations, also consult docs/reviewer_wave/voice_activity_integration.md, docs/voice_conversation_foundation.md and docs/blofin_native_activity.md only when relevant.

## Autonomous decisions and clarification policy

Work in implementation/default mode for agreed coding tasks, not open ended planning interviews. The owner has delegated routine technical choices inside the assigned task scope. Before asking a question, inspect the repository, relevant decisions, tests, contracts and the task handoff. Choose the most compatible, minimal, reversible implementation that preserves existing behavior, risk controls, exact identities, data provenance and cost limits. Record important assumptions and the chosen rationale in the PR handoff. Do not ask the owner to pick libraries, test commands, filenames, component layouts, code organization, minor interface choices, or routine repair approaches when the repository and approved acceptance criteria suffice.

If several safe approaches remain, choose one, implement, test, and continue. If optional credentials, hosted access or external providers are missing, complete independent offline work with truthful test limitations and record the external blocker; do not repeatedly ask for access or retry rejected access. Do not claim an unknown external state succeeded. Avoid repeated question loops or asking the owner to resend facts already recorded.

Only escalate a decision that changes approved product intent, expands execution authority or risk, requires an unauthorized paid service, changes credentials or access controls, activates exchange actions or real trading, mutates external accounts, changes production/deployment or main merge authorization, performs an irreversible migration, or cannot be resolved without a materially unsafe guess. Continue all independent authorized work while the blocked operation remains paused. Do not bypass a denied permission, override an approval control, impersonate ChatGPT/owner assent, or assume access to secrets.

## Delivery and cost

Respect current branch and file ownership, at most three independent coding builders, immutable migration ancestry, generated API contracts and explicit release gates. Preserve current operator watcher, Telegram and kill switch settings. Use focused local tests and batched commits, with GitHub Actions complete backend acceptance only once at the final reviewed release gate. Never treat skipped checks as passing evidence. Do not merge to main, deploy, enable paid services or place/cancel BloFin orders without their separate authorizations.

Complete the full assigned bounded task without routine confirmation checkpoints. Handoff with exact branch/SHA, implemented behavior, affected files, focused test results and skips, remaining blockers, and next dependency. If a genuine escalation is unavoidable, ask one precise question with the recommended option and why other independent work can or cannot continue.
