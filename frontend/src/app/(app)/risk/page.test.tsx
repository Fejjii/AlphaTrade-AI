import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RiskSettingsPage from "./page";

const settings = {
  organization_id: "org",
  user_id: "user",
  daily_loss_limit: "50",
  daily_target: "100",
  max_trades_per_day: 5,
  max_risk_per_trade_percent: "1",
  default_account_balance: "10000",
  timezone: "UTC",
  green_day_protection_enabled: true,
  one_loss_stop_enabled: false,
  overtrading_guard_enabled: true,
  notes: null,
  using_defaults: false,
  timezone_fallback: false,
};

const useAsyncDataMock = vi.fn();

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: (...args: unknown[]) => useAsyncDataMock(...args),
}));

vi.mock("@/lib/api", () => ({
  api: {
    risk: {
      settings: vi.fn(),
      updateSettings: vi.fn(),
      resetSettings: vi.fn(),
    },
  },
  ApiError: class ApiError extends Error {},
}));

vi.mock("@/components/ui/paper-mode-indicator", () => ({
  VerifiedPaperModeIndicator: () => <div data-testid="paper-mode-indicator">Paper</div>,
}));

describe("Risk settings route ownership", () => {
  afterEach(() => {
    cleanup();
    useAsyncDataMock.mockClear();
  });

  beforeEach(() => {
    useAsyncDataMock.mockReturnValue({
      data: settings,
      loading: false,
      error: null,
      reload: vi.fn(),
    });
  });

  it("keeps /risk reachable as configuration-only with link to Portfolio posture", () => {
    render(<RiskSettingsPage />);
    expect(screen.getByTestId("risk-settings-page")).toBeInTheDocument();
    expect(screen.getByTestId("risk-settings-form-card")).toBeInTheDocument();
    expect(screen.getByTestId("risk-settings-portfolio-link")).toHaveAttribute("href", "/portfolio");
    expect(screen.getByTestId("risk-settings-ownership")).toHaveTextContent(/configuration only/i);
    expect(screen.getByTestId("risk-daily-loss-limit")).toBeInTheDocument();
    expect(screen.getByTestId("paper-mode-indicator")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-hub-safety")).not.toBeInTheDocument();
    expect(screen.queryByTestId("paper-mode-banner")).not.toBeInTheDocument();
  });

  it("renders loading and error states", () => {
    useAsyncDataMock.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      reload: vi.fn(),
    });
    const { rerender } = render(<RiskSettingsPage />);
    expect(screen.getByText(/loading risk settings/i)).toBeInTheDocument();

    useAsyncDataMock.mockReturnValue({
      data: null,
      loading: false,
      error: "settings down",
      reload: vi.fn(),
    });
    rerender(<RiskSettingsPage />);
    expect(screen.getByText(/settings down/i)).toBeInTheDocument();
  });
});
