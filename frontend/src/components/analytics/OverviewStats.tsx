"use client";

import Link from "next/link";
import { useMemo, type ReactNode } from "react";

import type { SourceResult } from "@/components/workflows";
import { DataNumber } from "@/components/ui/data-number";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LimitationsState } from "@/components/states";
import type { JournalStatsResponse, PaperPortfolioResponse, SampleConfidence } from "@/lib/api/types";

import {
  formatMonetary,
  formatPercent,
  formatProfitFactor,
  formatTrendLabel,
  monetaryTone,
  parseDecimal,
} from "./format";

type OverviewStatsProps = {
  journal: SourceResult<JournalStatsResponse> | null;
  portfolio: SourceResult<PaperPortfolioResponse> | null;
  loading?: boolean;
  onRetryJournal?: () => void;
  onRetryPortfolio?: () => void;
};

type TileSource = "journal" | "portfolio";

type OverviewTile = {
  label: string;
  value: string;
  tone: "default" | "positive" | "negative" | "muted";
  numeric: number | null;
  signed?: boolean;
  source: TileSource;
  insufficient: boolean;
  n: number | null;
  fallback?: boolean;
};

/** Default Analytics sample gate — align with filter min_sample default. */
const FALLBACK_MIN_SAMPLE = 5;

function confidenceInsufficient(confidence: SampleConfidence | undefined): boolean {
  return confidence === "insufficient";
}

function sampleInsufficient(tradeCount: number | null | undefined): boolean {
  if (tradeCount == null) return true;
  return tradeCount < FALLBACK_MIN_SAMPLE;
}

function buildEquitySparkline(points: { index: number; equity: string }[]): {
  sparkline: ReactNode;
  limitation: string | null;
} {
  const invalidCount = points.filter(
    (point) => point.equity != null && point.equity !== "" && parseDecimal(point.equity) === null,
  ).length;

  const valid = points
    .map((point) => ({ index: point.index, equity: parseDecimal(point.equity) }))
    .filter((point): point is { index: number; equity: number } => point.equity !== null);
  if (!valid.length) {
    return {
      sparkline: null,
      limitation: invalidCount
        ? "Equity sparkline omitted — source contains invalid monetary values."
        : "Equity sparkline unavailable — no valid equity points.",
    };
  }

  const values = valid.map((point) => point.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 160;
  const height = 40;
  const coords = valid
    .map((point, index) => {
      const x = (index / Math.max(valid.length - 1, 1)) * width;
      const y = height - ((point.equity - min) / span) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return {
    sparkline: (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-10 w-40 text-accent"
        role="img"
        aria-label="Equity sparkline from paper portfolio"
        data-testid="overview-equity-sparkline"
      >
        <polyline fill="none" stroke="currentColor" strokeWidth="2" points={coords} />
      </svg>
    ),
    limitation:
      invalidCount > 0
        ? `${invalidCount} equity point(s) omitted from sparkline — invalid monetary values.`
        : null,
  };
}

function buildJournalTiles(
  journalMetrics: JournalStatsResponse["overall"],
): OverviewTile[] {
  const pfWarnings = journalMetrics.warnings.map((warning) => warning.message);
  return [
    {
      label: "Realised P&L",
      value: formatMonetary(parseDecimal(journalMetrics.net_pnl_total)),
      tone: monetaryTone(parseDecimal(journalMetrics.net_pnl_total)),
      numeric: parseDecimal(journalMetrics.net_pnl_total),
      signed: true,
      source: "journal",
      insufficient: confidenceInsufficient(journalMetrics.confidence),
      n: journalMetrics.pnl_sample_count,
    },
    {
      label: "Win rate",
      value: confidenceInsufficient(journalMetrics.confidence)
        ? "—"
        : formatPercent(journalMetrics.win_rate),
      tone: confidenceInsufficient(journalMetrics.confidence) ? "muted" : "default",
      numeric: confidenceInsufficient(journalMetrics.confidence)
        ? null
        : journalMetrics.win_rate,
      source: "journal",
      insufficient: confidenceInsufficient(journalMetrics.confidence),
      n: journalMetrics.trade_count,
    },
    {
      label: "Closed trades",
      value: String(journalMetrics.trade_count),
      tone: "default",
      numeric: journalMetrics.trade_count,
      source: "journal",
      insufficient: false,
      n: journalMetrics.trade_count,
    },
    {
      label: "Expectancy",
      value: formatMonetary(parseDecimal(journalMetrics.expectancy)),
      tone: monetaryTone(parseDecimal(journalMetrics.expectancy)),
      numeric: parseDecimal(journalMetrics.expectancy),
      signed: true,
      source: "journal",
      insufficient: confidenceInsufficient(journalMetrics.confidence),
      n: journalMetrics.pnl_sample_count,
    },
    {
      label: "Profit factor",
      value: formatProfitFactor(journalMetrics.profit_factor, pfWarnings),
      tone: "default",
      numeric: journalMetrics.profit_factor,
      source: "journal",
      insufficient: confidenceInsufficient(journalMetrics.confidence),
      n: journalMetrics.pnl_sample_count,
    },
  ];
}

function buildPortfolioFallbackTiles(
  portfolioData: PaperPortfolioResponse,
): OverviewTile[] {
  const metrics = portfolioData.metrics;
  const account = portfolioData.account;
  const insufficient = sampleInsufficient(metrics.trade_count);
  return [
    {
      label: "Realised P&L",
      value: formatMonetary(parseDecimal(account.cumulative_realized_pnl)),
      tone: monetaryTone(parseDecimal(account.cumulative_realized_pnl)),
      numeric: parseDecimal(account.cumulative_realized_pnl),
      signed: true,
      source: "portfolio",
      insufficient,
      n: metrics.trade_count,
      fallback: true,
    },
    {
      label: "Win rate",
      value: insufficient ? "—" : formatPercent(metrics.win_rate),
      tone: insufficient ? "muted" : "default",
      numeric: insufficient ? null : metrics.win_rate,
      source: "portfolio",
      insufficient,
      n: metrics.trade_count,
      fallback: true,
    },
    {
      label: "Closed trades",
      value: String(account.closed_trade_count),
      tone: "default",
      numeric: account.closed_trade_count,
      source: "portfolio",
      insufficient: false,
      n: account.closed_trade_count,
      fallback: true,
    },
    {
      label: "Expectancy",
      value: formatMonetary(parseDecimal(metrics.expectancy)),
      tone: monetaryTone(parseDecimal(metrics.expectancy)),
      numeric: parseDecimal(metrics.expectancy),
      signed: true,
      source: "portfolio",
      insufficient,
      n: metrics.trade_count,
      fallback: true,
    },
    {
      label: "Profit factor",
      value: formatProfitFactor(metrics.profit_factor),
      tone: "default",
      numeric: metrics.profit_factor,
      source: "portfolio",
      insufficient,
      n: metrics.trade_count,
      fallback: true,
    },
  ];
}

export function OverviewStats({
  journal,
  portfolio,
  loading = false,
  onRetryJournal,
  onRetryPortfolio,
}: OverviewStatsProps) {
  const journalAvailable = journal?.available ?? false;
  const portfolioAvailable = portfolio?.available ?? false;

  const tiles = useMemo(() => {
    const metricTiles = journalAvailable
      ? buildJournalTiles(journal!.data!.overall)
      : portfolioAvailable
        ? buildPortfolioFallbackTiles(portfolio!.data!)
        : [];

    const portfolioTiles: OverviewTile[] = portfolioAvailable
      ? [
          {
            label: "Current equity",
            value: formatMonetary(parseDecimal(portfolio!.data!.account.current_equity)),
            tone: "default",
            numeric: parseDecimal(portfolio!.data!.account.current_equity),
            source: "portfolio",
            insufficient: false,
            n: null,
          },
          {
            label: "Trend",
            value: formatTrendLabel(portfolio!.data!.trend.label),
            tone: "default",
            numeric: null,
            source: "portfolio",
            insufficient: portfolio!.data!.trend.label === "insufficient_data",
            n: portfolio!.data!.trend.window_days,
          },
        ]
      : [];

    return [...metricTiles, ...portfolioTiles].slice(0, 7);
  }, [journal, journalAvailable, portfolio, portfolioAvailable]);

  const sparkline = useMemo(() => {
    if (!portfolioAvailable) return { sparkline: null, limitation: null };
    return buildEquitySparkline(portfolio!.data!.equity_curve ?? []);
  }, [portfolio, portfolioAvailable]);

  if (loading) {
    return (
      <section className="space-y-3" data-testid="overview-stats">
        <h2 className="text-lg font-medium">Overview</h2>
        <p className="text-sm text-text-muted" role="status">
          Loading overview metrics…
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-3" data-testid="overview-stats">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-medium">Overview</h2>
        <Link href="/portfolio" className="text-sm text-text-secondary underline">
          Full equity on Portfolio
        </Link>
      </div>

      {!journalAvailable ? (
        <div data-testid="overview-journal-error">
          <ErrorState
            message={`Journal statistics unavailable${journal?.error ? `: ${journal.error}` : "."}`}
            onRetry={onRetryJournal}
          />
        </div>
      ) : null}

      {!portfolioAvailable ? (
        <div data-testid="overview-portfolio-error">
          <ErrorState
            message={`Paper portfolio unavailable${portfolio?.error ? `: ${portfolio.error}` : "."}`}
            onRetry={onRetryPortfolio}
          />
        </div>
      ) : null}

      {(journalAvailable || portfolioAvailable) && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {tiles.map((tile) => (
            <Card
              key={tile.label}
              data-testid={`overview-tile-${tile.label.toLowerCase().replace(/\s+/g, "-")}`}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-text-secondary">
                  {tile.label}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                <DataNumber
                  value={tile.value}
                  tone={tile.tone}
                  numeric={tile.numeric}
                  signed={tile.signed ?? false}
                  className="text-xl"
                />
                <p className="text-caption text-text-muted" data-testid={`overview-source-${tile.label}`}>
                  Source: {tile.source === "journal" ? "Journal statistics" : "Paper portfolio"}
                  {tile.fallback ? " (fallback)" : ""}
                </p>
                {tile.insufficient && tile.n != null ? (
                  <p className="text-caption text-text-muted">n={tile.n} — insufficient</p>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {portfolioAvailable && sparkline.sparkline ? (
        <Card data-testid="overview-sparkline-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-text-secondary">
              Equity sparkline (paper)
            </CardTitle>
          </CardHeader>
          <CardContent>{sparkline.sparkline}</CardContent>
        </Card>
      ) : null}

      {sparkline.limitation ? (
        <LimitationsState message={sparkline.limitation} title="Sparkline limitation" />
      ) : null}

      {journalAvailable && journal?.data?.truncated ? (
        <p className="text-sm text-text-muted" data-testid="overview-truncated">
          Journal statistics truncated at {journal.data.max_rows} rows — narrow the date range.
        </p>
      ) : null}
    </section>
  );
}
