# Research Validation Loop (AT-035)

Advisory workflow that bridges **completed backtest evidence** into the existing **paper validation candidate queue**. Promotion creates a synthetic research-origin alert and ready draft so legacy non-null foreign keys remain satisfied, then enqueues a `paper_validation_candidates` row with frozen provenance.

**Paper-only.** Research validation never feeds execution, risk, position sizing, or live trading. Real trading remains disabled (`enable_real_trading=false`, `execution_mode=paper`).

See also: [backtesting.md](./backtesting.md) (deterministic backtests, setup evidence tiers) · [paper_validation.md](./paper_validation.md) (candidate queue, runtime)

## Purpose

| Step | What happens |
|------|----------------|
| 1. Backtest | User completes a deterministic backtest with OOS metrics and strategy version linkage (AT-034). |
| 2. Evidence review | `SetupEvidenceService` classifies tier1/tier2/tier3 from OOS + confirmation trades. |
| 3. Optional promote | Trader confirms with exact phrase → candidate enters paper validation queue for human review. |
| 4. Paper validation | Existing slice-80+ queue/run-plan/runtime flows apply — no new execution path. |

## Endpoints

Router prefix: `/research-validation`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/research-validation/evidence` | Reader | List evidence items for org backtests (optional filters: `backtest_run_id`, `strategy_id`, `strategy_version_id`). |
| GET | `/research-validation/backtests/{backtest_run_id}/status` | Reader | Evidence summary + linked candidate/run-plan + journal link paths for one run. |
| POST | `/research-validation/promote` | Trader | Promote eligible evidence into paper validation queue (idempotent per org + backtest run). |

Rate-limit keys: `research-validation:read` (120/hr), `research-validation:write` (60/hr).

### Promote request

```json
{
  "confirm": "PROMOTE_RESEARCH_VALIDATION_CANDIDATE",
  "backtest_run_id": "<uuid>"
}
```

Exact confirmation phrase is required. Mismatch returns `422`.

## Eligibility and warnings

Hard blocks (promotion refused):

| Condition | Block reason |
|-----------|--------------|
| Backtest not `completed` | Run not finished |
| Missing `strategy_version_id` | Version linkage required |
| Missing `oos_metrics` in result | OOS metrics required |
| Evidence tier3 | Insufficient evidence |

Soft warnings (promotion may still succeed for tier1/tier2):

| Warning code | Meaning |
|--------------|---------|
| `insufficient_confirm_sample` | Non-backtest confirm trade count below `backtest_tier1_min_confirm_trades` (default 20). |

Tier classification reuses `SetupEvidenceService` thresholds from `Settings` (`backtest_tier1_*`, `backtest_tier2_*`). See [backtesting.md](./backtesting.md#settings-defaults-from-settings).

## Idempotency

An active candidate (`queued` or `reviewing`) for the same `(organization_id, backtest_run_id)` returns `already_exists=true` without creating duplicate rows. Partial unique index: `uq_pvc_org_backtest_active` (migration `n0c1d2e3f4a5`).

## Synthetic alert and draft scaffolding

Promotion does **not** bypass the existing candidate queue model:

1. **Synthetic alert** — `PaperAlertType.RESEARCH_VALIDATION_PROMOTION`, delivery disabled, dedup key `research_validation:{backtest_run_id}`.
2. **Synthetic draft** — `prep_status=ready_for_validation`, complete checklist, conservative risk mode, thesis/entry/invalidation copied from research context.
3. **Candidate** — `promotion_source=research_validation`, provenance FKs/hashes/tier populated, `candidate_status=queued`.

Legacy alert-draft promotions leave provenance fields `null` (backward compatible).

## Provenance fields on candidates

Extended on `PaperValidationCandidateItem` (nullable for legacy rows):

| Field | Description |
|-------|-------------|
| `promotion_source` | `research_validation` or `null` (legacy alert-draft) |
| `backtest_run_id` | Source backtest run |
| `strategy_id`, `strategy_version_id` | Strategy linkage |
| `dataset_hash`, `config_hash`, `result_hash` | Frozen snapshot hashes |
| `evidence_tier` | `tier1` / `tier2` / `tier3` at promotion time |
| `sample_size`, `oos_expectancy`, `regime` | Measured context |
| `evidence_snapshot` | JSON blob: measured + thresholds + warnings at promotion |

## Audit events

Resource type `research_validation`, event type `paper_validation_runtime`:

- `research_validation_promote_requested`
- `research_validation_promote_blocked`
- `research_validation_promote_already_exists`
- `research_validation_candidate_created`

## Safety

- Tenant isolation via `organization_id` on all queries.
- Mutations require `OWNER` or `TRADER`; reads allow `VIEWER`.
- No changes to risk engine, execution service, or exchange adapters.
- Frontend route: `/research-validation` (advisory UI with confirmation phrase).

## Migration

Apply through head **`n0c1d2e3f4a5`** (after `m9b0c1d2e3f4`):

```bash
cd backend && uv run alembic upgrade head
```

## Disclaimer

Research validation promotion is an advisory handoff into paper review. It does not authorize real trading, guarantee performance, or override risk controls.
