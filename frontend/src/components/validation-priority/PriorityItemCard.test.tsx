import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PriorityItemCard } from "./PriorityItemCard";
import type { ValidationPriorityItem } from "@/lib/api/types";

const runPlanItem: ValidationPriorityItem = {
  item_type: "run_plan",
  item_id: "plan-1",
  symbol: "BTCUSDT",
  condition: "breakout",
  timeframe: "1h",
  direction: "long",
  confidence: 0.6,
  confidence_bucket: "medium",
  current_status: "planned",
  priority_score: 22,
  action_label: "avoid_for_now",
  reliability: "high",
  matched_dimension: "condition",
  matched_key: "breakout",
  matched_sample_size: 20,
  historical_success_rate: 0.2,
  historical_invalidation_rate: 0.6,
  factors: [
    {
      code: "invalidation_penalty",
      label: "Repeated invalidations",
      direction: "negative",
      contribution: -12,
      detail: "Invalidation was hit in 60% of matched sessions.",
    },
  ],
  rationale: ["Invalidation is hit often for this kind of setup."],
};

const candidateItem: ValidationPriorityItem = {
  ...runPlanItem,
  item_type: "candidate",
  item_id: "cand-2",
  condition: "pullback",
  current_status: "queued",
};

describe("PriorityItemCard", () => {
  afterEach(() => cleanup());

  it("renders action label, score, factors, and rationale", () => {
    render(<PriorityItemCard item={runPlanItem} />);
    expect(screen.getByTestId("validation-priority-item-plan-1")).toBeInTheDocument();
    expect(screen.getByTestId("validation-priority-score")).toHaveTextContent("score 22");
    expect(screen.getByText(/avoid for now/i)).toBeInTheDocument();
    expect(
      screen.getByTestId("validation-priority-factor-invalidation_penalty"),
    ).toBeInTheDocument();
    expect(screen.getByText(/invalidation is hit often/i)).toBeInTheDocument();
  });

  it("deep links run plan items to run plan detail page", () => {
    render(<PriorityItemCard item={runPlanItem} />);
    expect(screen.getByTestId("validation-priority-item-link-plan-1")).toHaveAttribute(
      "href",
      "/paper-validation/run-plans/plan-1",
    );
    expect(screen.getByTestId("validation-priority-detail-link-plan-1")).toHaveAttribute(
      "href",
      "/paper-validation/run-plans/plan-1",
    );
    expect(screen.getByRole("link", { name: "Open run plan" })).toBeInTheDocument();
  });

  it("deep links candidate items to candidate detail page", () => {
    render(<PriorityItemCard item={candidateItem} />);
    expect(screen.getByTestId("validation-priority-item-link-cand-2")).toHaveAttribute(
      "href",
      "/paper-validation/candidates/cand-2",
    );
    expect(screen.getByRole("link", { name: "Open candidate" })).toBeInTheDocument();
  });

  it("has no order, execution, proposal, or automation controls", () => {
    render(<PriorityItemCard item={runPlanItem} />);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start run/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /automate/i })).not.toBeInTheDocument();
  });
});
