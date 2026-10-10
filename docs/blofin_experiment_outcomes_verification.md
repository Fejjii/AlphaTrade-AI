# BloFin experiment resolver/outcome focused verification

Base: PR241 `6ca6a76201547524275266dfa22fdf12f5932b14`.
Branch: `codex/blofin-experiment-outcomes`. Exact published feature SHA is recorded in
the PR and dedicated handoff; this ledger is included in that commit.

The focused PostgreSQL fixture creates/drops only UUID-named schemas on disposable
local PostgreSQL 17.11. Native account verification reuses the existing MockTransport
manual-account fixture; new canonical commands, manifests and native facts are stored
synthetic fixtures. No actual exchange connection, order, balance change or activation.
All new cases execute on PostgreSQL, including existing a11 append-only guards and
account attribution locking. No SQLite substitution or skipped PostgreSQL evidence.

Final affected selection: **179 passed in 54.29s, no skips**, including **71 new
PostgreSQL cases**. Selection covers the resolver/outcome and actual domain consumer,
existing domain/native identity/API/concurrency/migration, and native activity provider/
durability regressions. Full backend CI/release acceptance, deployment and runtime
activation are outside this task.

Run from `backend` with its development environment installed. Both opt-in PostgreSQL
URLs point to the disposable fixture database; schema isolation is provided by tests:

```sh
EXPERIMENT_TEST_POSTGRES_URL=postgresql+psycopg://experiment_fixture@127.0.0.1:55439/experiment_outcomes_test \
BLOFIN_ACTIVITY_TEST_POSTGRES_URL=postgresql+psycopg://experiment_fixture@127.0.0.1:55439/experiment_outcomes_test \
python -m pytest \
  tests/test_blofin_experiment_outcomes_postgres.py \
  tests/test_experiment_domain.py tests/test_experiment_native_identity.py \
  tests/test_experiment_concurrency.py tests/test_experiment_api.py \
  tests/test_experiment_migration.py tests/test_blofin_activity_postgres.py \
  tests/test_blofin_activity_provider.py --tb=short --show-capture=no
```

Changed Python files passed Ruff lint/format (7 files); scoped strict mypy passed on
the 6 new source/example/exporter files. Pure module serialization export `--check`
passed. The existing offline OpenAPI exporter produced bytes identical to the PR241
shared client artifact. No shared generator input/artifact or migration changed.
`git diff --check` passed.

Contract SHA256:

- Module JSON Schema: `e568e0fc772d6b381c263485c3a56ebdc59b2bcb770eda68e17d8c9a6fc748ce`.
- Unchanged shared OpenAPI: `6f7f9ece7248442b53f9e3ebd84277053db284d1e52cf97a18a25ac5c4dcf0e3`.

Important capabilities exercised: exact attribution IDs/hashes, manual/echo rejection,
partial terminal entry and multiple exits, fee sign/rebates and unknown fee currency/
profit/methodology, duplicate pages/attestations, conflicting fill IDs, delayed receipts,
future-time refusal, coverage gaps/staleness, same-UID credential rotation, tenant/source
isolation, exclusive exit attribution, PostgreSQL serialization, fresh Validation start,
changed sample revalidation, insufficient sample nulls, multi-outcome Decimal aggregation,
18-place rounded win rate, large monetary values and caller-context independence.

The module-level integration example calls actual ExperimentService sample admission
and reads reconciled native performance. It performs no second collection or IO. Shared
HTTP wiring/generated contracts remain Agent 1's integration step. No trusted runtime
attestation producer is installed; undocumented native monetary semantics and protected
exit ancestry remain explicitly unavailable. Actual signed demo GET connectivity,
permissions, rotation, endpoint coverage/retention, fees/PnL basis and protected parent
lineage are unverified under enforced egress limits. No premium provider or paid data.
