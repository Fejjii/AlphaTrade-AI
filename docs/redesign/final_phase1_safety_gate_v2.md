# Final Phase 1 Safety Go/No-Go V2

**Target:** FINAL PHASE 1 SAFETY GO/NO-GO V2
**Target branch:** `cursor/final-architecture-alignment-c5d7`
**Exact head:** `d2a0e9e229a3857a5c6b82a8270d15e9ba19a267`
**Reference review:** PR #72,
`docs/redesign/final_phase1_safety_gate.md` at
`c743f886b6219896cafa1a892931ce06d7744fac`
**Scope:** last narrow close-protocol safety gate; documentation review only

## Verdict

**APPROVED FOR PHASE 1 IMPLEMENTATION**

## Material findings

### New blockers

None.

### New high

None.

## HIGH-01 — RESOLVED

`ClosePreClaimWorkingOrderSnapshotV1` is now the single explicit comparison contract
(`agentic_redesign_target_architecture.md:1982-2050`):

- the close service computes it from authoritative venue reads before creating the close
  command, claim, receipt, or effect;
- its included set is all and only relevant, positive-remaining, non-terminal venue working
  orders for the exact exchange account, venue, instrument, and NET position;
- the current local close command, claim, receipt, effect, and broader local projection rows
  are excluded, while a venue-observed order may not be hidden because AlphaTrade created it;
- the pre-POST check recomputes the same included set, fields, ordering, encoding, and hash;
- an ordinary no-race close remains equal and does not self-invalidate;
- TP, SL, fill, cancellation, remaining quantity/status/version, or a new competing venue order
  changes the snapshot and/or bound position projection, suppresses POST, and enters
  reconciliation;
- the canonical preimage, ordering, Decimal encoding, namespace, and SHA-256 operation are
  specified, while transport/request/callback/trace/cursor/timestamp metadata are excluded.

The channel-neutral close protocol repeats that exact contract and compares snapshot version,
canonical entries, and hash against the immutable claim
(`agentic_redesign_target_architecture.md:2529-2619`). No competing snapshot interpretation
remains.

## HIGH-02 — RESOLVED

Section 11 declares one authoritative execution and close state machine, and the diagram,
rules, domain table, normative dispatch protocol, and channel-neutral close protocol agree
(`agentic_redesign_target_architecture.md:1071-1109`, `:1129-1145`, `:1672-1675`,
`:2154-2160`, `:2581-2601`):

1. A safety-policy block with durable proof that no send was possible uses
   `CLOSE_PENDING -> BLOCKED_BEFORE_DISPATCH -> POSITION_OPEN`, with authoritative confirmation
   that the original exposure remains.
2. A changed position or working-order snapshot before POST uses
   `CLOSE_PENDING -> RECONCILIATION_REQUIRED` without POST.
3. A request that may have been sent also uses `RECONCILIATION_REQUIRED` and never
   `BLOCKED_BEFORE_DISPATCH`.
4. Authoritative close reconciliation resolves nonzero exposure to `POSITION_OPEN`, zero
   exposure to `CLOSED`, and unresolved or ambiguous truth to `OPERATOR_HOLD`.

The copyable Phase 0 audit summary uses the same distinctions
(`agentic_redesign_phase0_audit.md:843-859`).

## Fill / close safety

Duplicate web, agent, and Telegram close requests converge on the database-unique claim,
receipt, and one close effect for the exact position projection. A different semantic hash
conflicts without creating another effect
(`agentic_redesign_target_architecture.md:2529-2554`, `:2612-2618`).

`reduce_only=true` and **NET MODE ONLY** remain mandatory. Late, partial, TP/SL, and concurrent
fills are ingested as authoritative venue facts; reduce-only must prevent side flip or
over-close from creating reverse exposure. Reconciliation computes the truthful residual and
cannot fabricate `CLOSED`. Any additional residual close requires a new authorization and
position projection. Ambiguous sends are query-first and have no blind transport retry
(`agentic_redesign_target_architecture.md:1150-1178`, `:2585-2601`).

## Kill switch

The previously approved dispatch-time barriers remain intact: command claim, effect lease,
the transaction immediately before POST, and ambiguous/possibly-sent reconciliation all check
the account safety epoch. The pre-POST transaction remains the dispatch linearization point
(`agentic_redesign_target_architecture.md:2131-2165`). The close correction preserves the
proven-unsent versus possibly-sent distinction and does not weaken this contract.

## Permanent paper safety

Unchanged. The architecture still requires exact `EXECUTION_MODE == PAPER`,
`ENABLE_REAL_TRADING == false`, non-live `EXCHANGE_MODE`, a rejected `trade_live` tombstone,
production-host denial, and rejection of latent live switches. Configuration APIs, models,
Telegram, environment combinations, and runtime mutation cannot alter these constants
(`agentic_redesign_target_architecture.md:1770-1791`).

The correction range from PR #72's reviewed head
`d8f684f7c7a945986951c01aaed10bb3261eff4f` through the exact target changes only the two
canonical redesign documents. It changes no product code and no permanent paper-safety line.

## CI status

CI is recorded separately from architecture correctness.

For exact head `d2a0e9e229a3857a5c6b82a8270d15e9ba19a267`, GitHub reported all checks terminal
and successful on 2026-09-15 UTC:

- `backend`
- `deployment-safety`
- `frontend`
- `docker-build`
- `evaluation`
- `e2e-smoke`
- `Vercel`
- `Vercel Preview Comments`

Green CI supports repository validation but is not the basis for resolving HIGH-01 or HIGH-02;
those findings are resolved by the aligned deterministic contracts above.
