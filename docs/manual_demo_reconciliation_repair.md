# Manual BloFin demo: reconcile the existing order, preserve its identity

Base: `28b7dab` (main after PR228). One implementation agent; no parallel agents.
No `AGENTS.md` exists in this checkout, workspace parents or the main tree.

## Live evidence and its limits

The owner reports an existing BTC long in BloFin demo on 8 October 2026 at about
12:56 UTC: **0.1 contracts = 0.0001 BTC**, stop **82000**, target **83000**.
AlphaTrade returned `reconciliation_unavailable_operator_hold`. Chrome recording
now works, according to the owner; this followup makes no microphone changes.

Read-only Render inspection used the owner-confirmed workspace `My Workspace`,
service `alphatrade-api-staging`. Logs show the confirmation request completing
at **12:56:28.949993 UTC**, HTTP 200, trace
`acf02e05-925e-47aa-bf2c-1a58ac2dda5f`. No `blofin_request_failed` event appears in
the inspected 12:55–13:15 UTC window. The old service swallowed the reconciliation
exception and logged neither its stage nor its type. Consequently, these logs
cannot establish the exact live field mismatch. The cloud environment has no
BloFin credential binding; no live native response was retrieved.

**Actual live recovery is pending deployment and a read of this same command.**
Neither fixture fills nor the owner's position report replace native fill proof.
No exchange order was submitted, cancelled or resubmitted during this repair.

## Confirmed implementation defects

1. `ManualDemoService.reconcile` caught every provider exception and returned the
   same hold without an actionable diagnostic. The response, audit trail and
   runtime log now expose bounded stage, endpoint, reason, numeric field name
   where applicable, HTTP status and numeric venue code. Exception text, response
   bodies, credentials, signatures and URLs with query parameters are excluded.
2. Entry fill parsing rejected every negative fee. Executing the original main
   parser against a signed-fee fixture reproduces `Invalid demo fill fee`.
   Reconciliation now preserves finite native signed fees/rebates exactly, without
   taking an absolute value or deriving realized PnL from an uncertain convention.
3. Protection parsing required the entry client ID on the TPSL record and literal
   `"-1"` market-price strings. A fixture with a blank protective client ID, an
   exact TPSL ID returned by the native entry, and decimal-padded market prices
   reproduced `protection missing` on main. The repair accepts exact native
   parent/TPSL identity links and compares finite decimals. Identical prices,
   instrument or account membership alone never establish order lineage.
4. Permissive response extraction silently dropped malformed rows or treated
   unreadable payloads as absence. Native reads now reject malformed, ambiguous,
   duplicate or potentially incomplete pages, unknown order states, inconsistent
   quantity totals, invalid occurrence times and mismatched identities. Order
   acknowledgment/average price never generates a fill. REST `ts` is supported;
   a `fillTime` variant can supply occurrence time only when no conflicting `ts`
   exists. No observation timestamp is substituted for occurrence time.
5. The transport replaced a returned venue code with the HTTP status for HTTP
   errors. It now preserves a bounded numeric code such as `51000` separately
   from HTTP `400`, while retaining the existing non-JSON error behavior and
   request/retry policy.
6. Agent selection had only a `paper_only` origin filter, with no requested venue
   or manual-demo origin. Thus, missing demo Journal evidence allowed an older
   internal simulator trade to be selected. Explicit venue and origin constraints
   now apply before selection/limits, including explicit Journal IDs and
   conversation followups. An incomplete BloFin venue request asks for demo/real
   selection rather than guessing.
7. Manual Journal projection omitted `trade_plan_revision_id` and used
   `quantity_fraction` instead of the Journal's `size_fraction`. Reconciliation
   now writes the correct immutable plan link and target representation, including
   a verified legacy row in this same lifecycle. Conflicting account, origin,
   venue, symbol, direction or plan identities refuse projection.
8. The old parser applied the exchange order lot increment to each individual
   fill. Matching-engine partial executions can be smaller than the submission
   increment; the repair checks positive identity-bound fills and the exact total
   against native filled quantity and the authorized order.
9. Shared immutable fill hashes contain decimal strings. Equivalent native
   formatting on later reads could therefore conflict (`82894` versus
   `82894.000000000000000000`). The repair reuses the original representation
   only when full-precision audit amounts are economically identical and
   recreate the existing immutable hash. It never rewrites shared hashes, uses
   rounded database values as equality proof, or accepts a changed price/time.
   A proven legacy replay can append a precision-proof audit without modifying
   historical facts.

These reproduce defects in code. They do **not** establish that the signed-fee
fixture is the exact cause of the owner's live hold. If the deployed parser still
refuses that order, its structured diagnostic is the next required evidence.

## Same-order reconciliation and Agent behavior

Provider reconciliation performs only signed **GET** requests for order detail,
fill history and pending TPSL. It does not run flat-account entry preflight,
create an authorization, claim a new command or dispatch a POST. It binds the
durable client ID, instrument, side, contract quantity and native order ID.
Already stored native order IDs cannot change. Previously verified fill identities
must remain in the new complete observation; a regressed snapshot cannot erase
the ledger or shrink Journal size. Existing fill-content and fee-conflict checks
remain enforced. Repeated receipts, fill facts and Journal projection converge
under the existing account epoch lock.

Protection is a separate observation. A protection outage or malformed/unlinked
TPSL preserves proven fills and their Journal entry while reporting an operator
hold. A later valid observation updates the same Journal trade. It never clears
the kill switch or permits another entry. A later order/fill read outage retains
previously recorded facts and explicitly distinguishes them from unavailable
current protection evidence.

For a manual demo request the Agent selects the matching **command**, even if
reconciliation has not yet created a Journal fill row. Its deterministic answer
uses only that command's scoped immutable manual plan, authorization, native
receipt and fill ledger. It reports contract/BTC size, verified fills and recorded
protection separately, with their missing evidence. Historical simulator prose
or a model response cannot fill those gaps. Manual connectivity tests are labeled
as such; no strategy qualification, minimum 1R or historical strategy approval is
invented. Strategy risk policies are unchanged.

## Changed files

| Files | Purpose |
| --- | --- |
| `backend/src/app/providers/exchange/demo_reconciliation.py` | Strict native order/fill/protection parsing and safe stage diagnostics |
| `backend/src/app/providers/exchange/governed_blofin.py` | Delegate native reads; carry separate protection diagnostics |
| `backend/src/app/providers/exchange/blofin_client.py` | Preserve numeric venue codes on HTTP errors |
| `backend/src/app/services/manual_demo_service.py` | Persist/report diagnostics, guard identities/history, project correct Journal lineage |
| `backend/src/app/schemas/manual_demo.py` | Bounded diagnostic response contract |
| `backend/src/app/interactive_agent/actions.py` | Venue and origin selectors |
| `backend/src/app/interactive_agent/recorded_trade.py` | Route/filter requested scope before latest selection |
| `backend/src/app/interactive_agent/manual_demo_evidence.py` | Read the exact manual command and stored native facts, including unreconciled orders |
| `backend/src/app/interactive_agent/conversation_context.py` | Explicit venue/origin overrides prior conversation selection |
| `backend/src/app/interactive_agent/service.py` | Deterministic manual evidence replies prevent model/history substitution |
| `frontend/src/lib/api/manual-demo.ts` | Typed optional reconciliation diagnostics |
| `frontend/src/components/settings/ManualDemoTest.tsx` | Display failure stage/reason/field and same-command recovery guidance |
| `backend/tests/test_manual_demo_reconciliation.py` | Native-shaped lifecycle, failure/recovery, projection and mixed-venue regressions |
| `frontend/src/components/settings/ManualDemoTest.test.tsx` | Diagnostic display and same-command refresh regression |
| This document | Root causes, evidence and same-order acceptance |

## Focused verification

Fixture values mirror the reported size/stop/target and use October 8 occurrence
times, decimal-padded native numbers, an order-detail object and distinct native
order/trade/TPSL IDs. **82894 is a fixture entry price; all native IDs are fixture
identities, not the owner's live order.** Transport is `httpx.MockTransport`.
Integration tests use disposable local PostgreSQL; they do not access a deployed
database. Assertions verify stable command/order/Journal IDs and fill counts,
GET-only repeated recovery, retained holds, no synthetic outcomes, origin/venue
selection and isolation from simulator/model evidence.

Final focused results: **182 passed in 202.45 seconds**; frontend **18 passed**. No tests were
skipped in the PostgreSQL run. All edited Python files pass Ruff lint/format;
all ten edited Python source files pass mypy. Frontend TypeScript and ESLint on
the three edited frontend files pass. The existing FastAPI/httpx deprecation
warning remains.

Backend (from `backend/`, with local PostgreSQL available):

```sh
.venv/bin/pytest -o addopts='' -q \
  tests/test_manual_blofin_demo.py \
  tests/test_manual_demo_reconciliation.py \
  tests/test_governed_blofin_demo.py \
  tests/test_blofin_execution.py::test_place_order_read_only_or_trade_denied \
  tests/test_blofin_execution.py::test_place_order_venue_4xx_http_rejection \
  tests/test_blofin_execution.py::test_rejection_diagnostics_do_not_leak_secrets \
  tests/test_blofin_provider.py::test_signed_get_failure_does_not_log_secrets \
  tests/test_risk_engine.py \
  tests/test_agent_recorded_trade.py \
  tests/test_agent_conversation_continuity.py --tb=short
```

Frontend (from `frontend/`):

```sh
npm test -- src/components/settings/ManualDemoTest.test.tsx
npm run typecheck
npx eslint src/components/settings/ManualDemoTest.tsx \
  src/components/settings/ManualDemoTest.test.tsx src/lib/api/manual-demo.ts
```

No full backend CI workflow was dispatched and no workflow or branch protection
changed.

## Review → deploy → reconcile this same order

1. Preserve the existing command ID, revision/hash and client order ID from the
   original result. Compare its native order with the owner's **8 October,
   approximately 12:56 UTC** BloFin demo BTC long, **0.1 contracts**, stop **82000**,
   target **83000**. Do not use the October 6 simulator trade. If these identities
   are unavailable, the Agent's scoped read can expose the recorded command;
   it must not select a different trade to supply missing proof.
2. After review and deployment, use **Refresh venue evidence** on the existing
   result, or authenticated `POST /execution/manual-demo/<existing-command-id>/reconcile`.
   This route performs venue reads and local reconciliation only. Do not prepare,
   preview or confirm another order, and do not clear an operator/kill-switch hold.
3. Capture the response and its diagnostic if still held. For order/fill failure,
   inspect only that native order and the reported endpoint/field. For protection
   linkage failure, require its native parent/TPSL/client identity; matching stop
   and target prices alone are insufficient. Never patch in fills or guessed IDs.
4. On successful proof, verify the same native order, actual native trade IDs,
   **0.1 filled contracts = 0.0001 BTC**, venue occurrence time/price/fee, planned
   stop **82000**, target **83000**, and identity-linked active protection. Compare
   the actual price with BloFin; the fixture price is not acceptance evidence.
   Refresh twice: command/order IDs, fill count and Journal ID must remain stable.
5. Confirm one manual-demo Journal entry with `BLOFIN_DEMO`, the immutable manual
   plan link, correct contract-to-BTC size and no invented exit/PnL. Ask the Agent:
   **“Explain my latest manual BloFin demo BTC long trade.”** Then **“Explain that
   trade.”** Both must reference this same identity, or explicitly report missing
   evidence. Neither may return the October 6 **0.005 BTC at 86073.10** simulator
   trade as a substitute. The account remains held for operator review.
