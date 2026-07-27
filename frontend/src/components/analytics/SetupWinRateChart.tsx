"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
import { formatPercent } from "./format";
import {
  SETUP_CHART_MOBILE_CAP,
  buildSetupBucketRows,
  visibleSetupChartRows,
  type SetupBucketRow,
} from "./setupBucketTransforms";

function WinRateTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as SetupBucketRow;
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-primary shadow-elevation2"
      data-testid="setup-win-rate-tooltip"
    >
      <p className="mb-1 font-medium text-text-secondary">{row.displayLabel}</p>
      <p className="font-data">Win rate: {formatPercent(row.winRate)}</p>
      <p className="font-data">
        W {row.wins} / L {row.losses} / BE {row.breakeven}
      </p>
      <p className="font-data">n={row.tradeCount}</p>
      <p className="font-data">Confidence: {row.confidence}</p>
    </div>
  );
}

export type SetupWinRateChartProps = {
  source: SourceResult<JournalStatsResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
};

export function SetupWinRateChart({
  source,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
}: SetupWinRateChartProps) {
  const [showAll, setShowAll] = useState(false);

  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: [] as SetupBucketRow[],
        sampleSize: 0,
        empty: true,
        truncated: null as { maxRows: number } | null,
        generatedAt: null as string | null,
      };
    }
    const rows = buildSetupBucketRows(source.data.buckets ?? []);
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
  const chartHeight = Math.max(220, visible.length * 36 + 40);

  const ariaLabel =
    visible.length > 0
      ? `Setup win-rate chart with ${visible.length} journal setup buckets. Top ${visible[0]?.displayLabel} at ${formatPercent(visible[0]?.winRate)}.`
      : "Setup win-rate chart with no data";

  return (
    <ChartFrame
      title="Which setups win most often — with enough sample to matter?"
      sourceLabel="GET /journal/statistics · group_by setup buckets · win_rate"
      generatedAt={derived.generatedAt}
      filtersSummary={filtersSummary}
      sampleSize={derived.sampleSize}
      sampleLabel="closed trades"
      loading={loading}
      error={source && !source.available ? source.error ?? "Journal statistics unavailable" : null}
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="No closed trades have a recorded setup in this range."
      emptyDescription="Journal closed trades with a setup definition, or widen filters. Open journal statistics for the numeric table."
      truncated={derived.truncated}
      staleWholeTab={staleWholeTab}
      data-testid="setup-win-rate-chart"
    >
      <div
        role="img"
        aria-label={ariaLabel}
        className="w-full max-w-full overflow-x-hidden"
        style={{ height: chartHeight }}
        data-testid="setup-win-rate-chart-plot"
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
              domain={[0, 100]}
              tick={{ fontSize: 11 }}
              tickFormatter={(value: number) => `${value.toFixed(0)}%`}
            />
            <YAxis
              type="category"
              dataKey="displayLabel"
              width={120}
              tick={{ fontSize: 11 }}
              interval={0}
            />
            <Tooltip content={<WinRateTooltip />} />
            <Bar dataKey="winRatePct" isAnimationActive={false} name="Win rate">
              {visible.map((row) => (
                <Cell
                  key={row.key}
                  fill={row.insufficient ? "var(--color-text-muted)" : "var(--color-accent)"}
                  fillOpacity={row.insufficient ? 0.45 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul className="space-y-1 text-sm" data-testid="setup-win-rate-list" aria-label="Setup win rates">
        {visible.map((row) => (
          <li
            key={row.key}
            className={row.insufficient ? "text-text-muted" : "text-text-secondary"}
            data-testid={`setup-win-rate-row-${row.key}`}
          >
            <span className="font-medium text-text-primary">{row.displayLabel}</span>
            {": "}
            {formatPercent(row.winRate)} · n={row.tradeCount}
            {row.insufficient ? " — insufficient" : ""}
            {row.unassigned ? " · unassigned" : ""}
          </li>
        ))}
      </ul>

      {hiddenCount > 0 || showAll ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setShowAll((current) => !current)}
          data-testid="setup-win-rate-show-all"
        >
          {showAll ? `Show top ${SETUP_CHART_MOBILE_CAP}` : `Show all (${derived.rows.length})`}
        </Button>
      ) : null}

      <table className="sr-only" data-testid="setup-win-rate-a11y-table">
        <caption>Setup win-rate values (journal setup identity by key)</caption>
        <thead>
          <tr>
            <th>Key</th>
            <th>Label</th>
            <th>Win rate</th>
            <th>Wins</th>
            <th>Losses</th>
            <th>n</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {derived.rows.map((row) => (
            <tr key={row.key}>
              <td>{row.key}</td>
              <td>{row.label}</td>
              <td>{formatPercent(row.winRate)}</td>
              <td>{row.wins}</td>
              <td>{row.losses}</td>
              <td>{row.tradeCount}</td>
              <td>{row.confidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ChartFrame>
  );
}
