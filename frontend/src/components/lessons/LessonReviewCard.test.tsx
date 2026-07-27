import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  formatLessonConfidence,
  LessonReviewCard,
} from "@/components/lessons/LessonReviewCard";

describe("formatLessonConfidence", () => {
  it("treats confidence 0 as a real value", () => {
    expect(formatLessonConfidence("0")).toBe("confidence 0");
    expect(formatLessonConfidence(0 as unknown as string)).toBe("confidence 0");
  });

  it("shows unavailable for null or undefined", () => {
    expect(formatLessonConfidence(null)).toBe("confidence unavailable");
    expect(formatLessonConfidence(undefined)).toBe("confidence unavailable");
  });
});

describe("LessonReviewCard deep link", () => {
  afterEach(() => cleanup());

  it("shows deep-link notice when loaded outside paginated queues", () => {
    render(
      <LessonReviewCard
        lesson={{
          id: "deep-1",
          organization_id: "o",
          user_id: "u",
          source_type: "journal",
          lesson_text: "Accepted lesson",
          mistake_type: "early_exit",
          severity: "medium",
          status: "accepted",
          created_at: "2026-07-20T10:00:00.000Z",
        }}
        deepLinkNotice
      />,
    );
    expect(screen.getByTestId("lesson-deeplink-notice")).toHaveTextContent(
      /outside the current paginated queues/i,
    );
    expect(screen.queryByTestId("lesson-actions")).not.toBeInTheDocument();
  });
});
