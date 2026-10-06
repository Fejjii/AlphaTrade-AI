# Approved plan targets in Journal

The canonical execution producer omitted `planned_targets` from its instrument
payload. The Journal projector already accepted this field, so both the approved
plan projection and a governed demo's first verified fill could create a Journal
trade with no targets despite a complete immutable approved plan.

New events copy each approved target in semantic order: `price.value` becomes
`price`, `quantity_fraction` becomes `size_fraction`, and `order` becomes the
`TP1`, `TP2`, etc. label. Event payloads retain exact decimal strings because
canonical hashes prohibit binary floats. Projection converts those values to the
existing `PlannedTarget` schema (Decimal price, numeric size fraction). Reserved
runner allocation is not redistributed; no plan, strategy, approval, permission,
risk, execution activation or credential is changed.

Historical approved-plan and fill replays reuse their original recorded payloads.
They do not acquire new targets or new event hashes. Existing empty projections
require the explicit repair below; reads and execution replay do not repair them.

## Supervising repair procedure

This procedure has **not been run against live infrastructure**. Review the PR,
deploy the approved code, then have the supervisor confirm the tenant, authenticated
owner and execution account of the known trade. Use the service's existing secure
database configuration; do not put credentials in the command or review record.
The script does not contact a venue or submit orders.

From `backend/`, first preview exactly one trade; replace the three scope UUIDs
with independently verified values:

```bash
PYTHONPATH=src python scripts/repair_journal_plan_targets.py \
  --organization-id <verified-organization-uuid> \
  --user-id <verified-owner-uuid> \
  --account-id <verified-execution-account-uuid> \
  --journal-trade-id 83a7063d-c83f-4a91-a343-0f231f9585d3 \
  --revision-id 9c8c5c4f-3a8c-5301-bb63-b6b6a9bdc1b2
```

All five UUID arguments are mandatory. Default mode rolls back without writes.
Review the returned plan hash and ordered target list. For the reported case,
expect `status: would_repair`, `dry_run: true`, and:

```json
"planned_targets": [{"price": "84714.10", "size_fraction": 1.0, "label": "TP1"}]
```

Before applying, record the immutable plan revision/content hash, lifecycle event
payloads/hashes and projection receipt hashes, together with the Journal's status,
economics, lineage and projector watermark. If the preview disagrees with the
reviewed approved plan, stop and investigate; never alter the plan to fit the repair.

After review, run the same command with `--apply` appended. Expect `repaired`.
Rerun the default preview and then, if needed, the apply command: both must report
`already_correct`; repeated apply must create no additional repair audit event.

Verify the tenant-scoped Journal API/UI shows the target price and full allocation.
Compare the recorded plan/event/receipt hashes and other Journal fields with the
pre-repair snapshot. Only `planned_targets`, `projector_lock_version` and the
projection's update timestamp should change. Confirm one audit row with request ID
`journal-target-repair`, action metadata `repair_planned_targets`, exact trade,
revision and plan content hash. Record this supervised evidence in the release handoff.

## Checks and limits

- Repair requires PAPER_EXECUTION provenance, the exact tenant/owner/account,
  canonical immutable plan and envelope hashes, matching Journal helper lineage,
  an ALLOW command and its consumed PAPER authorization, and matching lineage in
  every recorded canonical event for this lifecycle.
- Missing or conflicting lineage, another tenant/owner/account/revision, or
  nonempty targets that disagree with the approved plan are refused. It never
  replaces a conflicting projection or guesses missing provenance.
- Apply holds the existing lifecycle advisory lock and Journal row lock, then
  rechecks scope and lineage. Concurrent/repeated applies converge on one update
  and one audit event. Audit failure prevents mutation; the caller owns commit.
- The repair changes the existing Journal projection only. It cannot edit/delete
  immutable plans, lifecycle events, receipts, fill facts or historical hashes.
  CLI scope is a single trade; there is no all-tenant or bulk repair switch.
- Exact allocation decimals remain in immutable events. The existing Journal API
  exposes a float allocation, retaining its existing numeric precision limits.
  Neither runner execution nor protective order behavior is changed.

Focused PostgreSQL projection/replay/isolation/concurrency tests and simulated
governed venue-fill regressions provide development evidence. The final consolidated
release gate remains one supervisor-approved exact-SHA CI dispatch with
`full_backend=true`, including evaluation and browser smoke. This task does not
run the full suite or establish deployed/live acceptance.
