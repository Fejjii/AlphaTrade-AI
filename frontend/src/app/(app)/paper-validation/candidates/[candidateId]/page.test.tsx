import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PaperValidationCandidateItem } from "@/lib/api/types";
import PaperValidationCandidateDetailPage from "./page";

const { createRunPlan, candidateState } = vi.hoisted(() => {
  const baseCandidate: PaperValidationCandidateItem = {
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
    thesis: "Queued thesis.",
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
    risk_mode: "conservative",
    candidate_status: "reviewing",
    created_at: "2026-06-28T12:00:00Z",
  };

  return {
    createRunPlan: vi.fn().mockResolvedValue({
      plan: { plan_id: "plan-1" },
      already_exists: false,
    }),
    candidateState: { data: baseCandidate },
  };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ candidateId: "candidate-1" }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: candidateState.data,
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    strategies: {
      getCandidate: vi.fn(),
      updateCandidateStatus: vi.fn(),
      createRunPlan,
    },
  },
}));

describe("PaperValidationCandidateDetailPage Slice 81", () => {
  afterEach(() => {
    cleanup();
    createRunPlan.mockClear();
    candidateState.data = { ...candidateState.data, candidate_status: "reviewing" };
  });

  it("renders candidate detail with safety copy and checklist", () => {
    render(<PaperValidationCandidateDetailPage />);

    expect(screen.getByTestId("paper-validation-candidate-detail")).toBeInTheDocument();
    expect(screen.getByTestId("paper-candidate-safety-copy")).toHaveTextContent(/queue only/i);
    expect(screen.getByTestId("paper-candidate-checklist")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
  });

  it("shows create plan section only for reviewing candidate with confirmation", async () => {
    render(<PaperValidationCandidateDetailPage />);

    expect(screen.getByTestId("paper-candidate-create-plan-section")).toBeInTheDocument();
    expect(screen.getByTestId("paper-candidate-plan-safety-copy")).toHaveTextContent(/plan only/i);
    expect(screen.getByTestId("paper-candidate-plan-safety-copy")).toHaveTextContent(/no run started/i);
    expect(screen.getByTestId("paper-candidate-plan-submit")).toBeDisabled();

    fireEvent.change(screen.getByTestId("paper-candidate-plan-confirm"), {
      target: { value: "CREATE_PAPER_VALIDATION_RUN_PLAN" },
    });
    fireEvent.click(screen.getByTestId("paper-candidate-plan-submit"));

    expect(createRunPlan).toHaveBeenCalledWith("candidate-1", expect.objectContaining({
      confirm: "CREATE_PAPER_VALIDATION_RUN_PLAN",
      validation_window: "intraday",
    }));
    expect(await screen.findByTestId("paper-candidate-plan-link")).toBeInTheDocument();
  });

  it("hides create plan section for queued candidate", () => {
    candidateState.data = { ...candidateState.data, candidate_status: "queued" };
    render(<PaperValidationCandidateDetailPage />);
    expect(screen.queryByTestId("paper-candidate-create-plan-section")).not.toBeInTheDocument();
  });
});
