import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TopBar } from "@/components/layout/TopBar";
import { ShellFreshnessProvider } from "@/contexts/ShellFreshnessContext";

const posture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

const navigationState = {
  pathname: "/",
};

vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    refreshStatus: vi.fn(),
    loading: false,
    killSwitchActive: false,
    killSwitchStatus: {
      organization_id: "org",
      active: false,
      reason: null,
      activated_by: null,
      activated_at: null,
      deactivated_by: null,
      deactivated_at: null,
      version: 1,
      scope: "organization",
      global_active: false,
      execution_blocked: false,
    },
    killSwitchError: null,
    health: { status: "ok", version: "0.1", execution_mode: "paper", real_trading_enabled: false },
    providers: { providers: [] },
  }),
  useMockProviders: () => [],
  useSafetyPosture: () => posture,
}));

const logout = vi.fn();

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "trader@example.com" },
    organization: { name: "Alpha Org" },
    logout,
  }),
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill</button>,
}));

function renderTopBar() {
  return render(
    <ShellFreshnessProvider>
      <div className="w-[390px]">
        <TopBar />
      </div>
    </ShellFreshnessProvider>,
  );
}

describe("TopBar status strip PaperModeIndicator", () => {
  beforeEach(() => {
    posture.executionMode = "paper";
    posture.realTradingEnabled = false;
    posture.postureKnown = true;
    navigationState.pathname = "/";
    logout.mockReset();
  });

  afterEach(() => cleanup());

  it("shows confirmed paper when /health verifies paper posture", () => {
    renderTopBar();
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
    renderTopBar();
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("fails closed when real trading is enabled", () => {
    posture.realTradingEnabled = true;
    renderTopBar();
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("fails closed for non-paper execution mode", () => {
    posture.executionMode = "live";
    renderTopBar();
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("keeps real-trading-disabled and advice messaging in the status strip", () => {
    renderTopBar();
    expect(screen.getByText("Real OFF")).toBeInTheDocument();
    expect(screen.getByTestId("status-strip-advice")).toHaveTextContent("Paper-only research");
  });
});

describe("TopBar page identity and account control", () => {
  beforeEach(() => {
    posture.executionMode = "paper";
    posture.realTradingEnabled = false;
    posture.postureKnown = true;
    navigationState.pathname = "/";
    logout.mockReset();
  });

  afterEach(() => cleanup());

  it("shows Dashboard title", () => {
    navigationState.pathname = "/";
    renderTopBar();
    expect(within(screen.getByTestId("topbar-page-identity")).getByText("Dashboard")).toBeInTheDocument();
  });

  it("shows Signals title", () => {
    navigationState.pathname = "/tradingview-signals";
    renderTopBar();
    expect(within(screen.getByTestId("topbar-page-identity")).getByText("Signals")).toBeInTheDocument();
  });

  it("shows nested Alerts Review breadcrumb subtitle", () => {
    navigationState.pathname = "/alerts/review";
    renderTopBar();
    const identity = screen.getByTestId("topbar-page-identity");
    expect(identity).toHaveTextContent("Signals");
    expect(screen.getByTestId("topbar-page-subtitle")).toHaveTextContent("Signals / Setup Review");
  });

  it("falls back safely for validation candidate detail", () => {
    navigationState.pathname = "/paper-validation/candidates/cand-123";
    renderTopBar();
    const identity = screen.getByTestId("topbar-page-identity");
    expect(identity).toHaveTextContent("Validate");
    expect(screen.getByTestId("topbar-page-subtitle")).toHaveTextContent("Candidates");
  });

  it("falls back for unknown routes", () => {
    navigationState.pathname = "/not-a-known-route";
    renderTopBar();
    expect(within(screen.getByTestId("topbar-page-identity")).getByText("Workspace")).toBeInTheDocument();
  });

  it("does not fabricate freshness claims", () => {
    renderTopBar();
    expect(screen.getByTestId("topbar-freshness")).toHaveTextContent("Freshness unavailable");
    expect(screen.queryByTestId("freshness-pill")).not.toBeInTheDocument();
  });

  it("keeps account control and logout accessible", () => {
    renderTopBar();
    fireEvent.click(screen.getByRole("button", { name: "Account menu" }));
    const menu = screen.getByRole("menu", { name: "Account" });
    expect(within(menu).getByText("trader@example.com")).toBeInTheDocument();
    expect(within(menu).getByText("Alpha Org")).toBeInTheDocument();
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Log out" }));
    expect(logout).toHaveBeenCalled();
  });

  it("avoids horizontal overflow at mobile width", () => {
    renderTopBar();
    const header = screen.getByRole("banner");
    expect(header.className).toContain("overflow");
    expect(screen.getByTestId("topbar-page-identity").className).toContain("min-w-0");
    expect(screen.getByTestId("topbar-account-control")).toBeInTheDocument();
  });
});
