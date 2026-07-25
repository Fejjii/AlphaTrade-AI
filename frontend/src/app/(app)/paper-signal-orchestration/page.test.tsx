import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PaperSignalOrchestrationPage from "./page";
import { APPROVE_PAPER_SIGNAL_PROPOSAL } from "@/lib/api";
import type { PaperSignalOrchestrationListResponse } from "@/lib/api/types";

const DECISION_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc";

const sampleList: PaperSignalOrchestrationListResponse = {
  items: [
    {
      id: DECISION_ID,
      organization_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      tradingview_signal_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      idempotency_key: "pso:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      status: "awaiting_review",
      mode: "approval_required",
      symbol: "BTCUSDT",
      timeframe: "15m",
      direction: "long",
      reason_codes: [],
      reason_summary: "Signal eligible for paper orchestration.",
      eligibility_checks: [
        { code: "signal_validated", passed: true, detail: "ok" },
        { code: "signal_fresh", passed: true, detail: "fresh" },
      ],
      risk_checks: [{ code: "kill_switch_clear", passed: true, detail: "clear" }],
      transitions: [
        {
          at: "2026-07-25T12:00:00Z",
          from_status: "eligible",
          to_status: "awaiting_review",
          reason: "approval_required_mode",
          actor_user_id: null,
        },
      ],
      links: {
        tradingview_signal_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        setup_definition_id: null,
        strategy_id: null,
        strategy_version_id: null,
        journal_trade_id: null,
        backtest_run_id: null,
        candidate_id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
        run_plan_id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        proposal_id: null,
        signal_path: "/tradingview-signals?id=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        candidate_path: "/paper-validation/candidates/dddddddd-dddd-dddd-dddd-dddddddddddd",
        run_plan_path: "/paper-validation/run-plans/eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        proposal_path: null,
        journal_path: null,
      },
      decided_by: null,
      approved_by: null,
      decided_at: "2026-07-25T12:00:00Z",
      expired_at: null,
      approved_at: null,
      created_at: "2026-07-25T12:00:00Z",
      updated_at: "2026-07-25T12:00:00Z",
      note: "Paper-signal orchestration only.",
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
  mode: "approval_required",
  enabled: true,
};

const mockReload = vi.fn();
const mockList = vi.fn();
const mockApprove = vi.fn();

let asyncState: {
  data: { forbidden: boolean; data: PaperSignalOrchestrationListResponse | null } | null;
  loading: boolean;
  error: string | null;
};

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({ health: null, providers: { providers: [] } }),
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: asyncState.data,
    loading: asyncState.loading,
    error: asyncState.error,
    reload: mockReload,
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      paperSignalOrchestration: {
        listDecisions: (...args: unknown[]) => mockList(...args),
        approvePaperProposal: (...args: unknown[]) => mockApprove(...args),
      },
    },
  };
});

describe("PaperSignalOrchestrationPage", () => {
  beforeEach(() => {
    mockList.mockReset();
    mockApprove.mockReset();
    mockReload.mockReset();
    safetyPosture.executionMode = "paper";
    safetyPosture.realTradingEnabled = false;
    safetyPosture.postureKnown = true;
    asyncState = {
      data: { forbidden: false, data: sampleList },
      loading: false,
      error: null,
    };
  });

  afterEach(() => {
    cleanup();
  });

  it("shows paper mode only when runtime safety is verified", () => {
    render(<PaperSignalOrchestrationPage />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });

  it("fails closed when runtime safety is missing", () => {
    safetyPosture.executionMode = null;
    safetyPosture.realTradingEnabled = null;
    safetyPosture.postureKnown = false;
    render(<PaperSignalOrchestrationPage />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("renders queue and progressive disclosure for checks", () => {
    render(<PaperSignalOrchestrationPage />);
    expect(screen.getByTestId("paper-signal-orch-page")).toBeInTheDocument();
    expect(screen.getByTestId("paper-signal-orch-queue")).toBeInTheDocument();
    expect(screen.getByTestId("paper-signal-orch-detail")).toHaveTextContent("BTCUSDT");
    expect(screen.queryByTestId("paper-signal-orch-checks")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Show eligibility/i }));
    expect(screen.getByTestId("paper-signal-orch-checks")).toBeInTheDocument();
    expect(screen.getByText(/kill_switch_clear/)).toBeInTheDocument();
  });

  it("shows forbidden state", () => {
    asyncState = { data: { forbidden: true, data: null }, loading: false, error: null };
    render(<PaperSignalOrchestrationPage />);
    expect(screen.getByTestId("paper-signal-orch-forbidden")).toBeInTheDocument();
  });

  it("requires exact confirm phrase before approve", async () => {
    mockApprove.mockResolvedValue({
      decision: sampleList.items[0],
      proposal_id: "ffffffff-ffff-ffff-ffff-ffffffffffff",
      already_exists: false,
      note: "ok",
    });
    render(<PaperSignalOrchestrationPage />);
    const approve = screen.getByRole("button", { name: /Approve paper proposal/i });
    expect(approve).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Approval confirmation/i), {
      target: { value: APPROVE_PAPER_SIGNAL_PROPOSAL },
    });
    expect(approve).not.toBeDisabled();
    fireEvent.click(approve);
    expect(mockApprove).toHaveBeenCalledWith(DECISION_ID, {
      confirm: APPROVE_PAPER_SIGNAL_PROPOSAL,
    });
  });

  it("shows empty state", () => {
    asyncState = {
      data: {
        forbidden: false,
        data: { ...sampleList, items: [], total: 0 },
      },
      loading: false,
      error: null,
    };
    render(<PaperSignalOrchestrationPage />);
    expect(screen.getByText(/No orchestration decisions/i)).toBeInTheDocument();
  });
});
