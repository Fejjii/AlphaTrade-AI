# Interview pitch

Use these as spoken explanations of the inspected product. Replace “I built” with your actual contribution when appropriate. Facts reflect main `b58beda`, October 7, 2026; [status](current_status.md) separates supplied runtime reports from verified source.

## Thirty seconds

“AlphaTrade is a paper trading workspace for crypto traders. It connects an approved strategy and market evidence to a risk decision, simulated execution and a Journal review. Its AI Agent explains recorded facts and drafts changes, while application services control confirmation, risk and execution. The engineering focus is traceable decisions and clear limits, using Next.js, FastAPI, a supervised worker and shared data services.”

## Sixty seconds

“Traders often use separate charts, AI chats and notes, so they lose the reason behind a decision. AlphaTrade brings those steps into six workspaces: Dashboard, Agent, Journal, Strategies, Knowledge and Settings.

Public market evidence feeds deterministic strategy detection. A genuine confirmed setup can become a Candidate, but risk, permissions, an immutable plan and explicit authority still gate paper execution. The Journal links the outcome back to its strategy and evidence. The Agent can explain those records and propose supported changes; a message does not confirm its draft.

The release evidence includes a received Watcher notification, a historical Nested internal paper fill and Journal, and successful BloFin demo account sync. Further SFP recovery, Journal repair and demo-venue acceptance remain pending. That is useful engineering evidence, not a profitability or complete acceptance claim.”

## Two-minute technical explanation

“The system has a Next.js client, a modular FastAPI backend and one separately deployed paper worker. PostgreSQL holds users, strategy versions, immutable evidence, plans, fills, Journal and audit records. Redis supports limits, revocation and caching. Qdrant indexes knowledge vectors for the knowledge service; the current Agent's default document retrieval is a bounded lexical SQL search, so I distinguish retrieval modes.

The current Agent routes typed actions and scoped reads, then sends bounded factual context to a model router for conversational synthesis. Models are configured by purpose. Risk, freshness, permissions, kill switch and execution authority are deterministic code. Supported mutations use a separate confirmation request and existing domain services. Strategy research, lifecycle approval and execution permission are separate.

The worker uses approved compiled strategy policy, source/freshness gates, durable leases and fencing. A confirmed Candidate can continue to an authorized internal paper fill and Journal lineage when the operator has explicitly armed that workflow. BloFin demo execution is a separately governed option with durable dispatch and fill/protection reconciliation; live demo acceptance is pending. Real-money execution is permanently refused in the inspected source.

The main tradeoffs are strict evidence consistency versus availability, external vector storage versus SQL transaction boundaries, and the gap between mock regressions, a deployed feature and real operational acceptance. I document those limits and preserve exact-base evidence instead of presenting a CI badge or a single event as proof of profitability.”

## Follow-up material

Use [the five-minute tour](demo_script.md) and [12-slide presentation](reviewer_presentation.md), [architecture diagrams](architecture.md), [technical walkthrough/glossary](interview_package.md), [defensible answers](technical_qa.md) and [limitations](limitations_roadmap.md). Do not promise a populated setup or use synthetic screenshot balances as results.
