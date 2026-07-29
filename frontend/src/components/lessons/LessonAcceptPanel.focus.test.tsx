import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LessonAcceptPanel } from "@/components/lessons/LessonAcceptPanel";
import type { LessonCandidate } from "@/lib/api/types";

vi.mock("@/lib/api", () => ({
  api: {
    strategies: {
      list: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
    },
  },
}));

const lesson: LessonCandidate = {
  id: "lesson-1",
  organization_id: "org",
  user_id: "user",
  mistake_type: "overtrading",
  severity: "medium",
  lesson_text: "Slow down after two losses.",
  source_type: "journal",
  status: "pending_review",
  confidence: "moderate",
  related_strategy_id: null,
  related_journal_entry_id: null,
  proposed_rule_update: null,
  created_at: "2026-07-25T12:00:00Z",
  reviewed_at: null,
  reviewer_notes: null,
};

describe("LessonAcceptPanel focus management (FP2-211)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => cleanup());

  it("moves focus onto the accept panel title when the card swap mounts", async () => {
    render(
      <LessonAcceptPanel lesson={lesson} busy={false} onAccept={vi.fn()} onCancel={vi.fn()} />,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Accept lesson" })).toHaveFocus();
    });
  });
});
