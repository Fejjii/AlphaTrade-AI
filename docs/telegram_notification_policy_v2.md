# Telegram notification policy v2

Branch: `codex/telegram_policy_v2_001`.
Exact base: PR155 `558af78fc1ef36d0d0f857945813bf539b82c168`.

This extends the existing notification preferences, Candidate gateway,
TelegramSecurityStore outbox, recipient binding, and delivery services. No new
Telegram service, credential store, execution path, or activation flag is added.
Telegram remains disarmed and network delivery remains disabled by default.

## Preferences and contract

The existing tenant/user-scoped `PATCH /notifications/preferences` accepts a
`telegram_policy` object with `schema_version: 2`. The existing GET returns its
effective defaults. The nested policy is a **full replacement**; omitting it in
a PATCH preserves it, and explicitly setting it to `null` restores v2 defaults.
The existing reset endpoint also resets it. Existing audit and timestamp fields
record preference changes. Unknown versions and invalid values are rejected.
Updating this object never enables a channel, changes a recipient, or arms
Telegram. Existing enrollment, tenant/RBAC, provider, and activation gates apply.

Example (strategy UUIDs are optional):

```json
{
  "telegram_policy": {
    "schema_version": 2,
    "symbol_subscriptions": ["BTCUSDT"],
    "setup_stages": ["N2", "N3"],
    "event_types": ["SETUP", "RISK", "STOP"],
    "minimum_severity": "INFO",
    "forming_alerts": false,
    "confirmed_alerts": true,
    "cooldown_seconds": 120,
    "duplicate_suppression_seconds": 86400,
    "quiet_hours": {
      "start": "22:00",
      "end": "07:00",
      "timezone": "Europe/Berlin"
    }
  }
}
```

`TelegramNotificationEvent/v1` carries typed producer facts: strategy UUID,
symbol, stage, phase, event type, severity, optional quality, semantic duplicate
key, event time, and a producer-owned mandatory-risk marker. The contract is
strategy-neutral and can support a future SFP producer. This change adds no SFP
producer or integration. It also adds no forming or daily-review producer.

## Deterministic rules

The first failing rule produces a stable `POLICY_*` reason. V2 checks apply only
to Telegram; the existing channel routing policy continues to apply as well.

1. Producer-marked mandatory risk bypasses v2 user filters, quiet hours,
   cooldown, and temporal duplicate suppression. Exact outbox idempotency still
   applies, and activation/security/network gates are never bypassed.
2. Strategy, symbol, setup-stage, event-type, and severity subscriptions match
   exact identifiers. `null` allows all; `[]` allows none. A missing fact cannot
   match a configured subscription. Candidate strategy UUIDs are canonical
   **strategy-version IDs**; legacy paper alerts use their existing strategy IDs.
3. Minimum severity uses `INFO < WATCH < ACTION < CRITICAL`. The optional
   `severities` list intersects this threshold. Legacy `warning` maps to `WATCH`.
4. Event toggles independently control `RISK`, `PAPER_TRADE_OPENED`,
   `PAPER_TRADE_CLOSED`, `STOP`, `PARTIAL_PROFIT`, and `DAILY_REVIEW`.
   `SETUP` and `OTHER` are also supported event types.
5. `forming_alerts` and `confirmed_alerts` independently control setup phase.
   Missing setup phase fails when either phase is disabled. Phase preferences
   cannot promote an assessment or mint a Candidate.
6. `minimum_quality` is a finite decimal in `[0, 100]`, inclusive. A missing
   quality fails every configured threshold, including zero. Quality is never
   synthesized from rule weights, confidence, PnL, or setup stage. Current
   canonical Candidate/Nested alerts have **no quality score** and therefore
   fail any configured quality threshold.
7. Quiet hours use validated IANA timezones, local wall-clock time, and a
   half-open `[start, end)` interval, including overnight windows and DST.
   Equal endpoints are rejected. `null` disables quiet hours.
8. Temporal duplicate suppression compares semantic duplicate keys within the
   configured window. Cooldown scope is `(strategy, symbol, event type, stage,
   phase)`. Both durations are integer seconds in `[0, 604800]`; zero disables
   that temporal rule. Exact outbox idempotency remains unconditional.

Defaults allow all subscriptions, phases, and event toggles, with `INFO` minimum,
no quality threshold, no quiet hours, zero cooldown, and a one-day temporal
duplicate window. PR155's confirmed-only Nested evidence gate is preserved;
enabling forming preferences cannot create forming Nested notifications.

## Integration and persistence

Candidate projection supplies facts from the existing canonical Candidate and
Nested summary after the existing authority/recipient checks. N2 and N3 use the
same exact stage subscription rule. The existing Nested episode identity and
informational-only behavior remain intact.

Admission checks and duplicate/cooldown reservations run inside the existing
TelegramSecurityStore transaction/lock. Accepted pending/claimed/retryable rows
reserve their admission time; sent/acknowledged rows use the persisted `sent_at`.
Suppressed/dead-letter rows do not reserve a window. History is scoped to
organization, user, binding, bot, and chat, has no arbitrary result-count cutoff,
and survives gateway/worker restart. A row never suppresses its own retry.

Delivery reloads the same user policy and rechecks immediately before transport.
Pre-v2 trader outbox rows without typed facts fail closed under a customized v2
policy (`POLICY_FACTS_MISSING`); default policy retains legacy compatibility.
Suppression is terminal: the existing outbox records `SUPPRESSED` and the reason,
with no transport call or attempt increment. Quiet-hour filtering discards the
event; it does not schedule delivery for later. Relaxing preferences does not
revive a suppressed semantic event. A new event may be admitted normally.

Existing Candidate footer notifications carry the same policy facts with a
distinct duplicate key; a configured cooldown can suppress that extra footer.
Watcher blocked notices map to risk events. Journal outcome notices map to paper
trade closed. User-requested discussion replies and security receipts remain
outside trader-event subscription filters.

Existing manual delivery, normal alert delivery, and automatic preview use the
same evaluator for paper alerts before transport. Paper alerts use explicit
`notification_quality` and `notification_phase` metadata when present. Stop hits
map to `STOP`; TP exits map to closed trades unless explicitly marked
`partial_profit: true`. Critical paper risk alerts are mandatory for the v2
policy. Legacy delivery history uses the existing alert records and recorded
user/bot/chat recipient scope. Pre-v2 legacy rows lacking that scope do not
participate in temporal history; existing row/episode idempotency still applies.

## Review handoff

Alembic revision `a2tgpolicy002` follows `a1brain001`. It adds nullable JSON policy
and event facts to the existing preferences/outbox tables, a nullable send
timestamp, and a scoped outbox-history index. No migration was applied to a
deployment. Downgrade converts suppressed rows to dead-letter before removing
v2 fields so older code cannot resend them.

Focused tests cover deterministic rules, missing quality, timezone/DST boundaries,
recipient isolation, competing admissions, restart/retry behavior, delayed-send
cooldown, Nested filtering, preference persistence, delivery/preview filtering,
immutable persisted facts, and migration upgrade/downgrade. Tests use fake or
mocked Telegram transport. No activation, network delivery, credential changes,
trading-authority changes, or deployment are part of this handoff.
