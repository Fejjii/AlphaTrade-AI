import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PaperModeBanner } from "@/components/PaperModeBanner";

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
    toggleKillSwitch: vi.fn(),
    refreshStatus: vi.fn(),
    loading: false,
    error: null,
  }),
  useSafetyPosture: () => ({
    executionMode: "paper",
    realTradingEnabled: false,
    providerMode: "mock",
  }),
}));

describe("PaperModeBanner", () => {
  it("shows paper mode and real trading disabled badges", () => {
    render(<PaperModeBanner />);
    expect(screen.getByText(/paper mode active/i)).toBeInTheDocument();
    expect(screen.getByText(/real trading disabled/i)).toBeInTheDocument();
  });

  it("does not expose real trading CTAs", () => {
    render(<PaperModeBanner />);
    expect(screen.queryByText(/place real order/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/execute live/i)).not.toBeInTheDocument();
  });
});
