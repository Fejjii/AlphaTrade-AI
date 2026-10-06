# Explicit five-market Nested subscription preview

`POST /strategy-brain/templates/nested/preview` is an authenticated, read-only API.
Send only `{"baseline_version_id": "<existing owner version UUID>"}` with the existing
Bearer token. Organization and owner identity come from authentication; another
owner's or tenant's baseline returns 404. A non-Nested or non-15m baseline is refused.

The result proposes BTCUSDT, ETHUSDT, ZECUSDT, TAOUSDT and HYPEUSDT, each long/short
15m, by copying the baseline's exact provisional relative parameters. It reports
the source version/hash, each proposed spec/hash, a stable preview hash and exact
existing-version state. Previewing creates no strategy, version, compiled artifact,
approval, subscription, provider request or execution authority. Market availability
is explicitly unverified here. SFP is excluded.

The preview hash binds the immutable baseline and ten proposed specs. It remains
stable after explicit creation; existence/approval observations can change. An
existing matching selected version is reused. A changed selected version under the
same deterministic template name is a visible `name_conflict`, not a silent overwrite.
Resolve that scope through explicit library review before creating anything.

After supervising review and read-only instrument verification, explicitly submit
each `propose_new` spec through the existing `POST /strategy-brain/templates/nested`.
Each new independent root has a draft version. Repeated identical proposals reuse
that exact draft; re-preview to confirm all ten identities. The existing compile and
review/approval endpoints must approve each exact new version separately. Approval
of the source baseline does not approve its copies. `existing_version_approved`
reports only an already executable exact stored version, never preview authority.

Enable only verified watchlist slots through the existing authenticated settings
workflow. The worker already binds approved authored symbols to their exact slot,
with independent scope identities and per-subscription rollback. Ten Nested scopes
fit the existing default maximum of 20; include SFP/other subscriptions when checking
that cap and current acquisition budgets. This PR does not raise those budgets,
change execution permission or activate demo trading.

Independent first-entry readiness is PR212. Repeat-entry/actual exit reconciliation
is a separate review. After integration, one exact-release-SHA CI dispatch with
`full_backend=true`, final evaluation and browser smoke remain required before
supervising deployment/preflight/approval/activation. Focused local PostgreSQL
tests do not establish live instrument availability or model/venue acceptance.
