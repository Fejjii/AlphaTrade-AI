import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TopBar } from "@/components/layout/TopBar";

const posture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    refreshStatus: vi.fn(),
    loading: false,
    killSwitchActive: false,
    health: { status: "ok", version: "0.1", execution_mode: "paper", real_trading_enabled: false },
    providers: { providers: [] },
  }),
  useMockProviders: () => [],
  useSafetyPosture: () => posture,
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "trader@example.com" },
    organization: { name: "Alpha Org" },
    logout: vi.fn(),
  }),
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill</button>,
}));

vi.mock("@/components/RiskBadge", () => ({
  RiskBadge: () => <span>Risk</span>,
}));

describe("TopBar status strip PaperModeIndicator", () => {
  beforeEach(() => {
    posture.executionMode = "paper";
    posture.realTradingEnabled = false;
    posture.postureKnown = true;
  });

  afterEach(() => cleanup());

  it("shows confirmed paper when /health verifies paper posture", () => {
    render(<TopBar />);
    expect(screen.getByTestId("status-strip")).toBeInTheDocument();
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });

  it("fails closed when safety posture is missing", () => {
    posture.executionMode = null;
    posture.realTradingEnabled = null;
    posture.postureKnown = false;
    render(<TopBar />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("fails closed when real trading is enabled", () => {
    posture.realTradingEnabled = true;
    render(<TopBar />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("fails closed for non-paper execution mode", () => {
    posture.executionMode = "live";
    render(<TopBar />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("keeps real-trading-disabled and advice messaging in the status strip", () => {
    render(<TopBar />);
    expect(screen.getByText("Real OFF")).toBeInTheDocument();
    expect(screen.getByTestId("status-strip-advice")).toHaveTextContent("Not financial advice");
  });
});
