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

/** Non-colour indication of sign, so meaning survives without hue (WCAG 1.4.1). */
function signMarker(value: number): string {
  if (value > 0) return "▲";
  if (value < 0) return "▼";
  return "–";
}

function signWord(value: number): string {
  if (value > 0) return "gain";
  if (value < 0) return "loss";
  return "flat";
}

/**
 * Screen-reader alternative to a graphic. The same numbers the bars encode,
 * in a real table, so the chart is never the only way to read the data.
 */
function ChartDataTable({
  caption,
  valueHeader,
  points,
  testId,
  withSign,
}: {
  caption: string;
  valueHeader: string;
  points: ChartPoint[];
  testId: string;
  withSign?: boolean;
}) {
  return (
    <table className="sr-only" data-testid={testId}>
      <caption>{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Period</th>
          <th scope="col">{valueHeader}</th>
          {withSign ? <th scope="col">Direction</th> : null}
        </tr>
      </thead>
      <tbody>
        {points.map((point) => (
          <tr key={`${point.label}-${point.value}`}>
            <th scope="row">{point.label}</th>
            <td>{formatDecimal(String(point.value))}</td>
            {withSign ? <td>{signWord(point.value)}</td> : null}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SimpleBarChart({
  points,
  testId,
  accessibleName,
  tableCaption,
  valueHeader,
  valueFormatter,
}: {
  points: ChartPoint[];
  testId: string;
  accessibleName: string;
  tableCaption: string;
  valueHeader: string;
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
      <div
        role="img"
        aria-label={`${accessibleName}. ${points.length} point${points.length === 1 ? "" : "s"}. The following table lists the same values.`}
        className="flex h-48 items-end gap-1 border-b border-border-subtle pb-2"
      >
        {points.map((point) => {
          const heightPct = Math.max(4, (Math.abs(point.value) / maxAbs) * 100);
          const positive = point.value >= 0;
          return (
            <div
              key={`${point.label}-${point.value}`}
              className="group flex min-w-0 flex-1 flex-col items-center justify-end gap-1"
              title={point.detail ?? point.label}
            >
              <span
                aria-hidden="true"
                className={`text-[10px] leading-none ${positive ? "text-success" : "text-danger"}`}
              >
                {signMarker(point.value)}
              </span>
              <div
                className={`w-full rounded-t ${positive ? "bg-success/70" : "bg-danger/70"}`}
                style={{ height: `${heightPct}%` }}
              />
              <span className="truncate text-[10px] text-text-muted">{point.label.slice(5)}</span>
            </div>
          );
        })}
      </div>
      <ChartDataTable
        caption={tableCaption}
        valueHeader={valueHeader}
        points={points}
        testId={`${testId}-table`}
        withSign
      />
      <p className="text-xs text-text-muted">
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
  const first = points[0]?.value ?? 0;
  const last = points[points.length - 1]?.value ?? 0;
  const direction = signWord(last - first);

  return (
    <div data-testid={testId}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-48 w-full rounded border border-border-subtle bg-surface-0/40"
        role="img"
        aria-label={`Simulated equity curve, ${points.length} point${points.length === 1 ? "" : "s"} from ${points[0]?.label} to ${points[points.length - 1]?.label}, ranging ${formatDecimal(String(min))} to ${formatDecimal(String(max))}, overall ${direction}. The following table lists the same values.`}
      >
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-accent"
          points={polyline}
        />
        {coords.map(({ x, y, point }) => (
          <circle key={point.label} cx={x} cy={y} r="3" className="fill-accent" />
        ))}
      </svg>
      <ChartDataTable
        caption="Simulated equity by point in the selected range"
        valueHeader="Equity"
        points={points}
        testId={`${testId}-table`}
      />
      <p className="mt-2 text-xs text-text-muted">
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
          <SimpleBarChart
            points={dailyPnlPoints}
            testId="portfolio-daily-pnl-chart-canvas"
            accessibleName="Daily simulated profit and loss"
            tableCaption="Daily simulated profit and loss by date"
            valueHeader="Daily P&L"
          />
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
            accessibleName="Daily simulated drawdown"
            tableCaption="Daily simulated drawdown by date"
            valueHeader="Daily drawdown"
            valueFormatter={(value) => formatDecimal(String(Math.abs(value)))}
          />
        </CardContent>
      </Card>
    </section>
  );
}
