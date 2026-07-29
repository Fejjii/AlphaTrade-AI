"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";

import type { SourceResult } from "@/components/workflows";
import type { JournalComparisonResponse } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { ChartFrame } from "./ChartFrame";
import {
  COMPARISON_METRICS,
  buildComparisonCohorts,
  evidenceIsInsufficient,
  metricValue,
  type ComparisonMetricId,
} from "./comparisonTransforms";
import { formatMonetary, formatPercent, formatProfitFactor } from "./format";
import { SOURCE_JOURNAL_COMPARISON_COHORTS } from "./sourceLabels";

type ComparisonChartProps = {
  source: SourceResult<JournalComparisonResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
};

function formatMetricDisplay(metric: ComparisonMetricId, value: number | null): string {
  if (value === null || value === undefined) return "—";
  switch (metric) {
    case "win_rate":
      return `${value.toFixed(1)}%`;
    case "expectancy":
      return formatMonetary(value);
    case "average_r":
      return value.toFixed(2);
    case "profit_factor":
      return formatProfitFactor(value);
  }
}

function ComparisonTooltip({
  active,
  payload,
  label,
}: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-primary shadow-elevation2"
      data-testid="comparison-tooltip"
    >
      <p className="mb-1 font-medium text-text-secondary">{label}</p>
      {payload.map((entry) => {
        const row = entry.payload as {
          metricId: ComparisonMetricId;
          samples: Record<string, number>;
          confidence: Record<string, string>;
        };
        const cohortKey = String(entry.dataKey);
        const raw = typeof entry.value === "number" ? entry.value : null;
        return (
          <p key={cohortKey} className="font-data">
            {entry.name}: {formatMetricDisplay(row.metricId, raw)} (n=
            {row.samples[cohortKey] ?? 0}, {row.confidence[cohortKey] ?? "—"})
          </p>
        );
      })}
    </div>
  );
}

export function ComparisonChart({
  source,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
}: ComparisonChartProps) {
  const [metric, setMetric] = useState<ComparisonMetricId>("win_rate");

  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        cohorts: buildComparisonCohorts(null),
        insufficientEvidence: true,
        empty: true,
        generatedAt: null as string | null,
        overallConfidence: null as string | null,
        drilldownHref: "/journal/comparison",
      };
    }
    const cohorts = buildComparisonCohorts(source.data);
    const empty = cohorts.every((cohort) => cohort.sampleCount === 0);
    return {
      cohorts,
      insufficientEvidence: evidenceIsInsufficient(cohorts),
      empty,
      generatedAt: source.data.generated_at,
      overallConfidence: source.data.confidence,
      drilldownHref: source.data.links.journal_comparison_path || "/journal/comparison",
    };
  }, [source]);

  const chartRows = useMemo(() => {
    const meta = COMPARISON_METRICS.find((item) => item.id === metric)!;
    const samples: Record<string, number> = {};
    const confidence: Record<string, string> = {};
    const row: Record<string, number | string | null | Record<string, number> | Record<string, string>> =
      {
        label: meta.label,
        metricId: metric,
        samples,
        confidence,
      };
    for (const cohort of derived.cohorts) {
      samples[cohort.cohort] = cohort.sampleCount;
      confidence[cohort.cohort] = cohort.confidence;
      row[cohort.cohort] = metricValue(cohort, metric);
    }
    return [row];
  }, [derived.cohorts, metric]);

  const ariaLabel = `Human versus system comparison for ${metric}. ${derived.cohorts
    .map(
      (cohort) =>
        `${cohort.label}: ${formatMetricDisplay(metric, metricValue(cohort, metric))} n=${cohort.sampleCount} confidence ${cohort.confidence}`,
    )
    .join("; ")}`;

  return (
    <ChartFrame
      title="Where does the human beat the system?"
      sourceLabel={SOURCE_JOURNAL_COMPARISON_COHORTS}
      generatedAt={derived.generatedAt}
      filtersSummary={filtersSummary}
      sampleSize={derived.cohorts.reduce((sum, cohort) => sum + cohort.sampleCount, 0)}
      sampleLabel="closed trades across cohorts"
      loading={loading}
      error={source && !source.available ? source.error ?? "Comparison unavailable" : null}
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="Not enough closed trades in one or both cohorts"
      emptyDescription="Journal more closed human and system trades in this filter range to unlock comparison."
      insufficientSample={
        derived.insufficientEvidence && !derived.empty
          ? {
              n: derived.cohorts.reduce((sum, cohort) => sum + cohort.sampleCount, 0),
            }
          : null
      }
      staleWholeTab={staleWholeTab}
      data-testid="comparison-chart"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2" data-testid="comparison-metric-toggle">
        <span className="text-caption text-text-muted">Metric:</span>
        {COMPARISON_METRICS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={cn(
              "rounded-control border px-2 py-1 text-caption",
              metric === item.id
                ? "border-accent bg-accent/10 text-text-primary"
                : "border-border-subtle text-text-muted",
            )}
            aria-pressed={metric === item.id}
            onClick={() => setMetric(item.id)}
          >
            {item.label}
          </button>
        ))}
        <span className="text-caption text-text-muted md:hidden">
          Progressive disclosure: one metric at a time on mobile.
        </span>
      </div>

      {derived.insufficientEvidence ? (
        <p
          className="mb-3 text-sm text-text-muted"
          data-testid="comparison-insufficient-note"
          role="status"
        >
          Evidence is insufficient for a cohort verdict. Sample sizes are shown; values stay muted
          and comparative verdict language is suppressed.
        </p>
      ) : null}

      {!derived.insufficientEvidence ? (
        <p className="mb-3 text-sm text-text-secondary" data-testid="comparison-evidence-note">
          Compare cohort metrics directly. Use the journal comparison page for numeric drill-down —
          this chart does not declare a guaranteed winner.
        </p>
      ) : null}

      <div
        role="img"
        aria-label={ariaLabel}
        className={cn(
          "h-[260px] w-full",
          derived.insufficientEvidence ? "opacity-60" : undefined,
        )}
        data-testid="comparison-chart-plot"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="var(--color-border-subtle)"
            />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis
              tick={{ fontSize: 11 }}
              tickFormatter={(value: number) => formatMetricDisplay(metric, value)}
            />
            <Tooltip content={<ComparisonTooltip />} />
            <Legend />
            <Bar
              dataKey="human"
              name="Human"
              fill="var(--color-accent)"
              isAnimationActive={false}
            />
            <Bar
              dataKey="paper_system"
              name="Paper system"
              fill="var(--color-text-secondary)"
              isAnimationActive={false}
            />
            <Bar
              dataKey="backtest"
              name="Backtest"
              fill="var(--color-text-muted)"
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul className="mt-3 grid gap-2 text-caption text-text-muted sm:grid-cols-3">
        {derived.cohorts.map((cohort) => (
          <li
            key={cohort.cohort}
            data-testid={`comparison-cohort-sample-${cohort.cohort}`}
            className={cohort.insufficient ? "opacity-70" : undefined}
          >
            {cohort.label}: n={cohort.sampleCount}
            {cohort.insufficient ? " — insufficient" : ""} ·{" "}
            {formatMetricDisplay(metric, metricValue(cohort, metric))}
          </li>
        ))}
      </ul>

      <p className="text-sm text-text-secondary">
        Numeric drill-down:{" "}
        <Link
          href={derived.drilldownHref}
          className="underline"
          data-testid="comparison-drilldown-link"
        >
          /journal/comparison
        </Link>
      </p>

      <table className="sr-only" data-testid="comparison-a11y-table">
        <caption>Human versus system comparison by metric</caption>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Cohort</th>
            <th>Value</th>
            <th>Sample count</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {COMPARISON_METRICS.flatMap((item) =>
            derived.cohorts.map((cohort) => (
              <tr key={`${item.id}-${cohort.cohort}`}>
                <td>{item.label}</td>
                <td>{cohort.label}</td>
                <td>
                  {item.id === "win_rate"
                    ? formatPercent(cohort.winRate)
                    : item.id === "expectancy"
                      ? formatMonetary(cohort.expectancy)
                      : item.id === "average_r"
                        ? cohort.averageR == null
                          ? "—"
                          : cohort.averageR.toFixed(2)
                        : formatProfitFactor(cohort.profitFactor)}
                </td>
                <td>{cohort.sampleCount}</td>
                <td>{cohort.confidence}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </ChartFrame>
  );
}
