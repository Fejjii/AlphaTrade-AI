# BloFin demo Dashboard integration

Base: latest `main` at `28b7dab06f85daa05cb9bf04dbaee52bbf413994`.
Branch: `codex/blofin-demo-dashboard`, isolated worktree.
PR229 merged during implementation. The final branch is rebased onto merged
`main` at `d9ebf87e9d50685da5078bdd4d590757b0a9c1c0`.

The Dashboard now presents the configured BloFin demo venue account above the
paper portfolio. Balances remain in their individual assets; native positions
show long/short direction, exact contract quantity, entry, mark, leverage and
observed unrealized PnL. Missing optional values remain unavailable. Account
snapshots do not establish order fills, protection linkage or realized results.
They can include positions placed outside AlphaTrade. Recent Journal rows now
show their recorded exchange/source so demo history is distinguishable.

## Retrieval and refresh contract

| Action | Behavior |
| --- | --- |
| Open Dashboard / Dashboard Refresh | Authenticated `GET /dashboard/demo-account`: read the latest saved snapshot for this organization, with no venue request. |
| Refresh demo account | Owner-only `POST /dashboard/demo-account/refresh`: reuse `BloFinSyncService.sync`, persist its snapshot/audit, return the typed projection. Rate limited to 30 refreshes per organization/user/hour. |
| Organization trader/viewer | May read their organization snapshot; cannot fetch native account data. |
| Native refresh | Existing account provider only: GET API-key permissions, balances and positions. Existing separate read-only credential mode and governed demo-account mode are both supported. |
| Expiry | Server applies the configured freshness window; the browser also changes the label to stale when `expires_at` passes, without a venue poll. |
| Failure | Latest failed sync is unavailable, with no older success fallback. HTTP failure clears the displayed account values and permits a saved-read retry. Errors/provenance payloads are excluded from the Dashboard response. |
| Bounded result | Truncated balance/position lists are explicit. An incomplete position list has no full account count. |

Both new endpoints use `Cache-Control: private, no-store`. Account reads require
the existing safe demo configuration. Inactive and never-synced states do not
claim zero balances or no positions. The browser prevents duplicate native
refresh clicks, drops late saved reads, and prevents a Dashboard read from
overtaking an in-flight native refresh. During loading it explicitly identifies
the prior saved snapshot. Refreshing account data does not refresh execution
commands, reconcile fills/protection, update Journal, or authorize a trade.

## Shared changes and dependency

Reconciliation PR [#229](https://github.com/Fejjii/AlphaTrade-AI/pull/229), branch
`codex/manual-demo-reconciliation`, was inspected at
`02f233d7ed131a7b819dc9d86d197334151c64a7`. Its order/fill/protection parsing,
manual command service, Journal projection and Agent venue selection are owned
there. None of those files is changed by this PR. Only the completed, merged
main change was incorporated by rebase; no unfinished branch was merged.

There is **no new interface dependency on PR229**. This integration uses existing main
interfaces: `BloFinSyncService.sync/latest`, `BloFinSyncSnapshotItem`,
`BloFinDemoSyncSnapshot`, the account provider and Journal list `exchange/source`.
The native account section works even when an existing execution command remains
on hold or lacks a Journal entry. **Review and release reconciliation first;
release this separate Dashboard PR afterward.** PR229 is merged; its deployed
same-order acceptance remains separate. If account credentials are rotated, fetch a new account snapshot
before interpreting saved historical data; the existing sync schema has one
configured demo account and no account-selector/fingerprint contract.

The only shared provider change is in `blofin_account.py`: account quantities and
response rows no longer silently become zero or disappear when malformed. Required
balance/size fields must be finite; absent optional position metrics remain `None`.
Signed net sizes are preserved. This affects read-only sync and other existing
account consumers; valid provider, exchange-probe and integration cases were
included in regression verification. Instrument, permission, leverage-setting,
transport and execution interfaces remain unchanged. No schema migration or new
credential/activation flag is introduced.

## Verification and acceptance

Verification uses authenticated SQLite fixtures with foreign keys and
`httpx.MockTransport` native account responses, plus component/API tests and
Chromium desktop/mobile fixtures. Browser fixtures are presentation evidence,
not native exchange proof. Exact test results are recorded in the PR.

After reconciliation releases and this PR deploys, an owner can open Dashboard,
fetch the existing configured demo account, and compare balances and the existing
BTC position with BloFin. Check timestamp, contracts (not BTC units), direction,
mark and PnL. Dashboard Refresh should only reread the saved snapshot; Refresh demo
account should fetch a new one. Confirm a second organization cannot read this
organization's snapshot, and readers cannot refresh it. Age a saved snapshot or
wait for its configured expiry to check the stale label. A failed sync must show
unavailable, never an invented flat account. Review command reconciliation and
SL/TP in their existing workflow independently.

No live exchange reads/orders, deployment, credential changes, activation or
reconciliation hold changes were performed for this PR.
