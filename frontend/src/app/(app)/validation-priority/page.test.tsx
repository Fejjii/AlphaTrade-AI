import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ValidationPriorityPage from "./page";

const sampleData = {
  summary: {
    organization_id: "org-1",
    user_id: null,
    date_range: { start: null, end: null },
    min_sample: 5,
    note: "Read-only validation prioritization for human study only.",
    total_pending: 2,
    run_plans_pending: 1,
    candidates_pending: 1,
    by_action: [
      { action_label: "prioritize" as const, count: 1 },
      { action_label: "watch" as const, count: 0 },
      { action_label: "collect_more_data" as const, count: 1 },
      { action_label: "avoid_for_now" as const, count: 0 },
    ],
    by_reliability: [
      { reliability: "none" as const, count: 1 },
      { reliability: "low" as const, count: 0 },
      { reliability: "medium" as const, count: 1 },
      { reliability: "high" as const, count: 0 },
    ],
  },
  queue: {
    organization_id: "org-1",
    user_id: null,
    date_range: { start: null, end: null },
    min_sample: 5,
    note: "Read-only validation prioritization for human study only.",
    item_type_filter: null,
    limit: 20,
    total_pending: 2,
    items: [
      {
        item_type: "run_plan" as const,
        item_id: "plan-1",
        symbol: "BTCUSDT",
        condition: "breakout",
        timeframe: "1h",
        direction: "long",
        confidence: 0.9,
        confidence_bucket: "very_high",
        current_status: "planned",
        priority_score: 81,
        action_label: "prioritize" as const,
        reliability: "medium" as const,
        matched_dimension: "condition",
        matched_key: "breakout",
        matched_sample_size: 10,
        historical_success_rate: 0.8,
        historical_invalidation_rate: 0,
        factors: [
          {
            code: "historical_quality",
            label: "Historical setup quality",
            direction: "positive" as const,
            contribution: 23.3,
            detail: "Matched history quality resolves to 73.",
          },
        ],
        rationale: ["Strong historical quality with sufficient evidence."],
      },
      {
        item_type: "candidate" as const,
        item_id: "cand-1",
        symbol: "ETHUSDT",
        condition: "novel_setup",
        timeframe: "4h",
        direction: "short",
        confidence: 0.5,
        confidence_bucket: "medium",
        current_status: "queued",
        priority_score: 50,
        action_label: "collect_more_data" as const,
        reliability: "none" as const,
        matched_dimension: "global",
        matched_key: "all",
        matched_sample_size: 0,
        historical_success_rate: null,
        historical_invalidation_rate: null,
        factors: [],
        rationale: ["Only 0 matched session(s) (min 5); validate more to build reliable evidence."],
      },
    ],
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

describe("ValidationPriorityPage Slice 85", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders queue, summary, and safety copy", () => {
    render(<ValidationPriorityPage />);
    expect(screen.getByTestId("validation-priority-page")).toBeInTheDocument();
    expect(screen.getByTestId("validation-priority-summary")).toBeInTheDocument();
    expect(screen.getByTestId("validation-priority-item-plan-1")).toBeInTheDocument();
    expect(screen.getByTestId("validation-priority-item-cand-1")).toBeInTheDocument();
    expect(screen.getByText(/no orders, no proposals, no automation/i)).toBeInTheDocument();
  });

  it("shows action counts and reliability for collect_more_data items", () => {
    render(<ValidationPriorityPage />);
    expect(screen.getByTestId("validation-priority-count-prioritize")).toHaveTextContent("1");
    expect(screen.getByTestId("validation-priority-item-cand-1")).toHaveTextContent(
      /collect more data/i,
    );
  });

  it("has no order, execution, proposal, or automation controls", () => {
    render(<ValidationPriorityPage />);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start run/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /automate/i })).not.toBeInTheDocument();
  });
});
