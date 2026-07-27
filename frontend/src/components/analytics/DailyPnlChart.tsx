"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";

import type { SourceResult } from "@/components/workflows";
import type { PaperPortfolioResponse } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import {
  BAR_WIDTH_PX,
  INITIAL_VISIBLE_BARS,
  buildDailyPnlRows,
  plottableDailyRows,
} from "./chartTransforms";
import { formatMonetary } from "./format";

type DailyPnlRowPayload = {
  label: string;
  dailyPnl: number;
  tradesClosed: number;
  endingEquity: number | null;
};

function DailyPnlTooltip({
  active,
  payload,
  label,
  weekly,
}: TooltipProps<number, string> & { weekly: boolean }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as DailyPnlRowPayload;
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-primary shadow-elevation2"
      data-testid="daily-pnl-tooltip"
    >
      <p className="mb-1 font-medium text-text-secondary">
        {weekly ? "Week" : "Date"} {label}
      </p>
      <p className="font-data">Daily P&L: {formatMonetary(row.dailyPnl)}</p>
      <p className="font-data">Trades closed: {row.tradesClosed}</p>
      <p className="font-data">Ending equity: {formatMonetary(row.endingEquity)}</p>
    </div>
  );
}

type DailyPnlChartProps = {
  source: SourceResult<PaperPortfolioResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
};

export function DailyPnlChart({
  source,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
}: DailyPnlChartProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: [],
        plottable: [],
        weekly: false,
        limitations: [] as string[],
        generatedAt: null as string | null,
        sampleSize: 0,
        empty: true,
        unavailable: false,
      };
    }

    const transformed = buildDailyPnlRows(source.data.daily_series ?? []);
    const plottable = plottableDailyRows(transformed.rows);
    const limitations = [
      ...(source.data.account.limitations ?? []),
      ...(source.data.open_exposure.limitations ?? []),
    ];
    if (transformed.invalidMonetaryCount > 0) {
      limitations.push(
        `${transformed.invalidMonetaryCount} daily point(s) contain invalid monetary values and were excluded from the chart.`,
      );
    }

    const sampleSize = source.data.metrics.trade_count;
    const empty = plottable.length === 0 && sampleSize === 0;
    const unavailable = transformed.malformed && plottable.length === 0 && sampleSize > 0;

    return {
      rows: transformed.rows,
      plottable,
      weekly: transformed.weekly,
      limitations,
      generatedAt: source.data.account.as_of,
      sampleSize,
      empty,
      unavailable,
    };
  }, [source]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || derived.plottable.length <= INITIAL_VISIBLE_BARS) return;
    container.scrollLeft = Math.max(0, container.scrollWidth - container.clientWidth);
  }, [derived.plottable]);

  const best = derived.plottable.reduce<(typeof derived.plottable)[number] | null>(
    (current, row) => (!current || row.dailyPnl > current.dailyPnl ? row : current),
    null,
  );
  const worst = derived.plottable.reduce<(typeof derived.plottable)[number] | null>(
    (current, row) => (!current || row.dailyPnl < current.dailyPnl ? row : current),
    null,
  );

  const ariaLabel =
    derived.plottable.length > 0
      ? `Daily P&L chart from ${derived.plottable[0]?.label} to ${derived.plottable[derived.plottable.length - 1]?.label}. Best ${formatMonetary(best?.dailyPnl)}. Worst ${formatMonetary(worst?.dailyPnl)}.`
      : "Daily P&L chart with no data";

  const chartWidth = Math.max(320, derived.plottable.length * BAR_WIDTH_PX);

  return (
    <ChartFrame
      title="Which days made or lost money?"
      sourceLabel="GET /performance/portfolio · daily_series"
      generatedAt={derived.generatedAt}
      filtersSummary={filtersSummary}
      sampleSize={derived.sampleSize}
      sampleLabel="closed trades"
      loading={loading}
      error={
        source && !source.available
          ? source.error ?? "Paper portfolio unavailable"
          : derived.unavailable
            ? "Daily P&L series contains malformed monetary values — cannot render chart."
            : null
      }
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="No closed paper trades in this range"
      emptyDescription="Widen the date range or close journaled paper trades to populate daily P&L."
      limitations={derived.limitations}
      derivedNote={
        derived.weekly ? "ISO week roll-up — derived client-side from daily_series" : undefined
      }
      staleWholeTab={staleWholeTab}
      data-testid="daily-pnl-chart"
    >
      <div
        ref={scrollRef}
        role="img"
        aria-label={ariaLabel}
        className="h-[220px] w-full overflow-x-auto"
        data-testid="daily-pnl-chart-plot"
      >
        <div style={{ width: chartWidth, height: "100%" }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={derived.plottable} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="var(--color-border-subtle)"
              />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(value: number) => formatMonetary(value)} />
              <Tooltip content={<DailyPnlTooltip weekly={derived.weekly} />} />
              <Bar dataKey="dailyPnl" fill="var(--color-accent)" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <table className="sr-only" data-testid="daily-pnl-a11y-table">
        <caption>Daily P&L values</caption>
        <thead>
          <tr>
            <th>Period</th>
            <th>Daily P&L</th>
            <th>Trades closed</th>
            <th>Ending equity</th>
          </tr>
        </thead>
        <tbody>
          {derived.rows.map((row) => (
            <tr key={row.key}>
              <td>{row.label}</td>
              <td>{formatMonetary(row.dailyPnl)}</td>
              <td>{row.tradesClosed}</td>
              <td>{formatMonetary(row.endingEquity)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ChartFrame>
  );
}
