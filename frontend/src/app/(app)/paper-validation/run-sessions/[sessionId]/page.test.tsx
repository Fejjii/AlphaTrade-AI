import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PaperValidationRunSessionDetailPage from "./page";

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

vi.mock("next/navigation", () => ({
  useParams: () => ({ sessionId: "session-1" }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: sampleSession,
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    strategies: {
      getRunSession: vi.fn(),
      updateRunSessionStatus: vi.fn(),
    },
  },
}));

describe("PaperValidationRunSessionDetailPage Slice 82", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders run session detail with record-only safety copy and no execution UI", () => {
    render(<PaperValidationRunSessionDetailPage />);

    expect(screen.getByTestId("paper-validation-run-session-detail")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-safety-copy")).toHaveTextContent(/record only/i);
    expect(screen.getByTestId("paper-run-session-safety-copy")).toHaveTextContent(/no live run/i);
    expect(screen.getByTestId("paper-run-session-safety-copy")).toHaveTextContent(/no telegram/i);
    expect(screen.getByTestId("paper-run-session-mark-completed")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-mark-cancelled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /deliver telegram/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute live/i })).not.toBeInTheDocument();
  });
});
