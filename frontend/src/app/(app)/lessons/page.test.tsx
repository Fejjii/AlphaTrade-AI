import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import LessonsPage from "@/app/(app)/lessons/page";
import { LessonAcceptPanel } from "@/components/lessons/LessonAcceptPanel";
import { LessonCandidateCard } from "@/components/lessons/LessonCandidateCard";
import { PaperValidationPanel } from "@/components/strategy/PaperValidationPanel";
import { StrategyVersionHistory } from "@/components/strategy/StrategyVersionHistory";
import { StructuredRuleEditor } from "@/components/strategy/StructuredRuleEditor";

const { acceptMock } = vi.hoisted(() => ({
  acceptMock: vi.fn().mockResolvedValue({}),
}));

vi.mock("@/lib/api", () => ({
  api: {
    strategies: {
      list: vi.fn().mockResolvedValue({
        items: [{ id: "strategy-1", name: "HTF Pullback", current_version: 2 }],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    },
    lessons: {
      listCandidates: vi.fn().mockResolvedValue({
        items: [
          {
            id: "lesson-1",
            organization_id: "org",
            user_id: "user",
            source_type: "runner_analysis",
            lesson_text: "Review runner rules before entry.",
            mistake_type: "early_exit",
            severity: "medium",
            status: "pending_review",
            proposed_rule_update: { summary: "Hold runner until structure break" },
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      listAccepted: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
      accept: acceptMock,
      reject: vi.fn().mockResolvedValue({}),
    },
  },
}));

const lesson = {
  id: "lesson-1",
  organization_id: "org",
  user_id: "user",
  source_type: "runner_analysis",
  lesson_text: "Review runner rules before entry.",
  mistake_type: "early_exit",
  severity: "medium",
  status: "pending_review",
  proposed_rule_update: { summary: "Hold runner until structure break" },
  created_at: new Date().toISOString(),
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LessonsPage", () => {
  it("renders lessons page", async () => {
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-page")).toBeInTheDocument();
    expect(await screen.findByTestId("lesson-candidate-card")).toBeInTheDocument();
  });

  it("opens accept panel for accept lesson only flow", async () => {
    render(<LessonsPage />);
    fireEvent.click(await screen.findByTestId("accept-lesson-btn"));
    expect(await screen.findByTestId("lesson-accept-panel")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("accept-path-accept_only"));
    fireEvent.click(screen.getByTestId("accept-confirm-checkbox"));
    fireEvent.click(screen.getByTestId("confirm-accept"));
    await waitFor(() => expect(acceptMock).toHaveBeenCalled());
  });
});

describe("LessonAcceptPanel", () => {
  it("supports attach rule and create version paths", async () => {
    const onAccept = vi.fn().mockResolvedValue(undefined);
    render(
      <LessonAcceptPanel
        lesson={{ ...lesson, related_strategy_id: "strategy-1" }}
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

describe("LessonCandidateCard", () => {
  it("renders accept and reject flow", () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();
    render(
      <LessonCandidateCard
        lesson={{
          id: "l1",
          organization_id: "o",
          user_id: "u",
          source_type: "journal",
          lesson_text: "Early exit lesson",
          mistake_type: "early_exit",
          severity: "medium",
          status: "pending_review",
          created_at: new Date().toISOString(),
        }}
        onAccept={onAccept}
        onReject={onReject}
      />,
    );
    fireEvent.click(screen.getByTestId("accept-lesson-btn"));
    fireEvent.click(screen.getByTestId("reject-lesson-btn"));
    expect(onAccept).toHaveBeenCalled();
    expect(onReject).toHaveBeenCalled();
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
          unresolved_lesson_candidates: [{ ...lesson, id: "pending-1" }],
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
