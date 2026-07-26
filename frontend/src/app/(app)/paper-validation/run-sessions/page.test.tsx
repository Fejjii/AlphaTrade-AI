import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows/sourceResult";

import PaperValidationRunSessionsPage from "./page";

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

const sampleSession = {
  session_id: "session-1",
  run_plan_id: "plan-1",
  candidate_id: "candidate-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "BTCUSDT",
  timeframe: "15m",
  condition: "order_block",
  direction: "long",
  risk_mode: "conservative" as const,
  validation_window: "intraday",
  observation_timeframe: "1h",
  max_duration_minutes: 240,
  session_status: "running" as const,
  notes: "Observation notes.",
  started_at: "2026-06-29T00:00:00Z",
  ended_at: null,
  created_at: "2026-06-29T00:00:00Z",
};

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      runSessions: ok({ items: [sampleSession], total: 1, limit: 50, offset: 0 }),
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("PaperValidationRunSessionsPage Slice 82 / Phase C2", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders run session list with active state and without execution UI", () => {
    render(<PaperValidationRunSessionsPage />);

    expect(screen.getByTestId("paper-validation-run-sessions-page")).toBeInTheDocument();
    expect(screen.getByTestId("paper-validation-run-sessions-list")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-session-1")).toBeInTheDocument();
    expect(screen.getByText(/record only/i)).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-status-session-1")).toHaveTextContent("running");
    expect(screen.getByTestId("paper-run-session-next-session-1")).toHaveTextContent(
      /Record observations/i,
    );
    expect(screen.getAllByText("Paper only").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /deliver telegram/i })).not.toBeInTheDocument();
  });
});
