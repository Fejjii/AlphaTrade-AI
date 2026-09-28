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

const navigationState = { pathname: "/tradingview-signals" };

vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
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
    navigationState.pathname = "/tradingview-signals";
  });

  afterEach(() => cleanup());

  it("renders five desktop primary destinations and highlights Settings on retained routes", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const sidebar = screen.getByTestId("desktop-sidebar");
    const links = within(sidebar).getAllByRole("link");
    expect(links).toHaveLength(5);
    for (const destination of PRIMARY_DESTINATIONS) {
      expect(within(sidebar).getByRole("link", { name: destination.ariaLabel })).toHaveAttribute(
        "href",
        destination.href,
      );
    }
    expect(within(sidebar).getByRole("link", { name: "Settings" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("renders five mobile tabs and no engineering menu sheet", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const bottom = screen.getByTestId("mobile-bottom-navigation");
    expect(within(bottom).getAllByRole("link")).toHaveLength(5);
    expect(within(bottom).getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(within(bottom).getByRole("link", { name: "Agent" })).toHaveAttribute("href", "/agent");
    expect(within(bottom).getByRole("link", { name: "Strategies" })).toHaveAttribute(
      "href",
      "/strategies",
    );
    expect(within(bottom).getByRole("link", { name: "Journal" })).toHaveAttribute("href", "/journal");
    expect(within(bottom).getByRole("link", { name: "Settings" })).toHaveAttribute(
      "href",
      "/settings",
    );
    expect(within(bottom).getByRole("link", { name: "Settings" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.queryByTestId("mobile-menu-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("mobile-menu-sheet")).not.toBeInTheDocument();
  });

  it("opens the command menu from the phone search control", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    fireEvent.click(screen.getByTestId("topbar-search"));
    expect(screen.getByTestId("command-menu")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Strategy Lab/i })).toBeInTheDocument();
  });

  it("shows Account and Advanced under Settings", () => {
    navigationState.pathname = "/settings";
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const secondary = screen.getByTestId("secondary-navigation");
    expect(secondary).toHaveAttribute("data-destination", "settings");
    expect(within(secondary).getByRole("link", { name: "Account" })).toHaveAttribute(
      "href",
      "/settings",
    );
    expect(within(secondary).getByRole("link", { name: "Advanced" })).toHaveAttribute(
      "href",
      "/settings/advanced",
    );
  });

  it("marks Advanced current on a retained operational route", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const secondary = screen.getByTestId("secondary-navigation");
    expect(within(secondary).getByRole("link", { name: "Advanced" })).toHaveAttribute(
      "aria-current",
      "page",
    );
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

  it("renders a skip link that targets and focuses #main (FP2-113)", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const skipLink = screen.getByRole("link", { name: "Skip to main content" });
    expect(skipLink).toHaveAttribute("href", "#main");
    // Visually hidden until keyboard focus reveals it.
    expect(skipLink.className).toContain("sr-only");
    expect(skipLink.className).toContain("focus:not-sr-only");

    const main = document.getElementById("main");
    expect(main).not.toBeNull();
    expect(main).toHaveAttribute("tabindex", "-1");

    fireEvent.click(skipLink);
    expect(main).toHaveFocus();
  });

  it("gives every shell control a distinct accessible name (FP2-224)", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const names = screen
      .getAllByRole("button")
      .map((button) => button.getAttribute("aria-label") ?? button.textContent?.trim() ?? "")
      .filter((name) => /menu/i.test(name));
    expect(names.length).toBeGreaterThan(0);
    expect(new Set(names).size).toBe(names.length);
    expect(screen.getByRole("button", { name: "Account menu" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search pages and destinations" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open navigation menu" })).not.toBeInTheDocument();
  });

  it("announces posture politely from the status strip (FP2-114)", () => {
    render(
      <AppShell>
        <div>Page</div>
      </AppShell>,
    );
    const strip = screen.getByTestId("status-strip");
    expect(strip).toHaveAttribute("role", "status");
    expect(strip).toHaveAttribute("aria-live", "polite");
    expect(screen.getByTestId("status-strip-announcement")).toHaveTextContent(
      "Trading posture: execution PAPER, verified; real trading disabled; risk low.",
    );
  });
});
