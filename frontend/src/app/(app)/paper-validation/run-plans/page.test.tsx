import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PaperValidationRunPlansPage from "./page";

const samplePlan = {
  plan_id: "plan-1",
  candidate_id: "candidate-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "BTCUSDT",
  timeframe: "15m",
  condition: "order_block",
  direction: "long",
  confidence: 0.88,
  trigger_level: 65000,
  invalidation_level: 64000,
  latest_price: 65100,
  thesis: "Plan thesis.",
  entry_criteria: "Entry rules",
  invalidation_criteria: "Invalidation rules",
  risk_notes: "Risk notes",
  checklist_snapshot: {
    trend_checked: true,
    support_resistance_checked: true,
    volume_checked: true,
    risk_reward_checked: true,
    invalidation_checked: true,
    higher_timeframe_checked: true,
    news_or_funding_checked: true,
  },
  risk_mode: "conservative" as const,
  plan_status: "planned" as const,
  validation_window: "intraday",
  observation_timeframe: "1h",
  max_duration_minutes: 240,
  planned_entry_rule: "Entry rule",
  planned_invalidation_rule: "Invalidation rule",
  planned_success_criteria: "Success criteria",
  planned_failure_criteria: "Failure criteria",
  created_at: "2026-06-28T12:00:00Z",
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: { items: [samplePlan], total: 1, limit: 50, offset: 0 },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("PaperValidationRunPlansPage Slice 81", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders run plan list without run or execution UI", () => {
    render(<PaperValidationRunPlansPage />);

    expect(screen.getByTestId("paper-validation-run-plans-page")).toBeInTheDocument();
    expect(screen.getByTestId("paper-validation-run-plans-list")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-plan-plan-1")).toBeInTheDocument();
    expect(screen.getByText(/plan only/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start run/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
  });
});
