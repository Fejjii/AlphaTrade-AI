import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

const mockSessionObservations = vi.fn();
const mockGetSessionResult = vi.fn();
const mockRecordObservation = vi.fn();
const mockRecordSessionResult = vi.fn();
const mockUpdateRunSessionStatus = vi.fn();
const mockGetRunSession = vi.fn();

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
      getRunSession: (...args: unknown[]) => mockGetRunSession(...args),
      updateRunSessionStatus: (...args: unknown[]) => mockUpdateRunSessionStatus(...args),
      sessionObservations: (...args: unknown[]) => mockSessionObservations(...args),
      getSessionResult: (...args: unknown[]) => mockGetSessionResult(...args),
      recordObservation: (...args: unknown[]) => mockRecordObservation(...args),
      recordSessionResult: (...args: unknown[]) => mockRecordSessionResult(...args),
    },
  },
}));

describe("PaperValidationRunSessionDetailPage Slice 82/83", () => {
  beforeEach(() => {
    mockSessionObservations.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    mockGetSessionResult.mockRejectedValue(new Error("not found"));
    mockRecordObservation.mockResolvedValue({
      observation_id: "obs-1",
      observation_kind: "general_note",
    });
    mockRecordSessionResult.mockResolvedValue({
      result: {
        result_id: "result-1",
        outcome: "success",
        success_criteria_met: "met",
        failure_criteria_met: "not_met",
        entry_assessment: "no_entry",
        discipline_assessment: "disciplined",
        invalidation_hit: false,
      },
      already_exists: false,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
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

  it("renders observation and result cards while running", async () => {
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-observations")).toBeInTheDocument();
    });
    expect(screen.getByTestId("paper-run-session-result")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-observation-form")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-result-form")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-outcome-required")).toBeInTheDocument();
  });

  it("disables observation submit until confirm phrase typed", async () => {
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-observation-submit")).toBeDisabled();
    });

    fireEvent.change(screen.getByTestId("paper-run-session-observation-confirm"), {
      target: { value: "RECORD_PAPER_VALIDATION_OBSERVATION" },
    });
    expect(screen.getByTestId("paper-run-session-observation-submit")).not.toBeDisabled();

    fireEvent.click(screen.getByTestId("paper-run-session-observation-submit"));
    await waitFor(() => {
      expect(mockRecordObservation).toHaveBeenCalledWith(
        "session-1",
        expect.objectContaining({
          confirm: "RECORD_PAPER_VALIDATION_OBSERVATION",
          observation_kind: "general_note",
        }),
      );
    });
  });

  it("disables mark completed until outcome exists", async () => {
    mockGetSessionResult.mockResolvedValue({
      result_id: "result-1",
      outcome: "success",
      success_criteria_met: "met",
      failure_criteria_met: "not_met",
      entry_assessment: "no_entry",
      discipline_assessment: "disciplined",
      invalidation_hit: false,
      recorded_at: "2026-06-29T01:00:00Z",
      created_at: "2026-06-29T01:00:00Z",
      run_session_id: "session-1",
      run_plan_id: "plan-1",
    });

    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-mark-completed")).not.toBeDisabled();
    });
    expect(screen.queryByTestId("paper-run-session-outcome-required")).not.toBeInTheDocument();
  });
});
