import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AutomaticTelegramDeliveryReadinessPanel,
  PreviewTelegramDeliveryButton,
} from "./AutomaticTelegramDeliveryReadiness";

const routing = {
  alerts_enabled: true,
  telegram_enabled: false,
  telegram_configured: true,
  telegram_chat_configured: true,
  manual_test_available: true,
  telegram_alert_delivery_available: true,
  telegram_delivered_count: 2,
  telegram_failed_count: 0,
  webhook_enabled: false,
  external_delivery_enabled: false,
  paper_only: true,
  quiet_hours: { enabled: false, start: null, end: null, timezone: "UTC", source: "none" },
  severity_filters: [],
  pending_alerts_count: 0,
  delivered_alerts_count: 0,
  failed_alerts_count: 0,
  market_watcher_configured: false,
  market_watcher_running: false,
  bridge_enabled: false,
  bridge_running: false,
  worker_enabled: false,
  worker_running: false,
  readiness: "ready" as const,
  automatic_telegram_delivery_ready: false,
  automatic_delivery_blockers: [
    "External alert delivery is disabled (ALERT_DELIVERY_ENABLED=false).",
    "Telegram is disabled in user notification preferences.",
  ],
  eligible_pending_telegram_count: 1,
  already_delivered_telegram_count: 2,
  next_delivery_preview_count: 1,
  delivery_limits: {
    max_preview_limit: 25,
    default_preview_limit: 5,
    max_automatic_batch_limit: 10,
  },
  dry_run_supported: true,
  warnings: [],
  generated_at: new Date().toISOString(),
};

vi.mock("@/lib/api", () => ({
  api: {
    alerts: {
      previewDelivery: vi.fn(),
    },
  },
}));

import { api } from "@/lib/api";

describe("AutomaticTelegramDeliveryReadiness Slice 71", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders readiness panel with badges and blockers", () => {
    render(<AutomaticTelegramDeliveryReadinessPanel routing={routing} />);
    expect(screen.getByTestId("automatic-telegram-readiness-panel")).toBeInTheDocument();
    expect(screen.getByText("Worker disabled")).toBeInTheDocument();
    expect(screen.getByText("Dry-run supported")).toBeInTheDocument();
    expect(screen.getByTestId("automatic-delivery-blockers")).toBeInTheDocument();
    expect(screen.getByTestId("eligible-pending-count")).toHaveTextContent("1");
    expect(screen.getByTestId("already-delivered-count")).toHaveTextContent("2");
  });

  it("renders preview results without send button", async () => {
    vi.mocked(api.alerts.previewDelivery).mockResolvedValue({
      channel: "telegram",
      eligible_count: 1,
      skipped_count: 0,
      already_delivered_count: 1,
      items: [
        {
          alert_id: "alert-1",
          alert_type: "setup_signal_detected",
          severity: "info",
          message_preview: "Setup on BTCUSDT",
          created_at: new Date().toISOString(),
          status: "eligible",
          reason: "Eligible for automatic Telegram delivery preview.",
        },
      ],
      warnings: [],
      generated_at: new Date().toISOString(),
    });
    render(<PreviewTelegramDeliveryButton />);
    expect(screen.queryByTestId("send-alert-telegram-button")).toBeNull();
    fireEvent.click(screen.getByTestId("preview-telegram-delivery-button"));
    await waitFor(() => {
      expect(screen.getByTestId("preview-results")).toBeInTheDocument();
    });
    expect(screen.getByTestId("preview-eligible-count")).toHaveTextContent("Eligible: 1");
  });

  it("does not render secrets", () => {
    render(<AutomaticTelegramDeliveryReadinessPanel routing={routing} />);
    expect(screen.queryByText(/bot\d+/)).toBeNull();
  });
});
