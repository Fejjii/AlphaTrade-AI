"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { SourceResult } from "@/components/workflows";
import type { DollarEquityPoint, PaperPortfolioResponse } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { formatMonetary, parseDecimal } from "./format";

const MAX_POINTS = 500;

type CurveRow = {
  index: number;
  label: string;
  cumulativePnl: number;
  hasTimestamp: boolean;
};

function decimatePoints(points: DollarEquityPoint[]): DollarEquityPoint[] {
  if (points.length <= MAX_POINTS) return points;
  const keep = new Set<number>([0, points.length - 1]);
  const step = Math.ceil(points.length / (MAX_POINTS - 2));
  for (let index = 0; index < points.length; index += step) keep.add(index);
  let maxIndex = 0;
  let minIndex = 0;
  let maxVal = Number.NEGATIVE_INFINITY;
  let minVal = Number.POSITIVE_INFINITY;
  points.forEach((point, index) => {
    const value = parseDecimal(point.cumulative_realized_pnl) ?? 0;
    if (value > maxVal) {
      maxVal = value;
      maxIndex = index;
    }
    if (value < minVal) {
      minVal = value;
      minIndex = index;
    }
  });
  keep.add(maxIndex);
  keep.add(minIndex);
  return [...keep]
    .sort((a, b) => a - b)
    .map((index) => points[index]);
}

function buildRows(points: DollarEquityPoint[]): { rows: CurveRow[]; missingTimestamps: number; decimated: boolean } {
  const filtered = points.filter((point) => point.event !== "live");
  const decimatedSource = decimatePoints(filtered);
  const missingTimestamps = decimatedSource.filter((point) => !point.timestamp).length;
  const rows = decimatedSource.map((point) => ({
    index: point.index,
    label: point.timestamp ? point.timestamp.slice(0, 10) : `#${point.index}`,
    cumulativePnl: parseDecimal(point.cumulative_realized_pnl) ?? 0,
    hasTimestamp: Boolean(point.timestamp),
  }));
  return {
    rows,
    missingTimestamps,
    decimated: decimatedSource.length < filtered.length,
  };
}

type CumulativePnlChartProps = {
  source: SourceResult<PaperPortfolioResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
};

export function CumulativePnlChart({
  source,
  loading = false,
  onRetry,
  filtersSummary,
}: CumulativePnlChartProps) {
  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: [] as CurveRow[],
        limitations: [] as string[],
        generatedAt: null as string | null,
        sampleSize: 0,
        empty: true,
        decimated: false,
        missingTimestamps: 0,
      };
    }

    const { rows, missingTimestamps, decimated } = buildRows(source.data.equity_curve ?? []);
    const limitations = [...(source.data.account.limitations ?? [])];
    if (missingTimestamps > 0) {
      limitations.push(`${missingTimestamps} equity points lack timestamps — plotted by index.`);
    }
    const sampleSize = source.data.metrics.trade_count;
    const empty = rows.length === 0 || sampleSize === 0;

    return {
      rows,
      limitations,
      generatedAt: source.data.account.as_of,
      sampleSize,
      empty,
      decimated,
      missingTimestamps,
    };
  }, [source]);

  const start = derived.rows[0]?.cumulativePnl ?? null;
  const end = derived.rows[derived.rows.length - 1]?.cumulativePnl ?? null;
  const change = start != null && end != null ? end - start : null;

  const ariaLabel =
    derived.rows.length > 0
      ? `Cumulative realised P&L from ${formatMonetary(start)} to ${formatMonetary(end)}, net change ${formatMonetary(change)}.`
      : "Cumulative realised P&L chart with no data";

  return (
    <ChartFrame
      title="Is realised P&L compounding or churning?"
      sourceLabel="GET /performance/portfolio · equity_curve.cumulative_realized_pnl"
      generatedAt={derived.generatedAt}
      filtersSummary={filtersSummary}
      sampleSize={derived.sampleSize}
      sampleLabel="closed trades"
      loading={loading}
      error={source && !source.available ? source.error ?? "Paper portfolio unavailable" : null}
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="No closed paper trades in this range"
      emptyDescription="Close journaled paper trades to build a cumulative realised P&L curve."
      limitations={derived.limitations}
      derivedNote={
        derived.decimated
          ? `Showing ${derived.rows.length} of ${source?.data?.equity_curve.length ?? 0} points (decimated evenly, first/last/extremes kept)`
          : undefined
      }
      data-testid="cumulative-pnl-chart"
    >
      <div
        role="img"
        aria-label={ariaLabel}
        className="h-[220px] w-full"
        data-testid="cumulative-pnl-chart-plot"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={derived.rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border-subtle)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(value: number) => formatMonetary(value)} />
            <Tooltip
              formatter={(value: number) => [formatMonetary(value), "Cumulative realised P&L"]}
              labelFormatter={(label) => String(label)}
            />
            <Line
              type="monotone"
              dataKey="cumulativePnl"
              stroke="var(--color-accent)"
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only" data-testid="cumulative-pnl-a11y-table">
        <caption>Cumulative realised P&L (every 10th point plus final)</caption>
        <thead>
          <tr>
            <th>Point</th>
            <th>Cumulative realised P&L</th>
          </tr>
        </thead>
        <tbody>
          {derived.rows
            .filter((_, index, all) => index % 10 === 0 || index === all.length - 1)
            .map((row) => (
              <tr key={row.index}>
                <td>{row.label}</td>
                <td>{formatMonetary(row.cumulativePnl)}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </ChartFrame>
  );
}
