import { describe, expect, it } from "vitest";

import { buildAnalyticsApiParams } from "./useAnalyticsFilters";

describe("buildAnalyticsApiParams", () => {
  it("maps shared filters to journal and portfolio params", () => {
    const params = buildAnalyticsApiParams({
      tab: "overview",
      dateFrom: "2026-01-01",
      dateTo: "2026-01-31",
      symbol: "BTCUSDT",
      timeframe: "1h",
      portfolioSource: null,
      ignoredParams: [],
    });

    expect(params.journal.group_by).toBe("overall");
    expect(params.journal.symbol).toBe("BTCUSDT");
    expect(params.journal.timeframe).toBe("1h");
    expect(params.journal.date_from).toBe("2026-01-01T00:00:00.000Z");
    expect(params.journal.date_to).toBe("2026-01-31T23:59:59.999Z");
    expect(params.portfolio.start_date).toBe("2026-01-01");
    expect(params.portfolio.end_date).toBe("2026-01-31");
    expect(params.portfolio.source).toBeUndefined();
  });

  it("applies portfolio source only on performance tab", () => {
    const params = buildAnalyticsApiParams({
      tab: "performance",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: "proposal_flow",
      ignoredParams: [],
    });
    expect(params.portfolio.source).toBe("proposal_flow");
  });

  it("does not send portfolio source on overview tab", () => {
    const params = buildAnalyticsApiParams({
      tab: "overview",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: "proposal_flow",
      ignoredParams: [],
    });
    expect(params.portfolio.source).toBeUndefined();
  });
});
