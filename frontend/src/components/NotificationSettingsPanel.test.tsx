import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NotificationSettingsPanel } from "./NotificationSettingsPanel";

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: (loader: () => unknown) => {
    const key = loader.toString();
    if (key.includes("deliveryStatus")) {
      return {
        data: {
          channel_statuses: [
            {
              channel: "webhook",
              env_enabled: false,
              user_enabled: false,
              configured: false,
              available: false,
              status_label: "disabled",
            },
            {
              channel: "telegram",
              env_enabled: false,
              user_enabled: false,
              configured: false,
              available: false,
              status_label: "disabled",
            },
          ],
        },
        loading: false,
        error: null,
        reload: vi.fn(),
      };
    }
    return {
      data: {
        in_app_enabled: true,
        webhook_enabled: false,
        telegram_enabled: false,
        min_severity: "info",
        using_defaults: true,
      },
      loading: false,
      error: null,
      reload: vi.fn(),
    };
  },
}));

vi.mock("@/lib/api", () => ({
  api: {
    notifications: {
      preferences: vi.fn(),
      updatePreferences: vi.fn(),
      sendTest: vi.fn(),
    },
    alerts: {
      deliveryStatus: vi.fn(),
    },
  },
}));

describe("NotificationSettingsPanel Slice 46", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders notification settings", () => {
    render(<NotificationSettingsPanel />);
    expect(screen.getByTestId("notification-settings-panel")).toBeInTheDocument();
  });

  it("renders provider disabled status", () => {
    render(<NotificationSettingsPanel />);
    expect(screen.getByTestId("provider-webhook")).toHaveTextContent("Disabled");
  });

  it("renders telegram toggle", () => {
    render(<NotificationSettingsPanel />);
    expect(screen.getByTestId("telegram-toggle")).toBeInTheDocument();
  });

  it("renders webhook toggle", () => {
    render(<NotificationSettingsPanel />);
    expect(screen.getByTestId("webhook-toggle")).toBeInTheDocument();
  });

  it("renders send test notification button", () => {
    render(<NotificationSettingsPanel />);
    expect(screen.getByTestId("send-test-notification")).toBeInTheDocument();
  });

  it("renders never-trade copy", () => {
    render(<NotificationSettingsPanel />);
    expect(screen.getByTestId("notifications-never-trade-copy")).toHaveTextContent(
      "never execute trades",
    );
  });
});
