import { describe, expect, it } from "vitest";

import {
  buildAnalyticsApiParams,
  buildSetupAnalyticsApiParams,
  formatAppliedFiltersSummary,
  parseAnalyticsSearchParams,
} from "./filterValidation";

const SETUP_UUID = "11111111-1111-1111-1111-111111111111";
const STRATEGY_UUID = "22222222-2222-2222-2222-222222222222";

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

  it("accepts journal setup_id deep links only on Setups tab", () => {
    const setups = parseAnalyticsSearchParams(
      new URLSearchParams(`tab=setups&setup_id=${SETUP_UUID}&date_from=2026-01-01`),
    );
    expect(setups.tab).toBe("setups");
    expect(setups.setupId).toBe(SETUP_UUID);
    expect(setups.dateFrom).toBe("2026-01-01");

    const overview = parseAnalyticsSearchParams(
      new URLSearchParams(`setup_id=${SETUP_UUID}`),
    );
    expect(overview.setupId).toBeNull();
    expect(overview.ignoredParams).toContain("setup_id");
  });

  it("rejects non-UUID setup_id and portfolio_setup without coercing identities", () => {
    const state = parseAnalyticsSearchParams(
      new URLSearchParams(
        `tab=setups&setup_id=Breakout&portfolio_setup=${SETUP_UUID}&user_strategy_id=not-a-uuid`,
      ),
    );
    expect(state.setupId).toBeNull();
    expect(state.userStrategyId).toBeNull();
    expect(state.ignoredParams).toEqual(
      expect.arrayContaining(["setup_id", "portfolio_setup", "user_strategy_id"]),
    );
  });

  it("accepts setup grouping and bucket offset on Setups tab", () => {
    const state = parseAnalyticsSearchParams(
      new URLSearchParams("tab=setups&group_by=strategy&offset=20"),
    );
    expect(state.groupBy).toBe("strategy");
    expect(state.bucketOffset).toBe(20);
  });
});

describe("buildAnalyticsApiParams", () => {
  it("never sends ignored invalid values or setup_id to portfolio", () => {
    const params = buildAnalyticsApiParams({
      tab: "overview",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: "proposal_flow",
      setupId: SETUP_UUID,
      userStrategyId: STRATEGY_UUID,
      groupBy: "setup",
      bucketOffset: 0,
      ignoredParams: ["source"],
    });
    expect(params.portfolio.source).toBeUndefined();
    expect(params.journal.symbol).toBeUndefined();
    expect(params.journal.setup_id).toBeUndefined();
    expect((params.portfolio as { setup?: string }).setup).toBeUndefined();
  });
});

describe("buildSetupAnalyticsApiParams", () => {
  it("sends journal setup_id and never builds portfolio params", () => {
    const params = buildSetupAnalyticsApiParams({
      tab: "setups",
      dateFrom: "2026-01-01",
      dateTo: "2026-01-31",
      symbol: "BTCUSDT",
      timeframe: "1h",
      portfolioSource: null,
      setupId: SETUP_UUID,
      userStrategyId: STRATEGY_UUID,
      groupBy: "setup_version",
      bucketOffset: 40,
      ignoredParams: [],
    });
    expect(params.journal.group_by).toBe("setup_version");
    expect(params.journal.setup_id).toBe(SETUP_UUID);
    expect(params.journal.user_strategy_id).toBe(STRATEGY_UUID);
    expect(params.journal.limit).toBe(20);
    expect(params.journal.offset).toBe(40);
    expect(params.evidence.setup_id).toBe(SETUP_UUID);
    expect(params.evidence.strategy_id).toBe(STRATEGY_UUID);
    expect(params).not.toHaveProperty("portfolio");
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
      setupId: null,
      userStrategyId: null,
      groupBy: "setup",
      bucketOffset: 0,
      ignoredParams: [],
    });
    expect(summary).toContain("dates 2026-01-01 → 2026-01-31");
    expect(summary).toContain("symbol BTCUSDT");
    expect(summary).toContain("timeframe 1h");
    expect(summary).toContain("source proposal_flow");
  });

  it("includes journal setup identity on Setups tab", () => {
    const summary = formatAppliedFiltersSummary({
      tab: "setups",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: null,
      setupId: SETUP_UUID,
      userStrategyId: STRATEGY_UUID,
      groupBy: "setup",
      bucketOffset: 0,
      ignoredParams: [],
    });
    expect(summary).toContain(`setup_id ${SETUP_UUID}`);
    expect(summary).toContain(`strategy ${STRATEGY_UUID}`);
    expect(summary).toContain("group setup");
  });
});
