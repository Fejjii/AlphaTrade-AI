import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LessonCandidateCard } from "./LessonCandidateCard";

describe("LessonCandidateCard", () => {
  afterEach(() => cleanup());

  it("shows coaching source badge and review-safe lesson text", () => {
    render(
      <LessonCandidateCard
        lesson={{
          id: "l-coach",
          organization_id: "o",
          user_id: "u",
          source_type: "coaching",
          lesson_text:
            "Review this behavior: invalidation was hit in 75% of sessions. Study what invalidated these setups.",
          mistake_type: "invalidation_hit",
          severity: "medium",
          status: "pending_review",
          created_at: new Date().toISOString(),
        }}
      />,
    );
    expect(screen.getByTestId("lesson-source-coaching")).toHaveTextContent("Coaching");
    expect(screen.getByTestId("lesson-text")).toHaveTextContent(/review this behavior/i);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
  });

  it("renders non-coaching source as plain label", () => {
    render(
      <LessonCandidateCard
        lesson={{
          id: "l-journal",
          organization_id: "o",
          user_id: "u",
          source_type: "journal",
          lesson_text: "Early exit lesson",
          mistake_type: "early_exit",
          severity: "medium",
          status: "pending_review",
          created_at: new Date().toISOString(),
        }}
      />,
    );
    expect(screen.queryByTestId("lesson-source-coaching")).not.toBeInTheDocument();
    expect(screen.getByTestId("lesson-source-label")).toHaveTextContent("journal");
  });

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
