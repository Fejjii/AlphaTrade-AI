import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RecentResultLoad } from "@/components/validate/sessionExtras";
import type { SourceResult } from "@/components/workflows/sourceResult";

import ValidateHubPage from "./page";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "fallback",
};

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({ killSwitchActive: false }),
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/contexts/ShellFreshnessContext", () => ({
  useShellFreshness: () => ({
    freshness: { state: null },
    setFreshness: vi.fn(),
    clearFreshness: vi.fn(),
  }),
}));

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(): SourceResult<T> {
  return { data: null, available: false, error: "down", fallbackUsed: false };
}

const checklist = {
  trend_checked: true,
  support_resistance_checked: true,
  volume_checked: true,
  risk_reward_checked: true,
  invalidation_checked: true,
  higher_timeframe_checked: true,
  news_or_funding_checked: true,
};

const draft = {
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "BTCUSDT",
  timeframe: "15m",
  condition: "order_block",
  direction: "long",
  confidence: 0.8,
  risk_mode: "conservative" as const,
  status: "draft" as const,
  created_at: "2026-07-26T10:00:00.000Z",
  prep_status: "ready_for_validation" as const,
  checklist,
  prep_completion_score: 100,
  missing_checklist_items: [] as string[],
  is_ready_for_validation: true,
  thesis: "Thesis",
  entry_criteria: "Entry",
  invalidation_criteria: "Invalidation",
};

const candidate = {
  candidate_id: "cand-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "ETHUSDT",
  timeframe: "1h",
  condition: "fvg",
  direction: "short",
  confidence: 0.7,
  checklist_snapshot: checklist,
  risk_mode: "conservative" as const,
  candidate_status: "reviewing" as const,
  created_at: "2026-07-26T11:00:00.000Z",
};

const plan = {
  plan_id: "plan-1",
  candidate_id: "cand-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "ETHUSDT",
  timeframe: "1h",
  condition: "fvg",
  direction: "short",
  checklist_snapshot: checklist,
  risk_mode: "conservative" as const,
  plan_status: "planned" as const,
  validation_window: "intraday",
  observation_timeframe: "1h",
  max_duration_minutes: 240,
  planned_entry_rule: "Enter",
  planned_invalidation_rule: "Invalidate",
  planned_success_criteria: "Success",
  planned_failure_criteria: "Failure",
  created_at: "2026-07-26T12:00:00.000Z",
};

const runningSession = {
  session_id: "sess-1",
  run_plan_id: "plan-1",
  candidate_id: "cand-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "ETHUSDT",
  timeframe: "1h",
  condition: "fvg",
  direction: "short",
  risk_mode: "conservative" as const,
  session_status: "running" as const,
  started_at: "2026-07-26T13:00:00.000Z",
  created_at: "2026-07-26T13:00:00.000Z",
};

const completedSession = {
  ...runningSession,
  session_id: "sess-done",
  session_status: "completed" as const,
  ended_at: "2026-07-26T15:00:00.000Z",
};

function recentResult(
  sessionId: string,
  overrides: Partial<RecentResultLoad> = {},
): RecentResultLoad {
  return {
    sessionId,
    data: null,
    available: true,
    error: null,
    fallbackUsed: false,
    resultNotRecorded: false,
    ...overrides,
  };
}

let asyncState = {
  data: {
    drafts: ok({ items: [draft], total: 1, limit: 50, offset: 0 }),
    candidates: ok({ items: [candidate], total: 1, limit: 50, offset: 0 }),
    runPlans: ok({ items: [plan], total: 1, limit: 50, offset: 0 }),
    runSessions: ok({ items: [runningSession], total: 1, limit: 50, offset: 0 }),
    recentResults: [] as RecentResultLoad[],
  },
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => asyncState,
}));

afterEach(() => {
  cleanup();
  safetyPosture.executionMode = "paper";
  safetyPosture.realTradingEnabled = false;
  asyncState = {
    data: {
      drafts: ok({ items: [draft], total: 1, limit: 50, offset: 0 }),
      candidates: ok({ items: [candidate], total: 1, limit: 50, offset: 0 }),
      runPlans: ok({ items: [plan], total: 1, limit: 50, offset: 0 }),
      runSessions: ok({ items: [runningSession], total: 1, limit: 50, offset: 0 }),
      recentResults: [],
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  };
});

describe("ValidateHubPage Phase C2", () => {
  it("renders pipeline overview, counts, attention, and active sessions", () => {
    render(<ValidateHubPage />);

    expect(screen.getByTestId("validate-hub-page")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Validate" })).toBeInTheDocument();
    expect(screen.getByTestId("validation-pipeline")).toBeInTheDocument();
    expect(screen.getByTestId("validation-pipeline-stages").children).toHaveLength(6);
    expect(screen.getByTestId("validate-stage-counts")).toBeInTheDocument();
    expect(screen.getByTestId("validation-attention-queue")).toBeInTheDocument();
    expect(screen.getByTestId("validate-active-sessions")).toBeInTheDocument();
    expect(screen.getByTestId("paper-run-session-sess-1")).toBeInTheDocument();
    expect(screen.getByTestId("validate-limitations")).toBeInTheDocument();
    expect(screen.getByTestId("validation-source-availability")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /override/i })).not.toBeInTheDocument();
  });

  it("shows partial source availability without zeroing failed counts", () => {
    asyncState = {
      ...asyncState,
      data: {
        ...asyncState.data,
        candidates: failed(),
        runSessions: failed(),
      },
    };
    render(<ValidateHubPage />);
    expect(screen.getByTestId("validate-hub-partial")).toBeInTheDocument();
    const candidateCard = screen.getByTestId("validation-summary-candidates");
    expect(within(candidateCard).getByTestId("validation-summary-unavailable")).toHaveTextContent(
      "unavailable",
    );
    expect(screen.queryByText("Count: 0")).not.toBeInTheDocument();
  });

  it("fails closed on contradictory paper posture", () => {
    safetyPosture.executionMode = "paper";
    safetyPosture.realTradingEnabled = true;
    render(<ValidateHubPage />);
    expect(screen.getByTestId("validate-safety-conflict")).toHaveTextContent(/Safety conflict/i);
    expect(screen.queryByRole("button", { name: /override/i })).not.toBeInTheDocument();
  });

  it("keeps paper-confirmed wording only for verified paper posture", () => {
    render(<ValidateHubPage />);
    expect(screen.getByTestId("validate-safety-strip")).toHaveTextContent("PAPER mode");
    expect(screen.getByTestId("validate-safety-strip")).toHaveTextContent("Real trading disabled");

    cleanup();
    safetyPosture.executionMode = null;
    safetyPosture.realTradingEnabled = false;
    render(<ValidateHubPage />);
    expect(screen.getByTestId("validate-safety-strip")).toHaveTextContent(
      /Paper mode not confirmed|Execution unverified|Runtime posture/,
    );
  });

  it("preserves existing validation stage routes in stage nav", () => {
    render(<ValidateHubPage />);
    const nav = screen.getByTestId("validate-stage-nav");
    expect(within(nav).getByRole("link", { name: "Drafts" })).toHaveAttribute(
      "href",
      "/paper-validation/drafts",
    );
    expect(within(nav).getByRole("link", { name: "Candidates" })).toHaveAttribute(
      "href",
      "/paper-validation/candidates",
    );
    expect(within(nav).getByRole("link", { name: "Run plans" })).toHaveAttribute(
      "href",
      "/paper-validation/run-plans",
    );
    expect(within(nav).getByRole("link", { name: "Run sessions" })).toHaveAttribute(
      "href",
      "/paper-validation/run-sessions",
    );
  });

  it("shows honest outcome coverage and Outcomes partial-data when result probes fail", () => {
    asyncState = {
      ...asyncState,
      data: {
        ...asyncState.data,
        runSessions: ok({
          items: [runningSession, completedSession, { ...completedSession, session_id: "sess-2" }],
          total: 3,
          limit: 50,
          offset: 0,
        }),
        recentResults: [
          recentResult("sess-done", {
            available: false,
            error: "down",
          }),
          recentResult("sess-2", {
            available: false,
            error: "down",
          }),
        ],
      },
    };
    render(<ValidateHubPage />);
    expect(screen.getByTestId("validate-hub-partial")).toHaveTextContent(/Outcomes/i);
    expect(screen.getByTestId("validate-outcome-coverage")).toHaveTextContent(
      /Unavailable:\s*2/i,
    );
    expect(screen.getByTestId("validate-recent-outcome-sess-done")).toHaveTextContent(
      /result unavailable/i,
    );
    expect(screen.queryByText("Count: 0")).not.toBeInTheDocument();
  });

  it("labels confirmed missing outcomes as not recorded", () => {
    asyncState = {
      ...asyncState,
      data: {
        ...asyncState.data,
        runSessions: ok({ items: [completedSession], total: 1, limit: 50, offset: 0 }),
        recentResults: [
          recentResult("sess-done", {
            available: true,
            resultNotRecorded: true,
            data: null,
          }),
        ],
      },
    };
    render(<ValidateHubPage />);
    expect(screen.getByTestId("validate-recent-outcome-sess-done")).toHaveTextContent(
      /not recorded/i,
    );
    expect(screen.queryByText(/result unavailable/i)).not.toBeInTheDocument();
  });
});
