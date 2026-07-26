import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StatusStrip } from "@/components/layout/StatusStrip";
import type { KillSwitchStatus } from "@/lib/api/types";

const posture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

const appState = {
  killSwitchStatus: null as KillSwitchStatus | null,
  killSwitchError: null as string | null,
  loading: false,
  killSwitchActive: false,
};

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => appState,
  useSafetyPosture: () => posture,
}));

describe("StatusStrip integration", () => {
  beforeEach(() => {
    posture.executionMode = "paper";
    posture.realTradingEnabled = false;
    posture.postureKnown = true;
    appState.killSwitchStatus = {
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
    };
    appState.killSwitchError = null;
    appState.loading = false;
    appState.killSwitchActive = false;
  });

  afterEach(() => cleanup());

  it("shows PAPER execution badge only when paper is confirmed", () => {
    render(<StatusStrip />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
    expect(within(screen.getByTestId("status-strip-execution")).getByText("PAPER")).toBeInTheDocument();
    expect(screen.getByText("Real OFF")).toBeInTheDocument();
    expect(within(screen.getByTestId("status-strip-risk")).getByText("Risk low")).toBeInTheDocument();
  });

  it("never shows PAPER badge when real trading is enabled", () => {
    posture.realTradingEnabled = true;
    render(<StatusStrip />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
    expect(within(screen.getByTestId("status-strip-execution")).getByText("Safety conflict")).toBeInTheDocument();
    expect(screen.queryByText("PAPER")).not.toBeInTheDocument();
    expect(screen.getByText("Real ON")).toBeInTheDocument();
  });

  it("shows Risk unknown when kill-switch status is missing", () => {
    appState.killSwitchStatus = null;
    appState.killSwitchActive = false;
    render(<StatusStrip />);
    expect(within(screen.getByTestId("status-strip-risk")).getByText("Risk unknown")).toBeInTheDocument();
    expect(screen.queryByText("Risk low")).not.toBeInTheDocument();
  });

  it("shows Risk unknown on kill-switch error", () => {
    appState.killSwitchStatus = null;
    appState.killSwitchError = "network failed";
    render(<StatusStrip />);
    expect(within(screen.getByTestId("status-strip-risk")).getByText("Risk unknown")).toBeInTheDocument();
  });

  it("shows Risk critical when kill switch blocks execution", () => {
    appState.killSwitchStatus = {
      ...appState.killSwitchStatus!,
      active: true,
      execution_blocked: true,
    };
    appState.killSwitchActive = true;
    render(<StatusStrip />);
    expect(within(screen.getByTestId("status-strip-risk")).getByText(/Risk critical/i)).toBeInTheDocument();
  });

  it("shows paper-only advice only when paper is confirmed", () => {
    render(<StatusStrip />);
    expect(screen.getByTestId("status-strip-advice")).toHaveTextContent("Paper-only research");
  });

  it("does not show paper-only advice when real trading is enabled", () => {
    posture.realTradingEnabled = true;
    render(<StatusStrip />);
    const advice = screen.getByTestId("status-strip-advice");
    expect(advice).not.toHaveTextContent(/paper-only research/i);
    expect(advice).toHaveTextContent(/Real trading appears enabled/i);
  });

  it("does not show paper-only advice for unknown posture", () => {
    posture.executionMode = null;
    posture.realTradingEnabled = null;
    posture.postureKnown = false;
    render(<StatusStrip />);
    const advice = screen.getByTestId("status-strip-advice");
    expect(advice).toHaveTextContent("Trading environment not verified");
    expect(advice).not.toHaveTextContent(/paper-only/i);
  });
});
