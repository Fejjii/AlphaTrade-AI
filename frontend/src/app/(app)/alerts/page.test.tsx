import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AlertsPage from "./page";

let hookCall = 0;

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => {
    hookCall += 1;
    const index = (hookCall - 1) % 3;
    if (index === 1) {
      return {
        data: { unread: 1, total: 2 },
        loading: false,
        error: null,
        reload: vi.fn(),
      };
    }
    if (index === 2) {
      return {
        data: {
          delivery_enabled: false,
          effective_external_enabled: false,
          webhook_enabled: false,
          channels: ["in_app"],
          paper_only: true,
        },
        loading: false,
        error: null,
        reload: vi.fn(),
      };
    }
    return {
      data: {
        items: [
          {
            id: "alert-1",
            alert_type: "setup_signal_detected",
            severity: "info",
            message: "Setup on BTCUSDT",
            delivery_status: "disabled",
            delivery_channel: "in_app",
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
      },
      loading: false,
      error: null,
      reload: vi.fn(),
    };
  },
}));

describe("AlertsPage Slice 41", () => {
  beforeEach(() => {
    hookCall = 0;
  });

  afterEach(() => {
    cleanup();
  });

  it("renders delivery status", () => {
    render(<AlertsPage />);
    expect(screen.getByTestId("alert-delivery-status")).toHaveTextContent("in_app");
    expect(screen.getByTestId("alert-delivery-status")).toHaveTextContent("disabled");
  });

  it("renders external delivery disabled copy", () => {
    render(<AlertsPage />);
    expect(screen.getByTestId("alerts-delivery-disabled-copy")).toHaveTextContent("disabled");
    expect(screen.getByTestId("alerts-in-app-copy")).toHaveTextContent("In-app alerts are active");
  });

  it("does not render manual delivery when external disabled", () => {
    render(<AlertsPage />);
    expect(screen.queryByTestId("deliver-pending-alerts")).toBeNull();
    expect(screen.queryByTestId("deliver-alert-button")).toBeNull();
  });

  it("renders paper only disclaimer", () => {
    render(<AlertsPage />);
    expect(screen.getByTestId("alerts-paper-only-disclaimer")).toHaveTextContent("No real trades");
  });
});
