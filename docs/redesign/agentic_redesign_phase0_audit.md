# AlphaTrade Agentic Redesign — Phase 0 Current-State Audit

**Audit base:** `main@c0bd1d4d9c49948c44e7e23dc2a2572ea68a4a20`  
**Audit scope:** repository evidence only; architecture/documentation only  
**Safety boundary:** paper/internal simulation or BloFin demo only; real-money execution remains
disabled

## 1. Executive assessment

AlphaTrade is not an empty scaffold and should not be rewritten. It already has a broad,
well-tested paper-trading platform: typed FastAPI APIs, tenant-scoped persistence, a LangGraph
agent, public Binance market data with provenance, deterministic analysis and risk, strategy
cards and versions, paper-validation workflows, alerts, approval records, internal paper
execution, a guarded BloFin demo adapter, canonical journal trades, analytics, RAG, a worker,
and a large Next.js UI.

The present system is nevertheless page- and workflow-oriented rather than agent-first. Its
capabilities are split across 59 Next.js page routes and 42 FastAPI route modules. The
background and external-integration paths are implemented behind flags but disabled in the
checked-in staging blueprint. There is no common evidence contract or deterministic
multi-source fusion lifecycle. CVD is missing; true order-flow evidence is missing; Telegram is
outbound-only; and BloFin synchronization is a read-only snapshot rather than authoritative
order/position/PnL reconciliation.

The current agent has a concrete routing defect for the target product. Keyword classification
maps words such as `analyze`, `setup`, and `entry` to `PLAN_TRADE`; that route traverses
`trade_proposal_generation`, whose own guard permits `PLAN_TRADE` and `EXECUTE`. Thus analytical
phrasing containing those terms can create an in-memory proposal and enter risk/approval
handling. This is not universal to every message classified `ANALYSIS_REQUEST`: for example,
the `btc`/`eth` message-class keywords alone do not force `PLAN_TRADE`. The persistence service
also restricts stored proposals to `PLAN_TRADE` and `EXECUTE`, but that does not repair the
semantic error because common analysis phrasing is itself classified as planning. Evidence:

- `backend/src/app/agents/nodes.py` (`message_classification`, `intent_classification`)
- `backend/src/app/agents/routing.py` (`route_after_intent`)
- `backend/src/app/agents/graph.py` (unconditional
  `strategy_module_execution -> trade_proposal_generation`)
- `backend/src/app/services/proposal_service.py` (`create_from_agent`)

### Verdict and reuse estimate

| Area | Assessment |
|---|---|
| Current architecture | Capable modular monolith with extensive paper workflow, but fragmented UX and no unified evidence/fusion/event lifecycle |
| Backend reuse | **Approximately 78%** capability-weighted for the target vertical slice |
| Frontend reuse | **Approximately 60%** component/API-client reuse; route-level information architecture needs substantial consolidation |
| Rewrite recommendation | **No rewrite.** Reuse, wrap, extend, merge, and hide |
| Safety | Strong defense-in-depth for paper-only operation; preserve existing authorities rather than recreating them |
| Principal gaps | Explicit intent/operation policy, normalized evidence, fusion lifecycle, CVD, true order flow, conversational watcher subscriptions, inbound Telegram actions, reliable execution/reconciliation state machine |

The estimates are architecture estimates, not measured code coverage. Backend reuse counts
existing domain responsibilities that can remain authoritative, even when adapters must be
added. Frontend reuse counts components and API clients, not retention of all 59 routes as
primary destinations.

## 2. Current-state architecture

```mermaid
flowchart LR
    UI["Next.js UI<br/>59 page routes"] --> API["FastAPI modular monolith<br/>42 route modules"]
    TGOUT["Telegram outbound provider"] <-->|"disabled by default"| ALERTS["Paper alerts"]
    TV["TradingView webhook"] -->|"flag-gated"| API
    API --> AG["LangGraph agent"]
    AG --> TOOLS["Typed tool registry"]
    API --> SVC["Domain services"]
    SVC --> DB[("Postgres / SQLite tests")]
    SVC --> RAG["Qdrant / in-memory fallback"]
    SVC --> MD["Binance public / mock market data"]
    WORKER["Dedicated or in-process worker"] -->|"flag-gated scans"| MD
    WORKER --> DB
    SVC -->|"paper_exchange_demo only"| BF["BloFin demo adapters"]
    SVC --> RISK["Deterministic risk + kill switch"]
```

The composition root in `backend/src/app/main.py` builds provider, strategy, and tool
registries, mounts all routers, and optionally starts an in-process worker. `AgentRuntime` in
`backend/src/app/agents/runtime.py` exposes services and tools rather than raw database access.
SQLAlchemy models are centralized in `backend/src/app/db/models.py`; repositories provide
domain-specific persistence. External boundaries use provider protocols under
`backend/src/app/providers/`.

The main architectural duplication is workflow representation. Similar concepts appear as
watcher candidates, setup detections, TradingView signals, paper-validation drafts/candidates,
paper signals, orchestration decisions, strategy signals, trade proposals, and alerts. Each is
useful in its context, but there is no shared evidence identity, lineage, freshness, or fusion
state.

## 3. Current frontend route inventory

“Current usage” means reachability in the checked-in application, not production traffic.
Primary/secondary navigation is defined by
`frontend/src/components/layout/navigation-config.ts`. Dynamic detail routes are reached from
their parent lists. Some compatibility routes re-export a page; others redirect through
`frontend/next.config.ts` and `frontend/src/lib/navigation/phase-b-redirects.ts`. Backend
dependencies are the route families used through `frontend/src/lib/api/index.ts`.

| Route | Purpose and important components | Backend dependencies | Current usage | Target disposition |
|---|---|---|---|---|
| `/` | Dashboard, discipline, attention queue; `TodaysDisciplineCard`, workflow adapters | `/dashboard`, `/risk`, workflow summaries | Primary nav | MERGE INTO AGENT |
| `/workspace` | Agent/plan workspace; `TradingAnalysisPanel`, `NarrativePanel`, plan summary, large message/symbol/timeframe form | `/chat`, `/proposals`, `/approvals`, `/risk` | Primary “Plan” nav | KEEP PRIMARY |
| `/tradingview-signals` | TradingView inbox and candidate action; `SignalsInbox` | `/tradingview`, `/paper-signal-orchestration` | Primary “Signals” nav | MERGE INTO LIVE WATCHER |
| `/paper-validation` | Validation hub/pipeline and attention queue | `/paper-validation` families | Primary “Validate” nav | KEEP SECONDARY |
| `/journal` | Journal hub, quick entry, needs-journaling queue | `/journal`, `/positions` | Primary “Journal” nav | KEEP PRIMARY |
| `/analytics` | Combined performance/setup/discipline/validation charts | `/analytics`, `/performance`, `/journal`, `/learning-analytics` | Primary “Analytics” nav | MERGE INTO TRADES & JOURNAL |
| `/portfolio` | Paper account, open/closed positions, exposure/history | `/performance`, `/positions`, `/journal`, `/dashboard` | Primary “Portfolio” nav | MERGE INTO TRADES & JOURNAL |
| `/settings` | Paper banner, safety disclaimers, notification preferences | `/providers`, `/notifications`, auth account state | Primary “Settings” nav | KEEP PRIMARY |
| `/proposals` | Proposal list/detail and kill switch | `/proposals`, `/risk` | Plan secondary nav | MERGE INTO AGENT |
| `/approvals` | Approval decisions/detail and kill switch | `/approvals`, `/proposals`, `/risk` | Plan secondary nav | MERGE INTO AGENT |
| `/pre-trade` | Large manual pre-trade and sizing form; `LossAcceptancePanel` | `/pretrade`, `/risk/size`, `/risk/loss-acceptance` | Plan secondary nav | MERGE INTO AGENT |
| `/manual-levels` | CRUD form for chart levels | `/manual-levels` | Plan secondary nav | MERGE INTO AGENT |
| `/strategy-lab` | Strategy library list | `/strategies` | Plan secondary nav | KEEP SECONDARY |
| `/strategy-lab/new` | Large `StrategyCardForm` | `/strategies` | Linked from strategy list | MERGE INTO AGENT |
| `/strategy-lab/[id]` | Strategy versions, structured rules, backtests, paper validation | `/strategies`, `/backtests`, `/paper-validation` | Dynamic detail | KEEP SECONDARY |
| `/strategy-lab/[id]/edit` | Large `StrategyCardForm` | `/strategies` | Dynamic edit | MERGE INTO AGENT |
| `/alerts` | In-app alerts, routing, Telegram test/manual delivery and auto-delivery preview | `/alerts`, `/notifications` | Signals secondary nav | MERGE INTO LIVE WATCHER |
| `/alerts/review` | Review scanner alerts and create drafts | `/alerts/setup-review`, `/paper-validation/drafts` | Signals secondary nav | MERGE INTO LIVE WATCHER |
| `/watcher` | Manual scanner and recent scans; `MarketWatcherScannerCard` | `/market-watcher/scan`, `/market-watcher/scans/recent` | Signals secondary nav | MERGE INTO LIVE WATCHER |
| `/market-watcher` | Legacy watcher status/history/bridge controls | `/market-watcher` | Signals secondary nav | MERGE INTO LIVE WATCHER |
| `/market` | Manual ticker/OHLCV/analyze form | `/market` | Signals secondary nav | MERGE INTO LIVE WATCHER |
| `/watchlist` | Watchlist CRUD form and kill switch | `/market/watchlist`, `/risk` | Signals secondary nav | MERGE INTO LIVE WATCHER |
| `/paper-signal-orchestration` | Advanced decisions and explicit paper-proposal action | `/paper-signal-orchestration` | Advanced signals nav | HIDE |
| `/paper-validation/drafts` | Validation draft list | `/paper-validation/drafts` | Validate secondary nav | KEEP SECONDARY |
| `/paper-validation/drafts/[draftId]` | Draft prep/checklist form | `/paper-validation/drafts/{id}` | Dynamic detail | MERGE INTO AGENT |
| `/paper-validation/candidates` | Candidate queue | `/paper-validation/candidates`, run plans | Validate secondary nav | KEEP SECONDARY |
| `/paper-validation/candidates/[candidateId]` | Candidate detail/status/plan action | `/paper-validation/candidates/{id}` | Dynamic detail | KEEP SECONDARY |
| `/paper-validation/run-plans` | Run-plan list | `/paper-validation/run-plans` | Validate secondary nav | KEEP SECONDARY |
| `/paper-validation/run-plans/[planId]` | Run-plan edit/start form | `/paper-validation/run-plans/{id}` | Dynamic detail | KEEP SECONDARY |
| `/paper-validation/run-sessions` | Manual validation sessions | `/paper-validation/run-sessions` | Validate secondary nav | KEEP SECONDARY |
| `/paper-validation/run-sessions/[sessionId]` | Observation and outcome recording | `/paper-validation/run-sessions/{id}` | Dynamic detail | KEEP SECONDARY |
| `/validation-priority` | Ranked validation work queue | `/validation-priority` | Validate secondary nav | KEEP SECONDARY |
| `/research-validation` | Evidence promotion workflow | `/research-validation`, `/backtests` | Advanced validate nav | HIDE |
| `/backtests/[id]` | Backtest result, verification, journal comparison/promotion | `/backtests`, `/research-validation`, `/journal` | Dynamic from strategy | KEEP SECONDARY |
| `/journal/import` | Large bulk import mapping/preview form | `/journal/trades/import`, `/journal/imports` | Journal secondary nav | KEEP SECONDARY |
| `/journal/statistics` | Journal aggregates and filters | `/journal/statistics` | Analytics secondary nav | MERGE INTO TRADES & JOURNAL |
| `/journal/comparison` | Human-versus-system comparison form | `/journal/comparison`, `/human-vs-system` | Analytics secondary nav | MERGE INTO TRADES & JOURNAL |
| `/lessons` | Lesson review/accept/reject and proposed rules | `/lessons` | Journal secondary nav | MERGE INTO TRADES & JOURNAL |
| `/knowledge` | RAG documents/chunks/search | `/knowledge` | Journal secondary nav | KEEP SECONDARY |
| `/learning-analytics` | Outcome, behavior, confidence and setup analytics | `/learning-analytics` | Analytics secondary nav | MERGE INTO TRADES & JOURNAL |
| `/coaching` | Coaching prompts/explanations | `/coaching` | Analytics secondary nav | MERGE INTO AGENT |
| `/strategy-quality` | Detector quality summaries/explanations | `/strategy-quality` | Analytics secondary nav | KEEP SECONDARY |
| `/positions` | Position list, stop/TP edit, paper close | `/positions`, `/risk` | Portfolio secondary nav | MERGE INTO TRADES & JOURNAL |
| `/risk` | Risk-setting form and kill switch | `/risk` | Portfolio secondary nav | MERGE INTO SAFETY & SETTINGS |
| `/settings/billing` | Combined billing and usage views | `/billing`, `/usage` | Settings secondary nav | KEEP SECONDARY |
| `/settings/team` | Alias for team/invitation view | `/organizations/invitations` | Settings secondary nav | KEEP SECONDARY |
| `/settings/audit` | Alias for audit view | `/audit/events` | Advanced settings nav | MERGE INTO SAFETY & SETTINGS |
| `/settings/exchange` | Alias for exchange diagnostics | `/exchange` | Advanced settings nav | MERGE INTO SAFETY & SETTINGS |
| `/settings/usage` | Client redirect shim to billing/usage | `/usage` | Compatibility route | DEPRECATE |
| `/billing` | Redirect shim to `/settings/billing` | `/billing` | Compatibility route, not main nav | DEPRECATE |
| `/usage` | Redirect shim to `/settings/billing` | `/usage` | Compatibility route, not main nav | DEPRECATE |
| `/audit` | Standalone audit list | `/audit/events` | Compatibility route | DEPRECATE |
| `/exchange` | Standalone BloFin sync/diagnostics | `/exchange` | Compatibility route | DEPRECATE |
| `/invitations` | Invitation management form | `/organizations/invitations` | Compatibility/deep link | DEPRECATE |
| `/login` | Authentication login | `/auth/login`, `/auth/me` through auth provider | Public route | KEEP SECONDARY |
| `/register` | Account registration | `/auth/register` | Public route | KEEP SECONDARY |
| `/forgot-password` | Password-reset request | `/auth/password-reset/request` | Public route | KEEP SECONDARY |
| `/reset-password` | Password-reset confirmation | `/auth/password-reset/confirm` | Public route | KEEP SECONDARY |
| `/verify-email` | Email verification | `/auth/verify-email/confirm` | Public/deep-link route | KEEP SECONDARY |

No route should be deleted in Phase 0. The strongest form-to-agent conversion candidates are
`/pre-trade`, `/manual-levels`, strategy create/edit, draft prep, run-plan edit,
`/journal/import`, `/journal/comparison`, `/risk`, `/market`, and `/watchlist`. The target agent
must call the same typed APIs/tools and show a reviewable structured preview; conversational UX
must not bypass validation or confirmation.

## 4. Current backend service inventory

### API surface

All route modules are mounted in `backend/src/app/main.py`.

| Route modules | Responsibility | Disposition |
|---|---|---|
| `api/routes/auth.py`, `organizations.py` | Auth, account, organization invitations | KEEP |
| `chat.py`, `tools.py` | Agent entry point and tool inspection/execution | MODIFY |
| `market.py`, `market_watcher.py`, `tradingview.py` | Market reads/history/watchlist, watcher, TradingView intake | MODIFY |
| `paper_signal_orchestration.py`, `paper_validation.py`, `research_validation.py`, `validation_priority.py` | Candidate and validation workflows | MERGE behind evidence/candidate lifecycle; keep APIs during migration |
| `strategy_library.py`, `strategy_modules.py`, `strategy_quality.py`, `backtests.py`, `manual_levels.py`, `pretrade.py` | Strategy versions, deterministic modules, tests and planning | MODIFY |
| `proposals.py`, `approvals.py`, `execution.py`, `positions.py`, `exchange.py` | Human-approved paper execution and position/exchange state | MODIFY |
| `risk.py` | Risk settings, sizing, kill switch and checks | KEEP |
| `alerts.py`, `notifications.py` | In-app/external alert lifecycle and preferences | MODIFY |
| `journal.py`, `human_vs_system.py`, `lessons.py`, `analytics.py`, `learning_analytics.py`, `coaching.py`, `performance.py`, `knowledge.py` | Journal, analytics, lessons and RAG | MODIFY/MERGE at orchestration and UI, not domain authority |
| `providers.py`, `health.py`, `metrics.py`, `worker.py`, `audit.py`, `usage.py` | Operations, telemetry and audit | KEEP |
| `billing.py`, `demo.py`, `dashboard.py` | Billing scaffold, demo seed, page summary | KEEP SECONDARY |

### Domain component families

| Major component | Exact repository paths | Current state | Disposition |
|---|---|---|---|
| Agent graph/state/routing | `backend/src/app/agents/graph.py`, `nodes.py`, `routing.py`, `runtime.py`; `schemas/agent.py` | Operational request graph, but intent semantics conflate analysis and planning | MODIFY |
| Tool boundary | `backend/src/app/tools/base.py`, `tools/registry.py` | Operational registry; some tools are stubs and mutation metadata is inconsistent | MODIFY |
| Provider abstraction | `backend/src/app/providers/base.py`, `factory.py`, `registry.py` | Operational and reusable | KEEP |
| Market providers/cache/history | `backend/src/app/providers/market_data.py`, `backend/src/app/services/market_data_service.py`, `backend/src/app/services/market_cache.py`, `backend/src/app/services/historical_candle_service.py`; `backend/src/app/repositories/historical_candles.py` | Binance public/mock data and stored candles with provenance/freshness | KEEP/MODIFY |
| Deterministic analysis | `backend/src/app/analysis/engine.py`, `indicators.py`, `structure.py`, `setups.py`, `confidence.py`, `filters.py` | Operational OHLCV analysis | KEEP |
| Watcher and bridge | `backend/src/app/services/market_watcher_service.py`, `backend/src/app/services/market_watcher_scanner.py`, `backend/src/app/services/market_watcher_setup_detectors.py`, `backend/src/app/services/market_watcher_bridge_service.py`; watcher repositories/schemas | Manual read-only scanner works; automation flag-gated and narrow | MODIFY |
| Worker | `backend/src/app/workers/entrypoint.py`, `runner.py`, `service.py`, `scanner.py`, `lock.py`, `repository.py`, `notifier.py` | Implemented; deployed definition exists; disabled in staging | MODIFY |
| TradingView | `backend/src/app/services/tradingview_signal_service.py`, `backend/src/app/security/tradingview_webhook.py`, `backend/src/app/repositories/tradingview_signal.py`, `backend/src/app/schemas/tradingview_signal.py` | Secure, idempotent intake implemented; disabled in staging | MODIFY |
| Paper orchestration | `backend/src/app/services/paper_signal_orchestration_service.py`; associated repository/schema | Deterministic TradingView-to-candidate/proposal path; disabled; no order placement | MERGE into common fusion/candidate lifecycle |
| Strategy system | `backend/src/app/services/strategy_library_service.py`, `backend/src/app/services/structured_rules_service.py`, `backend/src/app/services/strategy_rule_adapter.py`, `backend/src/app/services/structured_rule_resolver.py`, `backend/src/app/services/strategy_testability_service.py`; `backend/src/app/strategies/`; strategy schemas/repositories | Versioned cards, structured rules, deterministic built-ins | KEEP/MODIFY |
| Backtest/research/paper validation | `backend/src/app/services/backtest_*`, `backend/src/app/services/research_validation_service.py`, `backend/src/app/services/paper_validation_*`, `backend/src/app/services/paper_bot_engine.py`, `backend/src/app/services/paper_scheduler_service.py` | Extensive deterministic paper evidence lifecycle; scheduler disabled | KEEP/MODIFY |
| Planning/sizing | `backend/src/app/services/pretrade_analysis_service.py`, `backend/src/app/services/position_sizing_service.py`, `backend/src/app/services/loss_acceptance_service.py`, `backend/src/app/services/proposal_service.py` | Operational but pre-trade derivation uses simplistic constants/placeholders | MODIFY |
| Approval/execution | `backend/src/app/services/approval_service.py`, `backend/src/app/services/execution_service.py`, `backend/src/app/services/paper_execution_risk_gate.py`, `backend/src/app/services/execution_eligibility.py`, `backend/src/app/services/paper_order_idempotency.py` | Strong internal paper path; demo mirror best-effort | KEEP/MODIFY |
| Risk | `backend/src/app/services/risk/engine.py`, `backend/src/app/services/risk/rules.py`, `backend/src/app/services/risk/limits.py`, `backend/src/app/services/risk/kill_switch.py`, `backend/src/app/services/risk/daily_risk_accounting.py`, `backend/src/app/services/risk/settings_service.py`; `backend/src/app/services/risk_service.py` | Deterministic authority with execution-time recheck | KEEP |
| BloFin demo | `backend/src/app/providers/exchange/blofin_client.py`, `backend/src/app/providers/exchange/blofin_account.py`, `backend/src/app/providers/exchange/blofin_market_data.py`, `backend/src/app/providers/exchange/blofin_execution.py`, `backend/src/app/providers/exchange/factory.py`; `backend/src/app/services/blofin_sync_service.py` | Implemented and tested adapters; not configured/enabled in staging | MODIFY |
| Alerts/Telegram | `backend/src/app/services/paper_alert_service.py`, `backend/src/app/services/alert_delivery_service.py`, `backend/src/app/services/delivery_routing_service.py`, `backend/src/app/services/telegram_*`; `backend/src/app/providers/alert_delivery/telegram.py` | Outbound delivery and preferences implemented; inbound actions missing; disabled | MODIFY |
| Positions/portfolio/performance | `backend/src/app/services/position_service.py`, `backend/src/app/services/paper_portfolio_service.py`, `backend/src/app/services/performance/`, `backend/src/app/services/performance_service.py`; repositories | Internal paper lifecycle and analytics | KEEP/MODIFY |
| Journal/learning | `backend/src/app/services/journal_trade_service.py`, `backend/src/app/services/journal_service.py`, `backend/src/app/services/journal_excursion_*`, `backend/src/app/services/journal_statistics_service.py`, `backend/src/app/services/human_vs_system_service.py`, discipline analyzers, `backend/src/app/services/lesson_candidate_service.py`, `backend/src/app/services/journal_rag_sync_service.py`; repositories/schemas | Rich record/analysis layer; complete automatic lifecycle linkage is partial | KEEP/MODIFY |
| Audit/usage/observability | `backend/src/app/services/audit_service.py`, `backend/src/app/services/usage_service.py`, `backend/src/app/services/usage_cost.py`; `backend/src/app/observability/`; paper observability services | Operational structured records and cost metadata | KEEP |

No major backend family is a removal candidate during migration. Stubs in
`tools/registry.py` (`funding`, `scenario_simulator`, `journal_writer`, `position_reader`,
`paper_execution`) should be replaced by adapters to existing real services or deprecated
after callers move; they must not become a second execution path.

## 5. Agent and intent-routing audit

### Current graph

`backend/src/app/agents/graph.py` implements:

`receive -> auth -> quota -> rate -> injection -> moderation -> message class -> intent ->
context -> branch -> analysis/strategy/general -> policy -> risk -> approval -> tools -> memory
-> usage -> response -> narrative -> output validation`.

Strengths:

- typed `AgentState` with correlation, market context, proposal/risk, approval, citations,
  narrative, usage and audit fields (`backend/src/app/schemas/agent.py`);
- explicit prompt-injection, moderation, trading-policy, deterministic-risk and output guards;
- service/tool boundaries in `AgentRuntime`;
- deterministic final facts with an optional validated narrative;
- confirmation checks for several mutation tools
  (`backend/src/app/agents/mutation_policy.py`, `tools/registry.py`).

Defects relevant to redesign:

1. `message_classification` is keyword-based and treats `analyze`, `setup`, `plan`, `trade`,
   `btc`, or `eth` as `ANALYSIS_REQUEST`.
2. `intent_classification` maps `analyze`, `plan`, `setup`, `pullback`, or `entry` to
   `PLAN_TRADE`.
3. `route_after_intent` sends `MONITOR`, `PLAN_TRADE`, `EXECUTE`, or any
   `ANALYSIS_REQUEST`/`COMMAND` into `trading_analysis`. `COMMAND` is referenced here but is not
   currently assigned by `message_classification`.
4. The trading-analysis branch has no edge separating read-only analysis from plan
   construction; it always visits `trade_proposal_generation`. That node is a no-op unless the
   intent is `PLAN_TRADE` or `EXECUTE`, which is why the keyword-to-`PLAN_TRADE` mapping is the
   decisive defect.
5. `AgentState` has no explicit operation class, requested side effects, immutable approval
   token, fusion candidate, evidence bundle, position-management command, or clarification
   state.
6. `APPROVAL_RESPONSE` message class does not provide first-class `APPROVE`, `REJECT`, or
   `SKIP` intents. Existing approval mutations mostly live in HTTP APIs.
7. Several strategy-workflow intents can mutate through tools, but mutation policy is
   distributed rather than enforced by one operation-policy gate.

The existing taxonomy is much broader than the target table below:
`backend/src/app/schemas/agent.py` defines strategy, backtest, lesson, paper-validation,
scheduler, alert and watcher sub-intents. `backend/src/app/agents/strategy_intent.py` routes
many of them to `strategy_workflow_tools`. This is reusable coverage, but it remains
keyword-driven and lacks a uniform operation-class policy.

### Required-intent support today

| Required intent | Current support | Classification |
|---|---|---|
| `MARKET_ANALYSIS` | No distinct intent; becomes `PLAN_TRADE` or `MONITOR` | MISSING/unsafe mapping |
| `SETUP_ANALYSIS` | No distinct intent; “setup” becomes `PLAN_TRADE` | MISSING/unsafe mapping |
| `PLAN_TRADE` | Present | PARTIALLY IMPLEMENTED |
| `REVIEW_TRADE` | Generic `REVIEW` plus analytics/strategy sub-intents | PARTIALLY IMPLEMENTED |
| `MANAGE_POSITION` | Position HTTP APIs exist, but no first-class agent intent/tool | MISSING in agent |
| `JOURNAL` | Message class and many lesson/review intents exist; no single intent contract | PARTIALLY IMPLEMENTED |
| `EXPLAIN` | Present | EXISTS AND OPERATIONAL |
| `CONFIGURE` | Risk/notification tools exist, but no general intent | PARTIALLY IMPLEMENTED |
| `APPROVE` | Message class only; no first-class intent | MISSING in agent |
| `REJECT` | Message class only; lesson reject sub-intent exists | PARTIALLY IMPLEMENTED |
| `SKIP` | No first-class intent | MISSING |

## 6. LLM/model audit

The current provider protocol and OpenAI implementation are reusable:
`backend/src/app/providers/llm.py`. `OpenAILLMProvider` supports chat completions and routes
GPT-5.x/o-series models to the Responses API. It retries bounded transient failures, sanitizes
errors, records model/provider/token/latency/fallback metadata, and can fall back to
`MockLLMProvider` when policy allows. `backend/src/app/providers/factory.py` forces mock locally
when configured and fails closed for required providers outside local through provider policy
and deployment validation.

Current checked-in model configuration is one global `LLM_MODEL`, default and staging value
`gpt-4o-mini` (`backend/src/app/core/config.py`, `render.yaml`). There is no task-aware model
router.

Observed generation calls:

- `backend/src/app/services/narrative_service.py`: structured JSON narrative for trading
  analysis, risk explanation, or journal review; sanitized context; validated output; safe
  deterministic fallback.
- `backend/src/app/agents/nodes.py` usage-tracking path: a small completion associated with the
  request. Core intent classification, strategy execution, proposal calculations, risk and
  output checks are deterministic.
- `backend/src/app/services/structure_from_text_service.py` is currently keyword-assisted,
  despite an older “LLM-assisted” schema description; it does not call an LLM.

Cost handling exists in `services/usage_cost.py` and `cost_estimator.py`. Provider-reported
cost can be stored; otherwise deterministic placeholder rates are explicitly non-billing-grade.
The placeholder rate table only has named entries for `gpt-4o-mini` and `gpt-4o`; other models
use a generic default.

Classification: provider/failure/telemetry **operational**; narrative reasoning
**operational but narrow**; model routing **missing**; high-impact candidate synthesis
**missing**; cost visibility **partially implemented**.

## 7. Market-data and intelligence-source audit

### Provider and source inventory

| Source required by target | Repository evidence | Current classification |
|---|---|---|
| Price structure | Swing points, support/resistance, market structure, Fibonacci and five setup detectors in `backend/src/app/analysis/`; Binance OHLCV | EXISTS AND OPERATIONAL for request/manual scans |
| Market regime | Deterministic structure trend and simple pre-trade labels in `analysis/structure.py` and `pretrade_analysis_service.py` | PARTIALLY IMPLEMENTED |
| Volume | OHLCV volume, volume average/ratio/trend and VWAP in `analysis/indicators.py`, `indicator_service.py`, watcher high-volume condition | EXISTS AND OPERATIONAL, basic bar-volume only |
| CVD | No code or schema found for cumulative volume delta, aggressor-side trades, or divergence | MISSING |
| Order flow | Provider supports a point-in-time L2 order-book snapshot in `providers/market_data.py`; not normalized, persisted, fused, or used by detectors | PARTIALLY IMPLEMENTED |
| TradingView | Signed/idempotent intake and persistence in `tradingview_signal_service.py` | EXISTS BUT DISABLED in staging |
| Custom patterns | Versioned strategy cards/structured rules plus fixed detectors | PARTIALLY IMPLEMENTED |
| Current positions | Internal positions and optional BloFin sync snapshots | EXISTS AND OPERATIONAL internally; demo sync disabled |
| Portfolio exposure | Daily accounting, portfolio/performance services | EXISTS AND OPERATIONAL for paper records |
| Daily PnL | `risk/daily_risk_accounting.py`, dashboard discipline | EXISTS AND OPERATIONAL for paper sources |
| Risk settings | Persisted settings plus defaults | EXISTS AND OPERATIONAL |
| Cooldown state | Paper-signal loss cooldown/conflict windows in orchestration settings/service | PARTIALLY IMPLEMENTED and disabled with orchestration |
| Strategy evidence/statistics | Backtest, research evidence, paper windows, strategy quality and journal statistics | EXISTS AND OPERATIONAL as separate workflows |
| Journal history/recent behavior | Canonical and legacy journal, discipline analytics, RAG | EXISTS AND OPERATIONAL |
| User-approved rules | Accepted lessons and explicit strategy versions | PARTIALLY IMPLEMENTED |
| Current evaluation phase | Strategy/backtest/paper-validation statuses and version records | EXISTS AND OPERATIONAL |

`backend/src/app/providers/market_data.py` exposes ticker, OHLCV, funding, open interest, and
order book through typed envelopes containing source, timestamp, live/stale status, provider
and fallback. Binance failures fall back to deterministic mock data and mark that fact. This is
good for UI continuity but must be ineligible for candidate confirmation/execution.

Historical candles are persisted and bounded through
`backend/src/app/services/historical_candle_service.py` and
`repositories/historical_candles.py`. Watcher scans currently support only BTC/ETH/SOL and
15m/1h (`services/market_watcher_scanner.py`), despite the wider general `Timeframe` enum.

“Order block” in `analysis/setups.py` is a price-action candle pattern; it is not proof that
trade-level order-flow ingestion exists. The available order-book snapshot is also not enough
to compute CVD because it contains resting liquidity, not buyer/seller initiated executions.

## 8. Watcher/worker audit

The worker has a standalone Render-compatible entry point, fixed-interval loop, heartbeat,
pause/resume API, scan-run history, dead-letter behavior, bounded backtest draining, and a
token-fenced Redis lock with TTL. Paths:

- `backend/src/app/workers/entrypoint.py`
- `backend/src/app/workers/runner.py`
- `backend/src/app/workers/service.py`
- `backend/src/app/workers/scanner.py`
- `backend/src/app/workers/lock.py`
- `backend/src/app/workers/repository.py`

The worker scanner uses `market_watcher_default_symbols`, a fixed 1h timeframe, the
deterministic analysis engine, and persists fired `SetupDetectionRecord` rows. It does not call
the richer `MarketWatcherService.scan`, does not use user watchlists, and does not run signal
fusion. Its notifier sends aggregate outbound setup counts, not actionable candidates.

`MarketWatcherService` supports confirmed manual dry runs and in-app alert creation, persists
per-pair observations and scan summaries, captures provider degradation, emits audit and paper
observability events, and deduplicates alerts. `MarketWatcherBridgeService` can match fresh
observations to active paper-validation runs and trigger scans, but both bridge flags are
disabled. The bridge keeps latest tick state in process memory while decision history is
persisted.

Technical debt:

- worker and manual watcher use different scan pipelines;
- watchlist items do not carry timeframe/pattern/evidence-expression subscriptions;
- supported symbols/timeframes are hard-coded in the scanner;
- Redis lock construction falls back to a process-local lock when
  `rate_limit_use_redis=false` or when Redis cannot be reached, even outside local; this
  weakens cross-instance exclusion and should fail closed for an always-on deployment;
- no durable event/outbox connects evidence, alerts, approval, execution and journal;
- scan freshness is present, but candidate-level expiry and source-specific freshness are not
  unified.

## 9. Detector audit

Fixed setup detectors are pure and deterministic in `backend/src/app/analysis/setups.py`, run
by `analysis/engine.py`, and are adapted to watcher candidates by
`services/market_watcher_setup_detectors.py`.

| Detector | Rule | Main limitation |
|---|---|---|
| `liquidity_sweep` v1.0.0 | Wick exceeds prior swing by at least 0.25 ATR and closes back inside | Single-bar/prior-swing heuristic; no volume, CVD, flow, regime or multi-timeframe confirmation |
| `sfp` v1.0.0 | New extreme beyond prior swing, directional candle closes back inside | Single-bar heuristic; no threshold for excursion quality or evidence fusion |
| `trend_pullback` v1.0.0 | Structure trend, EMA12/26 alignment and close crosses/touches fast EMA | Loose touch rule; no sequence, depth, volume or invalidation quality |
| `order_block` v1.0.0 | Opposite candle before a 1.5 ATR move over three bars | Retrospective price proxy, not order-flow evidence; no mitigation/freshness logic |
| `breakout_retest` v1.0.0 | Close broke a support/resistance in five bars and latest close is within 0.25 ATR | Close-only retest approximation; no volume/flow acceptance or false-break lifecycle |

The watcher also has five generic conditions in `market_watcher_scanner.py`: `strong_move`,
`pullback_near_support`, `range_breakout_watch`, `high_volume_move`, and
`risk_volatility_warning`. Thresholds are module constants. Candidates are flat events, not
versioned pattern progression.

## 10. Telegram audit

| Capability | Evidence | State |
|---|---|---|
| Outbound provider | `providers/alert_delivery/telegram.py` | Implemented/tested, disabled in staging |
| Preferences/routing | `services/notifications/preferences_service.py`, `delivery_routing_service.py` | Implemented |
| Formatting | Provider builds fixed plain-text paper disclaimer | Implemented but basic |
| Manual delivery | `telegram_alert_delivery_service.py`; exact confirmation, owner API dependency, audit, duplicate check | Implemented/tested |
| Automatic delivery | `telegram_automatic_delivery_service.py` | Read-only preview/readiness only; actual automatic sender missing |
| Generic retries | `alert_delivery_service.py` | Implemented for routed delivery |
| Worker integration | `workers/notifier.py` | Outbound aggregate alerts; flags disabled |
| Incoming commands | No Telegram webhook/update consumer | MISSING |
| Interactive buttons/callbacks | No inline keyboard/callback-query model | MISSING |
| Approval support | No Telegram-bound proposal approval token/action | MISSING |
| Status feedback | Outbound delivery status exists; no conversational action receipts | PARTIALLY IMPLEMENTED |

Existing duplicate protection recognizes delivered Telegram alerts and stores a manual delivery
marker/id. Generic payloads use stable `alert-deliver:{alert_id}` keys, but Telegram itself is
not an idempotent API; durable claimed/sending/delivered state is needed before automatic
delivery. No target action (`APPROVE`, `REJECT`, `SKIP`, `REDUCE RISK`, `EXPLAIN`,
`SHOW CHART`, `CLOSE`, `STATUS`) is currently supported inbound.

## 11. BloFin demo audit

| Concern | Current evidence | Assessment |
|---|---|---|
| Client/signing/retries/rate limit | `providers/exchange/blofin_client.py` | Implemented and tested |
| Demo host safety | `core/exchange_safety.py`; client calls `assert_demo_host` | Strong allowlist and production-host denial |
| Account/permissions/mode/leverage | `blofin_account.py`, startup readiness | Implemented; rejects confirmed withdrawal/transfer scopes |
| Market data | `blofin_market_data.py` implements market provider contract | Implemented |
| Market/limit placement | `blofin_execution.py` maps typed order request | Implemented |
| Cancellation/get order | `blofin_execution.py` | Implemented |
| Fills/partial fills | Result parser supports accumulated size, average price and fill list | Parsing implemented; no durable polling lifecycle |
| Position mode | Account mode plus `position_side.py` mapping | Implemented |
| Duplicate-order protection | deterministic venue client ID from internal idempotency key; unique internal key | Implemented foundation |
| Account/position sync | `blofin_sync_service.py` bounded read-only snapshots | Implemented, disabled |
| Internal position reconciliation | No durable match of venue positions/fills to internal position lifecycle | MISSING |
| PnL/fee/funding reconciliation | Snapshot fields exist, but no authoritative reconciliation to orders/journal | MISSING |
| Close workflow | Internal `PositionService.close_paper`; provider supports reduce-only request, but no integrated demo close state machine | MISSING |

Tests include `backend/tests/test_blofin_provider.py`,
`test_blofin_execution.py`, `test_exchange_safety.py`, `test_exchange_blackbox.py`,
`test_exchange_status.py`, `test_exchange_diagnostics.py`, and
`test_at037_tradingview_blofin.py`.

The checked-in deployment is not configured or enabled for BloFin demo:
`render.yaml` sets `EXCHANGE_MODE=paper_internal` and does not declare BloFin credentials or
demo URLs. Therefore the capability is **implemented and tested**, has configuration fields,
has deployment-safe code, but is **not configured or currently enabled in staging**.

`ExecutionService` first creates an internal filled paper order/position and then
best-effort-mirrors it to demo; venue failure is swallowed and audited. That is acceptable for
an optional mirror but insufficient for a target loop claiming reconciled demo execution. The
target must expose `SUBMITTING`, `ACKNOWLEDGED`, `PARTIALLY_FILLED`, `FILLED`,
`CANCEL_PENDING`, `CANCELLED`, `REJECTED`, and `RECONCILIATION_REQUIRED` explicitly.

## 12. Risk and safety audit

Existing authorities to preserve:

| Invariant | Existing enforcement |
|---|---|
| Paper-only defaults | `Settings.execution_mode=PAPER`, `enable_real_trading=False`; `render.yaml` repeats them |
| Real trading disabled | `core/config.py`, `core/deployment_safety.py`, `core/exchange_safety.py`; `AgentRuntime.real_trading_allowed=False` |
| No production BloFin host | `core/exchange_safety.py`, `blofin_client.py` |
| Global/tenant kill switch | `global_kill_switch_active`; `services/risk/kill_switch.py`; checks before and immediately before fill in `execution_service.py` |
| Deterministic risk | `services/risk/engine.py`, rules/limits; fresh server-side recheck in `paper_execution_risk_gate.py` |
| Daily loss/trade count/exposure | `risk/daily_risk_accounting.py`, execution-time context |
| Cooldown/conflict | `paper_signal_orchestration_service.py` and settings |
| Overtrading/green-day guard | persisted risk settings and execution-time risk context |
| Request/proposal binding | symbol, side, size and price checks in `paper_execution_risk_gate.py` |
| Human approval | persisted approval must match proposal and be approved in `execution_service.py` |
| Loss acceptance | proposal fields/service; eligibility gate |
| Freshness/fallback | provider envelopes; execution refuses stale/fallback data when provider and market-provider modes are not `mock` |
| Order idempotency | unique idempotency key and concurrent convergence in `paper_order_idempotency.py` |
| Alert dedupe | `PaperAlertService` dedup keys; Telegram delivered markers |
| Audit | audit service plus proposal, approval, risk, order, watcher, alert, sync events |
| Failure recovery | worker dead-letter records, alert retry metadata, idempotent order replay; exchange reconciliation remains incomplete |

Important caveats:

- the paper-validation `AUTO_PAPER` simulator can open simulated paper trades without the
  proposal/approval API because it is a validation simulator, not `ExecutionService`; it must
  remain clearly separated from BloFin demo execution;
- `backend/src/app/services/pretrade_analysis_service.py` and proposal-related paths in
  `backend/src/app/agents/nodes.py` can substitute a `60000` placeholder when market context
  is unavailable. This is acceptable only for visibly limited analysis and must never reach
  execution;
- fallback market data is deliberately available. Candidate confirmation and demo execution
  must reject it, not merely label it;
- current demo mirroring is best-effort and needs explicit reconciliation states before it is
  used as the primary demo-execution path.

## 13. Journal, analytics and learning audit

The canonical journal model is a strong reuse anchor. `JournalTrade` and related models in
`backend/src/app/db/models.py`, with schemas in `schemas/journal_trades.py`, represent plans,
execution, PnL, fees/funding/slippage, links to position/paper trade/proposal/order/backtest/run,
strategy/version, evidence, rule checks, observations, and deterministic excursions.

Implemented:

- canonical journal CRUD/import/backfill and legacy journal entries;
- links to position, paper-validation trade, proposal, order, backtest trade and strategy;
- MFE/MAE, available profit, capture percentage and historical-candle replay with source,
  staleness, gaps and completeness (`journal_excursion_calculator.py`,
  `journal_excursion_replay_service.py`);
- setup statistics, performance, discipline, risk behavior, human-vs-system comparison;
- runner missed-profit and stop-refusal analyzers;
- lesson candidates that require accept/reject review;
- optional Journal-to-RAG sync;
- explicit strategy version creation from accepted lessons;
- opt-in auto-journal hooks after position close and paper-validation trade close.

Partial/missing:

- both auto-journal flags default off and are absent from `render.yaml`;
- one durable lifecycle record does not yet start at detection and carry the same lineage
  through candidate, approval, demo order, reconciliation, close and journal;
- internal position close can auto-journal, but BloFin fill/fee/funding/PnL reconciliation is
  absent;
- MFE/MAE replay is post-trade and depends on stored candle completeness;
- lesson review exists, but no orchestrated historical validation -> paper validation ->
  promotion workflow enforces all target gates as one state machine;
- no automatic self-modification exists, which is correct and must remain so.

## 14. Deployment and feature-flag audit

Repository configuration:

- backend API and worker: `render.yaml`;
- frontend: `frontend/vercel.json`;
- staged CORS URLs in `render.yaml`:
  `https://alpha-trade-ai-eight.vercel.app`,
  `https://alpha-trade-ai-alphatrade-ai.vercel.app`, and
  `https://alpha-trade-ai-git-main-alphatrade-ai.vercel.app`;
- deployment safety: `backend/src/app/core/deployment_safety.py`;
- exchange safety: `backend/src/app/core/exchange_safety.py`.

This audit did not query live Render/Vercel control planes. “Staging” below means checked-in
blueprint intent, not proof of the currently running service state.

| Capability/flag | API staging blueprint | Worker staging blueprint | Classification |
|---|---|---|---|
| `EXECUTION_MODE` | `paper` | `paper` | Enabled safe posture |
| `ENABLE_REAL_TRADING` | `false` | `false` | Enforced disabled |
| `PROVIDER_MODE` | `fallback` | `fallback` | Configured; non-local policy requires OpenAI/Qdrant |
| `EXCHANGE_MODE` | `paper_internal` | `paper_internal` | BloFin demo disabled |
| `MARKET_DATA_ENABLED` | `true` | `true` | Configured |
| `WORKER_ENABLED` | not set/default false | `false` | Deployed definition, disabled |
| `MARKET_WATCHER_ENABLED` | `false` | not set/default false | Implemented, disabled |
| `MARKET_WATCHER_BRIDGE_ENABLED` | `false` | not set/default false | Implemented, disabled |
| `ENABLE_PAPER_SCHEDULER` | absent/default false | absent/default false | Implemented, disabled |
| `TRADINGVIEW_WEBHOOK_ENABLED` | absent/default false | n/a | Implemented, disabled |
| `PAPER_SIGNAL_ORCHESTRATION_ENABLED` | absent/default false | n/a | Implemented, disabled |
| `ALERT_DELIVERY_ENABLED` | `false` | absent/default false | Implemented, disabled |
| `TELEGRAM_ALERTS_ENABLED` | `false` | absent/default false | Implemented, disabled |
| `AUTOMATIC_TELEGRAM_DELIVERY_ENABLED` | absent/default false | absent/default false | Preview only, disabled |
| `WORKER_ALERTS_ENABLED` | absent/default false | absent/default false | Implemented, disabled |
| BloFin demo fields | absent; `paper_internal` | absent | Not configured |
| Journal auto hooks | absent/default false | absent/default false | Implemented, disabled |
| `ALERT_WEBHOOK_ENABLED` | `false` | absent/default false | Implemented, disabled |
| `BILLING_ENABLED` | `false` | absent/default false | Billing scaffold disabled |
| `EMAIL_PROVIDER` | `mock` | absent/default `mock` | Mock delivery posture |
| `DEMO_SEED_ENABLED` | `true` | absent/default false | API staging-only demo seed |
| Refresh-cookie/denylist/rate-limit safety | Explicit secure cookie, Redis denylist and no rate-limit fallback | Partial shared settings | Enabled API safety posture |

`frontend/vercel.json` only defines Next.js install/build/output behavior. Frontend API URL
configuration is environment-driven elsewhere; no live deployment status is inferable from the
repository.

The worker shares the same `Settings` deployment validator as the API. The checked-in worker
block declares database, Redis, JWT and OpenAI settings, but not `QDRANT_URL` or
`CORS_ORIGINS`, both required by `backend/src/app/core/deployment_safety.py` in staging even
though a worker does not directly use browser CORS. Unless those values are supplied separately
in the Render dashboard, enabling the worker would fail settings validation. This deployment
contract should be simplified or made role-aware before activation.

## 15. Test and evaluation audit

Static inventory at the audit base found 112 backend test files, 184 frontend Vitest
unit/component files under `frontend/src`, and 20 Playwright spec files under `frontend/e2e`
(204 frontend test/spec files total). These are file counts, not test case counts or a claim
that they passed in this audit.

| Area | Evidence |
|---|---|
| Backend unit/integration | `backend/tests/` |
| Frontend/Vitest | colocated `*.test.ts[x]` under `frontend/src/` |
| Playwright | `frontend/playwright.config.ts`, `frontend/e2e/` |
| Agent graph | `backend/tests/test_agent_graph.py` |
| RAG | `backend/tests/test_rag.py`, `evaluation/evaluate_rag.py` |
| Guardrails | `backend/tests/test_guardrails.py`, `evaluation/evaluate_guardrails.py` |
| Agent evaluation | `evaluation/evaluate_agent.py`, `evaluation/datasets/agent_cases.json` |
| Deployment safety | `backend/tests/test_deployment_safety.py`, `test_deployment_scripts.py` |
| Exchange/BloFin | exchange and BloFin test files listed in section 11 |
| Watcher | four `test_market_watcher_scanner_slice_*.py` files plus `test_market_watcher_scan_staging_script.py` |
| Worker | `backend/tests/test_worker.py`, `test_worker_notifier.py` |
| Telegram | `test_telegram_alert_delivery.py`, `test_telegram_automatic_delivery.py`, `test_telegram_test_alert.py` plus frontend panel tests |
| Risk | `test_risk_engine.py`, `test_at012_paper_risk_at_execution.py`, `test_risk_settings_slice_45.py` |
| Journal | AT-030–033 journal tests plus statistics/auto-journal tests |

The evaluation scripts are deterministic and require 100% according to `docs/evaluation.md`;
they cover retrieval metadata, unsafe narrative phrases, mock disclosure, invalidation and
paper-mode claims. They do not evaluate CVD/order flow, fusion transitions, Telegram inbound
authorization, model-tier routing, or end-to-end BloFin demo reconciliation.

## 16. Consolidated disposition matrix

| Capability | KEEP | MODIFY | MERGE | HIDE/DEPRECATE | REMOVE |
|---|---:|---:|---:|---:|---:|
| Provider protocols/factory | ✓ |  |  |  |  |
| Binance/mock market data and provenance | ✓ | ✓ freshness eligibility |  |  |  |
| Deterministic analysis/indicators | ✓ | extend evidence adapters |  |  |  |
| Risk, kill switch, execution-time gate | ✓ |  |  |  |  |
| Strategy cards/versions/structured rules | ✓ | extend to Pattern Cards |  |  |  |
| Watcher, worker, watchlist |  | ✓ | one surveillance pipeline | legacy controls later hidden |  |
| TradingView/watcher/paper signal schemas |  | adapters | normalized evidence/fusion | old workflow screens |  |
| Agent graph/intent/routing |  | ✓ |  |  |  |
| Proposal/approval/internal execution | ✓ | lifecycle integration |  |  |  |
| BloFin demo adapters | ✓ | reconciliation/close |  |  |  |
| Alert/Telegram outbound | ✓ | inbound/actions/outbox |  |  |  |
| Journal/performance/lessons/RAG | ✓ | lifecycle automation | UI merge |  |  |
| Frontend primary navigation |  |  | four surfaces | compatibility routes |  |
| Stub registry tools |  | replace with adapters | existing services | then deprecate | only after no callers |

No product component is recommended for immediate removal. A future removal decision requires
usage telemetry, compatibility redirects, migrated links/tests, and an independent safety
review.

## 17. Missing capabilities

1. Explicit intent plus operation-class contract separating read, plan, mutation, approval,
   execution, configuration and journal actions.
2. Immutable normalized evidence with source lineage, source-specific freshness and quality.
3. Deterministic signal-fusion state machine and transition explanations.
4. Trade-level market feed and CVD computation/divergence evidence.
5. True order-flow feature extraction (aggressor imbalance, absorption/exhaustion); existing
   order-book snapshots are insufficient.
6. Versioned Pattern Card fields and deterministic sequence evaluator.
7. Conversational watcher subscriptions containing symbols, timeframes, patterns and evidence
   expressions.
8. One durable surveillance pipeline shared by worker and manual API.
9. Inbound Telegram webhook, user/chat binding, callbacks, expiring action tokens and
   idempotent action receipts.
10. Durable event/outbox handoff across candidate, delivery, approval, execution and journal.
11. BloFin demo order/fill/position/PnL reconciliation and integrated reduce-only close.
12. Task-aware model router and per-tier budgets/fallback policy.
13. Full lifecycle correlation ID from detection through learning/promotion.

## 18. Technical debt relevant to redesign

- Keyword intent and message classification create unsafe semantic coupling.
- `AgentState` is typed but graph storage is `StateGraph(dict)`, limiting compile-time state
  guarantees.
- Similar workflow records lack a common evidence/lineage contract.
- Worker and watcher scan different pipelines.
- In-memory fallback for worker lock is inappropriate for multi-instance staging.
- Watcher symbol/timeframe constraints are hard-coded.
- Pre-trade planning uses fixed percentages and a placeholder price on missing data.
- Some registered agent tools are successful no-op stubs and can misrepresent capability.
- Generic tool risk metadata does not centrally enforce every mutation confirmation.
- Automatic Telegram service is a preview despite naming that can suggest delivery.
- Demo execution mirror treats venue failure as best-effort after internal fill.
- Model cost rates are placeholders and do not cover routed tiers.
- Historical documentation can lag behavior; target work must keep operational claims tied to
  configuration and runtime health.

## 19. Reuse-percentage rationale

For the first vertical slice, 23 backend responsibility blocks were considered. Existing code
can remain the authority or a direct adapter for market data/history, price/volume analysis,
worker loop, lock/heartbeat, watcher persistence, strategy/versioning, paper validation,
candidate/proposal, alerts, outbound Telegram, approvals, risk, sizing, audit, idempotency,
BloFin client/account/execution, positions, journal, analytics, RAG and tests. Materially new
responsibilities are CVD, trade-flow/order-flow features, normalized evidence, fusion,
Telegram inbound actions, durable orchestration/outbox, and demo reconciliation. Accounting
for required modifications yields approximately **78% backend reuse**.

For frontend, auth, shell primitives, cards/tables/charts, safety indicators, API client/types,
agent panels, watcher panels, journal/portfolio components and settings controls are reusable.
Navigation, information architecture, combined surface containers and conversational action
previews need redesign. The estimate is approximately **60% frontend reuse**, while fewer than
half of current routes should remain prominent.

## 20. Risks and blockers

| Risk/blocker | Consequence | Required resolution before relevant implementation |
|---|---|---|
| No CVD/trade-flow source selected | Vertical slice cannot truthfully claim CVD/order flow | Select a read-only public/demo data source; define timestamp, sequence-gap and aggressor classification semantics |
| BloFin demo host/API behavior needs runtime verification | Repository tests do not prove current venue contract | Independently verify current official demo API documentation and sandbox behavior without enabling live connectivity |
| Inbound Telegram identity design absent | Remote mutations could be spoofed or replayed | Threat model bot webhook, secret header, chat/user allowlist, action nonce, expiry and replay store |
| Best-effort demo mirror diverges from target semantics | Internal “filled” can disagree with venue | Add explicit submission/reconciliation state machine and operator-visible recovery |
| Multiple candidate workflows | Duplicate alerts/proposals and confusing lineage | Normalize evidence and use adapters before enabling automation |
| Feature flags all disabled in staging | No always-on behavior is presently proven | Enable only after vertical-slice tests, deployment review and explicit human approval |
| Provider fallback can look usable | Mock/degraded evidence could contaminate decisions | Fusion and execution eligibility must reject fallback, stale and sequence-gapped evidence |
| Documentation-only evidence cannot prove deployment runtime | Enabled/configured claims could be wrong | Treat repository blueprint as intent; verify runtime in a separate deployment task |

There is no blocker to completing Phase 0 architecture. These are implementation gates. No
live-trading capability is required or proposed.
