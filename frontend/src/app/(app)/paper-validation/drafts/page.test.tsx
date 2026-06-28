import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PaperValidationDraftsPage from "./page";

const sampleDraft = {
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
  reason: "Bullish order block retest.",
  risk_mode: "conservative" as const,
  status: "draft" as const,
  created_at: "2026-06-28T12:00:00Z",
  created_by: "user-1",
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: { items: [sampleDraft], total: 1, limit: 50, offset: 0 },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("PaperValidationDraftsPage Slice 78", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders draft list without execution UI", () => {
    render(<PaperValidationDraftsPage />);

    expect(screen.getByTestId("paper-validation-drafts-page")).toBeInTheDocument();
    expect(screen.getByTestId("paper-validation-drafts-list")).toBeInTheDocument();
    expect(screen.getByTestId("paper-draft-draft-1")).toBeInTheDocument();
    expect(screen.getByText(/never place orders/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send to telegram/i })).not.toBeInTheDocument();
  });
});
