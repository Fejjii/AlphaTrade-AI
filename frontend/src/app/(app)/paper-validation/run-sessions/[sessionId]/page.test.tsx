import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import type { PaperValidationRunSessionItem } from "@/lib/api/types";

import PaperValidationRunSessionDetailPage from "./page";

const {
  mockUseAsyncDataState,
  sampleSession,
} = vi.hoisted(() => {
  const session: PaperValidationRunSessionItem = {
    session_id: "session-1",
    run_plan_id: "plan-1",
    candidate_id: "candidate-1",
    draft_id: "draft-1",
    source_alert_id: "alert-1",
    symbol: "BTCUSDT",
    timeframe: "15m",
    condition: "order_block",
    direction: "long",
    risk_mode: "conservative",
    validation_window: "intraday",
    observation_timeframe: "1h",
    max_duration_minutes: 240,
    session_status: "running",
    notes: "Observation notes.",
    started_at: "2026-06-29T00:00:00Z",
    ended_at: null,
    created_at: "2026-06-29T00:00:00Z",
  };
  return {
    sampleSession: session,
    mockUseAsyncDataState: {
      data: session,
      loading: false,
      error: null as string | null,
      reload: vi.fn(),
    },
  };
});

const mockSessionObservations = vi.fn();
const mockGetSessionResult = vi.fn();
const mockRecordObservation = vi.fn();
const mockRecordSessionResult = vi.fn();
const mockUpdateRunSessionStatus = vi.fn();
const mockGetRunSession = vi.fn();
const mockReload = vi.fn();

mockUseAsyncDataState.reload = mockReload;

vi.mock("next/navigation", () => ({
  useParams: () => ({ sessionId: "session-1" }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => mockUseAsyncDataState,
}));

vi.mock("@/lib/api", () => ({
  ApiError,
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

describe("PaperValidationRunSessionDetailPage Slice 82/83 / Phase C2 honesty", () => {
  beforeEach(() => {
    mockUseAsyncDataState.data = sampleSession;
    mockUseAsyncDataState.loading = false;
    mockUseAsyncDataState.error = null;
    mockSessionObservations.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    mockGetSessionResult.mockRejectedValue(
      new ApiError("Session result not found.", 404, {}),
    );
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
        run_session_id: "session-1",
        run_plan_id: "plan-1",
        recorded_at: "2026-06-29T01:00:00Z",
        created_at: "2026-06-29T01:00:00Z",
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

  it("does not enable the recording form during the initial outcome load", async () => {
    let rejectResult!: (error: unknown) => void;
    mockGetSessionResult.mockImplementation(
      () =>
        new Promise((_, reject) => {
          rejectResult = reject;
        }),
    );
    render(<PaperValidationRunSessionDetailPage />);

    expect(screen.getByTestId("paper-run-session-result-loading")).toBeInTheDocument();
    expect(screen.getByTestId("outcome-result-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("paper-run-session-result-form")).not.toBeInTheDocument();
    expect(screen.queryByTestId("outcome-result-unavailable")).not.toBeInTheDocument();
    expect(screen.queryByTestId("outcome-retry-extras")).not.toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-mark-completed")).toBeDisabled();

    rejectResult(new ApiError("Session result not found.", 404, {}));
    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-result-form")).toBeInTheDocument();
    });
  });

  it("shows neutral observation loading without unavailable, retry, or false zero", async () => {
    let resolveObs!: (value: unknown) => void;
    mockSessionObservations.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveObs = resolve;
        }),
    );
    render(<PaperValidationRunSessionDetailPage />);

    expect(screen.getByTestId("paper-run-session-obs-loading")).toBeInTheDocument();
    expect(screen.getByTestId("outcome-obs-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("paper-run-session-obs-unavailable")).not.toBeInTheDocument();
    expect(screen.queryByTestId("outcome-obs-unavailable")).not.toBeInTheDocument();
    expect(screen.queryByTestId("paper-run-session-obs-retry")).not.toBeInTheDocument();
    expect(screen.queryByTestId("outcome-retry-extras")).not.toBeInTheDocument();
    expect(screen.queryByTestId("paper-run-session-obs-empty")).not.toBeInTheDocument();

    resolveObs({ items: [], total: 0, limit: 50, offset: 0 });
    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-obs-empty")).toHaveTextContent(
        /No observations recorded yet/i,
      );
    });
    expect(screen.getByTestId("outcome-observation-count")).toHaveTextContent("0");
  });

  it("shows the recording form only after confirmed 404 not-recorded", async () => {
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-result-form")).toBeInTheDocument();
    });
    expect(screen.getByTestId("paper-run-session-outcome-required")).toBeInTheDocument();
    expect(screen.getByTestId("outcome-not-recorded")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-mark-completed")).toBeDisabled();
    expect(screen.queryByTestId("paper-run-session-result-unavailable")).not.toBeInTheDocument();
  });

  it("shows Retry and keeps the recording form unavailable on non-404 failures", async () => {
    mockGetSessionResult.mockRejectedValue(new ApiError("server error", 500, {}));
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-result-unavailable")).toBeInTheDocument();
    });
    expect(screen.getByTestId("paper-run-session-result-retry")).toBeInTheDocument();
    expect(screen.queryByTestId("paper-run-session-result-form")).not.toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-outcome-unverified")).toHaveTextContent(
      /until outcome state is verified/i,
    );
    expect(screen.queryByTestId("outcome-not-recorded")).not.toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-mark-completed")).toBeDisabled();
  });

  it("does not show observation count 0 when observations fail", async () => {
    mockSessionObservations.mockRejectedValue(new Error("obs down"));
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-obs-unavailable")).toBeInTheDocument();
    });
    expect(screen.getByTestId("outcome-observation-count")).toHaveTextContent("unavailable");
    expect(screen.queryByText(/No observations recorded yet/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-obs-retry")).toBeInTheDocument();
  });

  it("shows retrying observation state without unavailable while pending", async () => {
    let resolveObsRetry!: (value: unknown) => void;
    mockSessionObservations
      .mockRejectedValueOnce(new Error("obs down"))
      .mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveObsRetry = resolve;
          }),
      );
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-obs-unavailable")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("paper-run-session-obs-retry"));
    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-obs-retrying")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("paper-run-session-obs-unavailable")).not.toBeInTheDocument();

    resolveObsRetry({ items: [], total: 0, limit: 50, offset: 0 });
    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-obs-empty")).toBeInTheDocument();
    });
  });

  it("shows retrying outcome state without unavailable while pending", async () => {
    let rejectResultRetry!: (error: unknown) => void;
    mockGetSessionResult
      .mockRejectedValueOnce(new ApiError("server error", 500, {}))
      .mockImplementation(
        () =>
          new Promise((_, reject) => {
            rejectResultRetry = reject;
          }),
      );
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-result-unavailable")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("paper-run-session-result-retry"));
    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-result-loading")).toHaveTextContent(
        /Retrying outcome source/i,
      );
      expect(screen.getByTestId("outcome-result-loading")).toHaveTextContent(
        /Retrying outcome source/i,
      );
    });
    expect(screen.queryByTestId("paper-run-session-result-unavailable")).not.toBeInTheDocument();
    expect(screen.queryByTestId("outcome-result-unavailable")).not.toBeInTheDocument();

    rejectResultRetry(new ApiError("Session result not found.", 404, {}));
    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-result-form")).toBeInTheDocument();
    });
  });

  it("retries extras without requiring main session reload", async () => {
    mockGetSessionResult.mockRejectedValueOnce(new ApiError("server error", 500, {}));
    mockGetSessionResult.mockRejectedValueOnce(
      new ApiError("Session result not found.", 404, {}),
    );
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("outcome-retry-extras")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("outcome-retry-extras"));
    await waitFor(() => {
      expect(screen.getByTestId("outcome-not-recorded")).toBeInTheDocument();
    });
    expect(mockReload).not.toHaveBeenCalled();
    expect(mockGetSessionResult.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("hides the recording form when an outcome is already recorded", async () => {
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
      expect(screen.getByTestId("paper-run-session-result-summary")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("paper-run-session-result-form")).not.toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-mark-completed")).not.toBeDisabled();
  });

  it("enables completion only after a newly recorded outcome succeeds", async () => {
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-result-form")).toBeInTheDocument();
    });
    expect(screen.getByTestId("paper-run-session-mark-completed")).toBeDisabled();

    fireEvent.change(screen.getByTestId("paper-run-session-result-confirm"), {
      target: { value: "RECORD_PAPER_VALIDATION_OUTCOME" },
    });
    fireEvent.click(screen.getByTestId("paper-run-session-result-submit"));

    await waitFor(() => {
      expect(mockRecordSessionResult).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-mark-completed")).not.toBeDisabled();
    });
    expect(screen.queryByTestId("paper-run-session-result-form")).not.toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-result-summary")).toBeInTheDocument();
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

  it("uses historical wording for completed sessions with no recorded outcome", async () => {
    mockUseAsyncDataState.data = {
      ...sampleSession,
      session_status: "completed",
      ended_at: "2026-06-29T02:00:00Z",
    };
    render(<PaperValidationRunSessionDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("paper-run-session-result-not-recorded")).toHaveTextContent(
        /No outcome was recorded for this completed session/i,
      );
    });
    expect(screen.queryByTestId("paper-run-session-outcome-required")).not.toBeInTheDocument();
    expect(screen.queryByText(/before marking completed/i)).not.toBeInTheDocument();
  });
});
