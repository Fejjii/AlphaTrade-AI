# Brain Agent Daily Review read integration

Branch `codex/agent_daily_review_001` starts exactly at
`315ddd875567b60d3956f5f60ae6754f124642b1`. The existing authenticated
`POST /agent/turns` now reads `DailyReviewService` through `daily_review.read`.
The deterministic Daily Review package and its calculations are unchanged.

The nine requested questions route to this read: what happened today, setups
seen, trades taken, blocked trades, today's performance, recorded mistakes,
lessons to review, missing evidence, and what to review tomorrow. Questions
without a day use today in UTC; yesterday and a single `YYYY-MM-DD` are also
supported. General performance/setup questions keep their existing routes.
Explicit actions take precedence; live-trading requests retain their refusal.

For a particular local calendar day, supply the typed read action:

```json
{
  "message": "How did I perform today?",
  "action": {
    "name": "daily_review.read",
    "arguments": {
      "day": "2026-10-01",
      "timezone": "Europe/Berlin",
      "focus": "performance"
    }
  }
}
```

Inputs are `day` (optional, wins over relative_day), `relative_day` (`today` or
`yesterday`), `timezone` (IANA, default UTC), and `focus` (`summary`, `setups`,
`trades`, `blocked`, `performance`, `mistakes`, `lessons`, `evidence`, `tomorrow`).
Future days, invalid timezones/dates and extra input fields fail. Ambiguous
multi-day requests require one calendar day. Tomorrow's review suggestions use
the selected recorded day's lessons, mistakes and quality limitations; they
do not predict tomorrow's market or create a schedule.

Persisted membership authorizes the read before the service sees the API's
organization/user identity. Owner/trader/viewer members may read through the
service; the existing HTTP Agent endpoint still requires its Trader role gate.
Caller identity cannot be supplied through action arguments. Watcher/setup
evidence remains organization-wide; journals, lessons, risk and PnL retain the
service's user scope.

The turn returns the unchanged typed `DailyReview/v1` in `daily_review` and
retains it in the existing assistant transcript payload. It preserves review
identity/hash, source IDs/timestamps, all four evidence sections, counts,
account-level PnL and limitations. The visible reply separates facts, user
observations, system inference and research suggestions. It quotes stored text
as a preview, cites complete displayed source IDs and discloses omitted rows;
the accompanying review retains every row and source. Counts are recorded item
counts, not deduplicated trades or setups.

Daily Review turns bypass general retrieval, market reads and the narrative
model. Empty reviews mean unavailable evidence rather than an inactive market
or zero performance. Missing PnL, incomplete sums and insufficient samples are
explicit; no currency, cross-account total, unrealized PnL, missed profit or
profitability claim is added. Source failures propagate instead of producing
empty reviews. Current-day reads are current snapshots at the returned generation
time; mutable records cannot establish historical as-of state. The existing
request transaction owns these reads; no new snapshot-isolation guarantee is
introduced.

Validation covers all nine questions, unchanged service payloads, provenance,
organization/user isolation, backtest/manual performance exclusion, missing
measurements and sample limits, calendar/timezone and DST boundaries, permission
checks, live refusal, invalid inputs, failure propagation, bounded replies,
HTTP response/catalog contracts and transcript-only writes. Adjacent Daily
Review and Agent regression tests, Ruff and targeted strict mypy checks pass.

Handoff: review the draft PR. No Daily Review calculations, execution behavior,
worker activation, scheduler, proactive delivery, Telegram, migration or frontend
workflow is changed. The next integrations remain separate work. Do not merge
or deploy as part of this task.
