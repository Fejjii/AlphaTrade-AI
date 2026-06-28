import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SetupAlertReviewPage from "./page";

const { sampleAlert, summary } = vi.hoisted(() => ({
  sampleAlert: {
    alert_id: "alert-1",
    created_at: "2026-06-28T12:00:00Z",
    symbol: "BTCUSDT",
    timeframe: "15m",
    condition: "order_block",
    direction: "long",
    confidence: 0.88,
    reason: "Bullish order block retest.",
    trigger_level: 65000,
    invalidation_level: 64000,
    latest_price: 65100,
    delivery_channel: "in_app",
    delivery_status: "disabled",
    dedupe_key: "dedupe-1",
    review_status: "unreviewed" as const,
    review_notes: null,
    reviewed_at: null,
    reviewed_by: null,
    metadata: { source: "market_watcher" },
  },
  summary: {
    total_unreviewed: 1,
    total_watching: 0,
    total_important: 0,
    total_ignored: 0,
    by_condition: { order_block: 1 },
    by_symbol: { BTCUSDT: 1 },
    latest_created_at: "2026-06-28T12:00:00Z",
    highest_confidence_alerts: [
      {
        alert_id: "alert-1",
        symbol: "BTCUSDT",
        condition: "order_block",
        confidence: 0.88,
        created_at: "2026-06-28T12:00:00Z",
      },
    ],
  },
}));

let hookCall = 0;

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => {
    hookCall += 1;
    const index = (hookCall - 1) % 2;
    if (index === 1) {
      return {
        data: summary,
        loading: false,
        error: null,
        reload: vi.fn(),
      };
    }
    return {
      data: { items: [sampleAlert], total: 1, limit: 50, offset: 0 },
      loading: false,
      error: null,
      reload: vi.fn(),
    };
  },
}));

vi.mock("@/lib/api", () => ({
  api: {
    alerts: {
      setupReview: vi.fn(),
      setupReviewSummary: vi.fn(),
      updateSetupReview: vi.fn().mockResolvedValue({
        ...sampleAlert,
        review_status: "watching",
      }),
    },
  },
}));

describe("SetupAlertReviewPage Slice 77", () => {
  beforeEach(() => {
    hookCall = 0;
  });

  afterEach(() => {
    cleanup();
  });

  it("renders review page, filters, and alert card fields", () => {
    render(<SetupAlertReviewPage />);

    expect(screen.getByTestId("setup-alert-review-page")).toBeInTheDocument();
    expect(screen.getByText("Setup Alert Review")).toBeInTheDocument();
    expect(screen.getByTestId("setup-alert-review-filters")).toBeInTheDocument();
    expect(screen.getByTestId("setup-alert-condition")).toHaveTextContent("Order block");
    expect(screen.getByTestId("setup-alert-confidence")).toHaveTextContent("88%");
    expect(screen.getByTestId("setup-alert-reason")).toHaveTextContent(
      "Bullish order block retest.",
    );
    expect(screen.getByTestId("setup-alert-trigger")).toHaveTextContent("65,000");
    expect(screen.getByTestId("setup-alert-invalidation")).toHaveTextContent("64,000");
    expect(screen.getByTestId("setup-alert-latest-price")).toHaveTextContent("65,100");
    expect(
      screen.getByText(/never sends Telegram messages or places orders/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/send to telegram/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/place order/i)).not.toBeInTheDocument();
  });

  it("updates review status via save action", async () => {
    const { api } = await import("@/lib/api");
    render(<SetupAlertReviewPage />);

    fireEvent.change(screen.getByTestId("setup-alert-review-status"), {
      target: { value: "watching" },
    });
    fireEvent.click(screen.getByTestId("setup-alert-save"));

    await waitFor(() => {
      expect(api.alerts.updateSetupReview).toHaveBeenCalledWith("alert-1", {
        review_status: "watching",
        review_notes: null,
      });
    });
  });

  it("supports quick review actions", async () => {
    const { api } = await import("@/lib/api");
    render(<SetupAlertReviewPage />);

    fireEvent.click(screen.getByTestId("quick-action-important"));

    await waitFor(() => {
      expect(api.alerts.updateSetupReview).toHaveBeenCalledWith("alert-1", {
        review_status: "important",
        review_notes: null,
      });
    });
  });
});
