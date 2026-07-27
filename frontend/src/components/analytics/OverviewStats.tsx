"use client";

import Link from "next/link";

import type { SourceResult } from "@/components/workflows";
import { DataNumber } from "@/components/ui/data-number";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/states";
import type { JournalStatsResponse, PaperPortfolioResponse, SampleConfidence } from "@/lib/api/types";

import {
  formatMonetary,
  formatPercent,
  formatProfitFactor,
  monetaryTone,
  parseDecimal,
} from "./format";

type OverviewStatsProps = {
  journal: SourceResult<JournalStatsResponse> | null;
  portfolio: SourceResult<PaperPortfolioResponse> | null;
  onRetryJournal?: () => void;
  onRetryPortfolio?: () => void;
};

function confidenceInsufficient(confidence: SampleConfidence | undefined): boolean {
  return confidence === "insufficient";
}

function EquitySparkline({ points }: { points: { index: number; equity: string }[] }) {
  if (!points.length) return null;
  const values = points.map((point) => parseDecimal(point.equity) ?? 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 160;
  const height = 40;
  const coords = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / span) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-10 w-40 text-accent"
      role="img"
      aria-label="Equity sparkline from paper portfolio"
      data-testid="overview-equity-sparkline"
    >
      <polyline fill="none" stroke="currentColor" strokeWidth="2" points={coords} />
    </svg>
  );
}

export function OverviewStats({
  journal,
  portfolio,
  onRetryJournal,
  onRetryPortfolio,
}: OverviewStatsProps) {
  const journalMetrics = journal?.available ? journal.data?.overall : null;
  const portfolioAccount = portfolio?.available ? portfolio.data?.account : null;
  const portfolioTrend = portfolio?.available ? portfolio.data?.trend : null;
  const equityCurve = portfolio?.available ? portfolio.data?.equity_curve ?? [] : [];

  const netPnl =
    parseDecimal(journalMetrics?.net_pnl_total) ??
    parseDecimal(portfolioAccount?.cumulative_realized_pnl);
  const winRate = journalMetrics?.win_rate ?? portfolio?.data?.metrics.win_rate ?? null;
  const tradeCount =
    journalMetrics?.trade_count ?? portfolioAccount?.closed_trade_count ?? null;
  const expectancy = parseDecimal(journalMetrics?.expectancy ?? portfolio?.data?.metrics.expectancy);
  const profitFactor =
    journalMetrics?.profit_factor ?? portfolio?.data?.metrics.profit_factor ?? null;
  const pfWarnings = journalMetrics?.warnings.map((warning) => warning.message);

  const tiles = [
    {
      label: "Realised P&L",
      value: formatMonetary(netPnl),
      tone: monetaryTone(netPnl),
      numeric: netPnl,
      signed: true,
      insufficient: journalMetrics ? confidenceInsufficient(journalMetrics.confidence) : false,
      n: journalMetrics?.pnl_sample_count ?? tradeCount,
    },
    {
      label: "Win rate",
      value: formatPercent(winRate),
      tone: "default" as const,
      numeric: winRate,
      insufficient: journalMetrics ? confidenceInsufficient(journalMetrics.confidence) : false,
      n: journalMetrics?.trade_count ?? tradeCount,
    },
    {
      label: "Closed trades",
      value: tradeCount ?? "—",
      tone: "default" as const,
      numeric: tradeCount,
      insufficient: false,
      n: tradeCount,
    },
    {
      label: "Expectancy",
      value: formatMonetary(expectancy),
      tone: monetaryTone(expectancy),
      numeric: expectancy,
      signed: true,
      insufficient: journalMetrics ? confidenceInsufficient(journalMetrics.confidence) : false,
      n: journalMetrics?.pnl_sample_count ?? null,
    },
    {
      label: "Profit factor",
      value: formatProfitFactor(profitFactor, pfWarnings),
      tone: "default" as const,
      numeric: profitFactor,
      insufficient: journalMetrics ? confidenceInsufficient(journalMetrics.confidence) : false,
      n: journalMetrics?.pnl_sample_count ?? null,
    },
    {
      label: "Current equity",
      value: formatMonetary(parseDecimal(portfolioAccount?.current_equity)),
      tone: "default" as const,
      numeric: parseDecimal(portfolioAccount?.current_equity),
      insufficient: false,
      n: null,
    },
    {
      label: "Trend",
      value: portfolioTrend?.label ?? "—",
      tone: "default" as const,
      numeric: null,
      insufficient: portfolioTrend?.label === "insufficient_data",
      n: portfolioTrend?.window_days ?? null,
    },
  ].slice(0, 7);

  return (
    <section className="space-y-3" data-testid="overview-stats">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-medium">Overview</h2>
        <Link href="/portfolio" className="text-sm text-text-secondary underline">
          Full equity on Portfolio
        </Link>
      </div>

      {!journal?.available ? (
        <div data-testid="overview-journal-error">
          <ErrorState
            message={`Journal statistics unavailable${journal?.error ? `: ${journal.error}` : "."}`}
            onRetry={onRetryJournal}
          />
        </div>
      ) : null}

      {!portfolio?.available ? (
        <div data-testid="overview-portfolio-error">
          <ErrorState
            message={`Paper portfolio unavailable${portfolio?.error ? `: ${portfolio.error}` : "."}`}
            onRetry={onRetryPortfolio}
          />
        </div>
      ) : null}

      {(journal?.available || portfolio?.available) && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {tiles.map((tile) => (
            <Card key={tile.label} data-testid={`overview-tile-${tile.label.toLowerCase().replace(/\s+/g, "-")}`}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-text-secondary">{tile.label}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                <DataNumber
                  value={tile.value}
                  tone={tile.tone}
                  numeric={tile.numeric}
                  signed={"signed" in tile ? tile.signed : false}
                  className="text-xl"
                />
                {tile.insufficient && tile.n != null ? (
                  <p className="text-caption text-text-muted">n={tile.n} — insufficient</p>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {portfolio?.available && equityCurve.length ? (
        <Card data-testid="overview-sparkline-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-text-secondary">
              Equity sparkline (paper)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <EquitySparkline points={equityCurve} />
          </CardContent>
        </Card>
      ) : null}

      {journal?.available && journal.data?.truncated ? (
        <p className="text-sm text-text-muted" data-testid="overview-truncated">
          Journal statistics truncated at {journal.data.max_rows} rows — narrow the date range.
        </p>
      ) : null}
    </section>
  );
}
