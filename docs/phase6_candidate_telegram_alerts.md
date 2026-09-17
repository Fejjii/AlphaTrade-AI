# Phase 6 Candidate Telegram alert foundation

Connects canonical Phase 6 `Candidate` events to the existing Telegram security
protocol **without activating Telegram or execution**.

`TELEGRAM_INTERACTION_ENABLED` remains `false`. There is no webhook, no Telegram
network call, no `EXECUTE_PAPER_PLAN`, and no exchange mutation.

See also: [telegram_security_protocol.md](./telegram_security_protocol.md) ·
[phase6_compatibility_map.md](./redesign/phase6_compatibility_map.md)

## Authority

Canonical `Candidate` from `CandidateLifecycleService` is the **only** candidate
alert authority. These entities cannot mint or authorize an alert:

- `PaperValidationCandidate`
- `PaperSignal`
- `SetupDetection`
- `TradingViewSignal`

They remain compatibility consumers only.

## Identity

`CandidateAlertIntent` is a deterministic identity over:

- organization
- user
- account (required for Telegram nonce/account isolation)
- candidate ID
- candidate content hash
- strategy version
- compiled setup identity (id + content hash)
- fusion policy version
- evidence window hash
- candidate lifecycle revision (`transition_version`)
- alert kind (`CANDIDATE_ACTIVE`)
- delivery channel (`TELEGRAM`)

Duplicate semantic Candidate events converge to one intent and one outbox row
keyed by `candidate-alert:{identity_hash}` on the existing
`TelegramSecurityStore` outbox. A changed lifecycle revision or candidate
content hash produces a distinct identity and must not replay an older alert.

This slice does **not** add a second Telegram persistence model, PostgreSQL
adapter, or Alembic revision. PR 85 remains the owner of durable Telegram
store adapters.

## Alert content

Structured facts are copied from `Candidate`, `SetupAssessment`, and
`CanonicalEvidenceWindowV1`:

- instrument, direction, setup name, setup state
- trigger context, invalidation summary, expiry
- deterministic rule results
- evidence freshness and provenance summary
- candidate ID and revision

No profitability claim. No LLM-generated setup truth. Outbox text is a
deterministic formatter over those facts. A later formatter may use an LLM for
wording only; authoritative fields stay canonical.

## Actions

The typed application boundary is `CandidateAlertGateway`. It authorizes through
`TelegramSecurityProtocol`, then:

| Action | Effect |
|--------|--------|
| `APPROVE` | Protocol `AuthorizationIntent` only (`executes=false`). Candidate unchanged. Never calls execution. |
| `REJECT` | Canonical `Candidate` transition to `rejected` |
| `SKIP` | Canonical `Candidate` transition to `skipped` |
| `REDUCE_RISK` | Typed intent only. Does not mutate Candidate. Does not create a plan revision. |
| `EXPLAIN` / `SHOW_CHART` / `STATUS` | Read-only views |
| `CLOSE` | Unavailable |
| `EXECUTE_PAPER_PLAN` | Not a Telegram action |

Exact callback replay converges on the original receipt and candidate-scoped
idempotency key. Conflicting replay fails closed as `REPLAY_CONFLICT`.

## Safety defaults

- `TELEGRAM_INTERACTION_ENABLED=false`
- `ENABLE_REAL_TRADING=false`
- `EXECUTION_MODE=paper`

Private-chat binding, nonce expiry, payload binding, inbound size, rate limits,
and outbox idempotency remain the Telegram security protocol's contracts.
