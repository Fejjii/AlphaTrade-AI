import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/(app)/settings/page";

vi.mock("@/components/PaperModeBanner", () => ({
  PaperModeBanner: () => null,
}));

vi.mock("@/components/NotificationSettingsPanel", () => ({
  NotificationSettingsPanel: () => null,
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "owner@example.com", email_verified: true },
    organization: { name: "Alpha Org" },
  }),
}));

const posture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

vi.mock("@/contexts/AppContext", () => ({
  useSafetyPosture: () => posture,
}));

vi.mock("@/lib/config", () => ({
  appConfig: {
    apiBaseUrl: "http://localhost:8000",
    executionMode: "paper",
    providerMode: "mock",
  },
}));

beforeEach(() => {
  posture.executionMode = "paper";
  posture.realTradingEnabled = false;
  posture.postureKnown = true;
});

afterEach(cleanup);

describe("SettingsPage", () => {
  it("shows email verification status", () => {
    render(<SettingsPage />);
    expect(screen.getByText(/Email verified/i)).toBeInTheDocument();
    expect(screen.getByText(/Yes/)).toBeInTheDocument();
  });

  it("shows verified runtime posture when /health confirms paper (FP2-104)", () => {
    render(<SettingsPage />);
    expect(screen.getByTestId("settings-posture-execution")).toHaveTextContent(
      "Execution: PAPER",
    );
    expect(screen.getByTestId("settings-posture-real-trading")).toHaveTextContent(
      "Real trading: disabled",
    );
    expect(screen.getByTestId("settings-runtime-posture")).toHaveTextContent(
      "Confirmed from live backend health status.",
    );
  });

  it("shows explicit unverified posture until /health loads (FP2-104)", () => {
    posture.executionMode = null;
    posture.realTradingEnabled = null;
    posture.postureKnown = false;

    render(<SettingsPage />);
    expect(screen.getByTestId("settings-posture-execution")).toHaveTextContent(
      "Execution: unverified",
    );
    expect(screen.getByTestId("settings-posture-real-trading")).toHaveTextContent(
      "Real trading: unverified",
    );
    // The build-config card never masquerades as verified runtime state.
    expect(screen.getByTestId("settings-build-config")).toHaveTextContent(
      "Build configuration (not runtime-verified)",
    );
    expect(screen.queryByText("Runtime configuration")).not.toBeInTheDocument();
  });

  it("labels build-config values distinctly from runtime posture (FP2-104)", () => {
    render(<SettingsPage />);
    const buildCard = screen.getByTestId("settings-build-config");
    expect(buildCard).toHaveTextContent("Execution mode (build config): paper");
    expect(buildCard).toHaveTextContent("Provider mode (build config): mock");
  });
});
