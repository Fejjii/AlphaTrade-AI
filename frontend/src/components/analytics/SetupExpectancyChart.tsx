"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";

import { Button } from "@/components/ui/button";
import type { SourceResult } from "@/components/workflows";
import type { JournalStatsResponse } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { JournalStatisticsLink } from "./JournalStatisticsLink";
import { formatMonetary } from "./format";
import type { SetupGroupBy } from "./filterValidation";
import {
  SETUP_CHART_MOBILE_CAP,
  buildSetupBucketRows,
  visibleSetupChartRows,
  type SetupBucketRow,
} from "./setupBucketTransforms";
import { setupExpectancyAriaLabel, setupGroupCopy } from "./setupGroupCopy";

type ExpectancyPlotRow = SetupBucketRow & {
  plotExpectancy: number | null;
};

function ExpectancyTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as ExpectancyPlotRow;
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-primary shadow-elevation2"
      data-testid="setup-expectancy-tooltip"
    >
      <p className="mb-1 font-medium text-text-secondary">{row.displayLabel}</p>
      <p className="font-data">
        Expectancy (mean net P&L per trade):{" "}
        {row.noPnlData ? "No P&L data" : formatMonetary(row.expectancy)}
      </p>
      {row.rSampleCount > 0 ? (
        <p className="font-data">Average R: {row.averageR?.toFixed(2) ?? "—"}</p>
      ) : null}
      <p className="font-data">n={row.tradeCount}</p>
      <p className="font-data">Confidence: {row.confidence}</p>
    </div>
  );
}

export type SetupExpectancyChartProps = {
  source: SourceResult<JournalStatsResponse> | null;
  groupBy: SetupGroupBy;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
};

export function SetupExpectancyChart({
  source,
  groupBy,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
}: SetupExpectancyChartProps) {
  const [showAll, setShowAll] = useState(false);
  const copy = setupGroupCopy(groupBy);

  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: [] as ExpectancyPlotRow[],
        sampleSize: 0,
        empty: true,
        truncated: null as { maxRows: number } | null,
        generatedAt: null as string | null,
      };
    }
    const rows = buildSetupBucketRows(source.data.buckets ?? []).map((row) => ({
      ...row,
      // null expectancy must not plot as zero
      plotExpectancy: row.noPnlData ? null : row.expectancy,
    }));
    const sampleSize = source.data.overall.trade_count;
    const empty = sampleSize === 0 || rows.length === 0;
    return {
      rows,
      sampleSize,
      empty,
      truncated: source.data.truncated ? { maxRows: source.data.max_rows } : null,
      generatedAt: source.data.generated_at,
    };
  }, [source]);

  const { visible, hiddenCount } = visibleSetupChartRows(derived.rows, showAll);
  // Highest expectancy from all plottable rows, not only the mobile-capped visible set.
  const plottableAll = derived.rows.filter(
    (row) => !row.noPnlData && row.plotExpectancy !== null,
  );
  const chartHeight = Math.max(220, visible.length * 36 + 40);

  const best = plottableAll.reduce<ExpectancyPlotRow | null>(
    (current, row) =>
      !current || (row.plotExpectancy ?? Number.NEGATIVE_INFINITY) >
        (current.plotExpectancy ?? Number.NEGATIVE_INFINITY)
        ? row
        : current,
    null,
  );
  const ariaLabel = setupExpectancyAriaLabel(
    groupBy,
    derived.rows.length,
    best?.displayLabel ?? null,
    best ? formatMonetary(best.plotExpectancy) : null,
  );

  return (
    <ChartFrame
      title="Expectancy (mean net P&L per trade)"
      sourceLabel={copy.expectancySourceLabel}
      generatedAt={derived.generatedAt}
      filtersSummary={filtersSummary}
      sampleSize={derived.sampleSize}
      sampleLabel="closed trades"
      loading={loading}
      error={source && !source.available ? source.error ?? "Journal statistics unavailable" : null}
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle={copy.expectancyEmptyTitle}
      emptyDescription={copy.expectancyEmptyDescription}
      emptyAction={
        <JournalStatisticsLink data-testid="setup-expectancy-empty-journal-link" />
      }
      truncated={derived.truncated}
      staleWholeTab={staleWholeTab}
      data-testid="setup-expectancy-chart"
    >
      <div
        role="img"
        aria-label={ariaLabel}
        className="w-full max-w-full"
        style={{ height: chartHeight }}
        data-testid="setup-expectancy-chart-plot"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={visible}
            layout="vertical"
            margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-border-subtle)" />
            <XAxis
              type="number"
              tick={{ fontSize: 11 }}
              tickFormatter={(value: number) => formatMonetary(value)}
            />
            <YAxis
              type="category"
              dataKey="displayLabel"
              width={120}
              tick={{ fontSize: 11 }}
              interval={0}
            />
            <ReferenceLine x={0} stroke="var(--color-border-strong)" />
            <Tooltip content={<ExpectancyTooltip />} />
            <Bar dataKey="plotExpectancy" isAnimationActive={false} name="Expectancy">
              {visible.map((row) => (
                <Cell
                  key={row.key}
                  fill={
                    row.noPnlData
                      ? "transparent"
                      : row.insufficient
                        ? "var(--color-text-muted)"
                        : (row.plotExpectancy ?? 0) >= 0
                          ? "var(--color-positive)"
                          : "var(--color-negative)"
                  }
                  fillOpacity={row.insufficient ? 0.45 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul
        className="space-y-1 text-sm"
        data-testid="setup-expectancy-list"
        aria-label={copy.expectancyListAriaLabel}
      >
        {visible.map((row) => (
          <li
            key={row.key}
            className={row.insufficient ? "text-text-muted" : "text-text-secondary"}
            data-testid={`setup-expectancy-row-${row.key}`}
          >
            <span className="font-medium text-text-primary">{row.displayLabel}</span>
            {": "}
            {row.noPnlData ? "No P&L data" : formatMonetary(row.expectancy)}
            {" · n="}
            {row.tradeCount}
            {row.insufficient ? " — insufficient" : ""}
          </li>
        ))}
      </ul>

      {hiddenCount > 0 || showAll ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setShowAll((current) => !current)}
          data-testid="setup-expectancy-show-all"
        >
          {showAll ? `Show top ${SETUP_CHART_MOBILE_CAP}` : `Show all (${derived.rows.length})`}
        </Button>
      ) : null}

      <table className="sr-only" data-testid="setup-expectancy-a11y-table">
        <caption>{copy.expectancyA11yCaption}</caption>
        <thead>
          <tr>
            <th>Key</th>
            <th>Label</th>
            <th>Expectancy</th>
            <th>n</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {derived.rows.map((row) => (
            <tr key={row.key}>
              <td>{row.key}</td>
              <td>{row.label}</td>
              <td>{row.noPnlData ? "No P&L data" : formatMonetary(row.expectancy)}</td>
              <td>{row.tradeCount}</td>
              <td>{row.confidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ChartFrame>
  );
}
