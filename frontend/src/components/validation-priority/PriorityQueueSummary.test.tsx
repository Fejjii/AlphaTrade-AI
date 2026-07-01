import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PriorityQueueSummary } from "./PriorityQueueSummary";
import type { ValidationPrioritySummaryResponse } from "@/lib/api/types";

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
    { action_label: "prioritize", count: 2 },
    { action_label: "watch", count: 0 },
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

describe("PriorityQueueSummary", () => {
  afterEach(() => cleanup());

  it("renders totals and per-action counts", () => {
    render(<PriorityQueueSummary summary={summary} />);
    expect(screen.getByTestId("validation-priority-summary")).toHaveTextContent(
      /3 pending \(2 run plans, 1 candidates\)/i,
    );
    expect(screen.getByTestId("validation-priority-count-prioritize")).toHaveTextContent("2");
    expect(screen.getByTestId("validation-priority-count-collect_more_data")).toHaveTextContent(
      "1",
    );
  });
});
