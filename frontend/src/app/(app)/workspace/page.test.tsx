import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import WorkspacePage from "./page";

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({ killSwitchActive: false }),
  useSafetyPosture: () => ({
    executionMode: "paper",
    realTradingEnabled: false,
    providerMode: "fallback",
  }),
}));

vi.mock("@/contexts/ShellFreshnessContext", () => ({
  useShellFreshness: () => ({
    freshness: { state: null },
    setFreshness: vi.fn(),
    clearFreshness: vi.fn(),
  }),
}));

const proposal = {
  id: "prop-1",
  organization_id: "org",
  user_id: "user",
  signal_id: null,
  strategy_id: "htf_trend_pullback",
  symbol: "BTCUSDT",
  timeframe: "1h",
  direction: "long",
  entry_price: "65000",
  position_size: "0.1",
  leverage: "1",
  exit: {
    invalidation: "64000",
    stop_loss: "64000",
    take_profits: [{ price: "67000", size_fraction: 1 }],
  },
  confidence: 0.7,
  risk_level: "medium",
  rationale: "Clear demand reclaim with defined invalidation.",
  status: "pending_approval",
  approval_required: true,
  risk_result: {
    action: "block",
    severity: "high",
    triggered_rules: [
      {
        rule_id: "daily_loss_lock",
        action: "block",
        severity: "high",
        message: "Daily loss lock is active.",
      },
    ],
    summary: "Blocked by daily loss lock.",
  },
  created_at: "2026-07-26T11:00:00.000Z",
};

let asyncState = {
  data: {
    proposals: { items: [proposal], total: 1, limit: 50, offset: 0 },
    approvals: {
      items: [
        {
          id: "appr-1",
          proposal_id: "prop-1",
          organization_id: "org",
          user_id: "user",
          status: "pending",
          risk_level: "medium",
          confidence: 0.7,
          created_at: "2026-07-26T11:01:00.000Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    },
  },
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => asyncState,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      chat: {
        message: vi.fn(),
      },
    },
  };
});

afterEach(() => {
  cleanup();
  asyncState = {
    ...asyncState,
    loading: false,
    error: null,
  };
});

describe("Plan hub Phase C1", () => {
  it("renders plan hierarchy with evidence and approval state", () => {
    render(<WorkspacePage />);
    expect(screen.getByTestId("plan-hub-page")).toBeInTheDocument();
    expect(screen.getByTestId("plan-summary")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-summary")).toHaveTextContent("Clear demand reclaim");
    expect(screen.getByText(/entry/i)).toBeInTheDocument();
    expect(screen.getByText("65000")).toBeInTheDocument();
    expect(screen.getByText(/approval: pending/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open proposal/i })).toHaveAttribute(
      "href",
      "/proposals?id=prop-1",
    );
  });

  it("shows Risk BLOCK as final with no override control", () => {
    render(<WorkspacePage />);
    expect(screen.getByTestId("risk-block")).toHaveTextContent(/blocked/i);
    expect(screen.getByTestId("risk-block")).toHaveTextContent(/no override/i);
    expect(screen.queryByRole("button", { name: /override/i })).not.toBeInTheDocument();
  });

  it("keeps consolidated Plan deep links reachable", () => {
    render(<WorkspacePage />);
    const nav = screen.getByRole("navigation", { name: "Plan hub sections" });
    expect(within(nav).getByRole("link", { name: "Proposals" })).toHaveAttribute(
      "href",
      "/proposals",
    );
    expect(within(nav).getByRole("link", { name: "Approvals" })).toHaveAttribute(
      "href",
      "/approvals",
    );
    expect(within(nav).getByRole("link", { name: "Pre-Trade" })).toHaveAttribute(
      "href",
      "/pre-trade",
    );
    expect(within(nav).getByRole("link", { name: "Manual Levels" })).toHaveAttribute(
      "href",
      "/manual-levels",
    );
    expect(within(nav).getByRole("link", { name: "Strategy Lab" })).toHaveAttribute(
      "href",
      "/strategy-lab",
    );
  });

  it("keeps AI assist behind progressive disclosure", () => {
    render(<WorkspacePage />);
    expect(screen.queryByTestId("plan-hub-ai-assist")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /new plan \/ ai assist/i }));
    expect(screen.getByTestId("plan-hub-ai-assist")).toBeInTheDocument();
  });
});
