"use client";

import { useMemo, useState } from "react";
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
import Link from "next/link";

import type { SourceResult } from "@/components/workflows";
import type { JournalStatsResponse } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { ChartFrame } from "./ChartFrame";
import { formatMonetary, formatPercent } from "./format";
import {
  buildRuleComplianceRows,
  totalRuleComplianceSample,
  type RuleComplianceMetric,
  type RuleComplianceRow,
} from "./ruleComplianceTransforms";

type RuleComplianceChartProps = {
  source: SourceResult<JournalStatsResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
};

function RuleComplianceTooltip({
  active,
  payload,
  metric,
}: TooltipProps<number, string> & { metric: RuleComplianceMetric }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as RuleComplianceRow & { plotValue: number | null };
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-primary shadow-elevation2"
      data-testid="rule-compliance-tooltip"
    >
      <p className="mb-1 font-medium text-text-secondary">{row.label}</p>
      <p className="font-data">Sample n={row.tradeCount}</p>
      <p className="font-data">Win rate: {formatPercent(row.winRate)}</p>
      <p className="font-data">
        Expectancy (mean net P&amp;L per trade): {formatMonetary(row.expectancy)}
      </p>
      <p className="font-data">Confidence: {row.confidence}</p>
      <p className="text-text-muted">
        Showing {metric === "win_rate" ? "win rate" : "expectancy"}
      </p>
    </div>
  );
}

export function RuleComplianceChart({
  source,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
}: RuleComplianceChartProps) {
  const [metric, setMetric] = useState<RuleComplianceMetric>("win_rate");

  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: buildRuleComplianceRows(null),
        sampleSize: 0,
        empty: true,
        generatedAt: null as string | null,
        truncated: null as { maxRows: number } | null,
      };
    }
    const rows = buildRuleComplianceRows(source.data);
    const sampleSize = totalRuleComplianceSample(rows);
    return {
      rows,
      sampleSize,
      empty: sampleSize === 0 && source.data.overall.trade_count === 0,
      generatedAt: source.data.generated_at,
      truncated: source.data.truncated ? { maxRows: source.data.max_rows } : null,
    };
  }, [source]);

  const plotRows = derived.rows.map((row) => ({
    ...row,
    plotValue:
      metric === "win_rate"
        ? row.winRate == null
          ? null
          : row.winRate * 100
        : row.expectancy,
    muted: row.confidence === "insufficient" || row.tradeCount === 0,
  }));

  const ariaLabel = `Rule compliance breakdown by ${
    metric === "win_rate" ? "win rate" : "signed monetary expectancy"
  }. ${derived.rows
    .map(
      (row) =>
        `${row.label}: n=${row.tradeCount}, win rate ${formatPercent(row.winRate)}, expectancy ${formatMonetary(row.expectancy)}`,
    )
    .join("; ")}`;

  return (
    <ChartFrame
      title="Do I perform better when I follow my rules?"
      sourceLabel="GET /journal/statistics · group_by=rule_compliance"
      generatedAt={derived.generatedAt}
      filtersSummary={filtersSummary}
      sampleSize={derived.sampleSize}
      sampleLabel="closed trades across compliance buckets"
      loading={loading}
      error={source && !source.available ? source.error ?? "Rule compliance unavailable" : null}
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="No rule checks recorded yet"
      emptyDescription="Rule checks are recorded manually on journal trades. Assess closed trades to populate compliance buckets."
      truncated={derived.truncated}
      staleWholeTab={staleWholeTab}
      data-testid="rule-compliance-chart"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2" data-testid="rule-compliance-metric-toggle">
        <span className="text-caption text-text-muted">Metric:</span>
        {(
          [
            ["win_rate", "Win rate"],
            ["expectancy", "Expectancy"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={cn(
              "rounded-control border px-2 py-1 text-caption",
              metric === value
                ? "border-accent bg-accent/10 text-text-primary"
                : "border-border-subtle text-text-muted",
            )}
            aria-pressed={metric === value}
            onClick={() => setMetric(value)}
          >
            {label}
          </button>
        ))}
        <span className="text-caption text-text-muted">
          One metric at a time on narrow viewports. Unassessed remains visible as the honest
          denominator.
        </span>
      </div>

      <div
        role="img"
        aria-label={ariaLabel}
        className="h-[240px] w-full"
        data-testid="rule-compliance-chart-plot"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={plotRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="var(--color-border-subtle)"
            />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis
              tick={{ fontSize: 11 }}
              tickFormatter={(value: number) =>
                metric === "win_rate" ? `${value.toFixed(0)}%` : formatMonetary(value)
              }
            />
            <Tooltip content={<RuleComplianceTooltip metric={metric} />} />
            <Bar
              dataKey="plotValue"
              fill="var(--color-accent)"
              isAnimationActive={false}
              name={metric === "win_rate" ? "Win rate %" : "Expectancy"}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul className="mt-3 grid gap-2 text-caption text-text-muted sm:grid-cols-2 lg:grid-cols-4">
        {derived.rows.map((row) => (
          <li
            key={row.key}
            className={cn(row.key === "unassessed" ? "text-text-secondary" : undefined)}
            data-testid={`rule-compliance-sample-${row.key}`}
          >
            {row.label}: n={row.tradeCount}
            {row.key === "unassessed" ? " (unassessed bucket)" : ""}
          </li>
        ))}
      </ul>

      <p className="text-caption text-text-muted">
        Empty buckets stay at zero sample counts. Null win rate / expectancy stay unavailable (—),
        never fabricated zeros.{" "}
        <Link href="/journal" className="underline text-text-secondary">
          Open journal
        </Link>{" "}
        to record rule checks.
      </p>

      <table className="sr-only" data-testid="rule-compliance-a11y-table">
        <caption>Rule compliance buckets with sample counts and metrics</caption>
        <thead>
          <tr>
            <th>Compliance</th>
            <th>Sample count</th>
            <th>Win rate</th>
            <th>Expectancy</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {derived.rows.map((row) => (
            <tr key={row.key}>
              <td>{row.label}</td>
              <td>{row.tradeCount}</td>
              <td>{formatPercent(row.winRate)}</td>
              <td>{formatMonetary(row.expectancy)}</td>
              <td>{row.confidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ChartFrame>
  );
}
