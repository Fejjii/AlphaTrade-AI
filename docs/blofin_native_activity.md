# BloFin native activity mirroring — AT-118

The additive package stores authenticated native completed orders and individual fills,
including direct BloFin activity and verified AlphaTrade matches. It supplies history
evidence for later Dashboard and Journal integration; it does not calculate portfolio
performance or change execution/reconciliation.

## Baseline and ownership

Recorded starting revision: `4e515ddb8de20f4b2cfb7498ed6ce9bbbd2d2f2f`.
PR237 was refreshed before work; the **actual fork revision** is
`bda597c2fffbf1a49beadc64d757100808094ca2` on
`codex/reviewer-wave-integration`. Isolated feature branch: `codex/blofin-native-activity`.
The composer correction and frontend voice owner branches were not modified.

Own new backend `blofin_activity` provider, schema, database model, repository,
configuration/service, route, worker entry point, three focused test modules and
`a10blofinactivity001`. Shared edits are limited to:

- `core/blofin_readonly_access.py`: two bounded, signed history GETs and extraction of
  the existing restricted client factory. The explicit activity capability can use
  dedicated read-only credentials in either internal paper or demo paper mode.
  The original account-sync factory retains its original activation/mode restrictions.
- `db/models.py`: register three new additive tables.
- `main.py`: register one authenticated GET route.
- `.ai/TASKS.md`: append this task; `.ai/DECISIONS.md`: record its authority boundary.

No frontend, generated client, Agent turn, execution-control or CI workflow edits.

## Verified official contracts and coverage limits

Checked October 10, 2026 against the [official futures API](https://docs.blofin.com/index.html).
[Order history](https://docs.blofin.com/index.html#get-order-history) is
`GET /api/v1/trade/orders-history`; [fill history](https://docs.blofin.com/index.html#get-trade-history)
is `GET /api/v1/trade/fills-history`. Both accept millisecond `begin/end`, up to 100
rows, and mutually exclusive `after/before`. `after` retrieves earlier records using
`orderId` for orders and `tradeId` for fills. Responses descend newest first.
Orders cover completed states; fills carry per-fill quantities, price, fee and optional
closing PnL. Quantities are contracts; [instrument metadata](https://docs.blofin.com/index.html#get-instruments)
describes contract value and currencies. History fee currency and a retention duration
are not specified. No retention guarantee or settlement-currency fee assumption is made.
[API-key information](https://docs.blofin.com/index.html#get-api-key-info) supplies `uid`
and separate `parentUid`; the latter is not the subaccount identity.
[Rate limits](https://docs.blofin.com/index.html#rest-api-limits) include 30 trading requests
per 10 seconds per UID, 500/minute and 1,500/five minutes per IP. Demo uses the documented
demo origin. The order time-filter basis (creation versus update) is unspecified.

Implementation limits remain explicit even after an empty terminal page:

- Initial lookback defaults to seven days, configurable from one to 30 days. This is
  a local ingestion bound, not an asserted venue retention period.
- No pending order, separate TPSL/algo ancestry, spot, copy-trading, funding or older
  history ingestion. Fills for an order absent from the bounded order window remain
  native without fabricated linkage. Missing instrument metadata stays unknown.
- Current metadata is captured alongside each first-observed fact. Its timestamp and
  exact multiplier are exposed; it does not prove historical contract conversion.
- `partial_coverage` is always true. Exhausting an endpoint window does not prove
  complete account performance. Flat positions never manufacture realized PnL.
- Canonical API shapes are supported. Missing identity, malformed pages or incompatible
  repeated final facts stop safely and expose a sanitized error. Legitimate venue
  corrections require review; the package does not overwrite immutable historical facts.
- Deterministic fixtures verify implementation, not actual demo API availability or
  the owner's manual-order incident.

## Account identity and credential rotation

Every fact, checkpoint, stored binding and API continuation is scoped by
`(organization_id, demo, authenticated uid)`. The single configured connection is pinned
by `BLOFIN_ACTIVITY_ORGANIZATION_ID` and `BLOFIN_ACTIVITY_EXPECTED_UID`; there is no
organization/account selector supplied by the API caller. Existing organization reader
RBAC applies. Other organizations receive 404.

The worker queries `query-apikey` before initial binding and again immediately before
each history page. It requires exact `uid` equality, read permission, no trade permission,
and no transfer/withdrawal scopes. Only dedicated `BLOFIN_READONLY_API_*` credentials
are used. Stored execution credentials remain sealed from this package.

A SHA256 digest of the dedicated credential tuple is only an opaque binding selector;
it is never the account identity and is never returned by the API. Rotation to the
same UID re-verifies the new binding and resumes the same scoped cursors. Before that
verification, reads return `identity_status=unverified`, empty items and no reused
coverage. A missing/different UID records `identity_unverified`, withholds history and
never creates a replacement trading account. Changing the UID pin selects a separate
namespace with its own facts and initial window. Prior account data is retained.

The read API performs stored reads only. `identity_verified_at`, credential binding,
error status and freshness describe the last verified connection, rather than claiming
a new live probe on each HTTP request.

## Transactions, interruption and bounded synchronization

`run_activity_sync(engine, settings, config, shutdown=...)` is an importable single
worker tick. `python -m app.workers.blofin_activity` is a single-tick CLI with SIGINT/SIGTERM
handling. Nothing mounts a sync POST, registers a schedule, adds a service or starts it
from app lifespan. `BLOFIN_ACTIVITY_ENABLED=false` is the default.

Defaults: four history pages, 100 rows/page, 30-second dispatch budget, five-minute
window overlap, five-minute stale threshold. Maximum configured pages/budget are
10/60 seconds. The activity client limits all its requests to one/second, GET retries
to two and request timeout to ten seconds. Deadline/shutdown guards run before sends,
retries and persistence; an in-flight request may finish its bounded timeout before
cooperative shutdown completes. Coordinate aggregate UID/IP budgets with other clients.

A PostgreSQL session advisory lock serializes each account scope across workers;
competing ticks return `busy`. Orders and fills alternate so a bounded backfill cannot
starve one stream. A checkpoint fixes its `begin/end` window until an empty page.
Short nonempty pages do not imply completion. Repeated/nonadvancing frontiers or a
scan exceeding 1,000 distinct frontiers fail explicitly.

Each page transaction inserts immutable facts and advances its checkpoint together.
The native primary key is `(organization, environment, uid, kind, native_id)`.
Exact replays are no-ops. Different content for the same identity, conflicting
order/fill instrument or side, or a foreign checkpoint rolls back the entire page.
Earlier successful pages remain committed after interruption or failure. New windows
overlap the previous end; an outage beyond lookback sets `gap_detected` permanently.

Errors preserve the last successful sync and facts. A rate failure persists five-minute
backoff; other expected provider/identity/conflict failures persist one minute. Ticks
within backoff issue no network request. Error text and credential payloads are not
persisted; only fixed safe codes are exposed.

## Authenticated API and accounting contract

`GET /exchange/blofin/activity?kind=fill&limit=50&cursor=<opaque continuation>`

`kind` is `fill` (default) or `order`; limit is 1–100. The bearer-authenticated route
permits organization readers. There is no HTTP synchronization or mutation operation.
Unconfigured pins/credentials refuse safely; an unverified current binding returns
an empty, explicitly unverified page. Wrong-organization reads return 404; invalid or
foreign account/stream cursors return 422. Continuations are scoped keyset positions
ordered by native event milliseconds and native ID descending. They are not a frozen
snapshot: newly ingested newer facts are obtained by restarting at the first page.

Machine-readable V1 route and response schemas:
[blofin_activity_v1.openapi.json](contracts/blofin_activity_v1.openapi.json).
Schema SHA256: `b934f0e40ec77a9e8fbd50093a465ba04e6d8df93b25e653d60c1b1406b0274b`.
The application response model remains the authority; the exported route schema does
not replace the frontend owner's full generated clients.

| Field group | Contract |
| --- | --- |
| Account | `organization_id`, `venue=BLOFIN`, `environment=demo`, `account_uid`, identity status/error and verification time |
| Native identity | `kind`, `native_id`, `order_id`, optional `trade_id/client_order_id`, instrument and native side/position side |
| Exact facts | Decimal **strings**, contracts unit, requested versus accumulated order fill quantity, each individual fill size/price; millisecond timestamp **strings** |
| Origin | `native` or `alphatrade_matched`, optional existing command ID; unknown strategy remains null |
| Money | Original signed fee and explicit currency if returned; available native closing PnL string; unavailable PnL/currency/funding remain null |
| Metadata | Observed multiplier/type/base/settlement currency and observation time; nullable for missing instruments |
| Coverage | Per-stream requested bounds, native checkpoint, window exhaustion, completed bounds, gaps, successful sync/attempt/error/backoff timestamps |
| Freshness | `fresh`, `stale`, `never_synced` or `unverified`; fresh requires recent successful pages and recent window end for both streams, with no current errors |

Match only the actual native echoed `clientOrderId` to an existing unique
`VenueSubmitEffect`, scoped by organization and a matching `BLOFIN_DEMO` revision,
account, instrument and side. Fills inherit linkage through their exact native
`orderId`. An AlphaTrade-looking name, time proximity or position disappearance is
insufficient. No command, strategy, Journal trade or execution receipt is manufactured.

**Dashboard/Journal counting rule:** canonical individual fill identity is
`(organization, demo, uid, tradeId)`. Count each native fill once. Orders provide
context/accumulated quantities, not another fill amount. A matched command is a link
to the existing lifecycle, not an additional trade; do not add its local execution
projection to the same native totals. This API never unions simulator records or
updates current manual/strategy performance. Consumers must keep incomplete coverage
and unknown fees/funding visible instead of presenting inferred net returns.

## Migration and rollback

Generated from isolated PostgreSQL using SQLAlchemy/Alembic autogeneration filtered
to the three new tables. Historical migrations were not modified.

Chain: `a9knowledgeoutbox001 -> a10blofinactivity001` (one head).
Upgrade before any explicitly approved worker tick. The migration adds account bindings,
native facts and checkpoints with scoped keys, constraints and foreign keys; it does
not backfill execution records or change existing tables. Disposable PostgreSQL upgrade,
downgrade and re-upgrade verify that an existing organization survives.

Rollback first stops/disarms activity ticks; retaining additive tables preserves history.
Qualify a migration-aware rollback API image: a baseline image that automatically runs
`alembic upgrade head` cannot locate newly applied `a10blofinactivity001` because its
migration directory lacks that revision. Do not blindly restart that image against the
new schema or weaken its migration guard. If schema removal is separately authorized, export the activity
tables before `alembic downgrade a9knowledgeoutbox001`: downgrade removes **only these
new tables and their activity data**. Existing execution, Journal, risk and knowledge
history remains. No deployed migration or rollback was run by this implementation.

## PR237 integration instructions

1. Review the feature diff against the exact fork revision above. Keep the composer
   correction and voice package independent; only the three shared code edits listed
   above need conflict coordination.
2. Integrate the additive migration after `a9knowledgeoutbox001`; verify one head and
   update supervising release/migration expectations. Do not weaken runtime migration
   guards or activation gates to make a stale head acceptable.
3. The frontend/generated-client owner must regenerate the full OpenAPI artifacts after
   route integration (`npm run api:generate`, then `npm run api:check`). The new route
   changes the full schema hash, so the existing drift check will require that owner
   step. Generated frontend files were deliberately not edited here.
4. Use the V1 contract for later Dashboard/Journal work and follow the counting rule;
   preserve the current verified manual lifecycle performance scope.
5. After review, schema upgrade and separately authorized credentials/pins, an existing
   worker can call the bounded entry point. Keep synchronization disabled until then.
   Verify a direct native trade and an existing AlphaTrade command against the same
   authenticated UID through read-only history before making runtime coverage claims.
6. The [manual incident](reviewer_wave/manual_order_incident.md) still needs the exact
   failing sanitized request/error/request ID and corresponding server/native evidence.
   This package does not diagnose or claim to fix that incident.

## Milestones and evidence

| Package milestone | Weight | State |
| --- | ---: | --- |
| Refreshed isolated base, governance and official contracts | 20% | Complete |
| Restricted provider, identity and exact account-scoped schema | 20% | Complete |
| Atomic/resumable sync, verified linkage and read API | 20% | Complete |
| Focused verification, API/ownership and migration/rollback notes | 25% | Complete: 55 new and 186 existing focused cases |
| Batched publication and one draft feature PR | 15% | Pending |

Progress before final publication: **85% once verification closes; 100% after draft PR
publication**. Review, client regeneration, supervised native acceptance and deployment
are subsequent integration/release tasks rather than hidden implementation milestones.
Exact commands/results and final completion status are in
[blofin_native_activity_verification.md](blofin_native_activity_verification.md).

Implementation blockers: none. Integration dependency: generated schema owner update.
External acceptance and Mac/iCloud mirror remain unverified. No complete backend CI,
merge, deployment, runtime flag change, external order or Telegram message was performed.
