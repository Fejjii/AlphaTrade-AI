import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DecisionMarketPage from "./page";

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    killSwitchActive: true,
    killSwitchStatus: { active: true, execution_blocked: true },
  }),
  useSafetyPosture: () => ({
    executionMode: "paper",
    realTradingEnabled: false,
    postureKnown: true,
  }),
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill switch</button>,
}));

describe("Decision market page", () => {
  afterEach(() => cleanup());

  it("separates market quality from eligibility and surfaces kill switch block", () => {
    render(<DecisionMarketPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Market assessment" })).toBeInTheDocument();
    expect(screen.getByTestId("action-eligibility-card")).toHaveTextContent(/kill switch/i);
    expect(screen.getByTestId("eligibility-headline")).toHaveTextContent(/blocked/i);
    expect(screen.queryByText(/live order/i)).not.toBeInTheDocument();
  });
});
