# AT-063 — Strategy intelligence and conversational AI capability audit

**Task:** AT-063  
**Type:** Read-only capability audit (no product implementation)  
**Audit base:** `origin/main` @ `20d2cac` (merge of PR #106)  
**Branch:** `cursor/next_strategy_agent_audit`  
**Date (UTC):** 2026-09-20  
**Safety posture:** Paper-only. Watcher, Telegram, and live trading remain disabled by
default and are rejected in staging/production by `deployment_safety.py`.

This document is repository evidence only. Unknowns are marked **UNKNOWN**. It supersedes
the strategy / conversation portions of
`docs/redesign/agentic_redesign_phase0_audit.md` (older SHA) for current `main`.
The target architecture in `docs/redesign/agentic_redesign_target_architecture.md` remains
the design destination; this audit reports what is actually implemented now.

**Non-negotiable product rule (this audit):** the conversational agent may explain,
challenge, and propose refinements. It must never silently mutate deterministic trading
authority (`SetupAssessment`, `Candidate`, `ActionEligibility`, `TradePlanRevision`,
risk/kill-switch, compiled pattern identity, or paper/live execution).

---

## Target loop (audit question)

```text
User discusses strategy with AlphaTrade
  → AI structures the idea
  → user reviews rules
  → versioned strategy is stored
  → strategy becomes deterministic evaluation policy
  → historical validation
  → Watcher monitors live evidence
  → Candidate
  → interactive explanation and discussion
  → paper TradePlan
  → outcome
  → learning
  → strategy refinement
```

**Verdict:** The pieces exist as **two parallel product loops** plus **three evaluation
authorities**. The target is not one closed conversational lifecycle. Chat is a
request-scoped keyword copilot, not a durable strategy discussion system.

| Target step | Status |
|---|---|
| Discuss strategy | Partial — `/chat/message` + Plan-hub widget; no transcript store |
| AI structures the idea | Partial — keyword draft of `StructuredRules` only; no `pattern_spec` |
| User reviews rules | Exists — Strategy Lab editor + validate API; no structure-from-text UI |
| Versioned strategy stored | Exists — immutable `UserStrategyVersion` + content hash |
| Deterministic evaluation policy | Split — Lab adapter vs AST compile vs first-slice fusion constants |
| Historical validation | Exists as backtest / research-validation; not canonical Candidate mint |
| Watcher live evidence | Implemented and **off**; staging/prod forbid enabling |
| Candidate | Canonical service + Postgres; no public HTTP mint |
| Interactive explanation | Partial — `/decision` reads; Telegram EXPLAIN exists but off; chat does not bind canonical Candidate |
| Paper TradePlan | Exists via `CanonicalTradePlanService` + `POST /execution/paper-plan` |
| Outcome | Journal projector is the sole `JournalTrade` writer |
| Learning | Phase 8 Postgres attribution on canonical paper events |
| Strategy refinement | Explicit lesson accept / new version only; **no auto promotion** |

---

## 1. Existing capabilities

### 1.1 Strategy models (tenant library)

| Model | File | Role |
|---|---|---|
| `UserStrategy` | `backend/src/app/db/models.py` | Tenant library head: name, `setup_type`, `current_version`, `paper_eligible` |
| `UserStrategyVersion` | same | Immutable semantic payload: `card`, `structured_rules`, `pattern_spec`, `lesson_source_metadata`, `content_hash`, evaluation statuses |
| `CompiledSetupDefinition` | same | 1:1 compiler artifact: `compiled_ast`, `compiler_version`, `grammar_version`, `content_hash` |
| `StrategyLifecycleEvent` | same | Append-only lifecycle (`event_hash`) |
| `SetupDefinition` / `GlobalSetupTemplate` | same | Legacy global setup rows / compatibility alias |
| `SetupPerformance` | same | Per-setup rollup (legacy) |

Immutability: `backend/src/app/db/strategy_immutability.py` — semantic fields immutable
(ORM + PG trigger); evaluation statuses mutable; compiled setups and lifecycle events
append-only.

Versioning: `StrategyVersioningService.fork_semantic_update` /
`append_lifecycle` / `persist_compiled` in
`backend/src/app/services/strategy_versioning.py`.

Change sources (`StrategyChangeSource`): `create`, `card_update`, `structured_rules`,
`pattern_spec`, `lesson_attachment`, `rollback_select`, `migration`, `legacy`.
**`ROLLBACK_SELECT` has no service implementation** (enum only).

Lifecycle states (`StrategyLifecycleState`): `draft`, `structured`,
`historically_validated`, `paper_validating`, `review_required`, `approved`, `active`,
`retired`. **Writers found only emit `DRAFT` and `STRUCTURED`.**

### 1.2 Strategy Lab (UI + API)

Frontend: `frontend/src/app/(app)/strategy-lab/` (list, new, detail, edit) with
structured-rule editor, version history, backtest panel, paper-validation panel.

HTTP (`backend/src/app/api/routes/strategy_library.py`):

- CRUD `/strategies`, versions, backtests
- testability, structured-rules patch/validate
- `POST /strategies/{id}/structure-from-text` (draft only; `strategy_id` unused)
- paper eligibility + paper-validation start/scan/tick

Docs: `docs/strategy_library.md` (Slice 33–39 Lab path). Phase 3 AST identity is not
fully documented there.

### 1.3 Pattern definitions

Authored contract: `FirstSliceAuthoredPatternSpec` in
`backend/src/app/schemas/strategy_pattern_spec.py` — exact first-slice pattern
`bearish_liquidity_sweep_cvd_sell_imbalance_at_4h_resistance/v1` (BTCUSDT 15m trigger /
4h context, short). Missing fields fail closed; compiler does not invent thresholds.

Compiler: `setup_ast_compiler.py` → allowlisted `PatternAst`.
`CompiledSetupService.compile_version` persists `CompiledSetupDefinition`.

**No public compile or lifecycle HTTP routes** were found.

Lab historical sim uses a **different** path: `card` + optional `structured_rules` →
`resolve_backtest_rules` → `ParsedStrategyRules` → backtest engine. Structured rules
alone do **not** compile to `CompiledSetupDefinition` (`compile_from_authored` requires
`pattern_spec`).

### 1.4 Code strategy modules (separate authority)

`backend/src/app/strategies/` registry: seven hardcoded modules
(`HtfTrendPullback`, `LiquiditySweepReversal`, `CountertrendShortBuild`,
`PassiveLevelOrder`, `ProfitProtection`, `GreenDayGuard`, `MentalCapitalGuard`).

Chat trading-analysis evaluates **these modules**, not the user's Strategy Lab version.
APIs: `/strategies/modules`, `/strategies/evaluate`.

### 1.5 Chat / agent

- Entry: `POST /chat/message` (`backend/src/app/api/routes/chat.py`) → `AgentService` →
  LangGraph (`backend/src/app/agents/graph.py`).
- Deterministic intent: `classify_intent_decision` + `classify_strategy_workflow`.
- Confirmation helper: `mutation_policy.mutation_allowed` (non-question + explicit
  `I confirm` / `confirm=true`).
- Tools: RAG, market data, indicators, strategy library, structure-from-text,
  lessons, backtest, paper validation, human-vs-system, testability, risk settings,
  and others in `backend/src/app/tools/registry.py`.
- Narrative enhancement is optional and schema-validated; it cannot override
  deterministic tool/risk facts.
- UI: collapsible “AI assistance” on `/workspace` (Plan hub). Last response only;
  `conversation_id` is React state, not a server transcript.

### 1.6 RAG

- `RagService` + Postgres `documents`/`chunks` + Qdrant collection
  `alphatrade_knowledge`.
- Fail-closed ingest (AT-013): no mock embeddings into remote Qdrant.
- Journal → RAG when `journal_rag_sync_enabled=true` (default):
  `JournalRagSyncService`, source `trade_journal`.
- Accepted lessons → RAG as `review_note` (`LessonCandidateService._ingest_accepted_lesson`).
- Validated / in-review strategy cards ingest as `strategy_template`
  (`StrategyLibraryService._sync_rag`).
- Agent retrieval (`context_retrieval` / `retrieve_for_agent`) searches playbook,
  risk policy, journal, review notes, mistakes — **not** `strategy_template`.

### 1.7 Journal, lessons, coaching, analytics

- Canonical journal: `JournalTrade` + lifecycle projector
  (`JournalLifecycleProjector` is the sole trade writer).
- Statistics, import, attachments, excursion replay (MFE/MAE).
- Lessons: detect → `pending_review` → explicit accept/reject/archive; accept may
  attach rules or create a version (`docs/lesson_workflow.md`).
- Coaching HTTP produces prompts; save creates a lesson candidate only.
- Analytics: `/analytics/*` (setups, trade review, discipline, risk behavior),
  `/strategy-quality/*`, `/learning-analytics/*` (PVC-era; **not** Phase 7/8
  canonical), `/canonical/learning/*` (Phase 8 `LearningQueryService`).
- `/decision/strategy` composes those surfaces and states
  **“No automatic rule promotion.”**

### 1.8 Human versus system

- Per-trade: `HumanVsSystemService` — `GET/POST /human-vs-system/{trade_id}`
  (plan adherence, runner/stop analyzers, lesson suggestions).
- Aggregate: `GET /journal/comparison` — cohorts human / paper_system / backtest
  (does not call the per-trade orchestrator).
- Chat: `HUMAN_VS_SYSTEM` / early-exit / stop-discipline tools require a trade UUID
  in the message.
- UI: `/journal/comparison`.

### 1.9 Canonical SetupAssessment → Candidate → TradePlan → paper → learning

| Step | Authority | Location |
|---|---|---|
| Evidence window | `CanonicalEvidenceWindowV1` | `signal_fusion/evidence_window.py` |
| Setup evaluate | `evaluate_setup` → `SetupAssessment` | `evaluator.py`, `assessment.py` |
| Candidate mint | `CandidateLifecycleService.create_from_confirmed_setup` | `lifecycle.py` |
| Action gate | `ActionEligibilityService` (`live_executable=False`) | `action_eligibility.py` |
| TradePlan | `CanonicalTradePlanService.create` | `services/canonical_trade_plan.py` |
| Paper exec | `POST /execution/paper-plan` → `CanonicalPaperExecutionService` | `execution.py` |
| Journal | `JournalLifecycleProjector` | `journal_lifecycle_projector.py` |
| Learning | `attribute_canonical_paper_event` → `PostgresAttributionStore` | `canonical_execution_learning.py` |

`/canonical/*` is **read-only**. No FastAPI create for Candidate, eligibility, or
TradePlan. Runtime composition: `ProductionCanonicalRuntime`.

`SetupAssessment` has **no SQL table**. `CanonicalReadService.get_setup_assessment`
projects identity from Candidate + eligibility hash.

Canonical `Candidate` (`canonical_candidates`) ≠ ORM `PaperValidationCandidate`
(paper-validation queue). PVC cannot mint canonical identity
(`LegacyCandidateAuthorityError`).

Frontend: `/decision/*` = canonical; `/paper-validation/candidates` = compatibility.

### 1.10 Watcher (two systems)

| System | Role | Default |
|---|---|---|
| `app.watcher` | Fusion orchestration → `evaluate_setup` → Candidate when authorized | `watcher_orchestration_enabled=False` |
| Market Watcher | Ticker scans → observations → optional bridge to **paper-validation scan** | `market_watcher_enabled=False` |

`deployment_safety.py` rejects both flags (and Telegram) in staging/production.
Worker entrypoint does not start Watcher/Telegram loops.

### 1.11 Safety already in place (do not weaken)

- Paper defaults: `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`.
- Risk `BLOCK` is final; kill switch is server-enforced.
- `SetupAssessment` forbids account/risk fields.
- Attribution: narrative excluded from `facts_hash`;
  `NarrativeCannotRewriteFactsError` / `MarketTruthMutationError`.
- `ActionEligibilityEvaluation.live_executable` always `False`.
- APPROVE never executes; only explicit `EXECUTE_PAPER_PLAN` may reach agent tools.
- Agent `paper_execution` tool is **fail-closed `NOT_IMPLEMENTED`** (not
  `ExecutionService`). Canonical paper execution is the HTTP paper-plan path.
- `journal_writer` tool is fail-closed; journal writes go through
  `JournalTradeService` / projector.
- Persistence firewall: READ_ONLY IntentDecision cannot write domain rows.
- Lesson accept / create-version require `mutation_allowed` in nodes + tool.

---

## 2. Missing capabilities

Relative to the target loop. “Missing” means not implemented or not wired, not
“nice to have.”

### 2.1 Conversation

1. **No `Conversation` / `ChatMessage` tables.** `conversation_id` is an echo
   (`conv-{request_id[:8]}` if omitted). History is never loaded.
2. **`memory_update` is ephemeral** — in-process citation note only.
3. **`MemoryClass` is unused at runtime** (schema + `PersistenceKind` only).
4. **System prompt is a placeholder** (`backend/src/app/agents/prompts/system.md`).
   Slice 9 uses deterministic nodes; there is no conversational strategy coach.
5. **UI is single-turn.** Plan hub shows the last reply, not a thread.
6. **No chat intents that bind canonical Candidate / SetupAssessment** for explain
   or challenge. `SETUP_ANALYSIS` runs **code modules**, not user `pattern_spec`.
7. **`UPDATE_RULE` is a dead intent** — classified `CONFIGURATION`, not handled by
   `strategy_workflow_tools`, no node writes rules.

### 2.2 Structuring and review

1. Structure-from-text is **keyword heuristics**, not LLM structuring, and does not
   persist. Defaults (EMA pullback, H4, 2% stop, 1R TP) fill gaps.
2. Chat does **not** author `pattern_spec` or compile AST.
3. Frontend API client has `structureFromText`; **Strategy Lab has no control** that
   calls it.
4. No preview-diff UX: “here are the proposed rules — accept to create version.”

### 2.3 Evaluation-policy unification

Three authorities exist and are **not one chain**:

| Authority | Used by | Input |
|---|---|---|
| A. Code modules | Chat trading-analysis, `/strategies/evaluate` | Hardcoded `StrategyModule` |
| B. Lab backtest adapter | Strategy Lab historical sim | `card` + `structured_rules` → `ParsedStrategyRules` |
| C. Phase 6 fusion | `evaluate_setup` / Watcher (off) | First-slice **hardcoded constants**, not a generic AST walker |

`CompiledSetupDefinition` is a stored document. **No interpreter was found** that
walks `compiled_ast` at fusion time.

`HISTORICALLY_VALIDATED` is unused. Backtest success does not advance lifecycle
state. Research-validation promotion is **advisory → PVC**, not canonical Candidate.

No compile HTTP. No pattern-spec authoring UI. No rollback-select.

### 2.4 Watcher → Candidate → discuss → paper TradePlan

1. Live evidence loop is **disabled** and cannot be turned on in staging/prod
   without a separate safety program.
2. Market Watcher does not mint canonical Candidates.
3. Historical validation does not mint canonical Candidates.
4. Chat cannot mint or discuss a specific canonical Candidate (no tool / intent).
5. Chat cannot create a canonical TradePlan. Agent `paper_execution` is a stub.
   Paper TradePlan is Decision-UI / `POST /execution/paper-plan`.
6. Telegram Candidate EXPLAIN/STATUS/REJECT/SKIP exists (`candidate_alerts`) but
   `telegram_interaction_enabled=False` and is forbidden in staging/prod.

### 2.5 Memory / learning closed loop

1. Learning evidence renderer (`adapters/rag.py`) **does not ingest** into Qdrant.
2. Attribution lesson suggestions (`adapters/lessons.py`) set **`persist=false`** —
   they never auto-create `LessonCandidate` rows.
3. Agent RAG omits ingested `strategy_template` cards.
4. Learning analytics (`/learning-analytics`) is a **legacy PVC-era** surface,
   distinct from `/canonical/learning/*`.
5. No automatic (and must not become automatic) rule promotion from outcomes.

### 2.6 Confirmation gaps (not trading authority, but silent domain writes)

`mutation_allowed` is **not** applied uniformly. Classifier marks these as
`MUTATION` when the message is not a question; nodes then write **without**
requiring `I confirm`:

- `STRATEGY_CARD` → `strategy_library_tool` `create` (new library row + v1 card)
- `BACKTEST_RUN` → `backtest_tool` `run` (first listed strategy)
- `PAPER_VALIDATION_START` / `SCAN` → paper-validation runtime

Lesson accept/reject/create-version **do** require confirmation. Risk-settings and
notification updates require confirmation inside tools.

This is **not** silent mutation of Candidate / risk / execution. It **is** silent
mutation of strategy-library and validation runtime from a single non-question
sentence (e.g. “build strategy idea …”). That violates the target review step.

---

## 3. Memory architecture

```text
Request-scoped AgentState
  ├─ conversation_id          echo only; no load
  ├─ retrieved_context        RAG citations this turn
  ├─ memory_update            ephemeral “Session memory: intent=…”
  └─ MemoryClass              unused

Durable stores (not chat memory)
  ├─ Postgres documents/chunks + Qdrant     RAG corpus
  ├─ TradeJournal / JournalTrade            journal facts
  ├─ LessonCandidate                        reviewed memory
  ├─ UserStrategyVersion                    strategy identity
  ├─ PostgresAttributionStore               Phase 8 learning facts
  ├─ AuditLog / UsageEvent                  observability
  └─ Telegram / Watcher memory modules      isolated; flags off
```

| Layer | Persisted? | Notes |
|---|---|---|
| Chat transcript | **No** | No Conversation/Message ORM |
| Session notes | **No** | `memory_update` in-process only |
| `NON_DOMAIN_MEMORY` | Policy only | Allowed under READ_ONLY; no writer uses it |
| RAG corpus | Yes | Org/user scoped; fail-closed embeddings |
| Journal → RAG | Yes if enabled | Labeled pending observation until lesson accept |
| Accepted lessons → RAG | Yes if enabled | `review_note`, `lesson://{id}` |
| Strategy cards → RAG | Yes if in_review/validated | **Not retrieved by agent** |
| Learning attribution | Yes (canonical paper path) | Facts-first; narrative labeled; RAG render only |
| Domain writes under READ_ONLY | Denied | Persistence firewall + `write_allowed` |

**Implication:** AlphaTrade has **domain memory** (journal, lessons, versions,
attribution) and **retrieval memory** (RAG), but not **conversational memory**.
The agent cannot remember yesterday’s strategy discussion unless the user
re-states it or it was persisted through Lab / lessons.

---

## 4. Strategy lifecycle (as implemented)

### 4.1 Strategy Lab loop (interactive product today)

```text
POST /strategies (card v1, DRAFT)
  → edit card / PATCH structured-rules (fork + STRUCTURED)
  → testability score
  → backtest (historical sim on structured_rules adapter)
  → paper eligibility (conservative promotion; not live)
  → paper-validation start/scan/tick (local paper bot)
  → optional research-validation → PaperValidationCandidate queue
```

Chat can jump into this loop with keyword tools (create card, run backtest, start
paper validation) — sometimes without `I confirm`.

Lessons enter this loop only after explicit accept (+ optional attach / new version).

### 4.2 Phase 3 executable identity (partially built)

```text
UserStrategyVersion.pattern_spec (FirstSliceAuthoredPatternSpec)
  → compile_from_spec → PatternAst
  → CompiledSetupDefinition (optional persist)
```

Not wired to Lab UI, chat, or a generic fusion interpreter.

### 4.3 Canonical surveillance / decision loop (Phase 6–8)

```text
Evidence window
  → evaluate_setup → SetupAssessment (market truth only)
  → CONFIRMED_SETUP → CandidateLifecycleService
  → ActionEligibility (paper gate; never live_executable)
  → CanonicalTradePlanService (immutable revision)
  → human approval (authorization only)
  → POST /execution/paper-plan
  → JournalLifecycleProjector
  → PostgresAttributionStore / LearningQueryService
```

Watcher is the intended producer of live evidence → Candidate. It is **off**.
There is no HTTP mint. Decision UI reads and can execute an existing paper plan.

### 4.4 Two loops must not be silently merged

| Concern | Lab / PVC loop | Canonical loop |
|---|---|---|
| Identity | `UserStrategy` + `PaperValidationCandidate` | `strategy_version_id` + `Candidate` |
| Evaluation | Structured-rules adapter / code modules | First-slice `evaluate_setup` |
| Execution | Legacy paper validation / `POST /execution/paper` | `POST /execution/paper-plan` only |
| Learning | Journal stats + `/learning-analytics` | `/canonical/learning/*` |

Target architecture says merge via adapters, preserve old APIs. That merge is
**not complete**. Chat still drives the Lab loop; Decision UI drives the
canonical loop.

---

## 5. Conversation architecture

```text
POST /chat/message
  → auth / quota / rate limit
  → injection + moderation
  → message_classification (COMMAND tombstoned)
  → intent_classification → IntentDecision (intent, operation_class, requested_action)
  → context_retrieval (RAG)
  → route:
       strategy_workflow → keyword tools (Lab/lessons/backtest/paper-validation)
       analytics         → analytics_summary_tool
       trading_analysis  → market → indicators → code modules → optional PLAN_TRADE
       general           → skip to memory_update
  → risk gate (BLOCK final)
  → approval node (APPROVE never executes)
  → tools only for explicit EXECUTE_PAPER_PLAN (tool is stub)
  → memory_update (ephemeral)
  → usage + structured response + optional narrative + output validation
```

**Classifier properties (verified):**

- Ambiguous execute/close without a target → READ_ONLY clarify.
- Analysis wording cannot infer `EXECUTE_PAPER_PLAN`.
- Generic “execute” is not execution.
- APPROVE / REJECT / SKIP are approval-class; REJECT/SKIP never authorize.
- Strategy mutations become READ_ONLY when the message is a question.
- `STRUCTURE_STRATEGY` is always READ_ONLY (draft).

**What chat can do today**

| Behavior | Status |
|---|---|
| Explain (generic / RAG) | Yes, single-turn |
| Challenge discipline (HVS, early exit, stop) | Partial; needs trade UUID |
| Draft structured rules | Keyword only; no persist |
| Create strategy card | Yes, without `I confirm` if not a question |
| Run backtest / start paper validation | Yes, same confirmation gap |
| Accept lesson / new version | Yes, **with** confirmation |
| Evaluate user pattern vs live market | **No** (code modules only) |
| Explain a canonical Candidate | **No** |
| Create canonical TradePlan | **No** |
| Execute paper plan | Tool stub; Decision UI only |
| Silently change risk / Candidate / compiled identity | **No** |

---

## 6. Safety boundaries

Keep these invariants in every follow-up slice.

### 6.1 Deterministic trading authority (must not be chat-writable)

The agent must not create or rewrite:

- `SetupAssessment` / evidence-window hashes
- `Candidate` / `CandidateUniquenessTuple` / transitions
- `ActionEligibility`
- `TradePlanRevision` content
- RiskEngine results, kill switch, reservations
- `CompiledSetupDefinition` / executable `pattern_spec` without an explicit
  version fork **and** human review
- Paper or live execution

LLM narrative is explanation only. `facts_hash` excludes narrative.

### 6.2 Allowed conversational effects

- Read and explain existing cards, versions, backtests, journal, lessons,
  canonical reads, learning stats.
- Draft structured rules / proposed `pattern_spec` as **non-authoritative preview**.
- After explicit confirmation, call existing services that already require a
  human write path (lesson accept, version fork, structured-rules patch).
- Never treat a draft as evaluation policy.

### 6.3 Confirmation policy (current vs required)

| Action | Today | Required for target |
|---|---|---|
| Lesson accept/reject/version | `mutation_allowed` | Keep |
| Risk settings / notifications | tool-level confirm | Keep |
| Strategy card create | MUTATION if not `?` | Preview + `I confirm` |
| Backtest run / paper start/scan | MUTATION if not `?` | Preview + `I confirm` |
| Structure-from-text | READ_ONLY draft | Keep draft-only |
| Canonical Candidate / plan / exec | Unreachable from chat | Keep unreachable until a later explicit slice |

### 6.4 Deployment locks (do not lift here)

`market_watcher_enabled`, `watcher_orchestration_enabled`,
`telegram_interaction_enabled` default false and are illegal in staging/production.
Enabling Watcher live evidence is a **separate** safety/ops program, not the next
strategy-agent slice.

### 6.5 Residual risks

- Authenticated `POST /strategies/{id}/versions` can set `pattern_spec` (API).
  Frontend create-version does not expose it. Explicit write, not silent LLM.
- `STRATEGY_CARD` create uses a truncated chat message as the card body and
  hardcodes `HTF_TREND_PULLBACK`.
- `BACKTEST_RUN` / paper-validation tools operate on the **first listed**
  strategy, not a discussed id — easy to mutate the wrong row.
- Staging provider liveness (OpenAI/Qdrant) is **UNKNOWN** in this checkout
  (config-dependent; not probed).

---

## 7. Implementation slices (do not implement in this task)

Paper-only. Do not enable Watcher, Telegram, or real trading. Do not give the LLM
write access to fusion/risk/Candidate/TradePlan.

### Slice 1 — AT-064 Conversation persistence (read + history only)

**Goal:** Durable conversation so discussion can continue. No new domain writes.

- Add `Conversation` + `ChatMessage` (org/user scoped, no secrets in logs).
- Persist user/assistant turns from `/chat/message`; load last N into graph state.
- Keep `memory_update` non-domain; optionally persist `NON_DOMAIN_MEMORY` notes
  only (never strategy/candidate facts).
- Plan-hub thread UI (message list). No strategy mutation changes.

**Out of scope:** LLM coach, Watcher, pattern_spec.

### Slice 2 — AT-065 Uniform chat mutation confirmation

**Goal:** Chat cannot silently create cards, run backtests, or start paper
validation.

- Apply `mutation_allowed` to `STRATEGY_CARD`, `BACKTEST_RUN`,
  `PAPER_VALIDATION_START` / `SCAN` (same pattern as lessons).
- Bind tools to an explicit `strategy_id` (UUID in message or conversation
  target). Refuse “first listed strategy.”
- Questions and missing confirm → preview only.

**Out of scope:** New evaluation engine.

### Slice 3 — AT-066 Discuss → structure → review (preview authority)

**Goal:** Closest missing product step. AI structures; human reviews; version
store stays the authority.

- Replace or wrap keyword `StructureFromTextService` with a **preview** path that
  can emit `StructuredRules` and, when complete, a
  `FirstSliceAuthoredPatternSpec` draft.
- Persist **only** via existing `fork_semantic_update` after Lab review or
  confirmed chat action.
- Strategy Lab: wire existing `structureFromText` client; show draft +
  validation errors; user edits before save.
- Still do not compile-as-authority until the user saves a version.

**Safety:** Compiler fail-closed (no invented thresholds). Draft ≠
`CompiledSetupDefinition`.

### Slice 4 — AT-067 One evaluation-policy chain (Lab → compile → fusion)

**Goal:** A stored version becomes the deterministic policy the evaluator uses.

- Pattern-spec authoring/review UI (first-slice only).
- Compile + persist `CompiledSetupDefinition` on explicit save; expose compile
  status on the version.
- Either (a) walk compiled AST in `evaluate_setup`, or (b) keep first-slice
  constants but **require** the stored spec to match those constants and fail
  closed on mismatch. Do not run two silent policies.
- Write `HISTORICALLY_VALIDATED` only from deterministic backtest evidence
  bound to that `content_hash` — still not a Candidate mint.

**Out of scope:** Enabling Watcher; generic arbitrary-pattern language beyond
first slice.

### Slice 5 — AT-068 Canonical Candidate conversation (read-only)

**Goal:** Interactive explanation/challenge of an existing Candidate without
minting one.

- Chat intents: explain Candidate, show SetupAssessment lineage, eligibility,
  learning record — tools that call `CanonicalReadService` only.
- Decision UI deep-link from chat citations.
- Forbidden: create Candidate, mutate assessment, approve/execute from
  narrative.

**Out of scope:** Watcher enablement; Telegram inbound.

### Slice 6 — AT-069 Learning → explicit refinement

**Goal:** Close outcome → learning → refinement without auto-promotion.

- Ingest `LearningEvidenceDocument` into RAG (facts first, narrative banner).
- Include `strategy_template` + learning evidence in agent retrieval when the
  user discusses that strategy.
- Chat proposes a structured-rules / pattern-spec **diff** from attribution
  facts; persist as `LessonCandidate` or version fork only after confirm.
- Keep `/decision/strategy` “no automatic rule promotion.”

### Later / not next — Watcher live evidence

Code exists (`WatcherOrchestrator`, fusion wiring, Postgres adapters). Enabling
it is blocked by `deployment_safety` in staging/production and is a separate
high-risk ops program. Do **not** start this as the next strategy-agent task.

---

## 8. Exact recommended next prompts

Copy one prompt per new Cursor Cloud Agent. Base: latest `main`. Do not combine
slices. Do not enable Watcher, Telegram, or real trading.

### Prompt A — first implementation (recommended)

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main
CREATE: cursor/at064_conversation_persistence

OBJECTIVE
Implement AT-064 only: durable conversation persistence and history injection
for AlphaTrade chat. Read docs/AT063_strategy_agent_capability_audit.md and
.ai/TASKS.md AT-064.

REQUIREMENTS
- Add tenant-scoped Conversation + ChatMessage persistence (Postgres + Alembic).
- POST /chat/message stores user and assistant turns; loads last N messages
  into AgentState for the graph. conversation_id becomes a real id.
- Plan hub /workspace shows a message thread, not only the last reply.
- memory_update remains non-domain. Do not persist strategy, Candidate,
  TradePlan, risk, or journal facts through this path.
- Do not change mutation policy, strategy services, Watcher, Telegram, or
  execution. Paper-only invariants unchanged.

VALIDATION
Backend ruff + targeted pytest + full backend pytest. Frontend lint, typecheck,
unit tests, build. No deploy. No live trading.

OUTPUT
Tests, docs note, HANDOFF, draft PR.
```

### Prompt B — confirmation firewall (do immediately after A, or in parallel if A is delayed)

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main
CREATE: cursor/at065_chat_mutation_confirm

OBJECTIVE
Implement AT-065 only: uniform explicit confirmation for chat mutations.
Read docs/AT063_strategy_agent_capability_audit.md §2.6 and §6.3.

REQUIREMENTS
- STRATEGY_CARD, BACKTEST_RUN, PAPER_VALIDATION_START, PAPER_VALIDATION_SCAN
  must use mutation_policy.mutation_allowed (same as lesson accept).
- Questions and missing confirmation are preview-only; no DB writes.
- Mutating tools require an explicit strategy UUID; refuse first-listed
  strategy fallback.
- Do not add LLM structuring. Do not enable Watcher. Do not touch
  Candidate / TradePlan / risk authorities.

VALIDATION
Agent/tool regression tests for confirm/preview. Full backend pytest. No deploy.
```

### Prompt C — discuss → structure → review

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main
DEPENDS: AT-064, AT-065 preferred
CREATE: cursor/at066_strategy_structure_preview

OBJECTIVE
Implement AT-066 only: conversational + Lab preview of structured rules and
optional first-slice pattern_spec. Human review remains the write authority.

REQUIREMENTS
- Draft StructuredRules and, when fields are complete, FirstSliceAuthoredPatternSpec.
- Persist only through existing StrategyVersioningService fork after user
  review (Lab save or chat I confirm).
- Wire Strategy Lab to POST /strategies/{id}/structure-from-text.
- Compiler must not invent thresholds. Draft must not write
  CompiledSetupDefinition until explicit save/compile in a later slice
  (AT-067). Fail closed on incomplete spec.
- Paper only. No Watcher. No Candidate mint. No silent strategy overwrite.

VALIDATION
Deterministic tests for draft-vs-persist, incomplete spec, confirmation.
Frontend Lab preview/review path. Full backend + frontend tests. No deploy.
```

### Prompt D — do not run yet (evaluation chain)

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main
DEPENDS: AT-066
CREATE: cursor/at067_evaluation_policy_chain

OBJECTIVE
Implement AT-067 only after AT-066. Unify evaluation so one UserStrategyVersion
content_hash is the policy evaluate_setup uses. Read AT-063 §2.3 and §7 Slice 4.

Do not enable Watcher. Do not invent a general pattern language. First-slice
only. If AST walk is not ready, require stored spec to match first-slice
constants and fail closed on mismatch. No silent dual policy.
```

### Prompt E — do not run yet (Candidate conversation)

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main
DEPENDS: AT-064
CREATE: cursor/at068_candidate_explain_chat

OBJECTIVE
Implement AT-068 only: read-only chat tools for canonical Candidate,
SetupAssessment projection, eligibility, and learning records via
CanonicalReadService. No mint, no approve, no execute, no Watcher enablement.
```

---

## 9. Important code references

| Area | Path |
|---|---|
| Agent graph / nodes / classifier | `backend/src/app/agents/{graph,nodes,intent_classifier,strategy_intent,mutation_policy,routing}.py` |
| Chat API / schemas | `backend/src/app/api/routes/chat.py`, `schemas/chat.py`, `schemas/agent.py` |
| Tools / confirmation | `backend/src/app/tools/registry.py` |
| Persistence policy | `backend/src/app/core/operation_policy.py`, `persistence_firewall.py` |
| Strategy library / versioning | `services/strategy_{library_service,versioning,promotion}.py` |
| Structure / compile | `structure_from_text_service.py`, `setup_ast_compiler.py`, `compiled_setup_service.py` |
| Pattern spec / AST | `schemas/strategy_pattern_spec.py`, `schemas/setup_ast.py` |
| Fusion / Candidate | `signal_fusion/{assessment,candidate,lifecycle,evaluator,enums}.py` |
| Learning | `learning_attribution/`, `persistence/attribution_postgres.py` |
| Watcher | `backend/src/app/watcher/`, `core/config.py`, `core/deployment_safety.py` |
| Human vs system | `services/human_vs_system_service.py`, `api/routes/human_vs_system.py` |
| Decision UI | `frontend/src/app/(app)/decision/` |
| Strategy Lab | `frontend/src/app/(app)/strategy-lab/` |
| Plan chat widget | `frontend/src/app/(app)/workspace/page.tsx` |

---

## 10. UNKNOWN

- Whether any non-default environment has run Watcher with persisted Candidates
  (flags forbid staging/prod; not probed here).
- Row counts of `canonical_candidates` / attribution tables in deployed DBs.
- Whether staging OpenAI + Qdrant are healthy at this moment (AT-009 was done
  historically; this session did not call staging).
- Whether a general AST interpreter is already designed beyond first-slice
  constants (no implementation found).
- Product priority among AT-064–AT-066 if capacity allows only one slice
  (recommendation: A then B then C).

---

## 11. Tests and validation for this audit

Read-only. No application code changed. No pytest/CI run claimed for new
behavior. Inventory was verified by reading the files cited above on
`20d2cac`.
