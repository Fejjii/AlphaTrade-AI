import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import LessonsPage from "@/app/(app)/lessons/page";
import { LessonCandidateCard } from "@/components/lessons/LessonCandidateCard";
import { StructuredRuleEditor } from "@/components/strategy/StructuredRuleEditor";

vi.mock("@/lib/api", () => ({
  api: {
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
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      listAccepted: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
      accept: vi.fn().mockResolvedValue({}),
      reject: vi.fn().mockResolvedValue({}),
    },
  },
}));

afterEach(() => {
  cleanup();
});

describe("LessonsPage", () => {
  it("renders lessons page", async () => {
    render(<LessonsPage />);
    expect(await screen.findByTestId("lessons-page")).toBeInTheDocument();
    expect(await screen.findByTestId("lesson-candidate-card")).toBeInTheDocument();
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
