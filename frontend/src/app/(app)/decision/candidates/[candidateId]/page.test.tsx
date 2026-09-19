import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DecisionCandidateDetailPage from "./page";
import type { PaperValidationCandidateItem } from "@/lib/api/types";

const candidate: PaperValidationCandidateItem = {
  candidate_id: "cand-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "ETHUSDT",
  timeframe: "4h",
  condition: "liquidity_sweep",
  direction: "short",
  confidence: 0.81,
  thesis: "Sweep then displace.",
  entry_criteria: "Reclaim after sweep",
  invalidation_criteria: "Above sweep high",
  checklist_snapshot: {
    trend_checked: true,
    support_resistance_checked: true,
    volume_checked: true,
    risk_reward_checked: true,
    invalidation_checked: true,
    higher_timeframe_checked: true,
    news_or_funding_checked: false,
  },
  risk_mode: "moderate",
  candidate_status: "queued",
  created_at: "2026-09-19T11:00:00.000Z",
};

vi.mock("next/navigation", () => ({
  useParams: () => ({ candidateId: "cand-1" }),
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    killSwitchActive: false,
    killSwitchStatus: { active: false, execution_blocked: false },
  }),
  useSafetyPosture: () => ({
    executionMode: "paper",
    realTradingEnabled: false,
    postureKnown: true,
  }),
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill switch</button>,
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: candidate,
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("Candidate workspace page", () => {
  afterEach(() => cleanup());

  it("shows state, setup, evidence, confidence, and separate eligibility", () => {
    render(<DecisionCandidateDetailPage />);
    expect(screen.getByTestId("candidate-workspace")).toBeInTheDocument();
    expect(screen.getAllByText(/sweep then displace/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId("market-quality-card")).toBeInTheDocument();
    expect(screen.getByTestId("market-quality-separation")).toHaveTextContent(
      /not action eligibility/i,
    );
    expect(screen.getByTestId("action-eligibility-card")).toBeInTheDocument();
    expect(screen.getAllByText(/81% confidence/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });
});
