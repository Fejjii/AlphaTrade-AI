import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DetectorQualityCard } from "./DetectorQualityCard";
import type { DetectorQualityReport } from "@/lib/api/types";

const report: DetectorQualityReport = {
  condition: "sfp",
  detector_version: "1.0.0",
  sample_size: 6,
  insufficient_data: false,
  trust_tier: "medium",
  verdict: "avoid_for_now",
  quality_score: 40,
  raw_quality_score: 30,
  success_rate: 0.1,
  failure_rate: 0.2,
  invalidated_rate: 0.7,
  missed_entry_rate: 0,
  no_trade_rate: 0,
  inconclusive_rate: 0,
  invalidation_hit_rate: 0.8,
  behaved_as_expected_rate: 0.2,
  should_have_avoided_rate: 0.4,
  should_have_waited_rate: 0,
  outcome_distribution: [],
  discipline_breakdown: { should_have_avoided: 3 },
  entry_breakdown: {},
  confidence_calibration: {
    mean_confidence: 0.5,
    mean_success_rate: 0.1,
    correlation: "none",
    calibration_label: "overconfident",
    buckets: [],
  },
  warnings: [
    {
      code: "noisy_high_invalidation",
      message: "'sfp' hits invalidation frequently; it is noisy.",
      severity: "warning",
    },
  ],
  factors: [
    {
      code: "invalidation_avoidance",
      label: "Invalidation avoidance",
      direction: "positive",
      contribution: 4,
      detail: "Invalidation was hit in 80% of results.",
    },
  ],
  rationale: ["Invalidation is hit often for this detector."],
};

describe("DetectorQualityCard", () => {
  afterEach(() => cleanup());

  it("renders verdict, trust, rates, calibration, warnings, and factors", () => {
    render(<DetectorQualityCard report={report} />);
    expect(screen.getByTestId("strategy-quality-detector-sfp")).toBeInTheDocument();
    expect(screen.getByText("Avoid for now")).toBeInTheDocument();
    expect(screen.getByText("Medium evidence")).toBeInTheDocument();
    expect(screen.getByTestId("strategy-quality-score")).toHaveTextContent("quality 40");
    expect(screen.getByTestId("strategy-quality-rates")).toHaveTextContent("Invalidation hit");
    expect(screen.getByTestId("strategy-quality-calibration")).toHaveTextContent("Overconfident");
    expect(screen.getByTestId("strategy-quality-detector-warnings")).toHaveTextContent(
      /hits invalidation frequently/i,
    );
    expect(screen.getByTestId("strategy-quality-factor-invalidation_avoidance")).toBeInTheDocument();
  });

  it("renders an em dash for a detector with no data", () => {
    const empty: DetectorQualityReport = {
      ...report,
      sample_size: 0,
      insufficient_data: true,
      trust_tier: "none",
      verdict: "needs_more_validation",
      quality_score: null,
      raw_quality_score: null,
      success_rate: null,
      invalidation_hit_rate: null,
    };
    render(<DetectorQualityCard report={empty} />);
    expect(screen.getByTestId("strategy-quality-score")).toHaveTextContent("quality —");
    expect(screen.getByText("Needs more validation")).toBeInTheDocument();
  });
});
