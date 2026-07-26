import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows/sourceResult";

import WorkspacePage from "./page";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "fallback",
};

const search = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => search,
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({ killSwitchActive: false }),
  useSafetyPosture: () => safetyPosture,
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

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(): SourceResult<T> {
  return { data: null, available: false, error: "down", fallbackUsed: false };
}

let asyncState = {
  data: {
    proposals: ok({ items: [proposal], total: 1, limit: 50, offset: 0 }),
    approvals: ok({
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
    }),
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
  safetyPosture.executionMode = "paper";
  safetyPosture.realTradingEnabled = false;
  search.delete("source");
  search.delete("signal");
  search.delete("alert");
  asyncState = {
    data: {
      proposals: ok({ items: [proposal], total: 1, limit: 50, offset: 0 }),
      approvals: ok({
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
      }),
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  };
});

describe("Plan hub Phase C1 corrections", () => {
  it("renders plan hierarchy with evidence and approval state", () => {
    render(<WorkspacePage />);
    expect(screen.getByTestId("plan-hub-page")).toBeInTheDocument();
    expect(screen.getByTestId("plan-summary")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-summary")).toHaveTextContent("Clear demand reclaim");
    expect(screen.getByTestId("plan-approval-state")).toHaveTextContent("pending");
    expect(screen.getByTestId("plan-runtime-posture")).toHaveTextContent("Paper only");
  });

  it("shows Risk BLOCK as final with no override control", () => {
    render(<WorkspacePage />);
    expect(screen.getByTestId("risk-block")).toHaveTextContent(/blocked/i);
    expect(screen.getByTestId("risk-block")).toHaveTextContent(/no override/i);
    expect(screen.queryByRole("button", { name: /override/i })).not.toBeInTheDocument();
  });

  it("shows runtime posture conflict when real trading is enabled", () => {
    safetyPosture.realTradingEnabled = true;
    render(<WorkspacePage />);
    expect(screen.getByTestId("plan-runtime-posture")).toHaveTextContent("Safety conflict");
    expect(screen.getByTestId("plan-safety-conflict")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-runtime-posture")).not.toHaveTextContent(/^Paper only$/);
  });

  it("shows unverified runtime posture without claiming paper only", () => {
    safetyPosture.executionMode = null;
    safetyPosture.realTradingEnabled = null;
    render(<WorkspacePage />);
    expect(screen.getByTestId("plan-runtime-posture")).toHaveTextContent(
      "Runtime posture unverified",
    );
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
  });

  it("shows planning-from-signal context from typed query", () => {
    search.set("source", "tradingview");
    search.set("signal", "sig-123");
    render(<WorkspacePage />);
    expect(screen.getByTestId("plan-signal-context")).toHaveTextContent("Planning from signal");
    expect(screen.getByTestId("plan-signal-context")).toHaveTextContent("tradingview");
    expect(screen.getByTestId("plan-signal-context")).toHaveTextContent("sig-123");
    expect(screen.getByRole("link", { name: /back to evidence/i })).toHaveAttribute(
      "href",
      "/tradingview-signals?signal=sig-123",
    );
  });

  it("does not claim empty plan when sources failed", () => {
    asyncState = {
      ...asyncState,
      data: {
        proposals: failed(),
        approvals: failed(),
      },
    };
    render(<WorkspacePage />);
    expect(screen.getByRole("heading", { name: /plan data unavailable/i })).toBeInTheDocument();
    expect(screen.queryByText(/no in-flight paper plan/i)).not.toBeInTheDocument();
  });

  it("keeps AI assist behind progressive disclosure", () => {
    render(<WorkspacePage />);
    expect(screen.queryByTestId("plan-hub-ai-assist")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /new plan \/ ai assist/i }));
    expect(screen.getByTestId("plan-hub-ai-assist")).toBeInTheDocument();
  });
});
