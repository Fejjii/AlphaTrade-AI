import { describe, expect, it } from "vitest";

import {
  buildAnalyticsApiParams,
  formatAppliedFiltersSummary,
  parseAnalyticsSearchParams,
} from "./filterValidation";

describe("parseAnalyticsSearchParams", () => {
  it("rejects invalid ISO dates and reversed ranges", () => {
    const invalidFrom = parseAnalyticsSearchParams(
      new URLSearchParams("date_from=2026-13-40&date_to=2026-01-31"),
    );
    expect(invalidFrom.dateFrom).toBeNull();
    expect(invalidFrom.dateTo).toBe("2026-01-31");
    expect(invalidFrom.ignoredParams).toContain("date_from");

    const reversed = parseAnalyticsSearchParams(
      new URLSearchParams("date_from=2026-02-01&date_to=2026-01-01"),
    );
    expect(reversed.dateFrom).toBeNull();
    expect(reversed.dateTo).toBeNull();
    expect(reversed.ignoredParams).toEqual(expect.arrayContaining(["date_from", "date_to"]));
  });

  it("rejects overlong symbol and timeframe values", () => {
    const state = parseAnalyticsSearchParams(
      new URLSearchParams(`symbol=${"A".repeat(31)}&timeframe=${"x".repeat(9)}`),
    );
    expect(state.symbol).toBeNull();
    expect(state.timeframe).toBeNull();
    expect(state.ignoredParams).toEqual(expect.arrayContaining(["symbol", "timeframe"]));
  });

  it("ignores portfolio source outside Performance tab", () => {
    const state = parseAnalyticsSearchParams(
      new URLSearchParams("source=proposal_flow"),
    );
    expect(state.portfolioSource).toBeNull();
    expect(state.ignoredParams).toContain("source");
  });

  it("accepts portfolio source on Performance tab", () => {
    const state = parseAnalyticsSearchParams(
      new URLSearchParams("tab=performance&source=proposal_flow"),
    );
    expect(state.tab).toBe("performance");
    expect(state.portfolioSource).toBe("proposal_flow");
  });
});

describe("buildAnalyticsApiParams", () => {
  it("never sends ignored invalid values to APIs", () => {
    const params = buildAnalyticsApiParams({
      tab: "overview",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: "proposal_flow",
      ignoredParams: ["source"],
    });
    expect(params.portfolio.source).toBeUndefined();
    expect(params.journal.symbol).toBeUndefined();
  });
});

describe("formatAppliedFiltersSummary", () => {
  it("includes all active filters in provenance text", () => {
    const summary = formatAppliedFiltersSummary({
      tab: "performance",
      dateFrom: "2026-01-01",
      dateTo: "2026-01-31",
      symbol: "BTCUSDT",
      timeframe: "1h",
      portfolioSource: "proposal_flow",
      ignoredParams: [],
    });
    expect(summary).toContain("dates 2026-01-01 → 2026-01-31");
    expect(summary).toContain("symbol BTCUSDT");
    expect(summary).toContain("timeframe 1h");
    expect(summary).toContain("source proposal_flow");
  });
});
