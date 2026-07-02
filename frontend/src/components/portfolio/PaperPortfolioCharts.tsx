"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/states";
import type { DailyPortfolioPoint, DollarEquityPoint } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

type ChartPoint = {
  label: string;
  value: number;
  detail?: string;
};

function buildEquityPoints(curve: DollarEquityPoint[]): ChartPoint[] {
  return curve.map((point) => ({
    label: point.timestamp ? point.timestamp.slice(0, 10) : `#${point.index}`,
    value: Number(point.equity),
    detail: `Equity ${formatDecimal(point.equity)}`,
  }));
}

function buildDailyPoints(
  series: DailyPortfolioPoint[],
  field: "daily_pnl" | "daily_drawdown",
): ChartPoint[] {
  return series.map((point) => ({
    label: point.date,
    value: Number(point[field]),
    detail:
      field === "daily_pnl"
        ? `PnL ${formatDecimal(point.daily_pnl)}`
        : `Drawdown ${formatDecimal(point.daily_drawdown)}`,
  }));
}

function SimpleBarChart({
  points,
  testId,
  valueFormatter,
}: {
  points: ChartPoint[];
  testId: string;
  valueFormatter?: (value: number) => string;
}) {
  if (!points.length) {
    return (
      <EmptyState
        title="No chart data"
        description="Close paper trades or widen the date range to populate this chart."
      />
    );
  }

  const values = points.map((point) => point.value);
  const maxAbs = Math.max(...values.map((value) => Math.abs(value)), 1);

  return (
    <div className="space-y-2" data-testid={testId}>
      <div className="flex h-48 items-end gap-1 border-b border-zinc-800 pb-2">
        {points.map((point) => {
          const heightPct = Math.max(4, (Math.abs(point.value) / maxAbs) * 100);
          const positive = point.value >= 0;
          return (
            <div
              key={`${point.label}-${point.value}`}
              className="group flex min-w-0 flex-1 flex-col items-center justify-end gap-1"
              title={point.detail ?? point.label}
            >
              <div
                className={`w-full rounded-t ${positive ? "bg-emerald-500/70" : "bg-rose-500/70"}`}
                style={{ height: `${heightPct}%` }}
              />
              <span className="truncate text-[10px] text-zinc-500">{point.label.slice(5)}</span>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-zinc-500">
        Latest:{" "}
        {valueFormatter
          ? valueFormatter(points[points.length - 1]?.value ?? 0)
          : formatDecimal(String(points[points.length - 1]?.value ?? 0))}
      </p>
    </div>
  );
}

function EquityLineChart({ points, testId }: { points: ChartPoint[]; testId: string }) {
  if (!points.length) {
    return (
      <EmptyState
        title="No equity curve yet"
        description="Starting balance is shown once trades close in the selected range."
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
        aria-label="Equity curve chart"
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

export function PaperPortfolioCharts({
  equityCurve,
  dailySeries,
}: {
  equityCurve: DollarEquityPoint[];
  dailySeries: DailyPortfolioPoint[];
}) {
  const equityPoints = buildEquityPoints(equityCurve);
  const dailyPnlPoints = buildDailyPoints(dailySeries, "daily_pnl");
  const dailyDrawdownPoints = buildDailyPoints(dailySeries, "daily_drawdown");

  return (
    <section className="grid gap-4 lg:grid-cols-2" data-testid="paper-portfolio-charts">
      <Card data-testid="portfolio-equity-chart">
        <CardHeader>
          <CardTitle className="text-base">Equity curve</CardTitle>
        </CardHeader>
        <CardContent>
          <EquityLineChart points={equityPoints} testId="portfolio-equity-chart-canvas" />
        </CardContent>
      </Card>

      <Card data-testid="portfolio-daily-pnl-chart">
        <CardHeader>
          <CardTitle className="text-base">Daily PnL</CardTitle>
        </CardHeader>
        <CardContent>
          <SimpleBarChart points={dailyPnlPoints} testId="portfolio-daily-pnl-chart-canvas" />
        </CardContent>
      </Card>

      <Card className="lg:col-span-2" data-testid="portfolio-daily-drawdown-chart">
        <CardHeader>
          <CardTitle className="text-base">Daily drawdown</CardTitle>
        </CardHeader>
        <CardContent>
          <SimpleBarChart
            points={dailyDrawdownPoints}
            testId="portfolio-daily-drawdown-chart-canvas"
            valueFormatter={(value) => formatDecimal(String(Math.abs(value)))}
          />
        </CardContent>
      </Card>
    </section>
  );
}
