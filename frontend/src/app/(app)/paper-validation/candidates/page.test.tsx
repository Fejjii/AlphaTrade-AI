import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows/sourceResult";

import PaperValidationCandidatesPage from "./page";

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

const sampleCandidate = {
  candidate_id: "candidate-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "BTCUSDT",
  timeframe: "15m",
  condition: "order_block",
  direction: "long",
  confidence: 0.88,
  trigger_level: 65000,
  invalidation_level: 64000,
  latest_price: 65100,
  thesis: "Queued thesis.",
  entry_criteria: "Entry rules",
  invalidation_criteria: "Invalidation rules",
  risk_notes: "Risk notes",
  checklist_snapshot: {
    trend_checked: true,
    support_resistance_checked: true,
    volume_checked: true,
    risk_reward_checked: true,
    invalidation_checked: true,
    higher_timeframe_checked: true,
    news_or_funding_checked: true,
  },
  risk_mode: "conservative" as const,
  candidate_status: "queued" as const,
  created_at: "2026-06-28T12:00:00Z",
};

const activePlan = {
  plan_id: "plan-active-1",
  candidate_id: "candidate-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "BTCUSDT",
  timeframe: "15m",
  condition: "order_block",
  direction: "long",
  checklist_snapshot: sampleCandidate.checklist_snapshot,
  risk_mode: "conservative" as const,
  plan_status: "planned" as const,
  validation_window: "intraday",
  observation_timeframe: "1h",
  max_duration_minutes: 240,
  planned_entry_rule: "Enter",
  planned_invalidation_rule: "Invalidate",
  planned_success_criteria: "Success",
  planned_failure_criteria: "Failure",
  created_at: "2026-06-28T13:00:00Z",
};

const archivedPlan = {
  ...activePlan,
  plan_id: "plan-archived-1",
  plan_status: "archived" as const,
  created_at: "2026-06-29T13:00:00Z",
};

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(): SourceResult<T> {
  return { data: null, available: false, error: "down", fallbackUsed: false };
}

let asyncState = {
  data: {
    candidates: ok({ items: [sampleCandidate], total: 1, limit: 50, offset: 0 }),
    runPlans: ok({ items: [] as typeof activePlan[], total: 0, limit: 50, offset: 0 }),
  },
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => asyncState,
}));

describe("PaperValidationCandidatesPage Slice 80 / Phase C2", () => {
  afterEach(() => {
    cleanup();
    asyncState = {
      data: {
        candidates: ok({ items: [sampleCandidate], total: 1, limit: 50, offset: 0 }),
        runPlans: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      },
      loading: false,
      error: null,
      reload: vi.fn(),
    };
  });

  it("renders candidate list without run or execution UI", () => {
    render(<PaperValidationCandidatesPage />);

    expect(screen.getByTestId("paper-validation-candidates-page")).toBeInTheDocument();
    expect(screen.getByTestId("paper-validation-candidates-list")).toBeInTheDocument();
    expect(screen.getByTestId("paper-candidate-candidate-1")).toBeInTheDocument();
    expect(screen.getByText(/queue only/i)).toBeInTheDocument();
    expect(screen.getByTestId("paper-candidate-status-candidate-1")).toHaveTextContent("queued");
    expect(screen.getByTestId("paper-candidate-next-candidate-1")).toHaveTextContent(/reviewing/i);
    expect(screen.getByTestId("paper-candidate-run-plan-candidate-1")).toHaveTextContent(
      /no active run plan/i,
    );
    expect(screen.queryByRole("button", { name: /start run/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send to telegram/i })).not.toBeInTheDocument();
  });

  it("links an active run plan preferentially over archived plans", () => {
    asyncState = {
      ...asyncState,
      data: {
        candidates: ok({ items: [sampleCandidate], total: 1, limit: 50, offset: 0 }),
        runPlans: ok({ items: [archivedPlan, activePlan], total: 2, limit: 50, offset: 0 }),
      },
    };
    render(<PaperValidationCandidatesPage />);

    const link = screen.getByTestId("paper-candidate-run-plan-link-candidate-1");
    expect(link).toHaveAttribute("href", "/paper-validation/run-plans/plan-active-1");
    expect(link).toHaveTextContent(/planned/i);
    expect(link).not.toHaveTextContent(/historical/i);
  });

  it("labels a sole archived plan as historical", () => {
    asyncState = {
      ...asyncState,
      data: {
        candidates: ok({ items: [sampleCandidate], total: 1, limit: 50, offset: 0 }),
        runPlans: ok({ items: [archivedPlan], total: 1, limit: 50, offset: 0 }),
      },
    };
    render(<PaperValidationCandidatesPage />);

    const link = screen.getByTestId("paper-candidate-run-plan-link-candidate-1");
    expect(link).toHaveAttribute("href", "/paper-validation/run-plans/plan-archived-1");
    expect(link).toHaveTextContent(/historical/i);
  });

  it("shows partial-data warning and source-unavailable relation when run plans fail", () => {
    asyncState = {
      ...asyncState,
      data: {
        candidates: ok({ items: [sampleCandidate], total: 1, limit: 50, offset: 0 }),
        runPlans: failed(),
      },
      reload: vi.fn(),
    };
    render(<PaperValidationCandidatesPage />);

    expect(screen.getByTestId("candidates-run-plans-partial")).toHaveTextContent(
      /run-plan relationships are unavailable/i,
    );
    expect(screen.getByTestId("paper-candidate-run-plan-candidate-1")).toHaveTextContent(
      /relationship source unavailable/i,
    );
    fireEvent.click(screen.getByRole("button", { name: /^Retry$/i }));
    expect(asyncState.reload).toHaveBeenCalled();
  });
});
