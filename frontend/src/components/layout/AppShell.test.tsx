import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/layout/AppShell";
import { PRIMARY_DESTINATIONS } from "@/components/layout/navigation-config";

const posture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

vi.mock("next/navigation", () => ({
  usePathname: () => "/tradingview-signals",
}));

vi.mock("@/contexts/AppContext", () => ({
  AppProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
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
    health: { status: "ok" },
    providers: { providers: [] },
  }),
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

describe("AT-040 Phase B AppShell", () => {
  beforeEach(() => {
    posture.executionMode = "paper";
    posture.realTradingEnabled = false;
  });

  afterEach(() => cleanup());

  it("renders eight desktop primary destinations with accessible current page", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const sidebar = screen.getByTestId("desktop-sidebar");
    const links = within(sidebar).getAllByRole("link");
    expect(links).toHaveLength(8);
    for (const destination of PRIMARY_DESTINATIONS) {
      expect(within(sidebar).getByRole("link", { name: destination.ariaLabel })).toHaveAttribute(
        "href",
        destination.href,
      );
    }
    expect(within(sidebar).getByRole("link", { name: "Signals" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("renders mobile bottom navigation with Menu sheet destinations", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const bottom = screen.getByTestId("mobile-bottom-navigation");
    expect(within(bottom).getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(within(bottom).getByRole("link", { name: "Signals" })).toBeInTheDocument();
    expect(within(bottom).getByRole("link", { name: "Plan" })).toBeInTheDocument();
    expect(within(bottom).getByRole("link", { name: "Portfolio" })).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("mobile-menu-button"));
    const sheet = screen.getByTestId("mobile-menu-sheet");
    expect(within(sheet).getByRole("link", { name: "Validate" })).toBeInTheDocument();
    expect(within(sheet).getByRole("link", { name: "Journal" })).toBeInTheDocument();
    expect(within(sheet).getByRole("link", { name: "Analyze" })).toBeInTheDocument();
    expect(within(sheet).getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("closes the Menu sheet on Escape and returns focus to the Menu button", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const menuButton = screen.getByTestId("mobile-menu-button");
    menuButton.focus();
    fireEvent.click(menuButton);
    expect(screen.getByTestId("mobile-menu-sheet")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByTestId("mobile-menu-sheet")).not.toBeInTheDocument();
    expect(menuButton).toHaveFocus();
  });

  it("shows secondary navigation for the active destination including Advanced", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const secondary = screen.getByTestId("secondary-navigation");
    expect(secondary).toHaveAttribute("data-destination", "signals");
    expect(within(secondary).getByRole("link", { name: "Inbox" })).toBeInTheDocument();
    expect(within(secondary).getByText("Advanced")).toBeInTheDocument();
    expect(
      within(secondary).getByRole("link", { name: "Signal Orchestration" }),
    ).toHaveAttribute("href", "/paper-signal-orchestration");
  });

  it("keeps paper status fail-closed in the status strip", () => {
    posture.executionMode = null;
    posture.realTradingEnabled = null;
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const strip = screen.getByTestId("status-strip");
    expect(strip).toBeInTheDocument();
    expect(within(strip).getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("hides desktop and mobile nav from opposite breakpoints via CSS classes", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    expect(screen.getByTestId("desktop-sidebar").className).toContain("lg:flex");
    expect(screen.getByTestId("desktop-sidebar").className).toContain("hidden");
    expect(screen.getByTestId("mobile-bottom-navigation").className).toContain("lg:hidden");
  });

  it("applies safe-area padding on mobile bottom navigation", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    expect(screen.getByTestId("mobile-bottom-navigation").className).toContain(
      "safe-area-inset-bottom",
    );
  });
});
