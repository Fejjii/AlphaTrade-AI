import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import CoachingPage from "./page";

const { mockPrompts, mockSummary } = vi.hoisted(() => ({
  mockPrompts: {
    organization_id: "org-1",
    user_id: null,
    date_range: { start: null, end: null },
    min_sample: 5,
    note: "Read-only coaching guidance.",
    total: 1,
    items: [
      {
        signature: "sig-1",
        category: "invalidation_hit" as const,
        title: "Review: invalidation frequently hit on 'order_block'",
        prompt_text: "Review this behavior: invalidation was hit in 67% of sessions.",
        severity: "high" as const,
        reliability: "medium" as const,
        concern_score: 45,
        insufficient_data: false,
        source: {
          matched_dimension: "condition",
          matched_key: "order_block",
          sample_size: 6,
          source_session_ids: ["s1"],
          analytics_codes: ["invalidation_prone_setup"],
          rate: 0.67,
        },
        factors: [],
        rationale: ["Source session ids cited."],
      },
    ],
  },
  mockSummary: {
    organization_id: "org-1",
    user_id: null,
    date_range: { start: null, end: null },
    min_sample: 5,
    note: "Read-only coaching guidance.",
    total_open: 1,
    pending_coaching_lessons: 0,
    by_category: [],
    by_severity: [],
    top_prompt: null,
  },
}));

vi.mock("@/lib/api", () => ({
  api: {
    coaching: {
      summary: vi.fn().mockResolvedValue(mockSummary),
      prompts: vi.fn().mockResolvedValue(mockPrompts),
      savePrompt: vi.fn().mockResolvedValue({ id: "lesson-1" }),
    },
  },
}));

describe("CoachingPage", () => {
  afterEach(() => cleanup());

  it("renders coaching prompts", async () => {
    render(<CoachingPage />);
    expect(await screen.findByTestId("coaching-page")).toBeInTheDocument();
    expect(screen.getByTestId("coaching-prompt-sig-1")).toBeInTheDocument();
    expect(screen.getByTestId("coaching-prompt-text")).toHaveTextContent(/review this behavior/i);
  });
});
