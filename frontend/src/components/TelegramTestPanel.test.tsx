import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TelegramTestPanel } from "./TelegramTestPanel";
import type { AlertRoutingSummary } from "@/lib/api/types";

const baseRouting: AlertRoutingSummary = {
  alerts_enabled: true,
  telegram_enabled: false,
  telegram_configured: false,
  telegram_chat_configured: false,
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
  readiness: "ready",
  automatic_telegram_delivery_ready: false,
  automatic_delivery_blockers: ["External delivery is not enabled for this environment."],
  eligible_pending_telegram_count: 0,
  already_delivered_telegram_count: 0,
  next_delivery_preview_count: 0,
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
      testTelegram: vi.fn(),
    },
  },
}));

import { api } from "@/lib/api";

describe("TelegramTestPanel Slice 69", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders Telegram test panel", () => {
    render(<TelegramTestPanel routing={baseRouting} />);
    expect(screen.getByTestId("telegram-test-panel")).toBeInTheDocument();
    expect(screen.getByText("Worker disabled")).toBeInTheDocument();
    expect(screen.getByText("Paper only")).toBeInTheDocument();
  });

  it("shows missing config state", () => {
    render(<TelegramTestPanel routing={baseRouting} />);
    expect(screen.getByTestId("telegram-configured-badge")).toHaveTextContent("missing token");
    expect(screen.getByTestId("telegram-chat-badge")).toHaveTextContent("Chat missing");
  });

  it("requires confirmation before enabling send", () => {
    render(<TelegramTestPanel routing={baseRouting} />);
    expect(screen.getByTestId("telegram-test-send")).toBeDisabled();
    fireEvent.change(screen.getByTestId("telegram-confirm-input"), {
      target: { value: "SEND_TEST_TELEGRAM" },
    });
    expect(screen.getByTestId("telegram-test-send")).not.toBeDisabled();
  });

  it("shows success state", async () => {
    vi.mocked(api.alerts.testTelegram).mockResolvedValue({
      status: "sent",
      telegram_configured: true,
      chat_configured: true,
      paper_only: true,
      external_delivery_enabled: false,
      sent_at: new Date().toISOString(),
    });
    render(<TelegramTestPanel routing={{ ...baseRouting, telegram_configured: true, telegram_chat_configured: true }} />);
    fireEvent.change(screen.getByTestId("telegram-confirm-input"), {
      target: { value: "SEND_TEST_TELEGRAM" },
    });
    fireEvent.click(screen.getByTestId("telegram-test-send"));
    await waitFor(() => {
      expect(screen.getByTestId("telegram-test-result")).toHaveTextContent("Test alert sent");
    });
  });

  it("shows redacted failure state", async () => {
    vi.mocked(api.alerts.testTelegram).mockResolvedValue({
      status: "failed_redacted",
      telegram_configured: true,
      chat_configured: true,
      paper_only: true,
      external_delivery_enabled: false,
      error_code: "telegram_delivery_failed",
      error_message: "Telegram HTTP 403 for chat ***8777",
    });
    render(<TelegramTestPanel routing={{ ...baseRouting, telegram_configured: true, telegram_chat_configured: true }} />);
    fireEvent.change(screen.getByTestId("telegram-confirm-input"), {
      target: { value: "SEND_TEST_TELEGRAM" },
    });
    fireEvent.click(screen.getByTestId("telegram-test-send"));
    await waitFor(() => {
      expect(screen.getByTestId("telegram-test-result-error")).toHaveTextContent("403");
    });
    expect(screen.queryByText("bot123456789")).toBeNull();
    expect(screen.queryByText("TESTTOKEN")).toBeNull();
  });

  it("does not render secrets in configured state", () => {
    render(
      <TelegramTestPanel
        routing={{
          ...baseRouting,
          telegram_configured: true,
          telegram_chat_configured: true,
        }}
      />,
    );
    expect(screen.queryByText(/bot\d+/)).toBeNull();
    expect(screen.queryByText(/\d{9,}/)).toBeNull();
  });
});
