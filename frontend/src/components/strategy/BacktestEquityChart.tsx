"use client";

import { EmptyState } from "@/components/states";
import type { EquityCurvePoint } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

type ChartPoint = {
  label: string;
  value: number;
};

function buildPoints(curve: EquityCurvePoint[]): ChartPoint[] {
  return curve.map((point) => ({
    label: point.timestamp.slice(0, 10),
    value: Number(point.equity),
  }));
}

export function BacktestEquityChart({
  curve,
  testId = "backtest-equity-chart",
}: {
  curve: EquityCurvePoint[];
  testId?: string;
}) {
  const points = buildPoints(curve);

  if (!points.length) {
    return (
      <EmptyState
        title="No equity curve"
        description="Equity points appear once the backtest completes with trades."
      />
    );
  }

  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const width = 640;
  const height = 180;
  const padding = 12;

  const coords = points.map((point, index) => {
    const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - ((point.value - min) / span) * (height - padding * 2);
    return { x, y, point };
  });

  const polyline = coords.map(({ x, y }) => `${x},${y}`).join(" ");

  return (
    <div data-testid={testId}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-48 w-full rounded border border-zinc-800 bg-zinc-950/40"
        role="img"
        aria-label="Backtest equity curve"
      >
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-sky-400"
          points={polyline}
        />
        {coords.map(({ x, y, point }) => (
          <circle key={point.label} cx={x} cy={y} r="3" className="fill-sky-300" />
        ))}
      </svg>
      <p className="mt-2 text-xs text-zinc-500">
        Range {formatDecimal(String(min))} – {formatDecimal(String(max))} · {points.length} point
        {points.length === 1 ? "" : "s"}
      </p>
    </div>
  );
}
