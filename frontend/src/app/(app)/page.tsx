"use client";

import Link from "next/link";
import { useCallback } from "react";

import { AuditEventCard } from "@/components/AuditEventCard";
import { PositionCard } from "@/components/PositionCard";
import { ProviderStatusCard } from "@/components/ProviderStatusCard";
import { TodaysDisciplineCard } from "@/components/TodaysDisciplineCard";
import { WorkflowStepper } from "@/components/WorkflowStepper";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { alertTypeLabel, severityRank, severityVariant } from "@/lib/alert-display";
import { strategyStatusFor } from "@/lib/strategy-status";
import { formatDecimal } from "@/lib/utils";
import { buildWorkflowSteps, firstActionableStep } from "@/lib/workflow-steps";
import type { UserStrategy } from "@/lib/api/types";

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

export default function DashboardPage() {
  const { providers, health } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();

  const loader = useCallback(async () => {
    const [strategies, positions, alertSummary, alerts, lessons, discipline, risk, tradeReview, usage, audit] =
      await Promise.all([
        settled(api.strategies.list({ limit: 50 }), { items: [], total: 0, limit: 50, offset: 0 }),
        settled(api.positions.list({ limit: 5, status: "open" }), {
          items: [],
          total: 0,
          limit: 5,
          offset: 0,
        }),
        settled(api.alerts.summary(), { total: 0, unread: 0, by_type: {}, by_severity: {} }),
        settled(api.alerts.list({ limit: 5 }), { items: [], total: 0 }),
        settled(api.lessons.listCandidates({ status: "pending_review" }), {
          items: [],
          total: 0,
          limit: 50,
          offset: 0,
        }),
        settled(api.analytics.discipline(), null),
        settled(api.analytics.riskBehavior(), null),
        settled(api.analytics.tradeReview(), null),
        settled(api.usage.summary(), null),
        settled(api.audit.events({ limit: 5 }), { items: [], total: 0, limit: 5, offset: 0 }),
      ]);
    return { strategies, positions, alertSummary, alerts, lessons, discipline, risk, tradeReview, usage, audit };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  if (loading) return <LoadingState label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  const strategies = data?.strategies.items ?? [];
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

  const activePaper = strategies.filter((s) =>
    RUNNING_PAPER.has((s.paper_validation_status ?? "").toLowerCase()),
  );
  const pendingLessons = data?.lessons.total ?? 0;
  const unreadAlerts = data?.alertSummary.unread ?? 0;
  const latestAlerts = [...(data?.alerts.items ?? [])].sort(
    (a, b) => severityRank(b.severity) - severityRank(a.severity),
  );

  const nextActions: string[] = [];
  if (focus) nextActions.push(`${featured?.name}: ${focus.nextAction}`);
  if (pendingLessons > 0)
    nextActions.push(`Review ${pendingLessons} learning signal${pendingLessons === 1 ? "" : "s"} in Lessons.`);
  if (unreadAlerts > 0)
    nextActions.push(`Read ${unreadAlerts} new alert${unreadAlerts === 1 ? "" : "s"} (alerts never trade).`);
  if (strategies.length === 0) nextActions.push("Create your first strategy to start the workflow.");
  if (nextActions.length === 0) nextActions.push("You're up to date. Wait patiently for setups that match your plan.");

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
          {executionMode.toUpperCase()} mode
        </Badge>
        <Badge
          variant={realTradingEnabled ? "danger" : "success"}
          data-testid="dashboard-real-trading-status"
        >
          Real trading {realTradingEnabled ? "enabled" : "disabled"}
        </Badge>
        <Badge variant="muted">Simulated execution only</Badge>
      </div>

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
          <ul className="space-y-1 text-sm text-zinc-300">
            {nextActions.map((action) => (
              <li key={action}>• {action}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <TodaysDisciplineCard
          discipline={data?.discipline ?? null}
          risk={data?.risk ?? null}
          tradesToday={data?.tradeReview?.total_journaled_trades ?? null}
        />

        <Card data-testid="strategy-readiness-card">
          <CardHeader>
            <CardTitle className="text-base">Strategy readiness</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {strategies.length ? (
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

      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="active-paper-validations">
          <CardHeader>
            <CardTitle className="text-base">Active paper validations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {activePaper.length ? (
              activePaper.map((strategy) => (
                <Link
                  key={strategy.id}
                  href={`/strategy-lab/${strategy.id}`}
                  className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 px-3 py-2 hover:border-zinc-600"
                >
                  <span className="truncate text-zinc-200">{strategy.name}</span>
                  <Badge variant="info">Running</Badge>
                </Link>
              ))
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
            {data?.positions.items.length ? (
              data.positions.items.map((position) => (
                <PositionCard key={position.id} position={position} />
              ))
            ) : (
              <EmptyState title="No open paper positions" />
            )}
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
                {latestAlerts.slice(0, 5).map((alert) => (
                  <div
                    key={alert.id}
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
              {data?.audit.items.length ? (
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
