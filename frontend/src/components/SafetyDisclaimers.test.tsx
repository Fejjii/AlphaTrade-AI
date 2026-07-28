import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SafetyDisclaimers } from "@/components/SafetyDisclaimers";

const posture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

vi.mock("@/contexts/AppContext", () => ({
  useSafetyPosture: () => posture,
}));

beforeEach(() => {
  posture.executionMode = "paper";
  posture.realTradingEnabled = false;
  posture.postureKnown = true;
});

afterEach(cleanup);

describe("SafetyDisclaimers", () => {
  it("renders the consistent global disclaimers with verified paper posture", () => {
    render(<SafetyDisclaimers />);
    const list = screen.getByTestId("safety-disclaimers");
    expect(list).toHaveTextContent("Not financial advice.");
    expect(list).toHaveTextContent("Paper trading only");
    expect(list).toHaveTextContent("Real trading is disabled.");
    expect(list).toHaveTextContent("Alerts do not execute trades.");
    expect(list).toHaveTextContent("AI explanations never override deterministic risk rules.");
  });

  it("does not assert paper-only or real-disabled while posture is unverified (FP2-104)", () => {
    posture.executionMode = null;
    posture.realTradingEnabled = null;
    posture.postureKnown = false;

    render(<SafetyDisclaimers />);
    const list = screen.getByTestId("safety-disclaimers");
    expect(list).toHaveTextContent("Runtime trading posture unverified");
    expect(list).not.toHaveTextContent("Paper trading only — no real orders are placed.");
    expect(list).not.toHaveTextContent("Real trading is disabled.");
    // Universal disclaimers still apply.
    expect(list).toHaveTextContent("Not financial advice.");
  });

  it("flags a verified non-paper posture instead of claiming paper-only", () => {
    posture.executionMode = "paper";
    posture.realTradingEnabled = true;
    posture.postureKnown = true;

    render(<SafetyDisclaimers />);
    const list = screen.getByTestId("safety-disclaimers");
    expect(list).toHaveTextContent("not confirmed as paper-only");
    expect(list).not.toHaveTextContent("Real trading is disabled.");
  });
});
