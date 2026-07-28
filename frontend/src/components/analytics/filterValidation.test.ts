import { describe, expect, it } from "vitest";

import {
  buildAnalyticsApiParams,
  buildAnalyticsWindowFilterKey,
  buildLearningWindowFilterKey,
  buildRuleComplianceFilterKey,
  buildSetupAnalyticsApiParams,
  formatAnalyticsWindowFiltersSummary,
  formatAppliedFiltersSummary,
  formatJournalStatsFiltersSummary,
  formatLearningAnalyticsFiltersSummary,
  formatSetupEvidenceFiltersSummary,
  formatSetupEvidenceLimitationNote,
  parseAnalyticsSearchParams,
} from "./filterValidation";

const SETUP_UUID = "11111111-1111-1111-1111-111111111111";
const STRATEGY_UUID = "22222222-2222-2222-2222-222222222222";

const EMPTY_SCOPED = {
  setupId: null,
  userStrategyId: null,
  strategyVersionId: null,
  journalSource: null,
  ruleCompliance: null,
  marketRegime: null,
  groupBy: "setup" as const,
  bucketOffset: 0,
};

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
    expect(state.journalSource).toBeNull();
    expect(state.ignoredParams).toContain("source");
  });

  it("accepts portfolio source on Performance tab", () => {
    const state = parseAnalyticsSearchParams(
      new URLSearchParams("tab=performance&source=proposal_flow"),
    );
    expect(state.tab).toBe("performance");
    expect(state.portfolioSource).toBe("proposal_flow");
    expect(state.journalSource).toBeNull();
  });

  it("accepts journal trade source on Setups tab and rejects portfolio values", () => {
    const valid = parseAnalyticsSearchParams(
      new URLSearchParams("tab=setups&source=manual"),
    );
    expect(valid.journalSource).toBe("manual");
    expect(valid.portfolioSource).toBeNull();
    expect(valid.ignoredParams).not.toContain("source");

    const invalid = parseAnalyticsSearchParams(
      new URLSearchParams("tab=setups&source=proposal_flow"),
    );
    expect(invalid.journalSource).toBeNull();
    expect(invalid.ignoredParams).toContain("source");
  });

  it("rejects journal trade source on Performance tab", () => {
    const state = parseAnalyticsSearchParams(
      new URLSearchParams("tab=performance&source=manual"),
    );
    expect(state.portfolioSource).toBeNull();
    expect(state.journalSource).toBeNull();
    expect(state.ignoredParams).toContain("source");
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

  it("accepts behaviour and comparison tabs", () => {
    expect(parseAnalyticsSearchParams(new URLSearchParams("tab=behaviour")).tab).toBe(
      "behaviour",
    );
    expect(parseAnalyticsSearchParams(new URLSearchParams("tab=comparison")).tab).toBe(
      "comparison",
    );
  });

  it("accepts journal setup_id UUID only on behaviour/comparison", () => {
    const uuid = "11111111-2222-4333-8444-555555555555";
    const ignored = parseAnalyticsSearchParams(new URLSearchParams(`setup_id=${uuid}`));
    expect(ignored.setupId).toBeNull();
    expect(ignored.ignoredParams).toContain("setup_id");

    const behaviour = parseAnalyticsSearchParams(
      new URLSearchParams(`tab=behaviour&setup_id=${uuid}`),
    );
    expect(behaviour.setupId).toBe(uuid);
    expect(behaviour.ignoredParams).not.toContain("setup_id");
  });

  it("accepts journal source and rule_compliance on behaviour", () => {
    const state = parseAnalyticsSearchParams(
      new URLSearchParams(
        "tab=behaviour&source=manual&rule_compliance=unassessed",
      ),
    );
    expect(state.journalSource).toBe("manual");
    expect(state.ruleCompliance).toBe("unassessed");
    expect(state.portfolioSource).toBeNull();
  });

  it("never treats setup_id as a portfolio setup identity", () => {
    const state = parseAnalyticsSearchParams(
      new URLSearchParams(
        "tab=behaviour&setup_id=11111111-2222-4333-8444-555555555555&portfolio_setup=trend_pullback",
      ),
    );
    expect(state.setupId).toBe("11111111-2222-4333-8444-555555555555");
    expect(state.ignoredParams).toContain("portfolio_setup");
    const params = buildAnalyticsApiParams(state);
    expect(params.portfolio.setup).toBeUndefined();
    expect(params.ruleComplianceJournal.setup_id).toBe(
      "11111111-2222-4333-8444-555555555555",
    );
    expect(params.comparison.setup_id).toBe("11111111-2222-4333-8444-555555555555");
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
      ...EMPTY_SCOPED,
      ignoredParams: ["source"],
    });
    expect(params.portfolio.source).toBeUndefined();
    expect(params.journal.symbol).toBeUndefined();
    expect(params.journal.setup_id).toBeUndefined();
    expect((params.portfolio as { setup?: string }).setup).toBeUndefined();
  });

  it("maps UserStrategy identity to user_strategy_id for journal stats, not strategy_id", () => {
    const params = buildSetupAnalyticsApiParams({
      tab: "setups",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: null,
      journalSource: null,
      setupId: null,
      userStrategyId: STRATEGY_UUID,
      strategyVersionId: null,
      ruleCompliance: null,
      marketRegime: null,
      groupBy: "setup",
      bucketOffset: 0,
      ignoredParams: [],
    });
    expect(params.journal.user_strategy_id).toBe(STRATEGY_UUID);
    expect(params.journal).not.toHaveProperty("strategy_id");
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
      journalSource: null,
      setupId: SETUP_UUID,
      userStrategyId: STRATEGY_UUID,
      strategyVersionId: null,
      ruleCompliance: null,
      marketRegime: null,
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

  it("builds rule_compliance and comparison params for behaviour/comparison", () => {
    const behaviour = buildAnalyticsApiParams({
      tab: "behaviour",
      dateFrom: "2026-01-01",
      dateTo: "2026-01-31",
      symbol: "BTCUSDT",
      timeframe: "1h",
      portfolioSource: null,
      setupId: "11111111-2222-4333-8444-555555555555",
      userStrategyId: null,
      strategyVersionId: null,
      journalSource: "manual",
      ruleCompliance: "partial",
      marketRegime: null,
      groupBy: "setup",
      bucketOffset: 0,
      ignoredParams: [],
    });
    expect(behaviour.ruleComplianceJournal.group_by).toBe("rule_compliance");
    expect(behaviour.ruleComplianceJournal.setup_id).toBe(
      "11111111-2222-4333-8444-555555555555",
    );
    expect(behaviour.ruleComplianceJournal.rule_compliance).toBe("partial");
    expect(behaviour.analyticsWindow).toEqual({
      start_date: "2026-01-01",
      end_date: "2026-01-31",
    });
    expect(behaviour.portfolio.setup).toBeUndefined();
  });
});

describe("behaviour source filter keys", () => {
  it("builds independent keys per endpoint parameter set", () => {
    const journalParams = {
      group_by: "rule_compliance" as const,
      limit: 20,
      symbol: "BTCUSDT",
    };
    const analyticsWindow = { start_date: "2026-01-01", end_date: "2026-01-31" };
    const learningWindow = { start_date: "2026-02-01" };

    expect(buildRuleComplianceFilterKey(journalParams)).not.toBe(
      buildAnalyticsWindowFilterKey(analyticsWindow),
    );
    expect(buildAnalyticsWindowFilterKey(analyticsWindow)).not.toBe(
      buildLearningWindowFilterKey(learningWindow),
    );
  });
});

describe("endpoint-specific provenance summaries", () => {
  it("formatJournalStatsFiltersSummary reflects only journal statistics params", () => {
    const summary = formatJournalStatsFiltersSummary({
      group_by: "rule_compliance",
      date_from: "2026-01-01T00:00:00Z",
      date_to: "2026-01-31T23:59:59Z",
      symbol: "BTCUSDT",
      setup_id: SETUP_UUID,
      user_strategy_id: STRATEGY_UUID,
      rule_compliance: "partial",
    });
    expect(summary).toContain("dates 2026-01-01 → 2026-01-31");
    expect(summary).toContain("symbol BTCUSDT");
    expect(summary).toContain(`user_strategy_id ${STRATEGY_UUID}`);
    expect(summary).not.toMatch(/\bstrategy_id\b/);
  });

  it("formatAnalyticsWindowFiltersSummary shows dates only", () => {
    const summary = formatAnalyticsWindowFiltersSummary({
      start_date: "2026-01-01",
      end_date: "2026-01-31",
    });
    expect(summary).toBe("dates 2026-01-01 → 2026-01-31");
    expect(summary).not.toContain("symbol");
    expect(summary).not.toContain("setup");
  });

  it("formatLearningAnalyticsFiltersSummary shows dates only", () => {
    const summary = formatLearningAnalyticsFiltersSummary({
      start_date: "2026-02-01",
    });
    expect(summary).toBe("from 2026-02-01");
    expect(summary).not.toContain("symbol");
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
      ...EMPTY_SCOPED,
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
      journalSource: null,
      setupId: SETUP_UUID,
      userStrategyId: STRATEGY_UUID,
      strategyVersionId: null,
      ruleCompliance: null,
      marketRegime: null,
      groupBy: "setup",
      bucketOffset: 0,
      ignoredParams: [],
    });
    expect(summary).toContain(`setup_id ${SETUP_UUID}`);
    expect(summary).toContain(`user_strategy_id ${STRATEGY_UUID}`);
    expect(summary).toContain("group setup");
  });

  it("includes journal trade source in provenance text on Setups tab", () => {
    const summary = formatAppliedFiltersSummary({
      tab: "setups",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: null,
      journalSource: "paper_execution",
      setupId: null,
      userStrategyId: null,
      strategyVersionId: null,
      ruleCompliance: null,
      marketRegime: null,
      groupBy: "strategy",
      bucketOffset: 0,
      ignoredParams: [],
    });
    expect(summary).toContain("source paper_execution");
    expect(summary).toContain("group strategy");
  });
});

describe("buildSetupAnalyticsApiParams journal source", () => {
  it("sends journal source only to journal statistics, not evidence", () => {
    const params = buildSetupAnalyticsApiParams({
      tab: "setups",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: null,
      journalSource: "backtest",
      setupId: null,
      userStrategyId: null,
      strategyVersionId: null,
      ruleCompliance: null,
      marketRegime: null,
      groupBy: "setup",
      bucketOffset: 0,
      ignoredParams: [],
    });
    expect(params.journal.source).toBe("backtest");
    expect(params.evidence).not.toHaveProperty("source");
    expect(params).not.toHaveProperty("portfolio");
  });
});

describe("setup evidence provenance", () => {
  const baseSetupsState = {
    tab: "setups" as const,
    dateFrom: null,
    dateTo: null,
    symbol: null,
    timeframe: null,
    portfolioSource: null,
    journalSource: null,
    setupId: null,
    userStrategyId: null,
    strategyVersionId: null,
    ruleCompliance: null,
    marketRegime: null,
    groupBy: "setup" as const,
    bucketOffset: 0,
    ignoredParams: [] as string[],
  };

  it("summarizes only setup_id and strategy_id for setup-evidence", () => {
    const summary = formatSetupEvidenceFiltersSummary({
      ...baseSetupsState,
      dateFrom: "2026-01-01",
      dateTo: "2026-01-31",
      symbol: "BTCUSDT",
      timeframe: "1h",
      journalSource: "manual",
      groupBy: "strategy",
      setupId: SETUP_UUID,
      userStrategyId: STRATEGY_UUID,
    });
    expect(summary).toBe(`setup_id ${SETUP_UUID} · strategy_id ${STRATEGY_UUID}`);
    expect(summary).not.toContain("dates");
    expect(summary).not.toContain("symbol");
    expect(summary).not.toContain("timeframe");
    expect(summary).not.toContain("group");
  });

  it("returns limitation note when journal-only filters are active", () => {
    const note = formatSetupEvidenceLimitationNote({
      ...baseSetupsState,
      dateFrom: "2026-01-01",
      symbol: "BTCUSDT",
      journalSource: "backtest",
      groupBy: "setup_version",
    });
    expect(note).toMatch(/journal statistics only — not setup evidence/i);
    expect(note).toContain("dates");
    expect(note).toContain("symbol");
    expect(note).toContain("journal source");
    expect(note).toContain("grouping");
  });

  it("returns null limitation note when only evidence filters are active", () => {
    expect(
      formatSetupEvidenceLimitationNote({
        ...baseSetupsState,
        setupId: SETUP_UUID,
      }),
    ).toBeNull();
  });
});
