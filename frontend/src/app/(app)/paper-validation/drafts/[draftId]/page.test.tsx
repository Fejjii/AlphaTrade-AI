import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PaperValidationDraftItem } from "@/lib/api/types";

import PaperValidationDraftDetailPage from "./page";

const baseDraft: PaperValidationDraftItem = {
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
  risk_mode: "conservative",
  status: "draft",
  created_at: "2026-06-28T12:00:00Z",
  created_by: "user-1",
  thesis: "",
  entry_criteria: "",
  invalidation_criteria: "",
  risk_notes: "",
  prep_status: "draft",
  checklist: {
    trend_checked: false,
    support_resistance_checked: false,
    volume_checked: false,
    risk_reward_checked: false,
    invalidation_checked: false,
    higher_timeframe_checked: false,
    news_or_funding_checked: false,
  },
  prep_completion_score: 0,
  missing_checklist_items: [
    "trend_checked",
    "support_resistance_checked",
    "volume_checked",
    "risk_reward_checked",
    "invalidation_checked",
    "higher_timeframe_checked",
    "news_or_funding_checked",
  ],
  is_ready_for_validation: false,
};

const mockReload = vi.fn();
const mockUpdateDraftPrep = vi.fn();
let draftData: PaperValidationDraftItem = baseDraft;

vi.mock("next/navigation", () => ({
  useParams: () => ({ draftId: "draft-1" }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: draftData,
    loading: false,
    error: null,
    reload: mockReload,
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    strategies: {
      getDraft: vi.fn(),
      updateDraftPrep: (...args: unknown[]) => mockUpdateDraftPrep(...args),
    },
  },
}));

describe("PaperValidationDraftDetailPage Slice 79", () => {
  beforeEach(() => {
    draftData = baseDraft;
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders prep form and safety copy without execution UI", () => {
    render(<PaperValidationDraftDetailPage />);

    expect(screen.getByTestId("paper-validation-draft-detail")).toBeInTheDocument();
    expect(screen.getByTestId("paper-draft-prep-section")).toBeInTheDocument();
    expect(screen.getByTestId("paper-draft-safety-copy")).toHaveTextContent(/prep only/i);
    expect(screen.getByTestId("paper-draft-safety-copy")).toHaveTextContent(/no order/i);
    expect(screen.getByTestId("paper-draft-safety-copy")).toHaveTextContent(/no execution/i);
    expect(screen.getByTestId("paper-draft-safety-copy")).toHaveTextContent(/no proposal/i);
    expect(screen.getByTestId("paper-draft-checklist")).toBeInTheDocument();
    expect(screen.getByTestId("paper-draft-prep-score")).toHaveTextContent("0%");
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send to telegram/i })).not.toBeInTheDocument();
  });

  it("calls PATCH when saving prep", async () => {
    mockUpdateDraftPrep.mockResolvedValue({
      ...baseDraft,
      thesis: "Updated thesis",
      prep_completion_score: 10,
    });

    render(<PaperValidationDraftDetailPage />);

    fireEvent.change(screen.getByTestId("paper-draft-thesis"), {
      target: { value: "Updated thesis" },
    });
    fireEvent.click(screen.getByTestId("paper-draft-save-prep"));

    await waitFor(() => {
      expect(mockUpdateDraftPrep).toHaveBeenCalledWith(
        "draft-1",
        expect.objectContaining({ thesis: "Updated thesis" }),
      );
    });
  });

  it("shows ready badge when draft is ready for validation", () => {
    draftData = {
      ...baseDraft,
      is_ready_for_validation: true,
      prep_status: "ready_for_validation",
      prep_completion_score: 100,
      missing_checklist_items: [],
    };

    render(<PaperValidationDraftDetailPage />);
    expect(screen.getByTestId("paper-draft-ready-badge")).toBeInTheDocument();
  });
});
