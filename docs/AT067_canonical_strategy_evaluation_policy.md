# AT-067 — Canonical strategy evaluation policy

**Task:** AT-067  
**Type:** Implementation (paper-only)  
**Base:** `main@20d2cac`  
**Inputs:** PR #107 strategy-intelligence audit, PR #108 live-market/Watcher audit  
**Safety:** Watcher, Telegram, and live trading remain disabled. SetupAssessment
stays market truth. No Candidate minting changes.

## Architecture

```text
approved immutable UserStrategyVersion
  → CompiledSetupDefinition (content_hash lineage)
  → canonical market evidence (CanonicalEvidenceWindowV1)
  → evaluate_canonical_strategy
       → first-slice compatibility adapter (compiled spec → FirstSliceEvaluationParams)
       → evaluate_setup
  → SetupAssessment
```

| Layer | Authority |
|---|---|
| Who may evaluate | `resolve_executable_strategy_policy` — APPROVED or ACTIVE only |
| What rules apply | Stored `pattern_spec` + `CompiledSetupDefinition.content_hash` |
| How presence is decided | `evaluate_setup` (AT-ADR-025) |
| Adapter | `bind_first_slice_compatibility_adapter` — first-slice kind only |

Draft conversational proposals, STRUCTURED/PAPER_VALIDATING versions, missing
compile artifacts, hash mismatch, and unsupported specs fail closed. There is
no LLM on this path.

## Legacy authorities

| Path | Status |
|---|---|
| First-slice constants in `evaluate_setup` | Retained as adapter defaults; product callers pass compiled params |
| Strategy Lab paper-bot `scan`/`tick` | Retained as compatibility simulation (not SetupAssessment) |
| Code strategy modules `/strategies/evaluate` | Unchanged; not canonical setup truth |
| Watcher fusion evaluation | Calls `evaluate_canonical_strategy`; flag remains off |

## Remaining integration

- Paper-bot `scan`/`tick` remain a compatibility simulator, not SetupAssessment.
  Canonical evidence assembly is `app.evidence_pipeline` (AT-064) and is used by
  the AT-063 fixture proof after explicit compile + approval.
- Conversational confirmation (AT-066) stores a draft version only. It cannot
  resolve executable policy until compile + APPROVED/ACTIVE.
- Pattern-spec authoring UI remains limited; complete explicit first-slice text
  can preview a validated spec without inventing thresholds.
- Do not enable Watcher.
