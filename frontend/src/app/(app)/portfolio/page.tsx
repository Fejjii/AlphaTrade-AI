"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import {
  AccountOverviewPanel,
  buildClosedPositionRows,
  buildOpenPositionRows,
  buildRiskPosture,
  ClosedPositionsPanel,
  OpenPositionsPanel,
  PortfolioHistoryPanel,
  PortfolioHubChrome,
  PortfolioSourceAvailability,
  RiskPosturePanel,
} from "@/components/portfolio";
import { OpenExposurePanel } from "@/components/portfolio/OpenExposurePanel";
import { PaperPortfolioFilters } from "@/components/portfolio/PaperPortfolioFilters";
import { PaperPortfolioSafetyBanner } from "@/components/portfolio/PaperPortfolioSafetyBanner";
import { PortfolioBreakdownTable } from "@/components/portfolio/PortfolioBreakdownTable";
import { PortfolioTrendBadge } from "@/components/portfolio/PortfolioTrendBadge";
import { coverageFromPage } from "@/components/portfolio/portfolioMetricDisplay";
import { LoadingState } from "@/components/states";
import {
  describeSafetyPosture,
  loadSource,
  type SourceResult,
} from "@/components/workflows";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type {
  DashboardSummary,
  PaginatedJournalEntries,
  PaginatedPositions,
  PaperPortfolioResponse,
  PortfolioSourceFilter,
} from "@/lib/api/types";

type PortfolioCommandCentreData = {
  portfolio: SourceResult<PaperPortfolioResponse>;
  dashboard: SourceResult<DashboardSummary>;
  openPositions: SourceResult<PaginatedPositions>;
  closedPositions: SourceResult<PaginatedPositions>;
  journal: SourceResult<PaginatedJournalEntries>;
};

function disciplineSource(
  dashboard: SourceResult<DashboardSummary> | null | undefined,
): SourceResult<DashboardSummary["daily_discipline"]> | null {
  if (!dashboard) return null;
  if (!dashboard.available) {
    return {
      data: null,
      available: false,
      error: dashboard.error,
      fallbackUsed: false,
    };
  }
  return {
    data: dashboard.data?.daily_discipline ?? null,
    available: true,
    error: null,
    fallbackUsed: false,
  };
}

export default function PaperPortfolioPage() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [source, setSource] = useState<PortfolioSourceFilter>("all");
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const { killSwitchStatus, killSwitchError } = useAppContext();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);

  const loader = useCallback(async (): Promise<PortfolioCommandCentreData> => {
    const dateParams = {
      ...(startDate ? { start_date: startDate } : {}),
      ...(endDate ? { end_date: endDate } : {}),
      source,
    };
    const [portfolio, dashboard, openPositions, closedPositions, journal] = await Promise.all([
      loadSource(api.performance.portfolio(dateParams)),
      loadSource(api.dashboard.summary()),
      loadSource(api.positions.list({ status: "open", limit: 50 })),
      loadSource(api.positions.list({ status: "closed", limit: 50 })),
      loadSource(api.journal.list({ limit: 50 })),
    ]);
    return { portfolio, dashboard, openPositions, closedPositions, journal };
  }, [startDate, endDate, source]);

  const { data, loading, error, reload } = useAsyncData(loader, [startDate, endDate, source]);

  const discipline = useMemo(() => disciplineSource(data?.dashboard), [data?.dashboard]);
  const riskPosture = useMemo(
    () =>
      buildRiskPosture({
        discipline,
        killSwitchStatus,
        killSwitchError,
        posture,
      }),
    [discipline, killSwitchStatus, killSwitchError, posture],
  );

  const openPositionsView = useMemo(
    () =>
      buildOpenPositionRows(
        data?.openPositions,
        data?.dashboard.available
          ? data.dashboard.data?.open_paper_trades_summary ?? null
          : null,
      ),
    [data?.openPositions, data?.dashboard],
  );

  const closedPositionsView = useMemo(
    () => buildClosedPositionRows(data?.closedPositions, data?.journal),
    [data?.closedPositions, data?.journal],
  );

  const sourceStatuses = useMemo(() => {
    if (!data) return [];
    const openCoverage =
      data.openPositions.available && data.openPositions.data
        ? coverageFromPage(data.openPositions.data.items.length, data.openPositions.data.total)
        : null;
    const closedCoverage =
      data.closedPositions.available && data.closedPositions.data
        ? coverageFromPage(
            data.closedPositions.data.items.length,
            data.closedPositions.data.total,
          )
        : null;
    return [
      {
        name: "Portfolio performance",
        available: data.portfolio.available,
        error: data.portfolio.error,
        timestamp: data.portfolio.data?.account.as_of ?? null,
        required: true,
        coverage: data.portfolio.available
          ? data.portfolio.data?.equity_curve.length
            ? ("complete" as const)
            : ("truncated" as const)
          : null,
      },
      {
        name: "Risk state",
        available: data.dashboard.available,
        error: data.dashboard.error,
        timestamp: data.dashboard.data?.daily_discipline?.date ?? null,
        required: true,
        coverage: data.dashboard.available ? ("complete" as const) : null,
      },
      {
        name: "Open positions",
        available: data.openPositions.available,
        error: data.openPositions.error,
        timestamp: data.openPositions.data?.items[0]?.opened_at ?? null,
        required: true,
        coverage: openCoverage,
      },
      {
        name: "Closed positions",
        available: data.closedPositions.available,
        error: data.closedPositions.error,
        timestamp:
          data.closedPositions.data?.items[0]?.closed_at ??
          data.closedPositions.data?.items[0]?.opened_at ??
          null,
        required: true,
        coverage: closedCoverage,
      },
      {
        name: "Journal relationships",
        available: data.journal.available,
        error: data.journal.error,
        timestamp: data.journal.data?.items[0]?.created_at ?? null,
        required: false,
        coverage:
          data.journal.available && data.journal.data
            ? coverageFromPage(data.journal.data.items.length, data.journal.data.total)
            : null,
      },
    ];
  }, [data]);

  const freshnessSources = sourceStatuses.map((sourceStatus) => ({
    name: sourceStatus.name,
    available: sourceStatus.available,
    required: sourceStatus.required ?? true,
    timestamp: sourceStatus.timestamp,
  }));

  const limitations = useMemo(() => {
    const items: string[] = [...riskPosture.limitations];
    if (data?.portfolio.available) {
      items.push(...(data.portfolio.data?.account.limitations ?? []));
      items.push(...(data.portfolio.data?.open_exposure.limitations ?? []));
    }
    if (data?.dashboard.available) {
      items.push(...(data.dashboard.data?.limitations ?? []));
    }
    return items;
  }, [data, riskPosture.limitations]);

  const attentionTone =
    riskPosture.tradingState === "blocked"
      ? "blocked"
      : riskPosture.tradingState === "warned"
        ? "warn"
        : riskPosture.tradingState === "allowed"
          ? "ok"
          : "muted";

  return (
    <PortfolioHubChrome
      title="Portfolio & Risk"
      description="Paper command centre for simulated performance, exposure, drawdown, and risk posture. Read-only analytics — no live trading, no orders, no automation, and not investment advice."
      posture={posture}
      providerMode={providerMode}
      freshnessSources={freshnessSources}
      attentionSummary={riskPosture.attentionSummary}
      attentionTone={attentionTone}
      riskBlocked={riskPosture.showRiskBlock}
      riskBlockReason={riskPosture.riskBlockReason}
      testId="paper-portfolio-page"
      activeHref="/portfolio"
    >
      {loading && !data ? <LoadingState label="Loading paper portfolio…" /> : null}

      {error && !data ? (
        <div
          role="alert"
          className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
          data-testid="portfolio-command-centre-error"
        >
          {error}
          <button
            type="button"
            className="ml-3 underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            onClick={() => void reload()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {data ? (
        <>
          <PortfolioSourceAvailability
            sources={sourceStatuses}
            onRetry={() => void reload()}
            limitations={limitations}
          />

          {data.portfolio.available && data.portfolio.data ? (
            <PaperPortfolioSafetyBanner safety={data.portfolio.data.safety} />
          ) : null}

          <PaperPortfolioFilters
            startDate={startDate}
            endDate={endDate}
            source={source}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
            onSourceChange={setSource}
          />

          <AccountOverviewPanel
            portfolio={data.portfolio}
            dailyPnl={riskPosture.dailyPnl}
            paperConfirmed={posture.paperConfirmed}
            discipline={discipline}
          />

          <RiskPosturePanel posture={riskPosture} />

          {data.portfolio.available && data.portfolio.data ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <PortfolioTrendBadge trend={data.portfolio.data.trend} />
              <OpenExposurePanel exposure={data.portfolio.data.open_exposure} />
            </div>
          ) : null}

          <OpenPositionsPanel view={openPositionsView} />
          <ClosedPositionsPanel view={closedPositionsView} />
          <PortfolioHistoryPanel portfolio={data.portfolio} />

          {data.portfolio.available && data.portfolio.data ? (
            <section className="space-y-4" data-testid="paper-portfolio-breakdowns">
              <h2 className="text-lg font-medium text-text-primary">Breakdowns</h2>
              <div className="grid gap-4 lg:grid-cols-2">
                <PortfolioBreakdownTable
                  title="By symbol"
                  rows={data.portfolio.data.breakdowns.by_symbol}
                  testId="portfolio-breakdown-symbol"
                />
                <PortfolioBreakdownTable
                  title="By setup"
                  rows={data.portfolio.data.breakdowns.by_setup}
                  testId="portfolio-breakdown-setup"
                />
                <PortfolioBreakdownTable
                  title="By timeframe"
                  rows={data.portfolio.data.breakdowns.by_timeframe}
                  testId="portfolio-breakdown-timeframe"
                />
                <PortfolioBreakdownTable
                  title="By strategy"
                  rows={data.portfolio.data.breakdowns.by_strategy}
                  testId="portfolio-breakdown-strategy"
                />
                <PortfolioBreakdownTable
                  title="By source"
                  rows={data.portfolio.data.breakdowns.by_source}
                  testId="portfolio-breakdown-source"
                />
                {data.portfolio.data.breakdowns.by_detector.length ? (
                  <PortfolioBreakdownTable
                    title="By detector"
                    rows={data.portfolio.data.breakdowns.by_detector}
                    testId="portfolio-breakdown-detector"
                  />
                ) : null}
              </div>
            </section>
          ) : null}

          <section
            className="flex flex-wrap gap-4 text-sm"
            data-testid="paper-portfolio-related-links"
          >
            <Link href="/risk" className="text-text-secondary underline">
              Risk settings
            </Link>
            <Link href="/positions" className="text-text-secondary underline">
              Positions
            </Link>
            <Link href="/learning-analytics" className="text-text-secondary underline">
              Learning Analytics
            </Link>
            <Link href="/strategy-quality" className="text-text-secondary underline">
              Strategy Quality
            </Link>
            <Link href="/lessons" className="text-text-secondary underline">
              Lessons
            </Link>
          </section>
        </>
      ) : null}
    </PortfolioHubChrome>
  );
}
