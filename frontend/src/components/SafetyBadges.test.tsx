import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PaperModeBanner } from "@/components/PaperModeBanner";

const posture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    health: { status: "ok", version: "0.1", execution_mode: "paper", real_trading_enabled: false },
    providers: {
      providers: [
        {
          name: "mock_exchange",
          kind: "exchange",
          health: "healthy",
          using_fallback: false,
          is_mock: true,
          detail: "Paper only",
        },
      ],
    },
    killSwitchActive: false,
    killSwitchStatus: null,
    killSwitchError: null,
    killSwitchBusy: false,
    refreshKillSwitch: vi.fn(),
    setKillSwitchActive: vi.fn(),
    refreshStatus: vi.fn(),
    loading: false,
    error: null,
  }),
  useSafetyPosture: () => posture,
}));

describe("PaperModeBanner", () => {
  beforeEach(() => {
    posture.executionMode = "paper";
    posture.realTradingEnabled = false;
    posture.postureKnown = true;
  });

  afterEach(() => {
    cleanup();
  });

  it("shows paper mode and real trading disabled badges when /health confirms paper", () => {
    render(<PaperModeBanner />);
    expect(screen.getByText(/paper mode active/i)).toBeInTheDocument();
    expect(screen.getByText(/real trading disabled/i)).toBeInTheDocument();
  });

  it("does not expose real trading CTAs", () => {
    render(<PaperModeBanner />);
    expect(screen.queryByText(/place real order/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/execute live/i)).not.toBeInTheDocument();
  });

  it("never claims paper mode before /health is loaded", () => {
    posture.executionMode = null;
    posture.realTradingEnabled = null;
    posture.postureKnown = false;
    render(<PaperModeBanner />);
    expect(screen.queryByText(/paper mode active/i)).not.toBeInTheDocument();
    expect(screen.getByText(/execution mode unverified/i)).toBeInTheDocument();
  });

  it("alerts instead of claiming paper mode when /health reports real trading enabled", () => {
    posture.realTradingEnabled = true;
    render(<PaperModeBanner />);
    expect(screen.queryByText(/paper mode active/i)).not.toBeInTheDocument();
    expect(screen.getByText(/paper-only posture not confirmed/i)).toBeInTheDocument();
    expect(screen.getByText(/real trading enabled/i)).toBeInTheDocument();
  });

  it("alerts when /health reports a non-paper execution mode", () => {
    posture.executionMode = "live";
    render(<PaperModeBanner />);
    expect(screen.queryByText(/paper mode active/i)).not.toBeInTheDocument();
    expect(screen.getByText(/paper-only posture not confirmed/i)).toBeInTheDocument();
    expect(screen.getByText("LIVE")).toBeInTheDocument();
  });
});
