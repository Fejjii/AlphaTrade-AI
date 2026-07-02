import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DetectorQualitySummary } from "./DetectorQualitySummary";
import type { StrategyQualitySummaryResponse } from "@/lib/api/types";

const summary: StrategyQualitySummaryResponse = {
  organization_id: "org-1",
  user_id: null,
  date_range: { start: null, end: null },
  min_sample: 5,
  note: "Read-only strategy quality review for human study only.",
  total_detectors: 3,
  detectors_with_data: 2,
  total_results: 11,
  by_trust_tier: [
    { trust_tier: "none", count: 1 },
    { trust_tier: "low", count: 0 },
    { trust_tier: "medium", count: 2 },
    { trust_tier: "high", count: 0 },
  ],
  by_verdict: [
    { verdict: "trusted", count: 1 },
    { verdict: "watch", count: 0 },
    { verdict: "improve", count: 0 },
    { verdict: "avoid_for_now", count: 1 },
    { verdict: "needs_more_validation", count: 1 },
  ],
  ranked: [
    {
      condition: "liquidity_sweep",
      rank: 1,
      quality_score: 75,
      sample_size: 5,
      trust_tier: "medium",
      verdict: "trusted",
    },
  ],
  warnings: [
    {
      code: "detectors_without_data",
      message: "No validated results yet for: breakout_retest.",
      severity: "info",
    },
  ],
};

describe("DetectorQualitySummary", () => {
  afterEach(() => cleanup());

  it("renders verdict and trust counts, ranking, and coverage warnings", () => {
    render(<DetectorQualitySummary summary={summary} />);
    expect(screen.getByTestId("strategy-quality-summary")).toBeInTheDocument();
    expect(screen.getByTestId("strategy-quality-verdict-trusted")).toHaveTextContent("1");
    expect(screen.getByTestId("strategy-quality-trust-medium")).toHaveTextContent("2");
    expect(screen.getByTestId("strategy-quality-rank-liquidity_sweep")).toHaveTextContent(
      "liquidity_sweep",
    );
    expect(screen.getByTestId("strategy-quality-warnings")).toHaveTextContent(
      /no validated results yet/i,
    );
  });
});
