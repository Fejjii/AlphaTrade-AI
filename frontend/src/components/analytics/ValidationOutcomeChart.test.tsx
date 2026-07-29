import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { SourceResult } from "@/components/workflows";
import type { LearningAnalyticsSummaryResponse } from "@/lib/api/types";

import { containsCurrencySymbol } from "./format";
import { ValidationOutcomeChart } from "./ValidationOutcomeChart";

function ok(
  data: LearningAnalyticsSummaryResponse,
): SourceResult<LearningAnalyticsSummaryResponse> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed(
  error = "summary down",
): SourceResult<LearningAnalyticsSummaryResponse> {
  return { data: null, available: false, error, fallbackUsed: false };
}

const baseSummary: LearningAnalyticsSummaryResponse = {
  organization_id: "org",
  user_id: null,
  date_range: { start: "2026-01-01", end: "2026-01-31" },
  min_sample: 5,
  funnel: {
    alerts: 0,
    drafts: 0,
    candidates: 0,
    run_plans: 0,
    run_sessions: 3,
    completed_sessions: 3,
    cancelled_sessions: 0,
    results: 3,
  },
  total_sessions: 3,
  completed_sessions: 3,
  cancelled_sessions: 0,
  results_count: 3,
  outcome_distribution: [
    { outcome: "success", count: 1, rate: 1 / 3 },
    { outcome: "failure", count: 1, rate: 1 / 3 },
    { outcome: "invalidated", count: 1, rate: 1 / 3 },
  ],
  rates: {
    success_rate: 1 / 3,
    failure_rate: 1 / 3,
    invalidated_rate: 1 / 3,
  },
  observations: { total_observations: 0, by_kind: {} },
  lessons_count: 0,
};

describe("ValidationOutcomeChart", () => {
  afterEach(() => cleanup());

  it("renders all six categorical outcomes and accessible table", () => {
    render(
      <ValidationOutcomeChart
        source={ok(baseSummary)}
        filtersSummary="dates 2026-01-01 → 2026-01-31 · Min sample 5"
      />,
    );
    expect(screen.getByTestId("validation-outcome-chart-plot")).toBeInTheDocument();
    for (const outcome of [
      "success",
      "failure",
      "invalidated",
      "missed_entry",
      "no_trade",
      "inconclusive",
    ]) {
      expect(screen.getByTestId(`validation-outcome-row-${outcome}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId("validation-outcome-a11y-table")).toBeInTheDocument();
    expect(screen.getByTestId("validation-outcome-no-pnl-caption")).toHaveTextContent(
      /no P&L is recorded for manual validation sessions/i,
    );
    expect(containsCurrencySymbol(screen.getByTestId("validation-outcome-chart").textContent ?? "")).toBe(
      false,
    );
  });

  it("shows insufficient sample banner without verdict language", () => {
    render(<ValidationOutcomeChart source={ok(baseSummary)} />);
    expect(screen.getByTestId("validation-outcome-insufficient-banner")).toHaveTextContent(
      /Insufficient sample \(n=3 < 5\)/,
    );
    expect(screen.getByTestId("validation-outcome-chart").textContent).not.toMatch(
      /trusted|avoid|verdict|beat the market/i,
    );
  });

  it("links empty state to run sessions", () => {
    render(
      <ValidationOutcomeChart
        source={ok({ ...baseSummary, results_count: 0, outcome_distribution: [] })}
      />,
    );
    expect(screen.getByTestId("validation-outcome-empty-sessions-link")).toHaveAttribute(
      "href",
      "/paper-validation/run-sessions",
    );
  });

  it("shows error retry without fabricating zeros", () => {
    render(<ValidationOutcomeChart source={failed()} />);
    expect(screen.getByTestId("validation-outcome-chart-error")).toHaveTextContent(/summary down/i);
    expect(screen.queryByTestId("validation-outcome-chart-plot")).not.toBeInTheDocument();
    expect(screen.queryByText("0 sessions")).not.toBeInTheDocument();
  });
});
