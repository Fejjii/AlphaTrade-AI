import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows/sourceResult";
import type { LessonCandidate, PaginatedLessonCandidates } from "@/lib/api/types";

import LessonsPage from "./page";
import { LessonAcceptPanel } from "@/components/lessons/LessonAcceptPanel";
import { PaperValidationPanel } from "@/components/strategy/PaperValidationPanel";
import { StrategyVersionHistory } from "@/components/strategy/StrategyVersionHistory";
import { StructuredRuleEditor } from "@/components/strategy/StructuredRuleEditor";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "fallback",
};

const search = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => search,
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    killSwitchActive: false,
    killSwitchBusy: false,
    killSwitchError: null,
    setKillSwitchActive: vi.fn(),
  }),
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

function failed<T>(error = "down"): SourceResult<T> {
  return { data: null, available: false, error, fallbackUsed: false };
}

function lesson(overrides: Partial<LessonCandidate> & { id: string }): LessonCandidate {
  return {
    organization_id: "org",
    user_id: "user",
    source_type: "runner_analysis",
    lesson_text: "Review runner rules before entry.",
    mistake_type: "early_exit",
    severity: "medium",
    status: "pending_review",
    proposed_rule_update: { summary: "Hold runner until structure break" },
    created_at: "2026-07-20T10:00:00.000Z",
    ...overrides,
  };
}

const pendingLesson = lesson({ id: "lesson-1" });
const acceptedLesson = lesson({
  id: "lesson-accepted",
  status: "accepted",
  reviewed_at: "2026-07-21T10:00:00.000Z",
});
const rejectedLesson = lesson({
  id: "lesson-rejected",
  status: "rejected",
  reviewed_at: "2026-07-22T10:00:00.000Z",
});

let asyncState = {
  data: {
    pending: ok<PaginatedLessonCandidates>({
      items: [pendingLesson],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    accepted: ok<PaginatedLessonCandidates>({
      items: [acceptedLesson],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    rejected: ok<PaginatedLessonCandidates>({
      items: [rejectedLesson],
      total: 1,
      limit: 50,
      offset: 0,
    }),
  } as {
    pending: SourceResult<PaginatedLessonCandidates>;
    accepted: SourceResult<PaginatedLessonCandidates>;
    rejected: SourceResult<PaginatedLessonCandidates>;
  } | null,
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

const acceptMock = vi.fn().mockResolvedValue({});
const rejectMock = vi.fn().mockResolvedValue({});
const getCandidateMock = vi.fn();

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => asyncState,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      strategies: {
        ...actual.api.strategies,
        list: vi.fn().mockResolvedValue({
          items: [{ id: "strategy-1", name: "HTF Pullback", current_version: 2 }],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      },
      lessons: {
        ...actual.api.lessons,
        listCandidates: vi.fn().mockImplementation(async ({ status }: { status?: string }) => {
          if (status === "rejected") {
            return asyncState.data?.rejected.data ?? { items: [], total: 0, limit: 50, offset: 0 };
          }
          return asyncState.data?.pending.data ?? { items: [], total: 0, limit: 50, offset: 0 };
        }),
        listAccepted: vi.fn().mockImplementation(async () => {
          return asyncState.data?.accepted.data ?? { items: [], total: 0, limit: 50, offset: 0 };
        }),
        accept: (...args: unknown[]) => acceptMock(...args),
        reject: (...args: unknown[]) => rejectMock(...args),
        getCandidate: (...args: unknown[]) => getCandidateMock(...args),
      },
    },
  };
});

function resetAsyncState() {
  asyncState = {
    data: {
      pending: ok({
        items: [pendingLesson],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      accepted: ok({
        items: [acceptedLesson],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      rejected: ok({
        items: [rejectedLesson],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  };
}

beforeEach(() => {
  resetAsyncState();
  safetyPosture.executionMode = "paper";
  safetyPosture.realTradingEnabled = false;
  search.forEach((_, key) => search.delete(key));
  acceptMock.mockClear();
  rejectMock.mockClear();
  getCandidateMock.mockReset();
  getCandidateMock.mockResolvedValue(pendingLesson);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LessonsPage hub", () => {
  it("renders loading state initially", () => {
    asyncState = { data: null, loading: true, error: null, reload: vi.fn() };
    render(<LessonsPage />);
    expect(screen.getByText(/loading lessons review hub/i)).toBeInTheDocument();
  });

  it("renders lessons review hub sections", async () => {
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-hub-page")).toBeInTheDocument();
    expect(screen.getByTestId("lessons-attention-queue")).toBeInTheDocument();
    expect(screen.getByTestId("lessons-recent-reviewed")).toBeInTheDocument();
    expect(screen.getByTestId("lessons-source-availability")).toBeInTheDocument();
  });

  it("shows honest empty attention queue", async () => {
    asyncState.data!.pending = ok({ items: [], total: 0, limit: 50, offset: 0 });
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-attention-empty")).toBeInTheDocument();
  });

  it("does not show empty queue when pending source failed", async () => {
    asyncState.data!.pending = failed("pending down");
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-attention-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("lessons-attention-empty")).not.toBeInTheDocument();
  });

  it("shows partial warning when rejected history fails", async () => {
    asyncState.data!.rejected = failed("rejected down");
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-recent-partial")).toBeInTheDocument();
    expect(screen.getByTestId("lessons-recent-item-lesson-accepted")).toBeInTheDocument();
  });

  it("shows recently reviewed accepted and rejected lessons", async () => {
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-recent-item-lesson-rejected")).toBeInTheDocument();
    expect(screen.getByTestId("lessons-recent-item-lesson-accepted")).toBeInTheDocument();
  });

  it("links journal entry when related_journal_entry_id exists", async () => {
    asyncState.data!.pending = ok({
      items: [lesson({ id: "lj", related_journal_entry_id: "entry-99" })],
      total: 1,
      limit: 50,
      offset: 0,
    });
    render(<LessonsPage />);
    const card = await screen.findByTestId("lessons-attention-item-lj");
    expect(within(card).getByRole("link", { name: /open/i })).toHaveAttribute(
      "href",
      "/journal?entry=entry-99",
    );
  });

  it("shows unavailable journal message when id missing", async () => {
    render(<LessonsPage />);
    const card = await screen.findByTestId("lessons-attention-item-lesson-1");
    expect(
      within(card).getByTestId("lesson-relationship-unavailable-journal"),
    ).toHaveTextContent(/no related_journal_entry_id/i);
  });

  it("shows stale message for invalid candidate deep link", async () => {
    search.set("candidate", "missing-lesson");
    getCandidateMock.mockRejectedValueOnce(new Error("not found"));
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-candidate-stale")).toHaveTextContent(
      /missing-lesson/i,
    );
    expect(screen.queryByTestId("lessons-attention-item-missing-lesson")).not.toBeInTheDocument();
  });

  it("supports accept mutation with confirmation", async () => {
    render(<LessonsPage />);
    fireEvent.click(await screen.findByTestId("accept-lesson-btn"));
    fireEvent.click(screen.getByTestId("accept-path-accept_only"));
    fireEvent.click(screen.getByTestId("accept-confirm-checkbox"));
    fireEvent.click(screen.getByTestId("confirm-accept"));
    await waitFor(() => expect(acceptMock).toHaveBeenCalled());
  });

  it("shows failed reject mutation and allows retry", async () => {
    rejectMock.mockRejectedValueOnce(new Error("reject failed"));
    render(<LessonsPage />);
    fireEvent.click(await screen.findByTestId("reject-lesson-btn"));
    expect(await screen.findByTestId("lesson-mutation-error")).toHaveTextContent(/reject failed/i);
    rejectMock.mockResolvedValueOnce({});
    fireEvent.click(screen.getByTestId("reject-lesson-btn"));
    await waitFor(() => expect(rejectMock).toHaveBeenCalledTimes(2));
  });

  it("prevents duplicate reject submissions while busy", async () => {
    let resolveReject: (() => void) | undefined;
    rejectMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveReject = resolve;
        }),
    );
    render(<LessonsPage />);
    const rejectBtn = await screen.findByTestId("reject-lesson-btn");
    fireEvent.click(rejectBtn);
    expect(rejectBtn).toBeDisabled();
    fireEvent.click(rejectBtn);
    expect(rejectMock).toHaveBeenCalledTimes(1);
    resolveReject?.();
    await waitFor(() => expect(rejectMock).toHaveBeenCalledTimes(1));
  });

  it("shows confirmed paper posture when verified", async () => {
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-hub-page")).toBeInTheDocument();
    expect(screen.getByTestId("journal-hub-safety")).toBeInTheDocument();
    expect(screen.getByTestId("lessons-limitations")).toHaveTextContent(
      /runtime posture verified as paper-only/i,
    );
  });

  it("uses conservative posture wording when paper is unverified", async () => {
    safetyPosture.executionMode = null;
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-limitations")).toHaveTextContent(
      /paper posture is not fully verified/i,
    );
  });

  it("uses card layout without horizontal scroll container at mobile width", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390, writable: true });
    render(<LessonsPage />);
    const list = await screen.findByTestId("lessons-attention-list");
    expect(list.className).not.toMatch(/overflow-x/);
    expect(within(list).getAllByTestId("lesson-review-card").length).toBeGreaterThan(0);
  });

  it("keeps lessons route reachable via journal hub nav", async () => {
    render(<LessonsPage />);
    expect(await screen.findByRole("link", { name: "Lessons" })).toHaveAttribute(
      "href",
      "/lessons",
    );
  });
});

describe("LessonAcceptPanel", () => {
  it("supports attach rule and create version paths", async () => {
    const onAccept = vi.fn().mockResolvedValue(undefined);
    render(
      <LessonAcceptPanel
        lesson={{ ...pendingLesson, related_strategy_id: "strategy-1" }}
        busy={false}
        onAccept={onAccept}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("accept-path-create_version"));
    fireEvent.change(screen.getByTestId("rule-update-editor"), {
      target: { value: "Edited rule summary" },
    });
    fireEvent.click(screen.getByTestId("accept-confirm-checkbox"));
    fireEvent.click(screen.getByTestId("confirm-accept"));
    await waitFor(() => expect(onAccept).toHaveBeenCalled());
  });
});

describe("StrategyVersionHistory", () => {
  it("displays source lesson metadata", () => {
    render(
      <StrategyVersionHistory
        versions={[
          {
            id: "v1",
            strategy_id: "s1",
            version: 3,
            card: {},
            validation_status: "in_review",
            backtest_status: "not_run",
            paper_validation_status: "not_started",
            created_at: new Date().toISOString(),
            lesson_source_metadata: {
              lesson_id: "lesson-1",
              mistake_type: "early_exit",
              accepted_lesson_text: "Hold runner",
              rule_update_summary: "Add runner exit",
              created_at: new Date().toISOString(),
            },
          },
        ]}
      />,
    );
    expect(screen.getByTestId("version-from-lesson-3")).toBeInTheDocument();
    expect(screen.getByText(/early_exit/)).toBeInTheDocument();
  });
});

describe("PaperValidationPanel", () => {
  it("renders eligibility blockers and status", () => {
    render(
      <PaperValidationPanel
        summary={null}
        eligibility={{
          strategy_id: "s1",
          status: "needs_more_sample",
          paper_eligible: false,
          testability_score: 80,
          blockers: ["Sample size below minimum"],
          eligibility_reasons: [],
          accepted_lessons: [],
          unresolved_lesson_candidates: [{ ...pendingLesson, id: "pending-1" }],
          recommendation: "improve",
          real_trading_enabled: false,
          limitations: ["Paper only"],
        }}
        busy={false}
        signals={[]}
        trades={[]}
        onStart={vi.fn()}
        onScan={vi.fn()}
        onTick={vi.fn()}
        onStop={vi.fn()}
        scheduler={null}
        history={[]}
        alerts={[]}
        onSchedulerTick={vi.fn()}
        onMarkAlertRead={vi.fn()}
      />,
    );
    expect(screen.getByTestId("paper-eligibility-status")).toBeInTheDocument();
    expect(screen.getByTestId("paper-eligibility-blockers")).toBeInTheDocument();
    expect(screen.getByTestId("unresolved-lesson-blocker")).toBeInTheDocument();
  });
});

describe("StructuredRuleEditor", () => {
  it("add edit delete blocks", () => {
    render(
      <StructuredRuleEditor
        rules={null}
        testability={{
          strategy_id: "s1",
          score: 55,
          band: "partial",
          ready_for_backtest: false,
          missing_fields: [{ field_key: "stop_loss", label: "Stop loss missing" }],
          has_structured_rules: true,
        }}
      />,
    );
    expect(screen.getByTestId("testability-score")).toHaveTextContent("55/100");
    fireEvent.click(screen.getByTestId("add-entry-block"));
    fireEvent.click(screen.getByTestId("add-exit-block"));
    fireEvent.click(screen.getByTestId("add-notrade-block"));
    expect(screen.getByTestId("entry-block-1")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("remove-entry-0"));
    expect(screen.queryAllByTestId(/^entry-block-/).length).toBe(1);
  });
});
