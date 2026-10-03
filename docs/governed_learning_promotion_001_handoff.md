# Governed learning and strategy promotion 001

Branch: `codex/governed_learning_promotion_001`

Exact base: `5f4f0a467ce8f68f9c7a82d3b32307d559a9f092` (`codex/release_consolidation_wave_002`).

No migration. Canonical storage already represents this lifecycle: `StrategyConversationProposal.context_refs`, immutable `UserStrategyVersion` rows with `parent_version_id`, `StrategyVersionConversationLink`, existing replay/backtest and paper run records, and append-only `StrategyLifecycleEvent.evidence_snapshot`. The Alembic release head is unchanged.

## Authorities and flow

`StrategyProposalService.create_governed` captures scoped source observations, hypothesis, reason, evidence IDs, exact affected strategy/base version, proposed card/rules/parameters, sample limitations, validation plan, creator and creation time. It captures existing discussion context (journal, lessons and learning attribution), Strategy Analytics, and optional Daily Review. Knowledge/research documents and Agent observation messages remain references, not approval or verified facts.

A typed validation request materializes an immutable candidate through `StrategyVersioningService`. It preserves the selected version and clears inherited validation badges. Conversation confirmation cannot confirm a governed proposal. Legacy conversation confirmation also preserves an approved/active selected parent while storing its new draft. Generic compiled approval cannot approve a governed candidate.

Create baseline and candidate runs using existing Strategy Replay and BacktestService workers. Both runs must name the proposal's exact versions and use identical input/dataset hashes, assumptions, risk limits, engine and training/evaluation windows. Comparison verifies stored config/result hashes and exact report/version identities. Differences in out-of-sample net PnL are descriptive; they do not establish a performance improvement claim.

Paper validation is a separate existing `PaperValidationRun` and closed `PaperTrade` cohort. An explicit candidate version can obtain evaluation policy only for its recorded isolated paper run; it cannot become a Watcher target. Existing canonical setup, risk and paper bot authorities continue to evaluate it. Paper completion must be PASSED with an end time, AUTO_PAPER mode, no blockers, and closed-trade count/net PnL reconciled to the stored metrics. Replay never substitutes for paper evidence.

`StrategyPromotionService` extends the existing `strategy_promotion.py` module. This exact base previously had the promotion evaluator but no class with that name. Human approval binds the proposal hash, immutable candidate, comparison hash and exact paper run. It activates the already validated immutable version through existing version/lifecycle authorities, records the human actor and evidence snapshot, and retains the prior version as the rollback relationship. Duplicate approval returns its original receipt and cannot reactivate after rollback.

`ACTIVE` means paper strategy selection here. Neither promotion nor rollback grants live execution permission or changes trading, Watcher or delivery enablement.

## API handoff

1. `POST /governed-learning/strategies/{strategy_id}/proposals` with `GovernedProposalCreate`.
2. `POST /governed-learning/proposals/{proposal_id}/validation-request` with `expected_content_hash`.
3. Queue baseline/candidate `POST /backtests/replays` runs with exact version IDs and identical inputs; let the existing worker complete them.
4. `PUT /governed-learning/proposals/{proposal_id}/validation-evidence` with the proposal hash and baseline/proposed run IDs.
5. `POST /strategies/{strategy_id}/paper-validation/start` with the exact candidate `strategy_version_id`, `runtime_mode: "auto_paper"`, and paper configuration. Run the existing paper scan/tick workflow.
6. Attach the completed `paper_validation_run_id` through validation-evidence.
7. Read `GET /governed-learning/proposals/{proposal_id}`. Approve through `POST /governed-learning/proposals/{proposal_id}/approve-paper-promotion` with `confirm: "APPROVE_PAPER_PROMOTION"`, `expected_content_hash`, `expected_version_id`, `expected_comparison_hash`, and `expected_paper_validation_run_id`.
8. Roll back through `POST /governed-learning/strategies/{strategy_id}/rollback-paper` with `confirm: "ROLLBACK_PAPER_STRATEGY"`, exact active/target version IDs and a reason.

Mutations require persisted OWNER/TRADER membership. Status reads permit authorized readers, retain organization/user scope, and return at most 20 proposals per page with a bounded offset. Agent `strategy.learning_status` reads at most 10 (five by default), exposes canonical structured status and deterministic prose, and has no promotion/rollback mutation tool. All seven lifecycle questions are covered.

## Evidence limits

Optional `StrategyCard.promotion_requirements` stores authored `minimum_replay_trades` and `minimum_paper_trades`. Promotion applies the immutable base strategy's requirements, preventing a candidate from lowering its own gates. Candidate paper runtime honors an authored paper sample requirement. Existing legacy runtime safety gates remain in effect.

No new universal statistical sample threshold is introduced. Missing authored requirements remain explicitly insufficient evidence and require a recorded `evidence_review` in human approval. Limited samples and an unchanged or worse observed baseline also require review. A single replay trade or single paper trade cannot establish promotion, including with review text.

This lifecycle accepts the existing exact Strategy Replay comparison authority. Its source implementation supports Nested Continuation versions. Wave 003 also integrates SFP structural replay through that same authority; SFP returns remain unavailable and explicitly block trade promotion. Unsupported strategies/configurations fail closed; this change does not add a second strategy engine or reinterpret legacy backtest recommendations as human approval.

## Validation

The new regression suite covers unauthorized promotion, missing replay, insufficient evidence, baseline/version/window mismatch, missing or mismatched paper validation, explicit approval, immutable version creation, rollback relationship, duplicate approval before/after rollback, tenant and user isolation, live enablement refusal, authored requirements, evidence identity/tampering, failed-candidate atomicity, bounded Agent reads and read-side autoflush prevention, real journal/knowledge/analytics/Daily Review capture, and legacy conversation selection preservation.

Validation passed: the full backend run completed with 3,329 passes and 297 environment-dependent skips; the final impacted paper/Watcher/replay run passed 130 tests, and the final strategy/conversation/Agent run passed 109 tests (including all 22 governed lifecycle cases). Ruff lint/format and focused strict type checks also passed. PostgreSQL-only tests require their existing opt-in database environment variables and were not enabled here. No deployment, live enablement or merge is part of this handoff.
