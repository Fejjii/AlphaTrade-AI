import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PaperValidationRunPlanDetailPage from "./page";

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

vi.mock("next/navigation", () => ({
  useParams: () => ({ planId: "plan-1" }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: samplePlan,
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    strategies: {
      getRunPlan: vi.fn(),
      updateRunPlanStatus: vi.fn(),
      startRunSession: vi.fn(),
    },
  },
}));

describe("PaperValidationRunPlanDetailPage Slice 81", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders run plan detail with safety copy and planning fields", () => {
    render(<PaperValidationRunPlanDetailPage />);

    expect(screen.getByTestId("paper-validation-run-plan-detail")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-plan-safety-copy")).toHaveTextContent(/plan only/i);
    expect(screen.getByTestId("paper-run-plan-safety-copy")).toHaveTextContent(/no run started/i);
    expect(screen.getByText("Entry rule")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-plan-checklist")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /deliver telegram/i })).not.toBeInTheDocument();
  });

  it("shows the planned-gated start run session section with record-only safety copy", () => {
    render(<PaperValidationRunPlanDetailPage />);

    expect(screen.getByTestId("paper-run-plan-start-section")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-safety-copy")).toHaveTextContent(/record only/i);
    expect(screen.getByTestId("paper-run-session-safety-copy")).toHaveTextContent(/no live run/i);
    // Submit stays disabled until the exact confirmation phrase is typed.
    expect(screen.getByTestId("paper-run-session-submit")).toBeDisabled();
  });
});
