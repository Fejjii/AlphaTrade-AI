import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  SendAlertToTelegramButton,
  TelegramManualDeliveryPanel,
} from "./TelegramManualDelivery";

const routingAvailable = {
  alerts_enabled: true,
  telegram_enabled: false,
  telegram_configured: true,
  telegram_chat_configured: true,
  manual_test_available: true,
  telegram_alert_delivery_available: true,
  telegram_delivered_count: 0,
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
  warnings: [],
  generated_at: new Date().toISOString(),
};

const alert = {
  id: "alert-1",
  alert_type: "setup_signal_detected",
  severity: "info",
  message: "Setup on BTCUSDT",
  delivery_status: "disabled",
  delivery_channel: "in_app",
  alert_source: "paper_validation_runtime",
  created_at: new Date().toISOString(),
};

vi.mock("@/lib/api", () => ({
  api: {
    alerts: {
      deliverTelegram: vi.fn(),
    },
  },
}));

import { api } from "@/lib/api";

describe("TelegramManualDelivery Slice 70", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders manual delivery panel with badges", () => {
    render(<TelegramManualDeliveryPanel routing={routingAvailable} />);
    expect(screen.getByTestId("telegram-manual-delivery-panel")).toBeInTheDocument();
    expect(screen.getByText("Manual delivery only")).toBeInTheDocument();
    expect(screen.getByText("Worker disabled")).toBeInTheDocument();
  });

  it("renders send button disabled until confirmation", () => {
    render(
      <SendAlertToTelegramButton alert={alert} routing={routingAvailable} />,
    );
    expect(screen.getByTestId("send-alert-telegram-button")).toBeDisabled();
    fireEvent.change(screen.getByTestId("telegram-alert-confirm-input"), {
      target: { value: "DELIVER_TELEGRAM_ALERT" },
    });
    expect(screen.getByTestId("send-alert-telegram-button")).not.toBeDisabled();
  });

  it("shows success state", async () => {
    vi.mocked(api.alerts.deliverTelegram).mockResolvedValue({
      status: "sent",
      alert_id: alert.id,
      channel: "telegram",
      sent_at: new Date().toISOString(),
      delivery_id: "delivery-1",
    });
    render(
      <SendAlertToTelegramButton alert={alert} routing={routingAvailable} />,
    );
    fireEvent.change(screen.getByTestId("telegram-alert-confirm-input"), {
      target: { value: "DELIVER_TELEGRAM_ALERT" },
    });
    fireEvent.click(screen.getByTestId("send-alert-telegram-button"));
    await waitFor(() => {
      expect(screen.getByTestId("telegram-alert-delivery-result")).toHaveTextContent(
        "Sent to Telegram",
      );
    });
  });

  it("shows already delivered state", () => {
    render(
      <SendAlertToTelegramButton
        alert={{
          ...alert,
          delivery_channel: "telegram",
          delivery_status: "delivered",
          delivered_at: new Date().toISOString(),
        }}
        routing={routingAvailable}
      />,
    );
    expect(screen.getByTestId("telegram-already-delivered")).toHaveTextContent(
      "Already sent to Telegram",
    );
    expect(screen.queryByTestId("send-alert-telegram-button")).toBeNull();
  });

  it("shows redacted failure state", async () => {
    vi.mocked(api.alerts.deliverTelegram).mockResolvedValue({
      status: "failed_redacted",
      alert_id: alert.id,
      channel: "telegram",
      error_code: "telegram_delivery_failed",
      error_message: "Telegram HTTP 403 for chat ***8777",
    });
    render(
      <SendAlertToTelegramButton alert={alert} routing={routingAvailable} />,
    );
    fireEvent.change(screen.getByTestId("telegram-alert-confirm-input"), {
      target: { value: "DELIVER_TELEGRAM_ALERT" },
    });
    fireEvent.click(screen.getByTestId("send-alert-telegram-button"));
    await waitFor(() => {
      expect(screen.getByTestId("telegram-alert-delivery-result-error")).toHaveTextContent("403");
    });
    expect(screen.queryByText("bot123456789")).toBeNull();
  });

  it("does not render secrets", () => {
    render(
      <SendAlertToTelegramButton alert={alert} routing={routingAvailable} />,
    );
    expect(screen.queryByText(/bot\d+/)).toBeNull();
    expect(screen.queryByText(/\d{9,}/)).toBeNull();
  });
});
