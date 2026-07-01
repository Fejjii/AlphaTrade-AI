import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ValidationPriorityDashboardCard } from "./ValidationPriorityDashboardCard";
import type {
  ValidationPriorityItem,
  ValidationPrioritySummaryResponse,
} from "@/lib/api/types";

const summary: ValidationPrioritySummaryResponse = {
  organization_id: "org-1",
  user_id: null,
  date_range: { start: null, end: null },
  min_sample: 5,
  note: "Read-only validation prioritization for human study only.",
  total_pending: 3,
  run_plans_pending: 2,
  candidates_pending: 1,
  by_action: [
    { action_label: "prioritize", count: 1 },
    { action_label: "watch", count: 1 },
    { action_label: "collect_more_data", count: 1 },
    { action_label: "avoid_for_now", count: 0 },
  ],
  by_reliability: [
    { reliability: "none", count: 1 },
    { reliability: "low", count: 0 },
    { reliability: "medium", count: 2 },
    { reliability: "high", count: 0 },
  ],
};

const topItems: ValidationPriorityItem[] = [
  {
    item_type: "run_plan",
    item_id: "plan-1",
    symbol: "BTCUSDT",
    condition: "breakout",
    timeframe: "1h",
    direction: "long",
    confidence: 0.9,
    confidence_bucket: "very_high",
    current_status: "planned",
    priority_score: 81,
    action_label: "prioritize",
    reliability: "medium",
    matched_dimension: "condition",
    matched_key: "breakout",
    matched_sample_size: 10,
    historical_success_rate: 0.8,
    historical_invalidation_rate: 0,
    factors: [],
    rationale: [],
  },
  {
    item_type: "candidate",
    item_id: "cand-1",
    symbol: "ETHUSDT",
    condition: "pullback",
    timeframe: "4h",
    direction: "short",
    confidence: 0.5,
    confidence_bucket: "medium",
    current_status: "queued",
    priority_score: 55,
    action_label: "watch",
    reliability: "none",
    matched_dimension: "global",
    matched_key: "all",
    matched_sample_size: 0,
    historical_success_rate: null,
    historical_invalidation_rate: null,
    factors: [],
    rationale: [],
  },
];

describe("ValidationPriorityDashboardCard", () => {
  afterEach(() => cleanup());

  it("renders distribution, top items, and link to full page", () => {
    render(<ValidationPriorityDashboardCard summary={summary} topItems={topItems} />);
    expect(screen.getByTestId("dashboard-validation-priority")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-validation-priority-distribution")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-validation-priority-count-prioritize")).toHaveTextContent(
      "1",
    );
    expect(screen.getByText("Validate next")).toBeInTheDocument();
    expect(screen.getByText("Study next")).toBeInTheDocument();
    expect(screen.getByText("Collect more data")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-validation-priority-top-plan-1")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-validation-priority-top-cand-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open validation priority" })).toHaveAttribute(
      "href",
      "/validation-priority",
    );
  });

  it("deep links top items to run plan and candidate detail pages", () => {
    render(<ValidationPriorityDashboardCard summary={summary} topItems={topItems} />);
    expect(screen.getByTestId("dashboard-validation-priority-link-plan-1")).toHaveAttribute(
      "href",
      "/paper-validation/run-plans/plan-1",
    );
    expect(screen.getByTestId("dashboard-validation-priority-link-cand-1")).toHaveAttribute(
      "href",
      "/paper-validation/candidates/cand-1",
    );
  });

  it("has no order, execution, proposal, or automation controls", () => {
    render(<ValidationPriorityDashboardCard summary={summary} topItems={topItems} />);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start run/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /automate/i })).not.toBeInTheDocument();
  });
});
