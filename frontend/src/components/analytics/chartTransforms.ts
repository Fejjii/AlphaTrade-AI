import type { DailyPortfolioPoint, DollarEquityPoint } from "@/lib/api/types";

import { parseDecimal } from "./format";

export const MAX_DAILY_BARS = 180;
export const MAX_CUMULATIVE_POINTS = 500;
export const INITIAL_VISIBLE_BARS = 30;
export const BAR_WIDTH_PX = 12;

export type DailyPnlRow = {
  key: string;
  label: string;
  dailyPnl: number | null;
  tradesClosed: number;
  endingEquity: number | null;
  invalidMonetary: boolean;
};

export type DailyPnlTransformResult = {
  rows: DailyPnlRow[];
  weekly: boolean;
  invalidMonetaryCount: number;
  malformed: boolean;
};

export type CumulativePnlRow = {
  index: number;
  label: string;
  cumulativePnl: number | null;
  hasTimestamp: boolean;
  invalidMonetary: boolean;
};

export type CumulativePnlTransformResult = {
  rows: CumulativePnlRow[];
  filteredPointCount: number;
  excludedLiveCount: number;
  missingTimestamps: number;
  decimated: boolean;
  invalidMonetaryCount: number;
  malformed: boolean;
};

/** ISO-8601 week key (year-Www) using UTC week boundaries. */
export function isoWeekKey(dateStr: string): string {
  const date = new Date(`${dateStr}T00:00:00.000Z`);
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const isoYear = date.getUTCFullYear();
  const yearStart = new Date(Date.UTC(isoYear, 0, 1));
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7);
  return `${isoYear}-W${String(week).padStart(2, "0")}`;
}

function parseDailyPoint(point: DailyPortfolioPoint): {
  dailyPnl: number | null;
  endingEquity: number | null;
  invalidMonetary: boolean;
} {
  const dailyPnl = parseDecimal(point.daily_pnl);
  const endingEquity = parseDecimal(point.ending_equity);
  const invalidMonetary =
    (point.daily_pnl != null && point.daily_pnl !== "" && dailyPnl === null) ||
    (point.ending_equity != null && point.ending_equity !== "" && endingEquity === null);
  return { dailyPnl, endingEquity, invalidMonetary };
}

export function buildDailyPnlRows(series: DailyPortfolioPoint[]): DailyPnlTransformResult {
  let invalidMonetaryCount = 0;

  const parsedSeries = series.map((point) => {
    const parsed = parseDailyPoint(point);
    if (parsed.invalidMonetary) invalidMonetaryCount += 1;
    return { point, parsed };
  });

  const dailyRows: DailyPnlRow[] = parsedSeries.map(({ point, parsed }) => ({
    key: point.date,
    label: point.date,
    dailyPnl: parsed.dailyPnl,
    tradesClosed: point.trades_closed,
    endingEquity: parsed.endingEquity,
    invalidMonetary: parsed.invalidMonetary,
  }));

  if (series.length <= MAX_DAILY_BARS) {
    return {
      rows: dailyRows,
      weekly: false,
      invalidMonetaryCount,
      malformed: invalidMonetaryCount > 0,
    };
  }

  const buckets = new Map<string, DailyPnlRow>();
  for (const { point, parsed } of parsedSeries) {
    const week = isoWeekKey(point.date);

    const existing = buckets.get(week);
    if (!existing) {
      buckets.set(week, {
        key: week,
        label: week,
        dailyPnl: parsed.dailyPnl,
        tradesClosed: point.trades_closed,
        endingEquity: parsed.endingEquity,
        invalidMonetary: parsed.invalidMonetary,
      });
      continue;
    }

    if (parsed.dailyPnl != null) {
      existing.dailyPnl = (existing.dailyPnl ?? 0) + parsed.dailyPnl;
    } else if (parsed.invalidMonetary) {
      existing.invalidMonetary = true;
    }
    existing.tradesClosed += point.trades_closed;
    if (parsed.endingEquity != null) existing.endingEquity = parsed.endingEquity;
    if (parsed.invalidMonetary) existing.invalidMonetary = true;
  }

  return {
    rows: [...buckets.values()].sort((a, b) => a.key.localeCompare(b.key)),
    weekly: true,
    invalidMonetaryCount,
    malformed: invalidMonetaryCount > 0,
  };
}

function decimateTradeClosePoints(points: DollarEquityPoint[]): DollarEquityPoint[] {
  if (points.length <= MAX_CUMULATIVE_POINTS) return points;

  const keep = new Set<number>([0, points.length - 1]);
  const step = Math.ceil(points.length / (MAX_CUMULATIVE_POINTS - 2));
  for (let index = 0; index < points.length; index += step) keep.add(index);

  let maxIndex = 0;
  let minIndex = 0;
  let maxVal = Number.NEGATIVE_INFINITY;
  let minVal = Number.POSITIVE_INFINITY;

  points.forEach((point, index) => {
    const value = parseDecimal(point.cumulative_realized_pnl);
    if (value === null) return;
    if (value > maxVal) {
      maxVal = value;
      maxIndex = index;
    }
    if (value < minVal) {
      minVal = value;
      minIndex = index;
    }
  });
  keep.add(maxIndex);
  keep.add(minIndex);

  return [...keep]
    .sort((a, b) => a - b)
    .map((index) => points[index]);
}

export function buildCumulativePnlRows(
  equityCurve: DollarEquityPoint[],
): CumulativePnlTransformResult {
  const excludedLiveCount = equityCurve.filter((point) => point.event === "live").length;
  const tradeClosePoints = equityCurve.filter((point) => point.event === "trade_close");

  let invalidMonetaryCount = 0;
  const parsedPoints = tradeClosePoints.map((point) => {
    const cumulativePnl = parseDecimal(point.cumulative_realized_pnl);
    const invalidMonetary =
      point.cumulative_realized_pnl != null &&
      point.cumulative_realized_pnl !== "" &&
      cumulativePnl === null;
    if (invalidMonetary) invalidMonetaryCount += 1;
    return { point, cumulativePnl, invalidMonetary };
  });

  const missingTimestamps = tradeClosePoints.filter((point) => !point.timestamp).length;
  const validForPlot = parsedPoints.filter((item) => !item.invalidMonetary);
  const decimatedSource = decimateTradeClosePoints(validForPlot.map((item) => item.point));

  const rows: CumulativePnlRow[] = decimatedSource.map((point) => ({
    index: point.index,
    label: point.timestamp ? point.timestamp.slice(0, 10) : `#${point.index}`,
    cumulativePnl: parseDecimal(point.cumulative_realized_pnl),
    hasTimestamp: Boolean(point.timestamp),
    invalidMonetary: false,
  }));

  return {
    rows,
    filteredPointCount: tradeClosePoints.length,
    excludedLiveCount,
    missingTimestamps,
    decimated: decimatedSource.length < validForPlot.length,
    invalidMonetaryCount,
    malformed: invalidMonetaryCount > 0,
  };
}

/** Plottable daily rows exclude invalid monetary values (never coerced to zero). */
export function plottableDailyRows(rows: DailyPnlRow[]): Array<DailyPnlRow & { dailyPnl: number }> {
  return rows.filter(
    (row): row is DailyPnlRow & { dailyPnl: number } =>
      row.dailyPnl !== null && !row.invalidMonetary,
  );
}

/** Plottable cumulative rows exclude invalid monetary values. */
export function plottableCumulativeRows(
  rows: CumulativePnlRow[],
): Array<CumulativePnlRow & { cumulativePnl: number }> {
  return rows.filter(
    (row): row is CumulativePnlRow & { cumulativePnl: number } =>
      row.cumulativePnl !== null && !row.invalidMonetary,
  );
}
