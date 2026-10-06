# Current status and evidence

**Documentation inspection date:** October 6, 2026.

**Main commit inspected:** `ff90d0c8f51b72d0ee215335321be7a7f4d56dcd` (PR209).

**Scope of this verification:** repository source, manifests, committed deployment options and existing documentation/images. Remote main was checked through the GitHub connector and then a fresh fetch in the isolated documentation checkout. No deployed API, worker, database, exchange, microphone or Telegram transport was probed here.

## Reading a claim

| Label | What it establishes |
| --- | --- |
| Implemented | A path exists in the inspected source; this does not establish deployment or successful runtime use. |
| Configured option/default | A manifest, Settings field or committed template declares it; this does not establish an active service. |
| Recorded development evidence | An earlier document records tests on its stated base; those tests were not rerun for this documentation change. |
| Supervisor-reported deployment/runtime | Supplied by the October 6 supervising session; not independently verified here. |
| Pending / UNKNOWN | Acceptance or current runtime detail is not established. |
| Planned | Product direction beyond the inspected implementation. |

## Repository findings

| Area | Implemented/source evidence | Limit |
| --- | --- | --- |
| Product shell | Six destinations in [navigation configuration](../frontend/src/components/layout/navigation-config.ts). | Browser/device acceptance is separate. |
| Canonical paper lifecycle | [Canonical runtime](../backend/src/app/runtime/canonical.py), [Watcher](../backend/src/app/workers/watcher_paper.py), [internal loop](../backend/src/app/services/automated_paper_loop.py). | Requires approved strategy, evidence, account, eligibility/risk and explicit authority. |
| Nested and SFP | [Strategy Brain](../backend/src/app/strategy_brain/) and [canonical evaluation policy](AT067_canonical_strategy_evaluation_policy.md). | Strategy-specific support; current SFP structural research has no authorized SFP execution plan. No universal natural-language strategy engine. |
| Agent | [Interactive Agent](../backend/src/app/interactive_agent/), [model router](../backend/src/app/services/model_router.py). | Model conversation and proposals are separate from confirmation and execution authority. |
| Knowledge | [Scoped retrieval](../backend/src/app/interactive_agent/retrieval.py), [file import](knowledge_file_import.md), [provider policy](../backend/src/app/core/provider_policy.py). | Default Agent retrieval is lexical; Qdrant is not automatically queried by every turn. |
| Learning | [Governed learning lifecycle](governed_learning_promotion_001_handoff.md), [promotion service](../backend/src/app/services/strategy_promotion.py). | Human approval and recorded validation are required; no silent self-modification. |
| Voice | [Browser speech provider](../frontend/src/lib/voice/browser-voice-provider.ts). | Earlier fixture evidence only; actual microphone, speech service and Safari/iOS acceptance UNKNOWN here. Server voice contracts remain unimplemented. |
| Real trading | [Permanent paper safety](../backend/src/app/core/paper_safety.py). | `ENABLE_REAL_TRADING=true` / trade mode are refused; not a normal enablement option. |

## October 6 presentation release follow-up

Main `e75e8bf411918094bd50eaf3d633d459efd40b40` includes PR211–215. The supervisor
reports PR215 deployed; this source inspection does not establish live acceptance.
Agent trade continuity, readable presentation and Knowledge preview/explicit save
are implemented. Five-market Nested preview and native demo lifecycle foundations
are also implemented; live instrument/strategy activation and actual protected demo
fill/exit acceptance remain unverified. Earlier specialist runbooks describe their
original PR boundaries and must be read with the later lifecycle follow-up.

The [minimum planned-R release](minimum_planned_reward_risk_release.md) adds a
prospective gross allocation-weighted1R floor and linked setup/assessment evidence
reads on a separate review branch. It is not yet deployed or fully accepted.
The known0.65R historical trade and its target projection need the existing scoped
supervising repair/verification. College destination inspection is access-blocked;
no submission synchronization has occurred. Existing historical evidence below
retains its original date and limitations.

## October 6 supervising evidence

These are supplied reports, **not runtime verification performed by the documentation agent**. They contain no private account IDs, trade IDs, credentials or audit payloads.

| Report | Supported conclusion | Still pending / UNKNOWN |
| --- | --- | --- |
| PR208 and PR209 deployed on Render API and worker. | Supervisor reports the Journal projection and Binance REST finalization code reached both services. | Exact currently running SHA, healthy migration revision, rollout consistency and full release acceptance were not probed here. |
| Real Nested Watcher event → Candidate → risk decision → internal paper fill → Journal → received Telegram alert. | A supervised real-data event reportedly exercised those linked paper paths and notification receipt. | Profitability, statistical reliability, every strategy/symbol, complete MVP acceptance and BloFin execution are not established. |
| Journal target projection corrected by PR208. | [Merged source/documentation](journal_plan_target_repair.md) describes preservation of approved plan targets. | Existing Journal target repair and its acceptance remain pending; do not infer old rows are repaired by deployment. |
| PR209 finalization/history correction deployed. | [Merged acquisition policy](sfp_candle_finalization_recovery.md) guards and confirms REST rows while preserving v1 evidence. | Fresh live SFP recovery acceptance remains pending. Neither a merge nor deployment proves both SFP scopes now succeed. |
| Owner accepted mobile page loading. | A supervising usability report exists for page loading. | Comprehensive physical-device, voice and Safari verification is not established. |
| BloFin demo implementation exists. | [Governed demo guide](governed_blofin_demo_execution.md) records simulated/disposable development evidence. | Real demo execution/protection/fill reconciliation acceptance remains pending. |

## Runtime details not established here

Current resolved Agent/embedding model, deployed dependency/server versions, authoritative Qdrant health, active Bybit failover, exact watchlist/strategy versions, activation flags and current hosting inventory are **UNKNOWN** without a fresh scoped observation. Committed Render/Compose settings and historical staging URLs are not such observations.

Use [deployment](deployment.md) and [monitoring](observability.md) to establish these facts in a separately authorized operational session. Use [limitations](limitations_roadmap.md) to distinguish implemented foundations from future product direction.

## Historical documents

The [v0.1.0 release](releases/v0.1.0-paper-mvp.md), [AT010 audit](AT010_readiness_audit.md), release/acceptance JSON, exact-base handoffs and old screenshot sets are historical evidence. Keep their original results and decisions; do not combine results from different commits into a claim that today's full suite or deployed product passed. Migration-head and environment tables in older handoffs apply to their recorded release only.

Current reading order: [README](../README.md) → [architecture](architecture.md) → [Agent](agent_workflow.md)/[retrieval](rag_system.md)/[security](security.md) → [deployment](deployment.md). Specialist documents supply exact contracts and earlier development evidence rather than a competing top-level product description.
