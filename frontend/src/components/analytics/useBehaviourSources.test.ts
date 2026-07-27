import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import type { AnalyticsFilterParams } from "./filterValidation";
import { useBehaviourSources } from "./useBehaviourSources";

vi.mock("@/lib/api", () => ({
  api: {
    journal: { statistics: vi.fn() },
    analytics: { discipline: vi.fn(), riskBehavior: vi.fn() },
    learningAnalytics: { discipline: vi.fn() },
  },
}));

const params: AnalyticsFilterParams = {
  journal: { group_by: "overall" },
  portfolio: { timezone: "UTC" },
  ruleComplianceJournal: { group_by: "rule_compliance", limit: 20 },
  comparison: {},
  analyticsWindow: { start_date: "2026-01-01" },
  learningWindow: { start_date: "2026-01-01" },
  state: {
    tab: "behaviour",
    dateFrom: "2026-01-01",
    dateTo: null,
    symbol: null,
    timeframe: null,
    portfolioSource: null,
    setupId: null,
    userStrategyId: null,
    strategyVersionId: null,
    journalSource: null,
    ruleCompliance: null,
    marketRegime: null,
    groupBy: "setup",
    bucketOffset: 0,
    ignoredParams: [],
  },
};

describe("useBehaviourSources", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps sibling widgets available when one source fails", async () => {
    vi.mocked(api.journal.statistics).mockRejectedValue(new Error("rule compliance down"));
    vi.mocked(api.analytics.discipline).mockResolvedValue({
      score: 80,
      grade: "B",
      positive_behaviors: [],
      negative_behaviors: [],
      improvement_suggestions: [],
    } as never);
    vi.mocked(api.learningAnalytics.discipline).mockResolvedValue({
      organization_id: "org",
      date_range: {},
      min_sample: 5,
      sample_size: 8,
      insufficient_data: false,
      discipline_score: 70,
      discipline_grade: "C",
      discipline_breakdown: {},
      entry_breakdown: {},
      issue_frequency: {},
      positive_behaviors: [],
      negative_behaviors: [],
      improvement_suggestions: [],
    } as never);
    vi.mocked(api.analytics.riskBehavior).mockResolvedValue({
      risk_blocks_count: 0,
      daily_loss_warnings: 1,
      green_day_warnings: 0,
      overtrading_warnings: 0,
      revenge_trading_warnings: 0,
      proposals_rejected: 0,
      proposals_needs_more_analysis: 0,
      paper_orders_rejected: 0,
      approval_pending_count: 0,
      approval_approved_count: 0,
      journal_completion_rate: 0.5,
      triggered_rules: {},
    } as never);

    const { result } = renderHook(() => useBehaviourSources(params, true));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.ruleCompliance?.available).toBe(false);
    expect(result.current.proposalDiscipline?.available).toBe(true);
    expect(result.current.learningDiscipline?.available).toBe(true);
    expect(result.current.riskBehavior?.available).toBe(true);
  });

  it("clears stale data when filters change", async () => {
    vi.mocked(api.journal.statistics).mockResolvedValue({
      group_by: "rule_compliance",
      filters: {},
      overall: {
        trade_count: 1,
        wins: 1,
        losses: 0,
        breakeven: 0,
        win_rate: 1,
        pnl_sample_count: 1,
        net_pnl_total: "1",
        gross_pnl_total: "1",
        expectancy: "1",
        average_winner: "1",
        average_loser: null,
        profit_factor: null,
        r_sample_count: 0,
        average_r: null,
        cost_sample_count: 0,
        fees_total: "0",
        funding_total: "0",
        slippage_total: "0",
        total_costs: "0",
        mfe_sample_count: 0,
        average_mfe_amount: null,
        mae_sample_count: 0,
        average_mae_amount: null,
        capture_sample_count: 0,
        available_profit_total: null,
        realized_on_available_total: null,
        average_realized_vs_available_pct: null,
        confidence: "insufficient",
        warnings: [],
      },
      buckets: [],
      total_buckets: 0,
      limit: 20,
      offset: 0,
      truncated: false,
      max_rows: 5000,
      generated_at: "2026-07-25T12:00:00Z",
    } as never);
    vi.mocked(api.analytics.discipline).mockResolvedValue({
      score: 80,
      grade: "B",
      positive_behaviors: [],
      negative_behaviors: [],
      improvement_suggestions: [],
    } as never);
    vi.mocked(api.learningAnalytics.discipline).mockResolvedValue({
      organization_id: "org",
      date_range: {},
      min_sample: 5,
      sample_size: 8,
      insufficient_data: false,
      discipline_score: 70,
      discipline_grade: "C",
      discipline_breakdown: {},
      entry_breakdown: {},
      issue_frequency: {},
      positive_behaviors: [],
      negative_behaviors: [],
      improvement_suggestions: [],
    } as never);
    vi.mocked(api.analytics.riskBehavior).mockResolvedValue({
      risk_blocks_count: 0,
      daily_loss_warnings: 0,
      green_day_warnings: 0,
      overtrading_warnings: 0,
      revenge_trading_warnings: 0,
      proposals_rejected: 0,
      proposals_needs_more_analysis: 0,
      paper_orders_rejected: 0,
      approval_pending_count: 0,
      approval_approved_count: 0,
      journal_completion_rate: 1,
      triggered_rules: {},
    } as never);

    const { result, rerender } = renderHook(
      ({ current }: { current: AnalyticsFilterParams }) => useBehaviourSources(current, true),
      { initialProps: { current: params } },
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.ruleCompliance).not.toBeNull();

    const next: AnalyticsFilterParams = {
      ...params,
      ruleComplianceJournal: {
        ...params.ruleComplianceJournal,
        symbol: "ETHUSDT",
      },
      state: { ...params.state, symbol: "ETHUSDT" },
    };
    rerender({ current: next });
    expect(result.current.loading).toBe(true);
    expect(result.current.ruleCompliance).toBeNull();
    expect(result.current.proposalDiscipline).toBeNull();
  });
});
