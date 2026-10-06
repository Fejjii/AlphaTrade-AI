# Presentation MVP: minimum planned reward/risk release

This is prospective implementation and local development evidence, not deployment,
complete backend acceptance or a live account repair. Base main is
`e75e8bf411918094bd50eaf3d633d459efd40b40` (PR215); its deployment is a supervising
report. Existing strategy versions, economic records and immutable hashes remain intact.

## Deterministic entry policy

`planned-gross-weighted-rr/v1` requires allocation-weighted **gross planned R ≥ 1**
for linear instruments. Long entry uses the upper permitted entry-zone boundary;
short entry uses the lower boundary. Risk is full-position entry-to-stop distance.
Reward is the sum of each target's profit distance multiplied by its approved
quantity fraction. Targets plus reserved runner must allocate exactly 100%.
An unpriced runner contributes zero promised reward; its allocation is never
redistributed. For example, 80% at 0.5R and 20% at 3R is exactly 1R; 50% at 1R
and a 50% unpriced runner is only 0.5R. Exact rational comparison avoids Decimal
context rounding at the boundary. Invalid direction, units, allocation, nonfinite
values, excessive decimal precision and inverse instruments refuse entry.

Fees, funding and slippage allowances remain in existing deterministic maximum-loss
and capacity checks. This floor measures gross price distances; it does **not** promise
net 1R after costs, actual execution prices or a profitable realized outcome.
A future net-R policy needs its own explicit review and cost definition.

The same guard runs before new canonical plan storage, authorization issuance,
atomic execution claim and final governed demo entry dispatch. Old plans remain
parseable and replayable; a historical low-R plan cannot obtain new authority or
an unsent demo entry under this policy. Existing reconciliation, protection,
exits, idempotency, fencing, reservations and kill-switch behavior remain authoritative.
No targets are moved to pass. If an active definition needs different exits, author,
compile and explicitly approve a new version through existing governance; never
silently edit or approve the active version. Refused setups may still be detected.

## Reported BTC short and Journal repair

Reported prices imply reward `85111.40 − 84714.10 = 397.30`, risk
`85720.80 − 85111.40 = 609.40`, and **0.6519527404…R (about 0.65R)**.
Source inspection found no minimum planned-R check in the previous canonical plan,
authorization or claim policy. Eligibility, sizing and approval therefore did not
establish a 1R floor. This explains the policy gap, not an independently verified
live authorization trace. The supervisor must inspect the linked immutable plan,
eligibility, exact authorization and execution receipts before attesting that trade.

Reuse the existing [single-trade audited repair procedure](journal_plan_target_repair.md).
From `backend/`, using the service's secure database configuration, preview:

```bash
PYTHONPATH=src python scripts/repair_journal_plan_targets.py \
  --organization-id <verified-organization-uuid> \
  --user-id <verified-owner-uuid> \
  --account-id <verified-execution-account-uuid> \
  --journal-trade-id 83a7063d-c83f-4a91-a343-0f231f9585d3 \
  --revision-id 9c8c5c4f-3a8c-5301-bb63-b6b6a9bdc1b2
```

Confirm `would_repair`, target `84714.10`, allocation `1`, and reviewed plan hash.
Record original plan/event/receipt hashes and Journal watermark. After supervising
review, append `--apply` to this exact scoped command. Expect `repaired`, one
`journal-target-repair` audit, then `already_correct` on repeat with no extra audit.
Verify only projection targets/lock/update timestamp changed. Stop on any refusal,
conflicting nonempty targets or lineage disagreement; never change immutable evidence.
**No live repair was run by this task; live access was unavailable.**

## Agent evidence and acceptance

The recorded-trade read now supplies authenticated owner/version-scoped compiled
setup, the exact candidate/assessment/plan detector decision and integrity-checked
learning assessment summary with usable record references. A current mutable setup
projection does not prove an earlier decision. Stored assessment state/reasons are
not a complete assessment rule snapshot or new execution authority. Missing scoped
records are reported separately from temporarily unreadable stores, whose existence
is unknown. Specific material missing warnings remain visible once rather than
being repeated as a generic missing-evidence warning. Full evidence stays expandable.

1. Review the exact PR SHA and focused evidence. Keep demo disarmed and real trading
   disabled. Consolidate reviewed release changes before **one** exact-SHA CI dispatch
   with `full_backend=true`; complete backend, evaluation and browser smoke must pass.
   This coding task does not dispatch it or equate focused checks with that gate.
2. Supervise deployment and verify matching API/worker SHA and migration readiness;
   a heartbeat alone does not establish fresh evaluations. Run the scoped repair
   above after checking ownership and lineage; record idempotence and hash preservation.
3. Repeat the latest BTC short question and “Explain that trade.” Verify plan versus
   fill, 0.65R historical comparison, target source, setup/assessment references,
   actual authorization and venue, and truthful unique material missing warnings.
   Read failure must not be presented as proof the record never existed.
4. Preserve the existing Knowledge preview and explicit-save acceptance. Import does
   not approve strategies, change risk or create Journal trades. Live model quality
   and deployed usability require this supervised acceptance.
5. Demo expansion remains a separate reviewed/configured workstream. Apply the
   [lifecycle acceptance](governed_demo_lifecycle.md) and exact instrument checks;
   an otherwise eligible Nested plan below 1R must refuse, never move its targets.
