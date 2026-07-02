"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { OpenExposurePanel } from "@/components/portfolio/OpenExposurePanel";
import { PaperPortfolioCharts } from "@/components/portfolio/PaperPortfolioCharts";
import { PaperPortfolioFilters } from "@/components/portfolio/PaperPortfolioFilters";
import { PaperPortfolioSafetyBanner } from "@/components/portfolio/PaperPortfolioSafetyBanner";
import { PaperPortfolioSummaryCards } from "@/components/portfolio/PaperPortfolioSummaryCards";
import { PortfolioBreakdownTable } from "@/components/portfolio/PortfolioBreakdownTable";
import { PortfolioTrendBadge } from "@/components/portfolio/PortfolioTrendBadge";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { PortfolioSourceFilter } from "@/lib/api/types";

export default function PaperPortfolioPage() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [source, setSource] = useState<PortfolioSourceFilter>("all");

  const loader = useCallback(async () => {
    const dateParams = {
      ...(startDate ? { start_date: startDate } : {}),
      ...(endDate ? { end_date: endDate } : {}),
      source,
    };
    return api.performance.portfolio(dateParams);
  }, [startDate, endDate, source]);

  const { data, loading, error, reload } = useAsyncData(loader, [startDate, endDate, source]);

  const limitations = [
    ...(data?.account.limitations ?? []),
    ...(data?.open_exposure.limitations ?? []),
  ];

  return (
    <div className="space-y-8" data-testid="paper-portfolio-page">
      <div>
        <h1 className="text-2xl font-semibold">Paper Portfolio</h1>
        <p className="text-sm text-zinc-400">
          Evaluate simulated paper portfolio performance over time. Read-only analytics — no live
          trading, no orders, no automation, and not investment advice.
        </p>
      </div>

      {loading && !data ? <LoadingState label="Loading paper portfolio…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {!loading && !error && !data ? (
        <EmptyState
          title="No portfolio data"
          description="Paper portfolio metrics will appear once simulated trades are recorded."
        />
      ) : null}

      {data ? (
        <>
          <PaperPortfolioSafetyBanner safety={data.safety} />

          <PaperPortfolioFilters
            startDate={startDate}
            endDate={endDate}
            source={source}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
            onSourceChange={setSource}
          />

          <PaperPortfolioSummaryCards account={data.account} metrics={data.metrics} />

          <div className="grid gap-4 lg:grid-cols-2">
            <PortfolioTrendBadge trend={data.trend} />
            <OpenExposurePanel exposure={data.open_exposure} />
          </div>

          <PaperPortfolioCharts equityCurve={data.equity_curve} dailySeries={data.daily_series} />

          {limitations.length ? (
            <section
              className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-500/90"
              data-testid="paper-portfolio-limitations"
            >
              <p className="font-medium">Limitations</p>
              <ul className="mt-2 space-y-1 text-xs">
                {limitations.map((item) => (
                  <li key={item}>• {item}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="space-y-4" data-testid="paper-portfolio-breakdowns">
            <h2 className="text-lg font-medium">Breakdowns</h2>
            <div className="grid gap-4 lg:grid-cols-2">
              <PortfolioBreakdownTable
                title="By symbol"
                rows={data.breakdowns.by_symbol}
                testId="portfolio-breakdown-symbol"
              />
              <PortfolioBreakdownTable
                title="By setup"
                rows={data.breakdowns.by_setup}
                testId="portfolio-breakdown-setup"
              />
              <PortfolioBreakdownTable
                title="By timeframe"
                rows={data.breakdowns.by_timeframe}
                testId="portfolio-breakdown-timeframe"
              />
              <PortfolioBreakdownTable
                title="By strategy"
                rows={data.breakdowns.by_strategy}
                testId="portfolio-breakdown-strategy"
              />
              <PortfolioBreakdownTable
                title="By source"
                rows={data.breakdowns.by_source}
                testId="portfolio-breakdown-source"
              />
              {data.breakdowns.by_detector.length ? (
                <PortfolioBreakdownTable
                  title="By detector"
                  rows={data.breakdowns.by_detector}
                  testId="portfolio-breakdown-detector"
                />
              ) : null}
            </div>
          </section>

          <section
            className="flex flex-wrap gap-4 text-sm"
            data-testid="paper-portfolio-related-links"
          >
            <Link href="/learning-analytics" className="text-zinc-400 underline">
              Learning Analytics
            </Link>
            <Link href="/strategy-quality" className="text-zinc-400 underline">
              Strategy Quality
            </Link>
            <Link href="/lessons" className="text-zinc-400 underline">
              Lessons
            </Link>
          </section>
        </>
      ) : null}
    </div>
  );
}
