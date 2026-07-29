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
import type { TooltipProps } from "recharts";

import type { SourceResult } from "@/components/workflows";
import type { PaperPortfolioResponse } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { buildCumulativePnlRows, plottableCumulativeRows } from "./chartTransforms";
import { formatMonetary } from "./format";
import { SOURCE_PAPER_CUMULATIVE_PNL } from "./sourceLabels";

function CumulativePnlTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as {
    index: number;
    cumulativePnl: number;
    label: string;
  };
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-primary shadow-elevation2"
      data-testid="cumulative-pnl-tooltip"
    >
      <p className="mb-1 font-medium text-text-secondary">Point {label}</p>
      <p className="font-data">Cumulative realised P&L: {formatMonetary(row.cumulativePnl)}</p>
      <p className="font-data">Trade counter: {row.index}</p>
    </div>
  );
}

type CumulativePnlChartProps = {
  source: SourceResult<PaperPortfolioResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
};

export function CumulativePnlChart({
  source,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
}: CumulativePnlChartProps) {
  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: [],
        plottable: [],
        limitations: [] as string[],
        generatedAt: null as string | null,
        sampleSize: 0,
        empty: true,
        unavailable: false,
        filteredPointCount: 0,
        decimated: false,
      };
    }

    const transformed = buildCumulativePnlRows(source.data.equity_curve ?? []);
    const plottable = plottableCumulativeRows(transformed.rows);
    const limitations = [...(source.data.account.limitations ?? [])];

    if (transformed.excludedLiveCount > 0) {
      limitations.push(
        `${transformed.excludedLiveCount} live/unrealised equity point(s) excluded from cumulative realised P&L.`,
      );
    }
    if (transformed.missingTimestamps > 0) {
      limitations.push(
        `${transformed.missingTimestamps} trade-close point(s) lack timestamps — plotted by index.`,
      );
    }
    if (transformed.invalidMonetaryCount > 0) {
      limitations.push(
        `${transformed.invalidMonetaryCount} trade-close point(s) contain invalid cumulative P&L values and were excluded.`,
      );
    }

    const sampleSize = source.data.metrics.trade_count;
    const empty = plottable.length === 0 && sampleSize === 0;
    const unavailable = transformed.malformed && plottable.length === 0 && sampleSize > 0;

    return {
      rows: transformed.rows,
      plottable,
      limitations,
      generatedAt: source.data.account.as_of,
      sampleSize,
      empty,
      unavailable,
      filteredPointCount: transformed.filteredPointCount,
      decimated: transformed.decimated,
    };
  }, [source]);

  const start = derived.plottable[0]?.cumulativePnl ?? null;
  const end = derived.plottable[derived.plottable.length - 1]?.cumulativePnl ?? null;
  const change = start != null && end != null ? end - start : null;

  const ariaLabel =
    derived.plottable.length > 0
      ? `Cumulative realised P&L from ${formatMonetary(start)} to ${formatMonetary(end)}, net change ${formatMonetary(change)}.`
      : "Cumulative realised P&L chart with no data";

  return (
    <ChartFrame
      title="Is realised P&L compounding or churning?"
      sourceLabel={SOURCE_PAPER_CUMULATIVE_PNL}
      generatedAt={derived.generatedAt}
      filtersSummary={filtersSummary}
      sampleSize={derived.sampleSize}
      sampleLabel="closed trades"
      loading={loading}
      error={
        source && !source.available
          ? source.error ?? "Paper portfolio unavailable"
          : derived.unavailable
            ? "Cumulative P&L series contains malformed monetary values — cannot render chart."
            : null
      }
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="No closed paper trades in this range"
      emptyDescription="Close journaled paper trades to build a cumulative realised P&L curve."
      limitations={derived.limitations}
      derivedNote={
        derived.decimated
          ? `Showing ${derived.rows.length} of ${derived.filteredPointCount} trade-close points (decimated evenly; first, last, and extremes kept)`
          : undefined
      }
      staleWholeTab={staleWholeTab}
      data-testid="cumulative-pnl-chart"
    >
      <div
        role="img"
        aria-label={ariaLabel}
        className="h-[220px] w-full"
        data-testid="cumulative-pnl-chart-plot"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={derived.plottable} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="var(--color-border-subtle)"
            />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(value: number) => formatMonetary(value)} />
            <Tooltip content={<CumulativePnlTooltip />} />
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
        <caption>
          Cumulative realised P&L (decimated evenly; first, last, and extremes kept)
        </caption>
        <thead>
          <tr>
            <th scope="col">Point</th>
            <th scope="col">Cumulative realised P&L</th>
            <th scope="col">Trade counter</th>
          </tr>
        </thead>
        <tbody>
          {derived.rows
            .filter((_, index, all) => index % 10 === 0 || index === all.length - 1)
            .map((row) => (
              <tr key={row.index}>
                <td>{row.label}</td>
                <td>{formatMonetary(row.cumulativePnl)}</td>
                <td>{row.index}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </ChartFrame>
  );
}
