import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PaperValidationCandidatesPage from "./page";

const sampleCandidate = {
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
  risk_mode: "conservative" as const,
  candidate_status: "queued" as const,
  created_at: "2026-06-28T12:00:00Z",
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: { items: [sampleCandidate], total: 1, limit: 50, offset: 0 },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("PaperValidationCandidatesPage Slice 80", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders candidate list without run or execution UI", () => {
    render(<PaperValidationCandidatesPage />);

    expect(screen.getByTestId("paper-validation-candidates-page")).toBeInTheDocument();
    expect(screen.getByTestId("paper-validation-candidates-list")).toBeInTheDocument();
    expect(screen.getByTestId("paper-candidate-candidate-1")).toBeInTheDocument();
    expect(screen.getByText(/queue only/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start run/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send to telegram/i })).not.toBeInTheDocument();
  });
});
