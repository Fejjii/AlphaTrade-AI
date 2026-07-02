import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CoachingPromptCard } from "./CoachingPromptCard";
import type { CoachingPrompt } from "@/lib/api/types";

const prompt: CoachingPrompt = {
  signature: "sig-1",
  category: "invalidation_hit",
  title: "Review: invalidation frequently hit on 'order_block'",
  prompt_text:
    "Review this behavior: invalidation was hit in 67% of 6 'order_block' sessions.",
  severity: "high",
  reliability: "medium",
  concern_score: 45,
  insufficient_data: false,
  source: {
    matched_dimension: "condition",
    matched_key: "order_block",
    sample_size: 6,
    source_session_ids: ["sess-1", "sess-2"],
    analytics_codes: ["invalidation_prone_setup"],
    rate: 0.67,
  },
  factors: [],
  rationale: ["Based on 6 session(s); more validation data strengthens this pattern."],
};

vi.mock("@/lib/api", () => ({
  api: {
    coaching: {
      savePrompt: vi.fn().mockResolvedValue({ id: "lesson-1" }),
    },
  },
}));

describe("CoachingPromptCard", () => {
  afterEach(() => cleanup());

  it("renders source, severity, and rationale", () => {
    render(<CoachingPromptCard prompt={prompt} minSample={5} />);
    expect(screen.getByTestId("coaching-prompt-sig-1")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByTestId("coaching-rationale")).toBeInTheDocument();
    expect(screen.getByTestId("coaching-source")).toHaveTextContent("order_block");
    expect(screen.getByTestId("coaching-prompt-text")).toHaveTextContent("Review this behavior");
  });

  it("save button calls API", async () => {
    const { api } = await import("@/lib/api");
    render(<CoachingPromptCard prompt={prompt} minSample={5} />);
    fireEvent.click(screen.getByTestId("coaching-save-button"));
    await waitFor(() => {
      expect(api.coaching.savePrompt).toHaveBeenCalledWith({
        category: "invalidation_hit",
        matched_dimension: "condition",
        matched_key: "order_block",
        min_sample: 5,
      });
    });
  });

  it("already saved state works", () => {
    render(
      <CoachingPromptCard
        prompt={{ ...prompt, already_saved_lesson_id: "lesson-99" }}
        minSample={5}
      />,
    );
    expect(screen.getByTestId("coaching-in-review-queue")).toHaveAttribute("href", "/lessons");
    expect(screen.queryByTestId("coaching-save-button")).not.toBeInTheDocument();
  });

  it("has no unsafe CTA", () => {
    render(<CoachingPromptCard prompt={prompt} minSample={5} />);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start run/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /automate/i })).not.toBeInTheDocument();
  });
});
