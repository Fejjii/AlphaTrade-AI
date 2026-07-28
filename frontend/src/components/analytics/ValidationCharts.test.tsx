import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnalyticsFilterParams } from "./filterValidation";
import { ValidationCharts } from "./ValidationCharts";

const reloadSummary = vi.fn();
const reloadSetupPerformance = vi.fn();
const reloadSetupRanking = vi.fn();
const reloadStrategyQuality = vi.fn();

vi.mock("./useValidationSources", () => ({
  useValidationSources: () => ({
    summary: {
      available: false,
      data: null,
      error: "summary failed",
      fallbackUsed: false,
    },
    summaryLoading: false,
    summaryRetryLoading: false,
    setupPerformance: {
      available: true,
      data: {
        organization_id: "org",
        date_range: {},
        min_sample: 5,
        dimension: "condition",
        groups: [
          {
            dimension_value: "breakout",
            sample_size: 6,
            insufficient_data: false,
            success_rate: 0.5,
            outcome_distribution: [],
          },
        ],
      },
      error: null,
      fallbackUsed: false,
    },
    setupPerformanceLoading: false,
    setupPerformanceRetryLoading: false,
    setupRanking: {
      available: true,
      data: {
        organization_id: "org",
        date_range: {},
        min_sample: 5,
        dimension: "condition",
        note: "observational",
        ranked: [{ setup_key: "breakout", rank: 1, quality_score: 0.5, sample_size: 6 }],
      },
      error: null,
      fallbackUsed: false,
    },
    setupRankingLoading: false,
    setupRankingRetryLoading: false,
    strategyQuality: {
      available: true,
      data: {
        organization_id: "org",
        date_range: {},
        min_sample: 5,
        note: "context",
        total_detectors: 1,
        detectors_with_data: 1,
        total_results: 6,
        by_trust_tier: [],
        by_verdict: [],
        ranked: [],
        warnings: [],
      },
      error: null,
      fallbackUsed: false,
    },
    strategyQualityLoading: false,
    strategyQualityRetryLoading: false,
    reloadSummary,
    reloadSetupPerformance,
    reloadSetupRanking,
    reloadStrategyQuality,
  }),
}));

vi.mock("./AnalyticsCharts", () => ({
  ValidationOutcomeChart: (props: { error?: string | null; source: { available: boolean; error?: string | null } }) => (
    <div data-testid="validation-outcome-chart">
      {props.source && !props.source.available
        ? `error:${props.source.error}`
        : "outcome-ok"}
    </div>
  ),
  SetupSuccessByDimension: () => <div data-testid="setup-success-by-dimension">dimension-ok</div>,
}));

const apiParams: AnalyticsFilterParams = {
  journal: { group_by: "overall" },
  portfolio: { timezone: "UTC" },
  ruleComplianceJournal: { group_by: "rule_compliance", limit: 20 },
  comparison: {},
  analyticsWindow: {},
  learningWindow: {},
  validation: {
    start_date: "2026-01-01",
    end_date: "2026-01-31",
    min_sample: 5,
    dimension: "condition",
  },
  strategyQuality: {
    start_date: "2026-01-01",
    end_date: "2026-01-31",
    min_sample: 5,
  },
  state: {
    tab: "validation",
    dateFrom: "2026-01-01",
    dateTo: "2026-01-31",
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
    minSample: 5,
    dimension: "condition",
    ignoredParams: [],
  },
};

describe("ValidationCharts", () => {
  afterEach(() => cleanup());

  it("renders partial failure without collapsing sibling widgets", () => {
    render(<ValidationCharts apiParams={apiParams} onDimensionChange={vi.fn()} />);
    expect(screen.getByTestId("validation-charts")).toBeInTheDocument();
    expect(screen.getByTestId("validation-outcome-chart")).toHaveTextContent(/summary failed/);
    expect(screen.getByTestId("setup-success-by-dimension")).toBeInTheDocument();
    expect(screen.getByTestId("validation-ranking-table")).toBeInTheDocument();
    expect(screen.getByTestId("validation-strategy-quality-context")).toBeInTheDocument();
    expect(screen.getByTestId("validation-freshness-limitation")).toHaveTextContent(
      /does not expose a server freshness timestamp/i,
    );
  });

  it("returns null when disabled", () => {
    const { container } = render(
      <ValidationCharts apiParams={apiParams} enabled={false} onDimensionChange={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
