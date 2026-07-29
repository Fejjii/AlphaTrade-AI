import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RecentResultLoad } from "@/components/validate/sessionExtras";
import type { SourceResult } from "@/components/workflows/sourceResult";
import type {
  PaperValidationRunSessionItem,
  PaperValidationSessionResultItem,
} from "@/lib/api/types";

import ValidateHubPage from "./page";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "fallback",
};

const setFreshness = vi.fn();

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({ killSwitchActive: false }),
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/contexts/ShellFreshnessContext", () => ({
  useShellFreshness: () => ({
    freshness: { state: null },
    setFreshness,
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

const runningSession: PaperValidationRunSessionItem = {
  session_id: "sess-1",
  run_plan_id: "plan-1",
  candidate_id: "cand-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "ETHUSDT",
  timeframe: "1h",
  condition: "fvg",
  direction: "short",
  risk_mode: "conservative",
  session_status: "running",
  started_at: "2026-07-26T13:00:00.000Z",
  created_at: "2026-07-26T13:00:00.000Z",
};

const completedSession: PaperValidationRunSessionItem = {
  ...runningSession,
  session_id: "sess-done",
  session_status: "completed",
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

function loadedResult(
  sessionId: string,
  item: PaperValidationSessionResultItem,
): RecentResultLoad {
  return recentResult(sessionId, {
    data: item,
    available: true,
    resultNotRecorded: false,
  });
}

function makeResult(sessionId: string, index: number): PaperValidationSessionResultItem {
  return {
    result_id: `res-${index}`,
    run_session_id: sessionId,
    run_plan_id: "plan-1",
    outcome: "success",
    success_criteria_met: "met",
    failure_criteria_met: "not_met",
    invalidation_hit: false,
    entry_assessment: "entered_as_planned",
    discipline_assessment: "disciplined",
    recorded_at: "2026-07-26T14:00:00.000Z",
    created_at: "2026-07-26T14:00:00.000Z",
  };
}

function fiveCompleted(): PaperValidationRunSessionItem[] {
  return Array.from({ length: 5 }, (_, i) => ({
    ...completedSession,
    session_id: `sess-${i}`,
  }));
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
  setFreshness.mockClear();
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
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
    expect(screen.queryByTestId("portfolio-hub-safety")).not.toBeInTheDocument();

    cleanup();
    safetyPosture.executionMode = null;
    safetyPosture.realTradingEnabled = false;
    render(<ValidateHubPage />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
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

  it("treats five loaded outcomes as complete coverage without partial warning", () => {
    const completed = fiveCompleted();
    asyncState = {
      ...asyncState,
      data: {
        ...asyncState.data,
        runSessions: ok({ items: completed, total: 5, limit: 50, offset: 0 }),
        recentResults: completed.map((session, index) =>
          loadedResult(session.session_id, makeResult(session.session_id, index)),
        ),
      },
    };
    render(<ValidateHubPage />);
    expect(screen.queryByTestId("validate-hub-partial")).not.toBeInTheDocument();
    expect(screen.getByTestId("validate-outcome-coverage")).toHaveTextContent(/Coverage: complete/i);
    expect(screen.getByTestId("validation-stage-outcome")).toHaveTextContent(
      /5 of 5 recent outcomes loaded/i,
    );
    expect(setFreshness).toHaveBeenCalled();
    // Complete coverage must not force page-level unavailable the way partial does.
    expect(setFreshness.mock.calls.some((call) => call[0]?.state === "unavailable")).toBe(false);
  });

  it("marks partial coverage with Outcomes warning, Retry, 3 of 5 label, and non-Live freshness", () => {
    const completed = fiveCompleted();
    asyncState = {
      ...asyncState,
      data: {
        ...asyncState.data,
        runSessions: ok({ items: completed, total: 5, limit: 50, offset: 0 }),
        recentResults: [
          loadedResult("sess-0", makeResult("sess-0", 0)),
          loadedResult("sess-1", makeResult("sess-1", 1)),
          loadedResult("sess-2", makeResult("sess-2", 2)),
          recentResult("sess-3", { available: false, error: "down" }),
          recentResult("sess-4", { available: false, error: "down" }),
        ],
      },
    };
    render(<ValidateHubPage />);
    const partial = screen.getByTestId("validate-hub-partial");
    expect(partial).toHaveTextContent(/Outcomes/i);
    expect(within(partial).getByRole("button", { name: /^Retry$/i })).toBeInTheDocument();
    expect(screen.getByTestId("validation-stage-outcome")).toHaveTextContent(
      /3 of 5 recent outcomes loaded/i,
    );
    expect(screen.getByTestId("validate-outcome-coverage")).toHaveTextContent(/Coverage: partial/i);
    expect(screen.getByTestId("validate-recent-outcome-sess-0")).toHaveTextContent(/success/i);
    expect(screen.getByTestId("validate-recent-outcome-sess-3")).toHaveTextContent(
      /result unavailable/i,
    );
    expect(setFreshness.mock.calls.some((call) => call[0]?.state === "live")).toBe(false);
    expect(setFreshness.mock.calls.some((call) => call[0]?.state === "unavailable")).toBe(true);
  });

  it("marks all failed probes as unavailable without a confirmed zero", () => {
    const completed = fiveCompleted();
    asyncState = {
      ...asyncState,
      data: {
        ...asyncState.data,
        runSessions: ok({ items: completed, total: 5, limit: 50, offset: 0 }),
        recentResults: completed.map((session) =>
          recentResult(session.session_id, { available: false, error: "down" }),
        ),
      },
    };
    render(<ValidateHubPage />);
    const partial = screen.getByTestId("validate-hub-partial");
    expect(partial).toHaveTextContent(/Outcomes/i);
    expect(within(partial).getByRole("button", { name: /^Retry$/i })).toBeInTheDocument();
    expect(screen.getByTestId("validation-stage-outcome")).toHaveTextContent(
      /Outcome results unavailable/i,
    );
    expect(screen.getByTestId("validation-stage-count-outcome")).toHaveTextContent("unavailable");
    expect(screen.getByTestId("validate-outcome-coverage")).toHaveTextContent(
      /Coverage: unavailable/i,
    );
  });

  it("classifies confirmed 404s as not recorded complete coverage", () => {
    const completed = fiveCompleted();
    asyncState = {
      ...asyncState,
      data: {
        ...asyncState.data,
        runSessions: ok({ items: completed, total: 5, limit: 50, offset: 0 }),
        recentResults: completed.map((session) =>
          recentResult(session.session_id, {
            available: true,
            resultNotRecorded: true,
            data: null,
          }),
        ),
      },
    };
    render(<ValidateHubPage />);
    expect(screen.queryByTestId("validate-hub-partial")).not.toBeInTheDocument();
    expect(screen.getByTestId("validate-outcome-coverage")).toHaveTextContent(/Coverage: complete/i);
    expect(screen.getByTestId("validate-outcome-coverage")).toHaveTextContent(/Not recorded:\s*5/i);
    expect(screen.getByTestId("validate-recent-outcome-sess-0")).toHaveTextContent(/not recorded/i);
  });

  it("uses not_applicable with honest zero and no false Outcomes warning", () => {
    render(<ValidateHubPage />);
    expect(screen.queryByTestId("validate-hub-partial")).not.toBeInTheDocument();
    expect(screen.queryByTestId("validate-outcome-coverage")).not.toBeInTheDocument();
    expect(screen.getByTestId("validation-stage-outcome")).toHaveTextContent(
      /No completed sessions/i,
    );
    expect(screen.getByTestId("validation-stage-count-outcome")).toHaveTextContent("Count: 0");
  });
});
