# Independent acceptance review — intelligence stack through PR114

**Reviewer:** Cursor Cloud Agent (Grok 4.6 Extra High), independent of PR114 authors  
**Mode:** Review only. No product-code changes. No merge. No deploy. Watcher, Telegram, and live trading not activated.  
**Source of truth:** repository code at exact HEAD `4c417c19639e501cf6512da1672f9fca43390c13`  
**PR under review:** [#114](https://github.com/Fejjii/AlphaTrade-AI/pull/114) (`cursor/intelligence_final_p1_remediation-d0c8`)  
**This review branch:** `cursor/intelligence_final_acceptance_review-c7b3`  
**Generated at UTC:** 2026-09-21T12:10:00Z  

PR summaries and prior reviewer conclusions were treated as claims, not evidence.

---

## FINAL VERDICT

**REMEDIATION REQUIRED**

The conversation → compile → approve → canonical evidence → SetupAssessment ladder exists and is mostly fail-closed. Three of the four last P1 remediations are closed on the product path. **Previous P1 3 (paper automation authority) remains OPEN:** after an approved compiled policy exists, paper-bot `scan` discards that policy object and can still mint `AUTO_PAPER` trades from `PaperBotEngine` + `structured_rules_to_parsed` (including invented stop/TP defaults). That is still a second trade-minting authority.

The architecture is **not** safe to start the separate Watcher paper-monitoring phase until that dual authority is closed and setup-lifetime pins are durable.

---

## Exact HEAD and CI

| Item | Evidence |
| --- | --- |
| Requested BASE | `4c417c19639e501cf6512da1672f9fca43390c13` |
| PR114 HEAD | identical |
| Tip commit | `fix(intelligence): type paper-bot setup_type and fence Postgres minting` |
| GitHub CI run [35588348865](https://github.com/Fejjii/AlphaTrade-AI/actions/runs/35588348865) | `conclusion=success`, `headSha=4c417c1` |
| backend | SUCCESS — `2363 passed, 236 warnings in 1610.64s` |
| frontend | SUCCESS — lint, typecheck, **1168** vitest passed, build |
| evaluation | SUCCESS — agent 16/16, RAG 5/5, guardrails 7/7 |
| e2e-smoke | SUCCESS — Chromium `26 passed`, `13 skipped` (staging specs skip without demo password) |
| docker-build | SUCCESS |
| deployment-safety | SUCCESS |
| Vercel | SUCCESS (preview only; not a product safety gate) |

Local corroboration (this review, not a full-suite rerun): targeted pytest on P1/safety/conversation/evidence/fusion files, **exit 0**. Independent probe: replay `FirstSliceEvidenceAssembler` + `fusion_policy()` evaluates to `SetupAssessmentState.WATCH`, not `CONFIRMED_SETUP`.

Alembic: single head `b7c8d9e0f1a2` (`test_alembic_single_head` passed locally). CI Postgres suite includes upgrade/downgrade coverage.

---

## Previously open P1s

### P1 1 — Setup expiry — **CLOSED**

**Claim to prove:** the real product evidence path preserves original setup lifetime and expires after the configured subsequent final bars. No test-only `setup_trigger_end` patch may be required.

**Product path**

`FirstSliceEvidenceAssembler.assemble` still *accepts* `setup_trigger_end`, but when the caller omits it (product Watcher/evidence callers do), it reads `SetupLifetimeStore.active_trigger_end` and later `remember`s the original trigger:

```110:155:backend/src/app/evidence_pipeline/assembler.py
        pin = setup_trigger_end
        if pin is None:
            pin = self._lifetime.active_trigger_end(lifetime_key)
        ...
        trigger, subsequent, series_15m = _trigger_and_subsequent(
            series_15m,
            identity=trigger_identity,
            evaluated_at=clock,
            setup_trigger_end=pin,
        )
```

Expiry uses `FIRST_SLICE_EXPIRY_BARS` (2). Subsequent final 15m bars are counted separately from quote freshness, stream freshness, and closed-evidence validity. The store is keyed by organization + symbol + strategy version.

`CanonicalEvidenceService` reuses one assembler instance, so the HTTP evidence path shares the in-process pin.

**Tests (product-shaped, not pin-patched)**

- `test_product_assembly_expires_after_configured_final_bars_without_patching_pin` — two `assemble()` calls on a shared `SetupLifetimeStore`; later source has `FIRST_SLICE_EXPIRY_BARS` extra final 15m bars; trigger identity is preserved; `setup_expired is True`.
- `test_subsequent_closed_bars_expire_setup_on_their_own_clock` — same product assembler path; wall-clock-only later evaluation does **not** expire (`subsequent_final_15m_count == 0` when no extra bars).

**Not closed by this P1 (new findings below):** pins are process-local RAM; they do not survive restart. That does not reopen P1 1 as specified (in-process product path without caller pins works).

---

### P1 2 — Chat confirmation identity — **CLOSED**

**Claim to prove:** bare confirmation binds the exact proposal shown. Newer / changed / superseded / cross-tenant / stale proposals must not be authorized by bare confirmation. Server pending-draft lookup must not substitute for presented identity.

**Product chat path**

`strategy_workflow` confirm does **not** use `latest_draft()` as the authorization target. It parses the last assistant-presented identity from transcript history, requires `confirmation_authorizes_mutation`, matches caller conversation/org/user, and passes those exact fields into `strategy_proposal_tool`:

```1178:1236:backend/src/app/agents/nodes.py
        presented = presented_confirmation_identity_from_history(agent.conversation_history)
        named_id = confirmed_proposal_id(agent.message) if authorized_confirm else None
        ...
        elif agent.conversation_id is None or proposal_id is None or presented is None:
            answer_lines.append(
                "Confirm the proposal that was presented. Bare confirmation cannot "
                "authorize whichever draft is currently pending."
            )
```

The tool refuses confirm without a 64-char hash and expected org/user/conversation (`backend/src/app/tools/registry.py`). `StrategyProposalService.confirm` re-checks hash, parent, target, org, user, conversation against the row; superseded/rejected fail closed; concurrent confirm converges (idempotent CONFIRMED or IntegrityError → winner).

Quoted / retrieved / fenced `I confirm` is rejected by `confirmation_authorizes_mutation`.

HTTP `POST /conversations/{id}/proposals/{proposal_id}/confirm` requires the same expected identity fields; mismatch is 409 before service lookup of “whatever is pending.”

`latest_draft()` is still loaded in `AgentService.run` to set `pending_proposal_id` for **re-presenting** identity on later assistant messages. It is not the confirm target. That is a presentation side-effect, not an authorization substitute (P2 below).

**Tests**

- `test_bare_confirm_without_presented_identity_fails_closed` — discussion-only thread, then chat `I confirm`, no new version.
- `test_superseded_presented_identity_cannot_confirm_stale_draft` / `test_chat_structure_request_supersedes_open_draft_identity`.
- `test_http_preview_presents_confirmation_identity`.
- Quoted confirm 422 in the integration fixture.
- Postgres `test_postgres_concurrent_confirmation_converges_to_one_version` (CI; this environment did not rerun Postgres).

Frontend Confirm button sends the identity **displayed on the proposal card**, which `loadThread` fills from `listProposals` (open `draft`). That is explicit HTTP identity, not bare chat confirm. Residual card-vs-transcript divergence is P2, not a reopen of the chat P1.

---

### P1 3 — Paper automation authority — **OPEN**

**Claim to prove:** automated paper `scan` cannot create a trade without approved strategy version, executable compiled definition, and matching canonical lineage. DRAFT, REVIEW_REQUIRED, incomplete, unsupported, and generic invented rules must fail closed. `POST /strategies/evaluate` is research-only.

**What is actually closed**

`_approved_compiled_lineage` calls `resolve_executable_strategy_policy`, which requires tenant match, lifecycle `APPROVED` or `ACTIVE`, executable `CompiledSetupDefinition`, and a recompile hash match. Failure → `lineage is None` → `PaperSignalStatus.NOT_TESTABLE` and `trade_created` cannot become true.

DEFAULT_SETUP / UNSUPPORTED / non-machine-readable compatibility rules also set `NOT_TESTABLE`. Tick only monitors already-open paper trades.

Proven tests:

- `test_paper_bot_scan_without_approved_lineage_creates_no_trade`
- `test_auto_paper_mode_can_create_trade` (name is stale; body asserts `trade_created is False` and `not_testable`)
- Integration fixture: confirm does not yield executable policy; compile without approve still raises `strategy_not_approved`; incomplete/unsupported cannot resolve executable policy.

`POST /strategies/evaluate` calls `StrategyService.evaluate` → in-process module `evaluate(data)` with no session, no compile, no Candidate, no paper trade. Response flags `research_only=true` / `mutates_strategy_authority=false` are schema defaults, but the implementation is genuinely research-only.

**Why P1 3 stays OPEN**

Once `resolve_executable_strategy_policy` succeeds, the returned `ExecutableStrategyPolicy` is **discarded**. Scan does not call `evaluate_canonical_strategy`. It runs a second engine:

```262:306:backend/src/app/services/paper_validation_runtime_service.py
        if lineage is None:
            signal_status = PaperSignalStatus.NOT_TESTABLE
            ...
        else:
            resolved = resolve_backtest_rules(ctx.card, ctx.setup_type, ctx.structured)
            rules = resolved.rules
            ...
                evaluation = self._engine.evaluate_entry(
                    rules, candle_rows, engine_source=engine_source
                )
```

`structured_rules_to_parsed` always sets `machine_readable=True` when entry rules exist and **invents** defaults (`stop_pct = Decimal("0.02")`, TP 1/2/3R) when those exits are absent. That is generic invented sizing/stop logic on the AUTO_PAPER mint path.

There is **no** test that an approved compiled version still cannot mint `AUTO_PAPER` from this parallel engine, and **no** test that a paper trade is produced from SetupAssessment / compiled AST. `lineage is not None` is a permission bit, not lineage-matched evaluation.

Watcher paper monitoring cannot treat compiled policy as the sole paper authority while this path remains.

---

### P1 4 — Candidate authority — **CLOSED**

**Claim to prove:** in-memory and injected Watcher policies cannot mint Candidates. Persistence requires persisted approved compiled authority.

**Product gates**

- `WatcherCanonicalScanEvidence.policy_authority` defaults to `in_memory_test_helper`.
- `InMemoryWatcherScanEvidence.bind` raises if the snapshot claims `persisted_approved_compiled`.
- `AssemblingWatcherScanEvidence`: injected `executable_resolver` is always `IN_MEMORY_TEST_HELPER`; session+store resolution is the only path labeled persisted, and it goes through `resolve_executable_strategy_policy`.
- Read-projection placeholder IDs cannot become scan evidence or Candidates.
- `_maybe_create_candidate` raises `CandidateCreationAuthorityError` unless authority is `PERSISTED_APPROVED_COMPILED`.
- `evaluate()` never inserts Candidates; `PERSIST_AND_NOTIFY` is blocked (`notify_disabled`).
- Watcher orchestrator default `enabled=False`; composition comment: not wired into the live worker. Settings defaults and staging/production deployment_safety reject Watcher/Telegram flags.

**Tests that actually bite**

- `test_in_memory_scan_evidence_cannot_claim_persisted_authority`
- Fusion wiring `_assert_in_memory_cannot_mint` on `make_world()` which **is** `CONFIRMED_SETUP` — worker persist fails with `candidate_creation_failed` and uniqueness is empty.
- Injected resolver snapshots are `IN_MEMORY_TEST_HELPER`.

**Test-quality caveat (does not reopen the code gate):**  
`test_persisted_watcher_path_uses_canonical_resolver` persist assertions are **vacuous on the replay product path**. Independent probe at this HEAD: replay assembly + `fusion_policy()` → state `WATCH`, failed pattern rules include `bearish_cvd_divergence` / `aggressive_sell_imbalance`. The test therefore takes the `else: assert persist.candidate_ids == ()` branch for both persisted and injected ports. Empty candidates would happen for WATCH regardless of authority.

Postgres fencing uses `_LiteralPersistedScanEvidence`, an explicit **test helper** that sets the persisted flag on `make_world()` in-memory policy so steal-during-persist can reach the repository fence. That proves fencing, not that mint-time re-resolves a DB compiled row.

Mint-time still trusts the enum rather than calling `resolve_executable_strategy_policy` again (P2).

---

## Architecture walk (conversation → Candidate)

| Stage | Product path | Fail-closed notes |
| --- | --- | --- |
| Conversation | `ConversationService`; chat `/chat/message` | Discussion does not write versions |
| Preview | `create_draft_from_text`; supersedes other open drafts | `is_preview=True`, `mutates_strategy_authority=False` |
| Explicit confirmation | Presented identity → `confirm` → `fork_semantic_update` | Creates **DRAFT** version; does not compile or approve |
| Immutable draft | Version row + content hash | Semantic immutability triggers exist (Alembic) |
| Explicit compile/review | `POST .../compile` → `REVIEW_REQUIRED` when persisted executable | Incomplete/unsupported → `NON_EXECUTABLE` |
| Explicit approval | `POST .../approve` with `I confirm` | Requires executable compiled row; confirm token required |
| Persisted executable policy | `resolve_executable_strategy_policy` | DRAFT / REVIEW_REQUIRED / hash mismatch fail |
| Canonical market evidence | `FirstSliceEvidenceAssembler` | USD-M perpetual; no spot fallback; no fallback_used |
| Deterministic SetupAssessment | `evaluate_canonical_strategy` → `evaluate_setup` | Account context ignored; CVD/flow/coverage payloads must match consumed hashes |
| Candidate boundary | `persist_confirmed_setup` only | Needs CONFIRMED_SETUP + PERSIST_EVIDENCE + persisted authority; Watcher unwired |

This ladder is real on HTTP + services. Paper-bot `scan` is a **bypass around SetupAssessment** after the lineage gate (P1 3 OPEN).

E2E `strategy-conversation.spec.ts` exercises preview → confirm → compile → approve on the Strategy Lab panel (Chromium project; included in `npm run test:e2e`). CI logged 26 passed / 13 skipped without per-test names in the compact summary; those two tests are not marked skip.

---

## VERIFY ALSO

### Tenant isolation — pass (with noted test looseness)

- `resolve_executable_strategy_policy` / `assert_tenant_version` / compiled org check.
- Confirm identity includes `organization_id` / `user_id`.
- Watcher snapshot org must match scan, policy, command, and executable policy.
- `test_cross_tenant_compile_and_approve_fail_closed` accepts `{403, 404, 409, 422}` — fail-closed, not a precise status contract.

### Restart determinism — mixed

- Semantic evidence hashes: **pass**. Transport fields (`observed_at`, connection IDs, scan/action/lineage IDs, receive times) excluded from `semantic_content_hash`. `test_restart_retry_same_semantic_batch_converges`, `test_connection_ids_and_equivalent_batches_converge`, `test_transport_observed_at_does_not_fork_envelope_hash`.
- Setup lifetime pins: **fail** across process restart (new P1). A new assembler has an empty `SetupLifetimeStore`, so the latest closed 15m bar becomes a new trigger and expiry restarts.

### Semantic evidence hashing / CVD / signed flow — pass

Consumed observation binding in `_bind_consumed_observations` requires command CVD/flow/coverage/OHLCV payload hashes to equal the evidence actually evaluated. Changing consumed CVD changes canonical window hash (`test_changing_consumed_cvd_changes_canonical_identity`). OHLCV placeholder in the CVD role does not confirm (`test_ohlcv_placeholder_for_cvd_fails_closed`).

### Freshness — pass

`FIRST_SLICE_TRADE_MAX_AGE_SECONDS == 10` is not relaxed. Quote, trade-stream, live-confirmation window, closed-evidence validity, and setup expiry are separate `EvidenceClockReport` fields. Live window uses forming/stale contracts; historical closed evidence can remain valid after the live window closes without expiring the setup.

### Migration integrity — pass at HEAD

Single Alembic head `b7c8d9e0f1a2`. Conversation/proposal tables live on that revision. CI Postgres tests cover candidate/trade-plan upgrade/downgrade. This review did not re-run destructive `DROP SCHEMA` cycles locally.

### Concurrent confirmation — pass on Postgres (CI); SQLite test is weaker

Postgres dedicated test converges to one version. Local SQLite `test_concurrent_confirmation_converges_to_one_version` exited 0 but emitted `PytestUnhandledThreadExceptionWarning` (`IndexError` in SQLAlchemy row processors) — not the production locking story.

### Prompt injection boundaries — pass on user-message confirm; residual assistant-echo

User quotes, `SYSTEM:`, `retrieved:`, and fenced blocks cannot confirm. Confirmation-only regex. Assistant history is the presentation channel: if the model copies a forged identity block, `IDENTITY_BEGIN` already in content **suppresses** appending the real pending identity (`agent_service.py`). Tenant/conversation/hash still have to match a real row — typically fail closed. Residual P2.

### Paper only / real trading disabled / Watcher disabled / Telegram disabled — pass

- `Settings.real_trading_enabled` always `False`; `ENABLE_REAL_TRADING=true` rejected in every environment.
- `execution_mode=trade` and `exchange_mode=trade_live` rejected.
- Defaults: `market_watcher_enabled=False`, `watcher_orchestration_enabled=False`, `telegram_alerts_enabled=False`, `telegram_interaction_enabled=False`, `worker_enabled=False`.
- Staging/production `deployment_safety` rejects enabling those flags.
- `docker-compose.yml`, `.env.example`, `render.yaml`: paper, Watcher off, Telegram off, `ENABLE_REAL_TRADING=false`.
- Worker default scanner is the old `analyze()` market scan, not fusion Candidate minting, and is not enabled here.
- `TELEGRAM_EXECUTION_ENTRY_PATHS == ()`.

---

## Test quality — vacuous or misleading tests

| Test / assertion | Issue | Product vs helper |
| --- | --- | --- |
| `test_default_scan_evidence_authority_is_in_memory_helper` | Asserts enum string values only | Helper |
| `test_clock_fields_are_independent` | `market_stream_fresh or not historical_closed_evidence` is nearly tautological | Product assembler, weak oracle |
| `test_persisted_watcher_path_uses_canonical_resolver` persist branches | Replay path is `WATCH`, so `candidate_ids == ()` does not prove authority | Product port + replay fixture |
| `test_incomplete_and_unsupported_cannot_become_executable_policy` | Allows confirm `200` or `409/422`; success path only then checks compile | Product HTTP, loose |
| `test_cross_tenant_compile_and_approve_fail_closed` | Any of 403/404/409/422 | Product HTTP |
| `test_strategies_list_and_evaluate` research flags | Flags are Pydantic defaults; does not assert zero writes | Product HTTP; implementation is still read-only |
| `test_confirmed_setup_creates_exactly_one_candidate` | **Name lies** — asserts in-memory **cannot** mint | Fusion helper `make_world` |
| `test_auto_paper_mode_can_create_trade` | **Name lies** — asserts no trade | Product paper-bot |
| `_LiteralPersistedScanEvidence` | Claims persisted authority for in-memory `make_world` policy | Explicit test helper (honest comment) |
| `test_quote_trade_and_setup_clocks_stay_separated` | `quote_fresh or live_confirmation_window_open` OR-gate | Product assembler |

Helpers that are **not** product authority: `InMemoryWatcherScanEvidence`, `executable_policy_from_fusion_policy`, `make_world()`, `_LiteralPersistedScanEvidence`, `first_slice_read_policy` (GET/read projection placeholders).

---

## Findings

### P0

None, **provided** Watcher, Telegram, and real trading remain disabled and PR114 is not used to activate them.

### P1

1. **OPEN (previous P1 3) — Paper-bot remains a second AUTO_PAPER minting authority.** After `resolve_executable_strategy_policy` succeeds, scan evaluates `PaperBotEngine` / `structured_rules_to_parsed` (invented 2% stop / TP multiples) instead of compiled AST + SetupAssessment. `ExecutableStrategyPolicy` is unused beyond a boolean gate.

2. **NEW — Setup lifetime is not restart-durable.** `SetupLifetimeStore` is in-process RAM. Watcher paper monitoring that expires setups after N final bars will reset trigger identity on process restart (and on a new assembler instance). Semantic hashes restart-converge; expiry clocks do not.

### P2

1. Frontend Confirm uses `listProposals` open draft as the card identity, not a parse of the last transcript footer. Server API still requires those fields.
2. `AgentService` re-appends `latest_draft` identity onto later assistant messages, which can change “last presented” after a discussion turn.
3. Candidate mint-time trusts `policy_authority` enum; does not re-resolve compiled policy from the session.
4. Vacuous/misleading tests listed above; replay product persist path never reaches `CONFIRMED_SETUP`.
5. `_APPROVE_FROM_STATES` includes `DRAFT` if an executable compiled row already exists (normal HTTP compile moves DRAFT → REVIEW_REQUIRED first).
6. `HISTORY_LIMIT = 20`; if identity falls out of history and is not re-presented, chat confirm fails closed (safe, but UX-brittle).
7. Cross-tenant tests do not pin a single expected status.
8. SQLite concurrent confirm is not a substitute for the Postgres test.
9. Paper validation `start()` can begin without compiled lineage; only `scan` fail-closes trades (status/metrics noise).
10. `setup_trigger_end` remains a public assembler argument (footgun for future tests/callers). It is not required on the product path.

---

## Watcher paper-monitoring phase

**Not safe to start** as a follow-on while:

- paper-bot can mint paper trades from a non-canonical engine once lineage exists;
- setup pins are not persisted with the scan/evidence identity;
- product Watcher persist is unwired **and** unproven at `CONFIRMED_SETUP` on the live assembler path;
- Watcher/Telegram flags remain correctly false (they must stay false until a dedicated activation program).

Merge of PR114 is a separate question from Watcher activation. This review’s merge verdict is **REMEDIATION REQUIRED** because previous P1 3 is still open in product code.

---

## What this review did not do

- No product-code edits, merge, or deploy.
- No Watcher, Telegram, or live-trading enablement.
- No full local 2363-test rerun (trusted CI run 35588348865 at the same SHA; targeted local pytest exit 0).
- No local Postgres `DROP SCHEMA` Alembic round-trip.
- Did not treat Vercel preview as a safety signal.
