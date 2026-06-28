"use client";

import Link from "next/link";
import { useCallback } from "react";

import { AlertRoutingCard } from "@/components/AlertRoutingCard";
import { MarketWatcherScannerCard } from "@/components/MarketWatcherScannerCard";
import { AuditEventCard } from "@/components/AuditEventCard";
import { ExchangeDiagnosticsCard } from "@/components/ExchangeDiagnosticsCard";
import { ProviderStatusCard } from "@/components/ProviderStatusCard";
import { TodaysDisciplineCard } from "@/components/TodaysDisciplineCard";
import { WorkflowStepper } from "@/components/WorkflowStepper";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { alertTypeLabel, setupConditionLabel, severityRank, severityVariant } from "@/lib/alert-display";
import { strategyStatusFor } from "@/lib/strategy-status";
import { formatDecimal } from "@/lib/utils";
import { buildWorkflowSteps, firstActionableStep } from "@/lib/workflow-steps";
import type { AlertRoutingSummary, DashboardSummary, ExchangeDiagnosticsSummary, MarketWatcherSummary, UserStrategy } from "@/lib/api/types";

async function settled<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch {
    return fallback;
  }
}

const RUNNING_PAPER = new Set(["running", "active", "in_progress"]);

function featuredStrategy(strategies: UserStrategy[]): UserStrategy | null {
  if (strategies.length === 0) return null;
  const running = strategies.find((s) =>
    RUNNING_PAPER.has((s.paper_validation_status ?? "").toLowerCase()),
  );
  const eligible = strategies.find((s) => s.paper_eligible);
  return running ?? eligible ?? strategies[0];
}

type DashboardData = {
  summary: DashboardSummary | null;
  strategies: UserStrategy[];
  usage: Awaited<ReturnType<typeof api.usage.summary>> | null;
  audit: Awaited<ReturnType<typeof api.audit.events>> | null;
  legacyDiscipline: Awaited<ReturnType<typeof api.analytics.discipline>> | null;
  legacyRisk: Awaited<ReturnType<typeof api.analytics.riskBehavior>> | null;
  legacyTradesToday: number | null;
  exchangeDiagnostics: ExchangeDiagnosticsSummary | null;
  alertRouting: AlertRoutingSummary | null;
  watcherSummary: MarketWatcherSummary | null;
  setupReviewSummary: Awaited<ReturnType<typeof api.alerts.setupReviewSummary>> | null;
  paperDraftSummary: Awaited<ReturnType<typeof api.strategies.draftSummary>> | null;
};

async function loadLegacyDashboard(): Promise<Partial<DashboardData>> {
  const [strategies, discipline, risk, tradeReview, usage, audit] = await Promise.all([
    settled(api.strategies.list({ limit: 50 }), { items: [], total: 0, limit: 50, offset: 0 }),
    settled(api.analytics.discipline(), null),
    settled(api.analytics.riskBehavior(), null),
    settled(api.analytics.tradeReview(), null),
    settled(api.usage.summary(), null),
    settled(api.audit.events({ limit: 5 }), { items: [], total: 0, limit: 5, offset: 0 }),
  ]);
  return {
    strategies: strategies.items,
    legacyDiscipline: discipline,
    legacyRisk: risk,
    legacyTradesToday: tradeReview?.total_journaled_trades ?? null,
    usage,
    audit,
  };
}

export default function DashboardPage() {
  const { providers, health } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();

  const loader = useCallback(async (): Promise<DashboardData> => {
    const [
      summary,
      usage,
      audit,
      exchangeDiagnostics,
      alertRouting,
      watcherSummary,
      setupReviewSummary,
      paperDraftSummary,
    ] = await Promise.all([
      settled(api.dashboard.summary(), null),
      settled(api.usage.summary(), null),
      settled(api.audit.events({ limit: 5 }), { items: [], total: 0, limit: 5, offset: 0 }),
      settled(api.exchange.diagnosticsSummary(), null),
      settled(api.alerts.routingSummary(), null),
      settled(api.marketWatcher.summary(), null),
      settled(api.alerts.setupReviewSummary(), null),
      settled(api.strategies.draftSummary(), null),
    ]);

    if (summary) {
      const strategies = await settled(api.strategies.list({ limit: 50 }), {
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      });
      return {
        summary,
        strategies: strategies.items,
        usage,
        audit,
        legacyDiscipline: null,
        legacyRisk: null,
        legacyTradesToday: null,
        exchangeDiagnostics,
        alertRouting,
        watcherSummary,
        setupReviewSummary,
        paperDraftSummary,
      };
    }

    const legacy = await loadLegacyDashboard();
    return {
      summary: null,
      strategies: legacy.strategies ?? [],
      usage: legacy.usage ?? null,
      audit: legacy.audit ?? null,
      legacyDiscipline: legacy.legacyDiscipline ?? null,
      legacyRisk: legacy.legacyRisk ?? null,
      legacyTradesToday: legacy.legacyTradesToday ?? null,
      exchangeDiagnostics,
      alertRouting,
      watcherSummary,
      setupReviewSummary,
      paperDraftSummary,
    };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  if (loading) return <LoadingState label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  const summary = data?.summary ?? null;
  const strategies = data?.strategies ?? [];
  const featured = featuredStrategy(strategies);
  const steps = featured
    ? buildWorkflowSteps({
        strategyId: featured.id,
        backtestStatus: featured.backtest_status,
        paperValidationStatus: featured.paper_validation_status,
        paperEligible: featured.paper_eligible,
      })
    : [];
  const focus = featured ? firstActionableStep(steps) : null;

  const daily = summary?.daily_discipline ?? null;
  const readiness = summary?.strategy_readiness;
  const alertsLessons = summary?.alerts_lessons;
  const nextAction = summary?.next_recommended_action;

  const pendingLessons = alertsLessons?.pending_lessons ?? 0;
  const unreadAlerts = alertsLessons?.unread_alerts ?? 0;
  const latestAlerts = summary?.alerts_lessons?.latest_high_priority ?? [];
  const setupReview = data?.setupReviewSummary;
  const latestSetupCondition = setupReview?.highest_confidence_alerts[0]?.condition;
  const paperDrafts = data?.paperDraftSummary;

  const activePaper =
    summary?.active_paper_validations ??
    strategies.filter((s) => RUNNING_PAPER.has((s.paper_validation_status ?? "").toLowerCase()));

  const nextActions: { text: string; href?: string; reason?: string }[] = [];
  if (nextAction) {
    nextActions.push({
      text: nextAction.action,
      href: nextAction.link,
      reason: nextAction.reason,
    });
  } else {
    if (focus) nextActions.push({ text: `${featured?.name}: ${focus.nextAction}` });
    if (pendingLessons > 0) {
      nextActions.push({
        text: `Review ${pendingLessons} learning signal${pendingLessons === 1 ? "" : "s"} in Lessons.`,
        href: "/lessons",
      });
    }
    if (unreadAlerts > 0) {
      nextActions.push({
        text: `Read ${unreadAlerts} new alert${unreadAlerts === 1 ? "" : "s"} (alerts never trade).`,
        href: "/alerts",
      });
    }
    if (strategies.length === 0) {
      nextActions.push({ text: "Create your first strategy to start the workflow.", href: "/strategy-lab" });
    }
    if (nextActions.length === 0) {
      nextActions.push({ text: "You're up to date. Wait patiently for setups that match your plan." });
    }
  }

  const disciplineSnapshot =
    daily ??
    (data?.legacyDiscipline || data?.legacyRisk || data?.legacyTradesToday != null
      ? {
          date: new Date().toISOString().slice(0, 10),
          timezone: "UTC",
          trades_today: data?.legacyTradesToday ?? 0,
          paper_trades_opened_today: 0,
          paper_trades_closed_today: 0,
          journal_entries_today: 0,
          realized_pnl_today_paper: null,
          unrealized_pnl_paper: null,
          net_pnl_today_paper: null,
          daily_loss_limit: null,
          daily_target: null,
          loss_lock_active: (data?.legacyRisk?.daily_loss_warnings ?? 0) > 0,
          green_day_protection_active: (data?.legacyRisk?.green_day_warnings ?? 0) > 0,
          overtrading_warning_active: (data?.legacyRisk?.overtrading_warnings ?? 0) > 0,
          max_trades_per_day: null,
          remaining_trades_allowed: null,
          discipline_status: "calm",
          risk_settings_source: "system_default",
          pnl_sources: {},
          reasons: [],
          recommended_action:
            data?.legacyDiscipline?.improvement_suggestions?.[0] ??
            "Stay patient and wait for setups that match your plan.",
          limitations: summary ? [] : ["Dashboard summary endpoint unavailable; showing legacy fallback."],
        }
      : null);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-50">Dashboard</h1>
        <p className="text-sm text-zinc-400">
          Your paper-only trading workspace — strategy readiness, discipline, and what to do next.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2" data-testid="dashboard-safety-status">
        <Badge variant="success" data-testid="dashboard-paper-only">
          {(summary?.safety.execution_mode ?? executionMode).toUpperCase()} mode
        </Badge>
        <Badge
          variant={
            (summary?.safety.real_trading_enabled ?? realTradingEnabled) ? "danger" : "success"
          }
          data-testid="dashboard-real-trading-status"
        >
          Real trading{" "}
          {(summary?.safety.real_trading_enabled ?? realTradingEnabled) ? "enabled" : "disabled"}
        </Badge>
        <Badge variant="muted">Simulated execution only</Badge>
      </div>

      {summary?.limitations.length ? (
        <p className="text-xs text-amber-500/80" data-testid="dashboard-summary-limitations">
          {summary.limitations.join(" ")}
        </p>
      ) : null}

      {featured ? (
        <WorkflowStepper steps={steps} />
      ) : (
        <EmptyState
          title="No strategies yet"
          description="Create a strategy to begin the Idea → Structure → Backtest → Paper Validate → Review Lessons → Improve workflow."
        />
      )}

      <Card data-testid="what-to-do-next">
        <CardHeader>
          <CardTitle className="text-base">What to do next</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm text-zinc-300">
            {nextActions.map((item) => (
              <li key={item.text}>
                {item.href ? (
                  <Link href={item.href} className="underline decoration-zinc-600 hover:text-zinc-100">
                    {item.text}
                  </Link>
                ) : (
                  <span>• {item.text}</span>
                )}
                {item.reason ? (
                  <p className="mt-0.5 text-xs text-zinc-500" data-testid="next-action-reason">
                    {item.reason}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <TodaysDisciplineCard
          snapshot={disciplineSnapshot}
          disciplineScore={summary?.discipline_score ?? null}
        />

        <Card data-testid="strategy-readiness-card">
          <CardHeader>
            <CardTitle className="text-base">Strategy readiness</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {readiness?.top_needing_action.length ? (
              readiness.top_needing_action.map((strategy) => (
                <Link
                  key={strategy.strategy_id}
                  href={strategy.link_hint}
                  className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 px-3 py-2 hover:border-zinc-600"
                >
                  <span className="truncate text-zinc-200">{strategy.name}</span>
                  <Badge variant="muted">{strategy.status}</Badge>
                </Link>
              ))
            ) : strategies.length ? (
              strategies.slice(0, 5).map((strategy) => {
                const view = strategyStatusFor(strategy);
                return (
                  <Link
                    key={strategy.id}
                    href={`/strategy-lab/${strategy.id}`}
                    className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 px-3 py-2 hover:border-zinc-600"
                  >
                    <span className="truncate text-zinc-200">{strategy.name}</span>
                    <Badge variant={view.variant}>{view.label}</Badge>
                  </Link>
                );
              })
            ) : (
              <EmptyState title="No strategies yet" description="Create one in Strategy Lab." />
            )}
          </CardContent>
        </Card>
      </div>

      {data?.exchangeDiagnostics ? (
        <ExchangeDiagnosticsCard diagnostics={data.exchangeDiagnostics} compact />
      ) : null}

      {data?.alertRouting ? (
        <AlertRoutingCard routing={data.alertRouting} compact />
      ) : null}

      {data?.watcherSummary ? (
        <MarketWatcherScannerCard summary={data.watcherSummary} compact />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="active-paper-validations">
          <CardHeader>
            <CardTitle className="text-base">Active paper validations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {activePaper.length ? (
              activePaper.map((strategy) => {
                const id = "strategy_id" in strategy ? strategy.strategy_id : strategy.id;
                const name = strategy.name;
                return (
                  <Link
                    key={id}
                    href={`/strategy-lab/${id}`}
                    className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 px-3 py-2 hover:border-zinc-600"
                  >
                    <span className="truncate text-zinc-200">{name}</span>
                    <Badge variant="info">Running</Badge>
                  </Link>
                );
              })
            ) : (
              <EmptyState
                title="No active paper validations"
                description="Start one from a paper-eligible strategy."
              />
            )}
          </CardContent>
        </Card>

        <Card data-testid="dashboard-open-paper-trades">
          <CardHeader>
            <CardTitle className="text-base">Open paper trades</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {summary?.open_paper_trades_summary ? (
              <p className="text-xs text-zinc-400" data-testid="open-paper-trades-counts">
                Proposal flow: {summary.open_paper_trades_summary.proposal_flow_count} · Paper
                validation: {summary.open_paper_trades_summary.paper_validation_count}
              </p>
            ) : null}
            {summary?.open_paper_trades.length ? (
              summary.open_paper_trades.map((trade) => (
                <div
                  key={trade.paper_trade_id ?? trade.position_id ?? `${trade.symbol}-${trade.source}`}
                  className="rounded-lg border border-zinc-800 px-3 py-2 text-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-zinc-200">
                      {trade.symbol}
                      {trade.strategy_name ? ` · ${trade.strategy_name}` : ""}
                    </span>
                    <Badge variant="muted">{trade.direction}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">
                    Source: {trade.source ?? "proposal_flow"}
                  </p>
                  {trade.unrealized_pnl != null ? (
                    <p className="mt-1 text-xs text-zinc-400">
                      Unrealized PnL: {formatDecimal(trade.unrealized_pnl)}
                    </p>
                  ) : null}
                </div>
              ))
            ) : (
              <EmptyState title="No open paper positions" />
            )}
            {summary?.open_paper_trades_summary?.limitations.length ? (
              <details className="text-xs text-amber-500/80" data-testid="open-paper-trades-limitations">
                <summary className="cursor-pointer text-zinc-400">Limitations</summary>
                <ul className="mt-2 space-y-1">
                  {summary.open_paper_trades_summary.limitations.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              </details>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="dashboard-latest-alerts">
          <CardHeader>
            <CardTitle className="text-base">Latest alerts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {latestAlerts.length ? (
              <>
                {[...latestAlerts]
                  .sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
                  .slice(0, 5)
                  .map((alert) => (
                    <div
                      key={`${alert.alert_type}-${alert.message}`}
                      className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 px-3 py-2"
                    >
                      <span className="truncate text-zinc-200">{alertTypeLabel(alert.alert_type)}</span>
                      <Badge variant={severityVariant(alert.severity)}>{alert.severity}</Badge>
                    </div>
                  ))}
                <Link href="/alerts" className="block text-xs text-zinc-400 underline">
                  View all alerts
                </Link>
              </>
            ) : (
              <EmptyState title="No alerts" description="Alerts appear here. They never execute trades." />
            )}
          </CardContent>
        </Card>

        <Card data-testid="dashboard-lessons-pending">
          <CardHeader>
            <CardTitle className="text-base">Lessons pending review</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-zinc-300">
            <p>
              <span className="text-2xl font-semibold text-zinc-100">{pendingLessons}</span> learning
              signal{pendingLessons === 1 ? "" : "s"} waiting for review.
            </p>
            <p className="text-xs text-zinc-500">
              Pending observations are not accepted trading rules until you review them.
            </p>
            <Link href="/lessons" className="inline-block text-xs text-zinc-400 underline">
              Open Lessons
            </Link>
          </CardContent>
        </Card>

        <Card data-testid="dashboard-setup-alerts-review">
          <CardHeader>
            <CardTitle className="text-base">Setup Alerts Review</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-zinc-300">
            <div className="grid grid-cols-3 gap-2 text-xs">
              <p>
                Unreviewed:{" "}
                <span className="font-semibold text-zinc-100">
                  {setupReview?.total_unreviewed ?? 0}
                </span>
              </p>
              <p>
                Watching:{" "}
                <span className="font-semibold text-zinc-100">
                  {setupReview?.total_watching ?? 0}
                </span>
              </p>
              <p>
                Important:{" "}
                <span className="font-semibold text-zinc-100">
                  {setupReview?.total_important ?? 0}
                </span>
              </p>
            </div>
            <p className="text-xs text-zinc-500">
              Latest condition:{" "}
              {latestSetupCondition
                ? setupConditionLabel(latestSetupCondition)
                : "None scanned yet"}
            </p>
            <Link href="/alerts/review" className="inline-block text-xs text-zinc-400 underline">
              Review setup alerts
            </Link>
          </CardContent>
        </Card>

        <Card data-testid="dashboard-paper-drafts">
          <CardHeader>
            <CardTitle className="text-base">Paper Drafts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-zinc-300">
            <p>
              Draft count:{" "}
              <span className="font-semibold text-zinc-100">{paperDrafts?.total_drafts ?? 0}</span>
            </p>
            <p className="text-xs text-zinc-500">
              Latest condition:{" "}
              {paperDrafts?.latest_condition
                ? setupConditionLabel(paperDrafts.latest_condition)
                : "None yet"}
            </p>
            <Link
              href="/paper-validation/drafts"
              className="inline-block text-xs text-zinc-400 underline"
            >
              View paper drafts
            </Link>
          </CardContent>
        </Card>
      </div>

      <details className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-4" data-testid="developer-details">
        <summary className="cursor-pointer text-sm font-medium text-zinc-300">
          Developer details
        </summary>
        <div className="mt-4 space-y-4">
          <div className="grid gap-3 sm:grid-cols-3 text-sm text-zinc-400">
            <p>Backend version: {health?.version ?? "—"}</p>
            <p>Usage events: {data?.usage?.event_count ?? 0}</p>
            <p>
              Estimated cost: {formatDecimal(data?.usage?.total_estimated_cost)}
              {data?.usage?.cost_is_placeholder ? " (placeholder)" : ""}
            </p>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-medium text-zinc-300">Provider status</h3>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {(providers?.providers ?? []).slice(0, 6).map((provider) => (
                <ProviderStatusCard key={provider.name} provider={provider} />
              ))}
            </div>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-medium text-zinc-300">Recent audit events</h3>
            <div className="space-y-2">
              {data?.audit?.items.length ? (
                data.audit.items.map((event) => <AuditEventCard key={event.event_id} event={event} />)
              ) : (
                <p className="text-sm text-zinc-500">No audit events yet.</p>
              )}
            </div>
          </div>
        </div>
      </details>
    </div>
  );
}
