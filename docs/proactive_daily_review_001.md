# Daily Review service and handoff

Branch `codex/proactive_daily_review_001` starts exactly at
`7df8bcc6e42ba68ab2194b980de1792abeceabcc`. The new `app.daily_review`
package builds a deterministic `DailyReview/v1` record from existing authorities.
It adds no tables, migrations, endpoints, scheduler, Agent edits, Telegram delivery,
market calls or execution capabilities.

## Calling the service

```python
from datetime import UTC, date, datetime
from app.daily_review.reader import DailyReviewService
from app.daily_review.service import daily_window

# Caller must authorize both organization_id and user_id, and own a consistent
# read transaction (repeatable-read when a concurrent-write snapshot is required).
review = DailyReviewService(session).review(
    organization_id=organization_id,
    user_id=user_id,
    window=daily_window(date(2026, 10, 1), "Europe/Berlin"),
    generated_at=datetime.now(UTC),
)
serialized = review.model_dump_json()
```

`daily_window` uses a local calendar day with UTC half-open boundaries, including
23/25-hour daylight-saving days. The reducer requires an explicit generation time;
its content hash and UUID exclude that time. Equivalent source order and duplicate
copies converge; conflicting copies fail. Changing recorded evidence changes the
review identity. Mutable source snapshots cannot reconstruct a historical as-of
view; callers can retain serialized review records through a later approved store.

## Records and interpretation

| Review content | Existing source and scope |
| --- | --- |
| Watcher activity, setup states, blocked reasons, data quality | Organization-level `paper_evaluation_observations`; retains observation ID, upstream source/event/version, hash and occurrence time |
| Paper entries, closes, daily net PnL | User-scoped canonical `journal_trades`, paper_execution/paper_validation sources only; entry/exit timestamps |
| Risk events | User-scoped `risk_events`, recorded rule/severity/action at event_at |
| Journal entries and reflections | User-scoped `journals` and canonical journal snapshots at updated_at; stored mistakes/lessons remain observations |
| Mistakes, lessons, strategy observations | `journal_trade_observations` joined to a scoped parent trade; explicit recorder distinguishes user observations from system inference |
| Lesson candidates and research suggestions | User-scoped `lesson_candidates`; pending candidates generate a suggestion to review, never a rule change |
| Missed setups | System inference only when a recorded confirmed setup explicitly reports reject, skip or block; no inference from missing fills |

Forming states retain the canonical `watch` and `partial_match` codes. They do not
predict confirmation. All content items have source IDs and timestamps. Four typed
sections separate facts, user observations, system inference and research
suggestions. Mutable evaluation narratives are excluded. Counts describe review
items by topic, not unique candidates aggregated across lifecycle stages.

PnL is the sum of measured, recorded realized net PnL by paper source and account.
Sources and missing values remain visible. No recorded closes yields unavailable
PnL, not zero. Partial recorded sums are marked incomplete. Currency is not present
in these records, so the service supplies no currency conversion or cross-account
total. Accounts must use consistent accounting units. Win rate is positive net
closes divided by all measured closes (including breakeven); expectancy is mean net
PnL. Both require at least five measured closes with no missing values in that
cohort, matching the existing paper-evaluation sample threshold. These daily
sample statistics do not establish profitability. No unrealized, counterfactual,
market-condition or missed-profit values are manufactured.

Recording coverage is not guaranteed; absence of evidence does not prove inactivity.
Mutable journal snapshots lack complete edit history. JournalTrade reflects the
canonical recorded paper lifecycle; the service does not reconcile venues or backfill
missing trades. Other users' private journal, risk and lesson records are excluded;
shared Watcher/setup observations remain organization-wide. Database failures and
invalid payloads propagate rather than becoming empty reviews. SELECTs suppress
autoflush and neither commit nor alter pending caller writes.

## Validation and next boundary

Focused tests cover source classification/provenance, organization/user isolation,
backtest/manual exclusion, entries versus close-day attribution, half-open and DST
boundaries, replay conflicts, decimal-context independence, missing PnL and sample
suppression, narrative exclusion, and SELECT-only behavior with pending writes.
Adjacent paper-evaluation and canonical-journal tests are also run, alongside Ruff
and strict mypy for the package.

Handoff: the Agent can later consume this typed service through a separately
reviewed, authenticated adapter. Persistence, proactive scheduling and Telegram
surfacing remain future integration decisions. This branch must not activate a
worker, place a trade, send Telegram, merge or deploy.
