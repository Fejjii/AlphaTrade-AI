import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import LearningAnalyticsPage from "./page";

const sampleData = {
  summary: {
    organization_id: "org-1",
    user_id: null,
    date_range: { start: null, end: null },
    min_sample: 5,
    funnel: {
      alerts: 8,
      drafts: 6,
      candidates: 5,
      run_plans: 4,
      run_sessions: 4,
      completed_sessions: 4,
      cancelled_sessions: 0,
      results: 4,
    },
    total_sessions: 4,
    completed_sessions: 4,
    cancelled_sessions: 0,
    results_count: 4,
    outcome_distribution: [
      { outcome: "success", count: 3, rate: 0.75 },
      { outcome: "failure", count: 1, rate: 0.25 },
    ],
    rates: {
      success_rate: 0.75,
      failure_rate: 0.25,
      invalidated_rate: 0,
      missed_entry_rate: 0,
      no_trade_rate: 0,
      inconclusive_rate: 0,
      behaved_as_expected_rate: 0.75,
      invalidation_hit_rate: 0.25,
    },
    observations: { total_observations: 2, average_per_session: 0.5, by_kind: {} },
    average_minutes_to_outcome: 30,
    lessons_count: 2,
  },
  performance: {
    organization_id: "org-1",
    date_range: { start: null, end: null },
    min_sample: 5,
    dimension: "condition" as const,
    groups: [
      {
        dimension_value: "breakout",
        sample_size: 6,
        insufficient_data: false,
        quality_score: 82.5,
        success_rate: 0.8,
        failure_rate: 0.2,
        invalidation_hit_rate: 0.1,
        behaved_as_expected_rate: 0.8,
        outcome_distribution: [],
      },
      {
        dimension_value: "pullback",
        sample_size: 1,
        insufficient_data: true,
        quality_score: null,
        success_rate: null,
        failure_rate: null,
        invalidation_hit_rate: null,
        behaved_as_expected_rate: null,
        outcome_distribution: [],
      },
    ],
  },
  discipline: {
    organization_id: "org-1",
    date_range: { start: null, end: null },
    min_sample: 5,
    sample_size: 6,
    insufficient_data: false,
    discipline_score: 67,
    discipline_grade: "D",
    discipline_breakdown: { disciplined: 4, should_have_avoided: 2 },
    entry_breakdown: {},
    issue_frequency: { should_have_avoided: 0.33 },
    positive_behaviors: [],
    negative_behaviors: ["You often took setups you should have avoided."],
    improvement_suggestions: ["Filter out low-quality conditions before committing."],
  },
  confidence: {
    organization_id: "org-1",
    date_range: { start: null, end: null },
    min_sample: 5,
    buckets: [
      {
        bucket: "low",
        lower: 0,
        upper: 0.5,
        sample_size: 3,
        insufficient_data: false,
        success_rate: 0,
      },
      {
        bucket: "very_high",
        lower: 0.85,
        upper: 1,
        sample_size: 3,
        insufficient_data: false,
        success_rate: 1,
      },
    ],
    correlation: "positive",
  },
  insights: {
    organization_id: "org-1",
    date_range: { start: null, end: null },
    min_sample: 5,
    insights: [
      {
        code: "misses_entries_on_strong_setups",
        message: "You miss entries often on strong (high-confidence) setups.",
        severity: "warning",
        sample_size: 5,
        confidence: "high",
      },
    ],
  },
  lessons: {
    organization_id: "org-1",
    date_range: { start: null, end: null },
    min_sample: 5,
    lessons_count: 2,
    themes: [{ theme: "patience", count: 2, example_excerpt: "Patience before entry" }],
  },
  ranking: {
    organization_id: "org-1",
    date_range: { start: null, end: null },
    min_sample: 5,
    dimension: "condition" as const,
    note: "Read-only ranking for human review only. This does not enable automation, ordering, proposals, approvals, or execution.",
    ranked: [{ setup_key: "breakout", rank: 1, quality_score: 82.5, sample_size: 6 }],
  },
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: sampleData,
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("LearningAnalyticsPage Slice 84", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders analytics sections and safety copy", () => {
    render(<LearningAnalyticsPage />);

    expect(screen.getByTestId("learning-analytics-page")).toBeInTheDocument();
    expect(screen.getByTestId("learning-outcome-rates-card")).toBeInTheDocument();
    expect(screen.getByTestId("learning-behavior-insights-card")).toBeInTheDocument();
    expect(screen.getByTestId("learning-setup-ranking")).toBeInTheDocument();
    expect(screen.getByText(/no orders, no/i)).toBeInTheDocument();
    expect(
      screen.getByTestId("learning-insight-misses_entries_on_strong_setups"),
    ).toBeInTheDocument();
  });

  it("shows insufficient-data flag for small groups", () => {
    render(<LearningAnalyticsPage />);
    expect(screen.getByTestId("learning-group-pullback")).toHaveTextContent(/insufficient data/i);
  });

  it("has no order, execution, proposal, or automation controls", () => {
    render(<LearningAnalyticsPage />);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start run/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /automate/i })).not.toBeInTheDocument();
  });
});
