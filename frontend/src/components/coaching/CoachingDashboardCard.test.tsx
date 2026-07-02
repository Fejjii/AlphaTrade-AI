import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CoachingDashboardCard } from "./CoachingDashboardCard";
import type { CoachingPrompt, CoachingSummaryResponse } from "@/lib/api/types";

const summary: CoachingSummaryResponse = {
  organization_id: "org-1",
  user_id: null,
  date_range: { start: null, end: null },
  min_sample: 5,
  note: "Read-only coaching guidance for human discipline review only.",
  total_open: 2,
  pending_coaching_lessons: 1,
  by_category: [
    { category: "invalidation_hit", count: 1 },
    { category: "missed_entry", count: 1 },
    { category: "should_have_waited", count: 0 },
    { category: "should_have_avoided", count: 0 },
    { category: "low_quality_setup", count: 0 },
    { category: "overconfidence", count: 0 },
    { category: "weak_confidence_correlation", count: 0 },
  ],
  by_severity: [
    { severity: "low", count: 0 },
    { severity: "medium", count: 1 },
    { severity: "high", count: 1 },
    { severity: "critical", count: 0 },
  ],
  top_prompt: null,
};

const topPrompts: CoachingPrompt[] = [
  {
    signature: "sig-1",
    category: "invalidation_hit",
    title: "Review: invalidation frequently hit on 'order_block'",
    prompt_text: "Review this behavior: invalidation was hit often.",
    severity: "high",
    reliability: "medium",
    concern_score: 50,
    insufficient_data: false,
    source: {
      matched_dimension: "condition",
      matched_key: "order_block",
      sample_size: 6,
      source_session_ids: [],
      analytics_codes: [],
    },
    factors: [],
    rationale: [],
  },
];

describe("CoachingDashboardCard", () => {
  afterEach(() => cleanup());

  it("renders distribution, top items, and links", () => {
    render(<CoachingDashboardCard summary={summary} topPrompts={topPrompts} />);
    expect(screen.getByTestId("dashboard-coaching")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-coaching-distribution")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-coaching-count-high")).toHaveTextContent("1");
    expect(screen.getByTestId("dashboard-coaching-top-sig-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review coaching" })).toHaveAttribute("href", "/coaching");
    expect(screen.getByRole("link", { name: "Open review queue" })).toHaveAttribute("href", "/lessons");
  });

  it("has no unsafe CTA", () => {
    render(<CoachingDashboardCard summary={summary} topPrompts={topPrompts} />);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /automate/i })).not.toBeInTheDocument();
  });
});
