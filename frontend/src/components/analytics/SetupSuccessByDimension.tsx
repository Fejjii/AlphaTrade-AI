"use client";

import { useMemo } from "react";
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
import type { SetupPerformanceResponse } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import {
  VALIDATION_DIMENSION_OPTIONS,
  type ValidationDimension,
} from "./filterValidation";
import { formatPercent } from "./format";
import { NO_SERVER_FRESHNESS_TIMESTAMP_NOTE } from "./sourceFreshness";

const DIMENSION_LABELS: Record<ValidationDimension, string> = {
  condition: "Condition",
  timeframe: "Timeframe",
  symbol: "Symbol",
  direction: "Direction",
  confidence_bucket: "Confidence bucket",
};

type DimensionRow = {
  key: string;
  label: string;
  successRate: number | null;
  successRatePct: number | null;
  sampleSize: number;
  insufficient: boolean;
};

function DimensionTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as DimensionRow;
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-primary shadow-elevation2"
      data-testid="setup-success-dimension-tooltip"
    >
      <p className="mb-1 font-medium text-text-secondary">{row.label}</p>
      <p className="font-data">Success rate: {formatPercent(row.successRate)}</p>
      <p className="font-data">n={row.sampleSize}</p>
      {row.insufficient ? <p className="text-text-muted">Insufficient sample</p> : null}
    </div>
  );
}

export type SetupSuccessByDimensionProps = {
  source: SourceResult<SetupPerformanceResponse> | null;
  dimension: ValidationDimension;
  onDimensionChange: (dimension: ValidationDimension) => void;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
};

export function SetupSuccessByDimension({
  source,
  dimension,
  onDimensionChange,
  loading = false,
  onRetry,
  filtersSummary,
}: SetupSuccessByDimensionProps) {
  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: [] as DimensionRow[],
        empty: true,
        minSample: 5,
        groupCount: 0,
      };
    }
    const rows: DimensionRow[] = (source.data.groups ?? []).map((group) => ({
      key: group.dimension_value,
      label: group.dimension_value || "(empty)",
      successRate: group.success_rate ?? null,
      successRatePct:
        group.success_rate === null || group.success_rate === undefined
          ? null
          : group.success_rate * 100,
      sampleSize: group.sample_size,
      insufficient: group.insufficient_data,
    }));
    return {
      rows,
      empty: rows.length === 0,
      minSample: source.data.min_sample,
      groupCount: rows.length,
    };
  }, [source]);

  const chartHeight = Math.max(220, derived.rows.length * 36 + 40);
  const ariaLabel = `Setup success rate by ${DIMENSION_LABELS[dimension]}, ${derived.rows.length} groups`;

  return (
    <ChartFrame
      title="Setup success rate by dimension"
      sourceLabel="GET /learning-analytics/setup-performance"
      filtersSummary={filtersSummary}
      sampleSize={source?.available ? derived.groupCount : null}
      sampleLabel="groups"
      loading={loading}
      error={
        source && !source.available
          ? source.error ?? "Setup performance unavailable"
          : null
      }
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="No setup-performance groups in this range"
      emptyDescription="Complete validation sessions so detector-condition groups can be ranked by categorical success rate."
      derivedNote={NO_SERVER_FRESHNESS_TIMESTAMP_NOTE}
      data-testid="setup-success-by-dimension"
    >
      <div
        role="radiogroup"
        aria-label="Validation setup-performance dimension"
        className="flex flex-wrap gap-2"
        data-testid="validation-dimension-toggle"
      >
        {VALIDATION_DIMENSION_OPTIONS.map((option) => {
          const selected = option === dimension;
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={selected}
              data-testid={`validation-dimension-${option}`}
              className={
                selected
                  ? "rounded-control border border-accent bg-accent/15 px-3 py-1.5 text-sm text-text-primary"
                  : "rounded-control border border-border-subtle bg-surface-0 px-3 py-1.5 text-sm text-text-secondary hover:border-border-strong"
              }
              onClick={() => onDimensionChange(option)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onDimensionChange(option);
                }
              }}
            >
              {DIMENSION_LABELS[option]}
            </button>
          );
        })}
      </div>

      <p
        className="text-caption text-text-muted"
        data-testid="setup-success-no-pnl-caption"
      >
        Categorical session outcomes — no P&L is recorded for manual validation sessions.
      </p>

      <div
        role="img"
        aria-label={ariaLabel}
        className="w-full max-w-full overflow-x-auto"
        style={{ height: chartHeight }}
        data-testid="setup-success-by-dimension-plot"
      >
        <ResponsiveContainer width="100%" height="100%" minWidth={280}>
          <BarChart
            data={derived.rows}
            layout="vertical"
            margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              horizontal={false}
              stroke="var(--color-border-subtle)"
            />
            <XAxis
              type="number"
              domain={[0, 100]}
              tick={{ fontSize: 11 }}
              tickFormatter={(value: number) => `${value.toFixed(0)}%`}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={120}
              tick={{ fontSize: 11 }}
              interval={0}
            />
            <Tooltip content={<DimensionTooltip />} />
            <Bar dataKey="successRatePct" isAnimationActive={false} name="Success rate">
              {derived.rows.map((row) => (
                <Cell
                  key={row.key}
                  fill={
                    row.insufficient || row.successRatePct === null
                      ? "var(--color-text-muted)"
                      : "var(--color-accent)"
                  }
                  fillOpacity={row.insufficient || row.successRatePct === null ? 0.45 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul
        className="space-y-1 text-sm"
        data-testid="setup-success-by-dimension-list"
        aria-label={`Success rate by ${DIMENSION_LABELS[dimension]}`}
      >
        {derived.rows.map((row) => (
          <li
            key={row.key}
            className={row.insufficient ? "text-text-muted" : "text-text-secondary"}
            data-testid={`setup-success-row-${row.key}`}
          >
            <span className="font-medium text-text-primary">{row.label}</span>
            {": "}
            {formatPercent(row.successRate)} · n={row.sampleSize}
            {row.insufficient ? " — insufficient" : ""}
          </li>
        ))}
      </ul>

      <table className="sr-only" data-testid="setup-success-by-dimension-a11y-table">
        <caption>
          Setup success rate by {DIMENSION_LABELS[dimension]} (categorical session outcomes)
        </caption>
        <thead>
          <tr>
            <th>Dimension value</th>
            <th>Success rate</th>
            <th>Sample size</th>
            <th>Insufficient</th>
          </tr>
        </thead>
        <tbody>
          {derived.rows.map((row) => (
            <tr key={row.key}>
              <td>{row.label}</td>
              <td>{formatPercent(row.successRate)}</td>
              <td>{row.sampleSize}</td>
              <td>{row.insufficient ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ChartFrame>
  );
}
