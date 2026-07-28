"use client";

import { useMemo } from "react";
import Link from "next/link";
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

import type { SourceResult } from "@/components/workflows";
import type { LearningAnalyticsSummaryResponse, OutcomeDistributionItem } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { formatPercent } from "./format";
import { NO_SERVER_FRESHNESS_TIMESTAMP_NOTE } from "./sourceFreshness";

export const VALIDATION_OUTCOME_CATEGORIES = [
  "success",
  "failure",
  "invalidated",
  "missed_entry",
  "no_trade",
  "inconclusive",
] as const;

export type ValidationOutcomeCategory = (typeof VALIDATION_OUTCOME_CATEGORIES)[number];

const CATEGORY_LABELS: Record<ValidationOutcomeCategory, string> = {
  success: "Success",
  failure: "Failure",
  invalidated: "Invalidated",
  missed_entry: "Missed entry",
  no_trade: "No trade",
  inconclusive: "Inconclusive",
};

const SHORT_LABELS: Record<ValidationOutcomeCategory, string> = {
  success: "Success",
  failure: "Failure",
  invalidated: "Invalid.",
  missed_entry: "Missed",
  no_trade: "No trade",
  inconclusive: "Inconcl.",
};

type OutcomeRow = {
  outcome: ValidationOutcomeCategory;
  label: string;
  shortLabel: string;
  count: number;
  rate: number | null;
};

function OutcomeTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as OutcomeRow;
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-primary shadow-elevation2"
      data-testid="validation-outcome-tooltip"
    >
      <p className="mb-1 font-medium text-text-secondary">{row.label}</p>
      <p className="font-data">Sessions: {row.count}</p>
      <p className="font-data">Rate: {formatPercent(row.rate)}</p>
    </div>
  );
}

function buildOutcomeRows(
  distribution: OutcomeDistributionItem[] | undefined,
): OutcomeRow[] {
  const byOutcome = new Map(
    (distribution ?? []).map((item) => [item.outcome, item] as const),
  );
  return VALIDATION_OUTCOME_CATEGORIES.map((outcome) => {
    const item = byOutcome.get(outcome);
    return {
      outcome,
      label: CATEGORY_LABELS[outcome],
      shortLabel: SHORT_LABELS[outcome],
      count: item?.count ?? 0,
      rate: item?.rate ?? null,
    };
  });
}

export type ValidationOutcomeChartProps = {
  source: SourceResult<LearningAnalyticsSummaryResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
};

export function ValidationOutcomeChart({
  source,
  loading = false,
  onRetry,
  filtersSummary,
}: ValidationOutcomeChartProps) {
  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: [] as OutcomeRow[],
        sampleSize: 0,
        minSample: 5,
        empty: true,
        insufficient: false,
      };
    }
    const rows = buildOutcomeRows(source.data.outcome_distribution);
    const sampleSize = source.data.results_count;
    const minSample = source.data.min_sample;
    return {
      rows,
      sampleSize,
      minSample,
      empty: sampleSize === 0,
      insufficient: sampleSize > 0 && sampleSize < minSample,
    };
  }, [source]);

  const muted = derived.insufficient;
  const ariaLabel = derived.empty
    ? "Validation outcome distribution with no recorded sessions"
    : `Validation outcome distribution across ${derived.rows.length} categorical outcomes, n=${derived.sampleSize}`;

  return (
    <ChartFrame
      title="How do manual validation sessions actually end?"
      sourceLabel="GET /learning-analytics/summary · outcome_distribution"
      filtersSummary={filtersSummary}
      sampleSize={source?.available ? derived.sampleSize : null}
      sampleLabel="recorded outcomes"
      loading={loading}
      error={
        source && !source.available
          ? source.error ?? "Learning analytics summary unavailable"
          : null
      }
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="No validation sessions with recorded outcomes in this range"
      emptyDescription="Run and complete paper-validation sessions to populate categorical outcome counts."
      emptyAction={
        <Link
          href="/paper-validation/run-sessions"
          className="text-accent underline-offset-2 hover:underline"
          data-testid="validation-outcome-empty-sessions-link"
        >
          Open run sessions
        </Link>
      }
      insufficientSample={
        derived.insufficient
          ? { n: derived.sampleSize, min: derived.minSample }
          : null
      }
      derivedNote={NO_SERVER_FRESHNESS_TIMESTAMP_NOTE}
      limitations={
        derived.insufficient
          ? [`Insufficient sample (n=${derived.sampleSize} < ${derived.minSample})`]
          : []
      }
      data-testid="validation-outcome-chart"
    >
      <p
        className="text-caption text-text-muted"
        data-testid="validation-outcome-no-pnl-caption"
      >
        Categorical session outcomes — no P&L is recorded for manual validation sessions.
      </p>
      {derived.insufficient ? (
        <p
          className="text-sm text-text-muted"
          data-testid="validation-outcome-insufficient-banner"
          role="status"
        >
          Insufficient sample (n={derived.sampleSize} &lt; {derived.minSample}). Counts remain
          visible; strong conclusions are suppressed.
        </p>
      ) : null}
      <div
        role="img"
        aria-label={ariaLabel}
        className="h-[260px] w-full max-w-full overflow-x-auto"
        data-testid="validation-outcome-chart-plot"
      >
        <ResponsiveContainer width="100%" height="100%" minWidth={280}>
          <BarChart
            data={derived.rows}
            margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="var(--color-border-subtle)"
            />
            <XAxis
              dataKey="shortLabel"
              tick={{ fontSize: 11 }}
              interval={0}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 11 }}
              label={{ value: "Sessions", angle: -90, position: "insideLeft", fontSize: 11 }}
            />
            <Tooltip content={<OutcomeTooltip />} />
            <Bar dataKey="count" isAnimationActive={false} name="Sessions">
              {derived.rows.map((row) => (
                <Cell
                  key={row.outcome}
                  fill={muted ? "var(--color-text-muted)" : "var(--color-accent)"}
                  fillOpacity={muted ? 0.45 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul
        className="space-y-1 text-sm"
        data-testid="validation-outcome-list"
        aria-label="Validation outcome counts"
      >
        {derived.rows.map((row) => (
          <li
            key={row.outcome}
            className={muted ? "text-text-muted" : "text-text-secondary"}
            data-testid={`validation-outcome-row-${row.outcome}`}
          >
            <span className="font-medium text-text-primary">{row.label}</span>
            {": "}
            {row.count} sessions
            {!muted ? ` · ${formatPercent(row.rate)}` : ""}
          </li>
        ))}
      </ul>

      <table className="sr-only" data-testid="validation-outcome-a11y-table">
        <caption>Validation outcome categories, session counts, and rates</caption>
        <thead>
          <tr>
            <th>Category</th>
            <th>Count</th>
            <th>Rate</th>
          </tr>
        </thead>
        <tbody>
          {derived.rows.map((row) => (
            <tr key={row.outcome}>
              <td>{row.label}</td>
              <td>{row.count}</td>
              <td>{formatPercent(row.rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ChartFrame>
  );
}
