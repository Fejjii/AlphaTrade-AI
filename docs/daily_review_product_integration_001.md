# Daily Review product integration handoff

Branch `codex/daily_review_product_integration_001` starts exactly at PR169 head
`315ddd875567b60d3956f5f60ae6754f124642b1`. The draft targets
`codex/proactive_daily_review_001` to isolate the product integration.

Authenticated readers (owner, trader, viewer) can call
`GET /dashboard/daily-review?date=2026-10-01&timezone=Europe/Berlin`.
Timezone defaults to UTC; omitted date uses the current calendar day in the requested
zone. Invalid dates/timezones return 422. Organization and user scope come only from
verified current membership, never query parameters. Responses use `private, no-store`
and the existing dashboard read rate limit.

The API returns the existing `DailyReview/v1` service contract unchanged. The trader
Dashboard includes date/timezone controls, item counts, expandable facts, user
observations, system inference, research suggestions, PnL by source/account, source
IDs/timestamps and coverage limitations. Loading and failures remain explicit;
failures hide stale metrics and support retry. Forming setups retain watch/partial_match
codes, and blocked reasons remain recorded codes.

Calculations and service readers are unchanged. No recorded closes means unavailable
PnL; missing values and incomplete cohorts stay visible. Win rate and expectancy
require five measured closes with no missing PnL. Currency and cross-account totals
remain unavailable. Review items are not unique-candidate counts. This reads current
recorded snapshots for a day; it does not persist a historical as-of reconstruction
or add stronger database snapshot isolation than the existing request session.

Validation covers authenticated API/service equivalence, tenant and same-tenant
private-user isolation, current membership and read roles, invalid inputs, DST and
local-date defaults, failure propagation; frontend coverage verifies dashboard
integration, classification separation, provenance, sample/missing metrics,
separate accounts, date/timezone submission and retry. Existing Daily Review and
adjacent dashboard tests, backend Ruff/format, frontend TypeScript and focused
ESLint checks are included.

No core Agent orchestration, execution, Telegram, scheduler, worker, persistence or
schema changes. Review this draft after PR169; Agent Paper Execution V4 remains
separate. Stop after push and draft PR creation: no CI wait, merge or deployment.
