import { describe, expect, it } from "vitest";

import type { DailyPortfolioPoint, DollarEquityPoint } from "@/lib/api/types";

import {
  MAX_DAILY_BARS,
  buildCumulativePnlRows,
  buildDailyPnlRows,
  isoWeekKey,
  plottableDailyRows,
} from "./chartTransforms";

function dailyPoint(date: string, pnl: string, trades = 1): DailyPortfolioPoint {
  return {
    date,
    starting_equity: "10000",
    ending_equity: "10100",
    daily_pnl: pnl,
    daily_drawdown: "0",
    daily_drawdown_pct: 0,
    trades_closed: trades,
  };
}

describe("isoWeekKey", () => {
  it("groups days within the same ISO week", () => {
    expect(isoWeekKey("2026-01-05")).toBe("2026-W02");
    expect(isoWeekKey("2026-01-11")).toBe("2026-W02");
  });

  it("keeps distinct weeks across month boundaries", () => {
    expect(isoWeekKey("2026-01-28")).not.toBe(isoWeekKey("2026-02-03"));
  });
});

describe("buildDailyPnlRows", () => {
  it("rolls up more than 180 daily points by ISO week", () => {
    const series = Array.from({ length: MAX_DAILY_BARS + 1 }, (_, index) =>
      dailyPoint(`2026-01-${String((index % 28) + 1).padStart(2, "0")}`, "10"),
    );
    const result = buildDailyPnlRows(series);
    expect(result.weekly).toBe(true);
    expect(result.rows.length).toBeLessThan(series.length);
    expect(result.rows[0]?.label).toMatch(/^\d{4}-W\d{2}$/);
  });

  it("does not coerce invalid monetary values to zero", () => {
    const result = buildDailyPnlRows([
      dailyPoint("2026-01-01", "not-a-number"),
      dailyPoint("2026-01-02", "25"),
    ]);
    expect(result.malformed).toBe(true);
    expect(plottableDailyRows(result.rows)).toHaveLength(1);
    expect(result.rows[0]?.dailyPnl).toBeNull();
  });

  it("counts malformed monetary values once when rolling up long series", () => {
    const series = Array.from({ length: MAX_DAILY_BARS + 1 }, (_, index) => {
      const day = String((index % 28) + 1).padStart(2, "0");
      const pnl = index === 3 || index === 47 ? "not-a-number" : "10";
      return dailyPoint(`2026-01-${day}`, pnl);
    });

    const result = buildDailyPnlRows(series);

    expect(result.weekly).toBe(true);
    expect(result.invalidMonetaryCount).toBe(2);
    expect(result.malformed).toBe(true);
  });
});

describe("buildCumulativePnlRows", () => {
  it("uses trade_close events only and excludes live points", () => {
    const curve: DollarEquityPoint[] = [
      {
        index: 0,
        timestamp: "2026-01-01T00:00:00Z",
        equity: "10000",
        cumulative_realized_pnl: "0",
        unrealized_pnl: "0",
        event: "start",
      },
      {
        index: 1,
        timestamp: "2026-01-02T00:00:00Z",
        equity: "10050",
        cumulative_realized_pnl: "50",
        unrealized_pnl: "0",
        event: "trade_close",
      },
      {
        index: 2,
        timestamp: "2026-01-03T00:00:00Z",
        equity: "10075",
        cumulative_realized_pnl: "75",
        unrealized_pnl: "5",
        event: "live",
      },
    ];
    const result = buildCumulativePnlRows(curve);
    expect(result.filteredPointCount).toBe(1);
    expect(result.excludedLiveCount).toBe(1);
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0]?.cumulativePnl).toBe(50);
  });

  it("reports pre-decimation filtered count in decimation metadata", () => {
    const curve: DollarEquityPoint[] = Array.from({ length: 600 }, (_, index) => ({
      index,
      timestamp: `2026-01-01T${String(index % 24).padStart(2, "0")}:00:00Z`,
      equity: "10000",
      cumulative_realized_pnl: String(index),
      unrealized_pnl: "0",
      event: "trade_close" as const,
    }));
    const result = buildCumulativePnlRows(curve);
    expect(result.filteredPointCount).toBe(600);
    expect(result.decimated).toBe(true);
    expect(result.rows.length).toBeLessThan(600);
  });

  it("excludes invalid cumulative P&L values instead of plotting zero", () => {
    const result = buildCumulativePnlRows([
      {
        index: 1,
        timestamp: "2026-01-02T00:00:00Z",
        equity: "10000",
        cumulative_realized_pnl: "bad",
        unrealized_pnl: "0",
        event: "trade_close",
      },
    ]);
    expect(result.malformed).toBe(true);
    expect(result.rows).toHaveLength(0);
  });
});
