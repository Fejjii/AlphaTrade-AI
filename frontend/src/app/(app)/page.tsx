"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";

import { TodaysDisciplineCard } from "@/components/TodaysDisciplineCard";
import {
  AttentionQueue,
  WorkflowFreshnessAdapter,
  anySourceFailed,
  buildAttentionItems,
  describeSafetyPosture,
  loadSource,
  unavailableSourceNames,
  type SourceResult,
} from "@/components/workflows";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { DashboardSummary } from "@/lib/api/types";

type DashboardData = {
  summary: SourceResult<DashboardSummary>;
  approvals: SourceResult<Awaited<ReturnType<typeof api.approvals.list>>>;
  proposals: SourceResult<Awaited<ReturnType<typeof api.proposals.list>>>;
  tvSignals: SourceResult<Awaited<ReturnType<typeof api.tradingview.listSignals>>>;
  setupReviewSummary: SourceResult<Awaited<ReturnType<typeof api.alerts.setupReviewSummary>>>;
  paperDraftSummary: SourceResult<Awaited<ReturnType<typeof api.strategies.draftSummary>>>;
  paperCandidateSummary: SourceResult<
    Awaited<ReturnType<typeof api.strategies.candidateSummary>>
  >;
  paperRunPlanSummary: SourceResult<Awaited<ReturnType<typeof api.strategies.runPlanSummary>>>;
  paperRunSessions: SourceResult<Awaited<ReturnType<typeof api.strategies.runSessions>>>;
  alertRouting: SourceResult<Awaited<ReturnType<typeof api.alerts.routingSummary>>>;
  watcherSummary: SourceResult<Awaited<ReturnType<typeof api.marketWatcher.summary>>>;
  discipline: SourceResult<Awaited<ReturnType<typeof api.analytics.discipline>>>;
  risk: SourceResult<Awaited<ReturnType<typeof api.analytics.riskBehavior>>>;
  tradeReview: SourceResult<Awaited<ReturnType<typeof api.analytics.tradeReview>>>;
};

function countOrNull(
  available: boolean,
  count: number | null | undefined,
): number | null {
  if (!available) return null;
  return count ?? 0;
}

export default function DashboardPage() {
  const { health } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();

  const loader = useCallback(async (): Promise<DashboardData> => {
    const [
      summary,
      approvals,
      proposals,
      tvSignals,
      setupReviewSummary,
      paperDraftSummary,
      paperCandidateSummary,
      paperRunPlanSummary,
      paperRunSessions,
      alertRouting,
      watcherSummary,
      discipline,
      risk,
      tradeReview,
    ] = await Promise.all([
      loadSource(api.dashboard.summary()),
      loadSource(api.approvals.list({ limit: 50 })),
      loadSource(api.proposals.list({ limit: 50 })),
      loadSource(api.tradingview.listSignals({ limit: 50 })),
      loadSource(api.alerts.setupReviewSummary()),
      loadSource(api.strategies.draftSummary()),
      loadSource(api.strategies.candidateSummary()),
      loadSource(api.strategies.runPlanSummary()),
      loadSource(api.strategies.runSessions({ limit: 50 })),
      loadSource(api.alerts.routingSummary()),
      loadSource(api.marketWatcher.summary()),
      loadSource(api.analytics.discipline()),
      loadSource(api.analytics.riskBehavior()),
      loadSource(api.analytics.tradeReview()),
    ]);

    return {
      summary,
      approvals,
      proposals,
      tvSignals,
      setupReviewSummary,
      paperDraftSummary,
      paperCandidateSummary,
      paperRunPlanSummary,
      paperRunSessions,
      alertRouting,
      watcherSummary,
      discipline,
      risk,
      tradeReview,
    };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const summary = data?.summary.data ?? null;
  const posture = describeSafetyPosture(
    summary?.safety.execution_mode ?? executionMode,
    summary?.safety.real_trading_enabled ?? realTradingEnabled,
  );

  const sourceCatalog = useMemo(() => {
    if (!data) return [];
    return [
      { name: "Dashboard summary", available: data.summary.available, required: true },
      { name: "Approvals", available: data.approvals.available, required: true },
      { name: "Proposals", available: data.proposals.available, required: true },
      { name: "TradingView signals", available: data.tvSignals.available, required: true },
      { name: "Setup review", available: data.setupReviewSummary.available, required: false },
      { name: "Validation drafts", available: data.paperDraftSummary.available, required: false },
      {
        name: "Validation candidates",
        available: data.paperCandidateSummary.available,
        required: false,
      },
      { name: "Run plans", available: data.paperRunPlanSummary.available, required: false },
      { name: "Run sessions", available: data.paperRunSessions.available, required: false },
      { name: "Alert routing", available: data.alertRouting.available, required: false },
      { name: "Watcher", available: data.watcherSummary.available, required: false },
      { name: "Discipline fallback", available: data.discipline.available, required: false },
      { name: "Risk fallback", available: data.risk.available, required: false },
    ];
  }, [data]);

  const partialData = anySourceFailed(sourceCatalog);
  const unavailableSources = unavailableSourceNames(sourceCatalog);

  const attentionItems = useMemo(() => {
    if (!data) return [];
    const daily = summary?.daily_discipline;
    const pendingApprovals = countOrNull(
      data.approvals.available,
      data.approvals.data?.items.filter(
        (item) => item.status === "pending" || item.status === "needs_more_analysis",
      ).length,
    );
    const pendingProposals = countOrNull(
      data.proposals.available,
      data.proposals.data?.items.filter((item) => item.status === "pending_approval").length,
    );
    const validatedSignalsNeedingReview = countOrNull(
      data.tvSignals.available,
      data.tvSignals.data?.items.filter(
        (item) => item.status === "validated" && !item.links.candidate_id,
      ).length,
    );
    const runningSessions = data.paperRunSessions.available
      ? (data.paperRunSessions.data?.items.filter((session) => session.session_status === "running")
          .length ?? 0)
      : null;
    const summaryActive = data.summary.available
      ? (summary?.active_paper_validations.length ?? 0)
      : null;
    const activeValidations =
      summaryActive == null && runningSessions == null
        ? null
        : Math.max(summaryActive ?? 0, runningSessions ?? 0);

    return buildAttentionItems({
      executionMode: summary?.safety.execution_mode ?? executionMode,
      realTradingEnabled: summary?.safety.real_trading_enabled ?? realTradingEnabled,
      paperOnlyConfirmed: posture.paperConfirmed,
      pendingApprovals,
      pendingProposals,
      unreadAlerts: countOrNull(
        data.summary.available,
        summary?.alerts_lessons?.unread_alerts,
      ),
      unreviewedSetupAlerts: countOrNull(
        data.setupReviewSummary.available,
        data.setupReviewSummary.data?.total_unreviewed,
      ),
      validatedSignalsNeedingReview,
      activeValidations,
      draftsReady: countOrNull(
        data.paperDraftSummary.available,
        data.paperDraftSummary.data?.ready_for_validation_count,
      ),
      candidatesQueued: countOrNull(
        data.paperCandidateSummary.available,
        data.paperCandidateSummary.data?.total_queued,
      ),
      runPlansPending: countOrNull(
        data.paperRunPlanSummary.available,
        data.paperRunPlanSummary.data?.total_planned,
      ),
      openPaperPositions: countOrNull(
        data.summary.available,
        summary?.open_paper_trades_summary?.total_count ?? summary?.open_paper_trades.length,
      ),
      riskAlertsActive: data.summary.available
        ? Boolean(
            daily?.loss_lock_active ||
              daily?.green_day_protection_active ||
              daily?.overtrading_warning_active,
          )
        : null,
      lossLockActive: data.summary.available ? Boolean(daily?.loss_lock_active) : null,
      greenDayProtectionActive: data.summary.available
        ? Boolean(daily?.green_day_protection_active)
        : null,
      overtradingWarningActive: data.summary.available
        ? Boolean(daily?.overtrading_warning_active)
        : null,
      pendingLessons: countOrNull(
        data.summary.available,
        summary?.alerts_lessons?.pending_lessons,
      ),
      nextAction: data.summary.available ? summary?.next_recommended_action ?? null : null,
    });
  }, [data, summary, executionMode, realTradingEnabled, posture.paperConfirmed]);

  const disciplineSnapshot = useMemo(() => {
    if (summary?.daily_discipline) return summary.daily_discipline;
    if (!data) return null;
    const hasFallback =
      data.discipline.available || data.risk.available || data.tradeReview.available;
    if (!hasFallback) return null;
    if (!data.summary.available) {
      // Explicit fallback limitations; do not invent zero-valued metrics as confirmed facts.
      return {
        date: new Date().toISOString().slice(0, 10),
        timezone: "UTC",
        trades_today: data.tradeReview.data?.total_journaled_trades ?? 0,
        paper_trades_opened_today: 0,
        paper_trades_closed_today: 0,
        journal_entries_today: 0,
        realized_pnl_today_paper: null,
        unrealized_pnl_paper: null,
        net_pnl_today_paper: null,
        daily_loss_limit: null,
        daily_target: null,
        loss_lock_active: (data.risk.data?.daily_loss_warnings ?? 0) > 0,
        green_day_protection_active: (data.risk.data?.green_day_warnings ?? 0) > 0,
        overtrading_warning_active: (data.risk.data?.overtrading_warnings ?? 0) > 0,
        max_trades_per_day: null,
        remaining_trades_allowed: null,
        discipline_status: "calm",
        risk_settings_source: "system_default",
        pnl_sources: {},
        reasons: [],
        recommended_action:
          data.discipline.data?.improvement_suggestions?.[0] ??
          "Stay patient and wait for setups that match your plan.",
        limitations: [
          "Dashboard summary endpoint unavailable; showing legacy fallback.",
          !data.tradeReview.available ? "Trades-today fallback unavailable." : null,
          !data.risk.available ? "Risk-behavior fallback unavailable." : null,
          !data.discipline.available ? "Discipline analytics fallback unavailable." : null,
        ].filter((item): item is string => Boolean(item)),
      };
    }
    return null;
  }, [summary, data]);

  const freshnessSources = useMemo(() => {
    if (!data) return [];
    return [
      {
        name: "watcher",
        available: data.watcherSummary.available || data.summary.available,
        required: false,
        timestamp:
          data.watcherSummary.data?.last_scan_at ??
          summary?.market_watcher?.last_scan_at ??
          null,
        fallbackUsed: false,
      },
      {
        name: "bridge",
        available: data.summary.available,
        required: false,
        timestamp: summary?.bridge?.last_tick_at ?? null,
      },
      {
        name: "alert-routing",
        available: data.alertRouting.available,
        required: false,
        timestamp: data.alertRouting.data?.generated_at ?? null,
      },
      {
        name: "setup-review",
        available: data.setupReviewSummary.available,
        required: false,
        timestamp: data.setupReviewSummary.data?.latest_created_at ?? null,
      },
      {
        name: "dashboard-summary",
        available: data.summary.available,
        required: true,
        timestamp: null,
      },
      {
        name: "approvals",
        available: data.approvals.available,
        required: true,
        timestamp: null,
      },
      {
        name: "proposals",
        available: data.proposals.available,
        required: true,
        timestamp: null,
      },
      {
        name: "tradingview",
        available: data.tvSignals.available,
        required: true,
        timestamp: null,
      },
    ];
  }, [data, summary]);

  if (loading) return <LoadingState label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-section" data-testid="dashboard-page">
      <WorkflowFreshnessAdapter sources={freshnessSources} />

      <PageHeader
        title="Dashboard"
        description="What needs my attention right now? Paper-first daily decision loop."
        meta={<PaperModeIndicator active={posture.paperConfirmed} />}
      />

      <section
        aria-labelledby="dashboard-safety-heading"
        className="space-y-2"
        data-testid="dashboard-safety-status"
      >
        <h2 id="dashboard-safety-heading" className="text-sm font-semibold text-text-secondary">
          Safety and trading posture
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant={posture.executionVariant}
            data-testid="dashboard-paper-only"
          >
            {posture.executionLabel}
          </Badge>
          <Badge
            variant={posture.realTradingVariant}
            data-testid="dashboard-real-trading-status"
          >
            {posture.realTradingLabel}
          </Badge>
          <Badge variant={posture.runtimeBadgeVariant === "paper" ? "paper" : posture.runtimeBadgeVariant === "danger" ? "danger" : "warning"} data-testid="dashboard-runtime-posture">
            {posture.runtimeBadgeLabel}
          </Badge>
        </div>
        {posture.conflictMessage ? (
          <p className="text-sm text-danger" data-testid="dashboard-safety-conflict" role="alert">
            {posture.conflictMessage}
          </p>
        ) : null}
        {summary?.limitations.length ? (
          <p className="text-xs text-amber-500/80" data-testid="dashboard-summary-limitations">
            {summary.limitations.join(" ")}
          </p>
        ) : null}
        {!data?.summary.available ? (
          <p className="text-xs text-amber-500/80" data-testid="dashboard-summary-unavailable">
            Dashboard summary unavailable
            {data?.summary.error ? `: ${data.summary.error}` : "."}
          </p>
        ) : null}
      </section>

      <AttentionQueue
        items={attentionItems}
        error={null}
        onRetry={() => void reload()}
        partialData={partialData}
        unavailableSources={unavailableSources}
        emptyTitle={
          partialData
            ? "No actionable items found in the available sources"
            : "Nothing needs your attention"
        }
        emptyDescription={
          partialData
            ? "Some required or optional sources failed. Retry before treating this as a complete catch-up state."
            : "You are caught up. New signals, approvals, and lessons will appear here."
        }
      />

      <details className="rounded-control border border-border-subtle bg-surface-0/40 p-4">
        <summary className="cursor-pointer text-sm font-medium text-text-secondary">
          Today&apos;s discipline snapshot
        </summary>
        <div className="mt-4">
          {disciplineSnapshot ? (
            <TodaysDisciplineCard
              snapshot={disciplineSnapshot}
              disciplineScore={summary?.discipline_score ?? null}
            />
          ) : (
            <p className="text-sm text-text-muted" data-testid="discipline-unavailable">
              Discipline snapshot unavailable from current sources.
            </p>
          )}
        </div>
      </details>

      <details
        className="rounded-control border border-border-subtle bg-surface-0/40 p-4"
        data-testid="dashboard-progressive-links"
      >
        <summary className="cursor-pointer text-sm font-medium text-text-secondary">
          More workflows
        </summary>
        <ul className="mt-3 grid gap-2 text-sm text-text-secondary sm:grid-cols-2">
          <li>
            <Link className="underline" href="/tradingview-signals">
              Signals inbox
            </Link>
          </li>
          <li>
            <Link className="underline" href="/approvals">
              Approvals
            </Link>
          </li>
          <li>
            <Link className="underline" href="/paper-validation/candidates">
              Validation queue
            </Link>
          </li>
          <li>
            <Link className="underline" href="/positions">
              Open positions
            </Link>
          </li>
          <li>
            <Link className="underline" href="/lessons">
              Lessons
            </Link>
          </li>
          <li>
            <Link className="underline" href="/portfolio">
              Portfolio overview
            </Link>
          </li>
          <li>
            <Link className="underline" href="/alerts/review">
              Setup alert review
            </Link>
          </li>
          <li>
            <Link className="underline" href="/risk">
              Risk &amp; cooldowns
            </Link>
          </li>
        </ul>
        <p className="mt-3 text-caption text-text-muted">
          Backend {health?.version ?? "—"}. Dense metrics live in their owning destinations.
        </p>
      </details>
    </div>
  );
}
