"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { SourceResult } from "@/components/workflows";
import type { DailyPortfolioPoint, PaperPortfolioResponse } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { formatDateRangeLabel, formatMonetary, parseDecimal } from "./format";

const MAX_DAILY_BARS = 180;

type DailyRow = {
  date: string;
  dailyPnl: number;
  tradesClosed: number;
  endingEquity: number;
};

function buildWeeklyRows(series: DailyPortfolioPoint[]): DailyRow[] {
  const buckets = new Map<string, DailyRow>();
  for (const point of series) {
    const weekKey = point.date.slice(0, 7);
    const existing = buckets.get(weekKey) ?? {
      date: weekKey,
      dailyPnl: 0,
      tradesClosed: 0,
      endingEquity: 0,
    };
    existing.dailyPnl += parseDecimal(point.daily_pnl) ?? 0;
    existing.tradesClosed += point.trades_closed;
    existing.endingEquity = parseDecimal(point.ending_equity) ?? existing.endingEquity;
    buckets.set(weekKey, existing);
  }
  return [...buckets.values()].sort((a, b) => a.date.localeCompare(b.date));
}

function buildDailyRows(series: DailyPortfolioPoint[]): DailyRow[] {
  return series.map((point) => ({
    date: point.date,
    dailyPnl: parseDecimal(point.daily_pnl) ?? 0,
    tradesClosed: point.trades_closed,
    endingEquity: parseDecimal(point.ending_equity) ?? 0,
  }));
}

type DailyPnlChartProps = {
  source: SourceResult<PaperPortfolioResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
};

export function DailyPnlChart({ source, loading = false, onRetry, filtersSummary }: DailyPnlChartProps) {
  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: [] as DailyRow[],
        weekly: false,
        limitations: [] as string[],
        generatedAt: null as string | null,
        sampleSize: 0,
        empty: true,
      };
    }

    const series = source.data.daily_series ?? [];
    const weekly = series.length > MAX_DAILY_BARS;
    const rows = weekly ? buildWeeklyRows(series) : buildDailyRows(series);
    const limitations = [
      ...(source.data.account.limitations ?? []),
      ...(source.data.open_exposure.limitations ?? []),
    ];
    const sampleSize = source.data.metrics.trade_count;
    const empty = rows.length === 0 || sampleSize === 0;

    return {
      rows,
      weekly,
      limitations,
      generatedAt: source.data.account.as_of,
      sampleSize,
      empty,
    };
  }, [source]);

  const best = derived.rows.reduce<DailyRow | null>((current, row) => {
    if (!current || row.dailyPnl > current.dailyPnl) return row;
    return current;
  }, null);
  const worst = derived.rows.reduce<DailyRow | null>((current, row) => {
    if (!current || row.dailyPnl < current.dailyPnl) return row;
    return current;
  }, null);

  const ariaLabel =
    derived.rows.length > 0
      ? `Daily P&L chart from ${derived.rows[0]?.date} to ${derived.rows[derived.rows.length - 1]?.date}. Best day ${formatMonetary(best?.dailyPnl)}. Worst day ${formatMonetary(worst?.dailyPnl)}.`
      : "Daily P&L chart with no data";

  return (
    <ChartFrame
      title="Which days made or lost money?"
      sourceLabel="GET /performance/portfolio · daily_series"
      generatedAt={derived.generatedAt}
      filtersSummary={filtersSummary}
      sampleSize={derived.sampleSize}
      sampleLabel="closed trades"
      loading={loading}
      error={source && !source.available ? source.error ?? "Paper portfolio unavailable" : null}
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="No closed paper trades in this range"
      emptyDescription="Widen the date range or close journaled paper trades to populate daily P&L."
      limitations={derived.limitations}
      derivedNote={
        derived.weekly ? "Weekly — derived client-side from daily_series" : undefined
      }
      data-testid="daily-pnl-chart"
    >
      <div
        role="img"
        aria-label={ariaLabel}
        className="h-[220px] w-full overflow-x-auto"
        data-testid="daily-pnl-chart-plot"
      >
        <ResponsiveContainer width="100%" height="100%" minWidth={320}>
          <BarChart data={derived.rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border-subtle)" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(value: number) => formatMonetary(value)} />
            <Tooltip
              formatter={(value: number) => [formatMonetary(value), "Daily P&L"]}
              labelFormatter={(label) => String(label)}
            />
            <Bar
              dataKey="dailyPnl"
              fill="var(--color-accent)"
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only" data-testid="daily-pnl-a11y-table">
        <caption>Daily P&L values</caption>
        <thead>
          <tr>
            <th>Date</th>
            <th>Daily P&L</th>
            <th>Trades closed</th>
          </tr>
        </thead>
        <tbody>
          {derived.rows.map((row) => (
            <tr key={row.date}>
              <td>{row.date}</td>
              <td>{formatMonetary(row.dailyPnl)}</td>
              <td>{row.tradesClosed}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ChartFrame>
  );
}

export function dailyPnlFiltersSummary(from: string | null, to: string | null): string {
  return formatDateRangeLabel(from, to);
}
