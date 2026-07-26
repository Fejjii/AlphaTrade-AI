"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";

import { TodaysDisciplineCard } from "@/components/TodaysDisciplineCard";
import {
  AttentionQueue,
  WorkflowFreshnessAdapter,
  buildAttentionItems,
} from "@/components/workflows";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import {
  isPaperModeConfirmed,
  PaperModeIndicator,
} from "@/components/ui/paper-mode-indicator";
import { ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { DashboardSummary } from "@/lib/api/types";

async function settled<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch {
    return fallback;
  }
}

type DashboardData = {
  summary: DashboardSummary | null;
  pendingApprovals: number;
  pendingProposals: number;
  validatedSignalsNeedingReview: number;
  setupReviewUnreviewed: number;
  draftsReady: number;
  candidatesQueued: number;
  runPlansPending: number;
  activeValidations: number;
  freshnessTimestamps: Array<string | null>;
  disciplineFallback: {
    legacyDiscipline: Awaited<ReturnType<typeof api.analytics.discipline>> | null;
    legacyRisk: Awaited<ReturnType<typeof api.analytics.riskBehavior>> | null;
    legacyTradesToday: number | null;
  };
};

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
      settled(api.dashboard.summary(), null),
      settled(api.approvals.list({ limit: 50 }), { items: [], total: 0, limit: 50, offset: 0 }),
      settled(api.proposals.list({ limit: 50 }), { items: [], total: 0, limit: 50, offset: 0 }),
      settled(api.tradingview.listSignals({ limit: 50 }), {
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
      settled(api.alerts.setupReviewSummary(), null),
      settled(api.strategies.draftSummary(), null),
      settled(api.strategies.candidateSummary(), null),
      settled(api.strategies.runPlanSummary(), null),
      settled(api.strategies.runSessions({ limit: 50 }), null),
      settled(api.alerts.routingSummary(), null),
      settled(api.marketWatcher.summary(), null),
      settled(api.analytics.discipline(), null),
      settled(api.analytics.riskBehavior(), null),
      settled(api.analytics.tradeReview(), null),
    ]);

    const pendingApprovals = approvals.items.filter(
      (item) => item.status === "pending" || item.status === "needs_more_analysis",
    ).length;
    const pendingProposals = proposals.items.filter(
      (item) => item.status === "pending_approval",
    ).length;
    const validatedSignalsNeedingReview = tvSignals.items.filter(
      (item) => item.status === "validated" && !item.links.candidate_id,
    ).length;
    const runningSessions =
      paperRunSessions?.items.filter((session) => session.session_status === "running").length ?? 0;
    const activeValidations = Math.max(
      summary?.active_paper_validations.length ?? 0,
      runningSessions,
    );

    return {
      summary,
      pendingApprovals,
      pendingProposals,
      validatedSignalsNeedingReview,
      setupReviewUnreviewed: setupReviewSummary?.total_unreviewed ?? 0,
      draftsReady: paperDraftSummary?.ready_for_validation_count ?? 0,
      candidatesQueued: paperCandidateSummary?.total_queued ?? 0,
      runPlansPending: paperRunPlanSummary?.total_planned ?? 0,
      activeValidations,
      freshnessTimestamps: [
        summary?.market_watcher?.last_scan_at ?? null,
        summary?.bridge?.last_tick_at ?? null,
        watcherSummary?.last_scan_at ?? null,
        watcherSummary?.generated_at ?? null,
        alertRouting?.generated_at ?? null,
        setupReviewSummary?.latest_created_at ?? null,
      ],
      disciplineFallback: {
        legacyDiscipline: discipline,
        legacyRisk: risk,
        legacyTradesToday: tradeReview?.total_journaled_trades ?? null,
      },
    };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const summary = data?.summary ?? null;
  const paperConfirmed = isPaperModeConfirmed(
    summary?.safety.execution_mode ?? executionMode,
    summary?.safety.real_trading_enabled ?? realTradingEnabled,
  );

  const attentionItems = useMemo(() => {
    if (!data) return [];
    const daily = summary?.daily_discipline;
    return buildAttentionItems({
      executionMode: summary?.safety.execution_mode ?? executionMode,
      realTradingEnabled: summary?.safety.real_trading_enabled ?? realTradingEnabled,
      paperOnlyConfirmed: paperConfirmed,
      pendingApprovals: data.pendingApprovals,
      pendingProposals: data.pendingProposals,
      unreadAlerts: summary?.alerts_lessons?.unread_alerts ?? 0,
      unreviewedSetupAlerts: data.setupReviewUnreviewed,
      validatedSignalsNeedingReview: data.validatedSignalsNeedingReview,
      activeValidations: data.activeValidations,
      draftsReady: data.draftsReady,
      candidatesQueued: data.candidatesQueued,
      runPlansPending: data.runPlansPending,
      openPaperPositions:
        summary?.open_paper_trades_summary?.total_count ??
        summary?.open_paper_trades.length ??
        0,
      riskAlertsActive: Boolean(
        daily?.loss_lock_active ||
          daily?.green_day_protection_active ||
          daily?.overtrading_warning_active,
      ),
      lossLockActive: Boolean(daily?.loss_lock_active),
      greenDayProtectionActive: Boolean(daily?.green_day_protection_active),
      overtradingWarningActive: Boolean(daily?.overtrading_warning_active),
      pendingLessons: summary?.alerts_lessons?.pending_lessons ?? 0,
      nextAction: summary?.next_recommended_action ?? null,
    });
  }, [data, summary, executionMode, realTradingEnabled, paperConfirmed]);

  const disciplineSnapshot =
    summary?.daily_discipline ??
    (data?.disciplineFallback.legacyDiscipline ||
    data?.disciplineFallback.legacyRisk ||
    data?.disciplineFallback.legacyTradesToday != null
      ? {
          date: new Date().toISOString().slice(0, 10),
          timezone: "UTC",
          trades_today: data.disciplineFallback.legacyTradesToday ?? 0,
          paper_trades_opened_today: 0,
          paper_trades_closed_today: 0,
          journal_entries_today: 0,
          realized_pnl_today_paper: null,
          unrealized_pnl_paper: null,
          net_pnl_today_paper: null,
          daily_loss_limit: null,
          daily_target: null,
          loss_lock_active: (data.disciplineFallback.legacyRisk?.daily_loss_warnings ?? 0) > 0,
          green_day_protection_active:
            (data.disciplineFallback.legacyRisk?.green_day_warnings ?? 0) > 0,
          overtrading_warning_active:
            (data.disciplineFallback.legacyRisk?.overtrading_warnings ?? 0) > 0,
          max_trades_per_day: null,
          remaining_trades_allowed: null,
          discipline_status: "calm",
          risk_settings_source: "system_default",
          pnl_sources: {},
          reasons: [],
          recommended_action:
            data.disciplineFallback.legacyDiscipline?.improvement_suggestions?.[0] ??
            "Stay patient and wait for setups that match your plan.",
          limitations: ["Dashboard summary endpoint unavailable; showing legacy fallback."],
        }
      : null);

  if (loading) return <LoadingState label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-section" data-testid="dashboard-page">
      <WorkflowFreshnessAdapter timestamps={data?.freshnessTimestamps ?? []} />

      <PageHeader
        title="Dashboard"
        description="What needs my attention right now? Paper-first daily decision loop."
        meta={
          <PaperModeIndicator
            active={paperConfirmed}
          />
        }
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
            variant={
              (summary?.safety.execution_mode ?? executionMode) === "paper" ? "success" : "warning"
            }
            data-testid="dashboard-paper-only"
          >
            {(summary?.safety.execution_mode ?? executionMode ?? "unverified").toUpperCase()} mode
          </Badge>
          <Badge
            variant={
              (summary?.safety.real_trading_enabled ?? realTradingEnabled) === false
                ? "success"
                : "danger"
            }
            data-testid="dashboard-real-trading-status"
          >
            Real trading{" "}
            {(summary?.safety.real_trading_enabled ?? realTradingEnabled) === false
              ? "disabled"
              : (summary?.safety.real_trading_enabled ?? realTradingEnabled)
                ? "enabled"
                : "unverified"}
          </Badge>
          <Badge variant="muted">Simulated execution only</Badge>
        </div>
        {summary?.limitations.length ? (
          <p className="text-xs text-amber-500/80" data-testid="dashboard-summary-limitations">
            {summary.limitations.join(" ")}
          </p>
        ) : null}
      </section>

      <AttentionQueue
        items={attentionItems}
        error={null}
        onRetry={() => void reload()}
      />

      <details className="rounded-control border border-border-subtle bg-surface-0/40 p-4">
        <summary className="cursor-pointer text-sm font-medium text-text-secondary">
          Today&apos;s discipline snapshot
        </summary>
        <div className="mt-4">
          <TodaysDisciplineCard
            snapshot={disciplineSnapshot}
            disciplineScore={summary?.discipline_score ?? null}
          />
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
