Status: REVIEW_REQUIRED
Last Updated: 2026-10-01 (Europe/Berlin)
Task: AlphaTrade strategy replay and experiments 001
Current Phase: Implementation and focused validation complete; draft PR handoff
Blocker: None
Human Action Needed: Review the draft PR stacked on PR160 and its GitHub checks
Next Step: Read docs/strategy_replay_experiments_001.md and the draft PR linked in the Codex chat

Branch: codex/strategy_replay_experiments_001
Exact PR160 parent: 78635e60e4f745fd50d6dc181b555a6948562077
PR base: codex/release_consolidation_wave_001 (PR160 is still open)

Implemented Nested Continuation research replay through the existing backtest
job/dataset/trade, canonical RiskEngine, audit and journal authorities. Jobs
expose frozen strategy-version/spec/parameters, windows, assumptions and risk
limits; results expose hashes, candidates, blocks, missing evidence, counts,
fees, slippage, entry/stop/targets, net R, MAE/MFE and holding periods. Comparisons
use identical chronological training/evaluation windows and always retain
improvement_claim=false. SFP remains unregistered pending PR168 consolidation.

Validation:
- Combined focused suite: 214 passed, 3 PostgreSQL-only cases skipped.
- Final replay suite after coverage additions: 27 passed. Includes API background
  execution, tenant/RBAC, immutable version fork comparison, dataset/result/config
  tamper refusal, missing evaluation delta, both-direction prefix causality,
  next-open entry, stop-first ambiguity, gap exit, canonical daily/position risk,
  independent windows, reload/Decimal determinism, journal targets and cancellation.
- Scoped Ruff lint and formatting, mypy across all 10 changed/new source files,
  git diff --check, exact parent and unchanged PR160 base checks passed.
- Alembic has the existing single head a1brain001; no schema/dependency change.

Combined suite command (from backend, with local network access enabled for
Starlette TestClient):
.venv/bin/pytest tests/test_strategy_replay_001.py tests/test_at034_engine.py tests/test_at034_api.py tests/test_at034_integration.py tests/test_strategy_brain_nested.py tests/test_phase3_strategy_immutability.py tests/test_strategy_analytics_foundation.py tests/test_deployment_safety.py

Final replay command:
.venv/bin/pytest tests/test_strategy_replay_001.py

The full repository suite and PostgreSQL-only cases were not run. The inherited
Starlette/httpx deprecation warning remains. The default network-isolated command
sandbox stalled TestClient startup; the same tests passed with local network
access enabled, without application changes for that issue.

Limitations: full held-bar excursion bounds and candle-end intrabar exit times;
first measured target closes full size; explicit constant funding assumption;
canonical default risk limits over an isolated simulated account, not live risk
approval. Legacy backtest slippage accounting retains its prior default; replay
uses adverse fills without subtracting slippage twice. Database snapshot hashing
now refreshes persisted Decimal values to remain stable after reload.

No live trading, deployment, runtime activation, shared database migration,
strategy promotion, PR168 integration, merge or CI wait. Stop after commit,
push, draft PR and handoff.
