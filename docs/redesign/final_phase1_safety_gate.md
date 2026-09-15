# Final Phase 1 Execution-Safety Gate — PR #70

**Target branch:** `cursor/final-architecture-alignment-c5d7`  
**Exact head:** `d8f684f7c7a945986951c01aaed10bb3261eff4f`  
**Reference:** PR #68 at `e050d743837c75694044a1fd6808315b7aca605f`  
**Scope:** narrow adversarial architecture gate; documentation only

## Final verdict

**NOT APPROVED**

## Material findings

### BLOCKERS

None.

### HIGH-01 — The close claim does not define a stable pre-POST working-order hash

`ClosePositionCommand` binds the reconciled working-order set/hash
(`agentic_redesign_target_architecture.md:1943-1947`). The claim transaction then inserts the
pending close effect into the next working-order projection/hash (`:2451-2453`). Immediately
before POST, the dispatcher compares the current working-order hash with the immutable close
claim and treats a change as stale (`:2460-2466`).

The contract does not say whether the comparison excludes the claim's own effect, whether the
claim stores a separately computed post-claim expected hash, or how that value is canonicalized.
An implementation can therefore make every ordinary close fail its own guard or can choose an
incompatible interpretation that misses a real competing-order change. PR #68 HIGH-16 is not
deterministically closed until one canonical comparison value is defined and tested for both
the no-race path and concurrent fill/cancel paths.

### HIGH-02 — Close reconciliation has contradictory terminal/residual transitions

The overview state model sends stale position/order/safety state through
`CLOSE_PENDING -> BLOCKED_BEFORE_DISPATCH -> POSITION_OPEN`
(`agentic_redesign_target_architecture.md:1091-1094`). The controlling close protocol instead
sends a pre-POST position/version or working-order/hash mismatch to
`RECONCILIATION_REQUIRED` without POST (`:2460-2466`). It then permits a reconciled residual to
return to `POSITION_OPEN` (`:2471-2475`), but the state diagram has no
`RECONCILIATION_REQUIRED -> POSITION_OPEN` transition (`:1094-1104`).

The document requires the overview and normative contracts to agree (`:1729-1733`). These
conflicting paths prevent deterministic handling of close/cancel/fill races and make replay
projection dependent on which section an implementation follows.

## Gate checks

### Kill-switch race

Pass. The architecture requires the same safety epoch at command claim, effect lease,
immediate pre-POST dispatch authorization, and ambiguous/possibly-sent reconciliation
(`agentic_redesign_target_architecture.md:2027-2039`). The pre-POST commit is the linearization
point: an earlier blocking epoch suppresses POST and records `BLOCKED_BEFORE_DISPATCH`
(`:2041-2048`). Once bytes may have been sent, the effect, reservation, and quarantine remain
truthful and query-first reconciliation replaces any blind retry (`:2050-2057`, `:2060-2096`).

### Close uniqueness

The channel-neutral identity contains organization and account principal, internal/applicable
exchange account, position ID/version, execution venue/instrument, NET mode, side, exact
reconciled quantity/unit, `reduce_only=true`, and working-order set/hash
(`agentic_redesign_target_architecture.md:2417-2433`). Web, agent, and Telegram use one
authoritative service and one position-version claim; same-hash competitors resolve the
existing receipt and cannot create a second effect (`:2436-2458`, `:2498-2503`).

The identity and atomic claim are present, but HIGH-01 leaves the claim-to-dispatch hash
contract unsafe to implement consistently.

### Fill versus close

The target requires immediate pre-POST position/order revalidation, stale-quantity suppression,
venue-enforced reduce-only behavior that cannot reverse exposure, authoritative fill
ingestion, final residual reconciliation, and a new authorization for any additional recovery
(`agentic_redesign_target_architecture.md:2460-2479`). Duplicate close and TP/SL/late-fill/
cancel-pending race tests are mandatory (`:2477-2481`).

Those safety rules are present, but HIGH-01 and HIGH-02 leave the working-order comparison and
resulting durable state nondeterministic.

### Execution state model

All requested states are named: `SUBMITTING`, `ACKNOWLEDGED`, `PARTIALLY_FILLED`,
`CANCEL_PENDING`, `CANCEL_RECONCILIATION_REQUIRED`, `CANCELLED`,
`PARTIALLY_FILLED_CANCELLED`, `POSITION_OPEN`, `CLOSE_PENDING`,
`RECONCILIATION_REQUIRED`, `ABSENCE_PENDING`, `ABSENCE_PROVEN`, `RESUBMIT_AUTHORIZED`,
`OPERATOR_HOLD`, and `CLOSED`
(`agentic_redesign_target_architecture.md:1074-1104`, `:2080-2113`).

The submit-uncertainty, absence-proof/resubmit, cancellation, and partial-fill paths are
consistent. The close residual path fails the consistency gate because of HIGH-02.

### Paper safety

Pass. The permanent contract requires exact `EXECUTION_MODE == PAPER`,
`ENABLE_REAL_TRADING == false`, non-live `EXCHANGE_MODE`, a rejected `trade_live` tombstone,
and invalidates execution-capable `READ_ONLY` configuration
(`agentic_redesign_target_architecture.md:1737-1749`). Services and provider construction must
reject non-paper mode, live switches, live credentials, and production hosts before mutation
or provider calls; production hosts remain unreachable by allowlist and network policy
(`:1750-1761`). PR #70 changes documentation only and does not enable any execution path.

## Required next gate

Correct HIGH-01 and HIGH-02 in the canonical architecture, keep every paper-only invariant
unchanged, and repeat this narrow gate against a new exact head before Phase 1 implementation.
