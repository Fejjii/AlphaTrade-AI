import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import StrategyQualityPage from "./page";
import type {
  DetectorQualityReport,
  StrategyQualityDetectorsResponse,
  StrategyQualitySummaryResponse,
} from "@/lib/api/types";

function emptyCalibration() {
  return {
    mean_confidence: null,
    mean_success_rate: null,
    correlation: "insufficient_data",
    calibration_label: "insufficient_data" as const,
    buckets: [],
  };
}

const trusted: DetectorQualityReport = {
  condition: "liquidity_sweep",
  detector_version: "1.0.0",
  sample_size: 5,
  insufficient_data: false,
  trust_tier: "medium",
  verdict: "trusted",
  quality_score: 75,
  raw_quality_score: 100,
  success_rate: 1,
  failure_rate: 0,
  invalidated_rate: 0,
  missed_entry_rate: 0,
  no_trade_rate: 0,
  inconclusive_rate: 0,
  invalidation_hit_rate: 0,
  behaved_as_expected_rate: 1,
  should_have_avoided_rate: 0,
  should_have_waited_rate: 0,
  outcome_distribution: [],
  discipline_breakdown: { disciplined: 5 },
  entry_breakdown: { entered_as_planned: 5 },
  confidence_calibration: {
    mean_confidence: 0.8,
    mean_success_rate: 1,
    correlation: "none",
    calibration_label: "underconfident",
    buckets: [],
  },
  warnings: [],
  factors: [
    {
      code: "success_rate",
      label: "Validated success rate",
      direction: "positive",
      contribution: 50,
      detail: "100% of results were graded success.",
    },
  ],
  rationale: ["Strong validated quality with sufficient evidence."],
};

const noisy: DetectorQualityReport = {
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
  confidence_calibration: emptyCalibration(),
  warnings: [
    { code: "noisy_high_invalidation", message: "'sfp' hits invalidation frequently; it is noisy.", severity: "warning" },
  ],
  factors: [],
  rationale: ["Invalidation is hit often for this detector."],
};

const empty: DetectorQualityReport = {
  condition: "order_block",
  detector_version: "1.0.0",
  sample_size: 0,
  insufficient_data: true,
  trust_tier: "none",
  verdict: "needs_more_validation",
  quality_score: null,
  raw_quality_score: null,
  success_rate: null,
  failure_rate: null,
  invalidated_rate: null,
  missed_entry_rate: null,
  no_trade_rate: null,
  inconclusive_rate: null,
  invalidation_hit_rate: null,
  behaved_as_expected_rate: null,
  should_have_avoided_rate: null,
  should_have_waited_rate: null,
  outcome_distribution: [],
  discipline_breakdown: {},
  entry_breakdown: {},
  confidence_calibration: emptyCalibration(),
  warnings: [{ code: "insufficient_data", message: "Only 0 validated result(s) for 'order_block'.", severity: "info" }],
  factors: [],
  rationale: ["Only 0 validated result(s) (min 5); validate 'order_block' more."],
};

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
    { condition: "liquidity_sweep", rank: 1, quality_score: 75, sample_size: 5, trust_tier: "medium", verdict: "trusted" },
    { condition: "sfp", rank: 2, quality_score: 40, sample_size: 6, trust_tier: "medium", verdict: "avoid_for_now" },
  ],
  warnings: [
    { code: "detectors_without_data", message: "No validated results yet for: breakout_retest, trend_pullback.", severity: "info" },
  ],
};

const detectors: StrategyQualityDetectorsResponse = {
  organization_id: "org-1",
  user_id: null,
  date_range: { start: null, end: null },
  min_sample: 5,
  note: "Read-only strategy quality review for human study only.",
  condition_filter: null,
  timeframe_filter: null,
  detectors: [trusted, noisy, empty],
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: { summary, detectors },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("StrategyQualityPage Slice 89", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders summary, detector cards, and read-only safety copy", () => {
    render(<StrategyQualityPage />);
    expect(screen.getByTestId("strategy-quality-page")).toBeInTheDocument();
    expect(screen.getByTestId("strategy-quality-summary")).toBeInTheDocument();
    expect(screen.getByTestId("strategy-quality-detector-liquidity_sweep")).toBeInTheDocument();
    expect(screen.getByTestId("strategy-quality-detector-sfp")).toBeInTheDocument();
    expect(screen.getByTestId("strategy-quality-detector-order_block")).toBeInTheDocument();
    expect(
      screen.getByText(/does not change strategy rules, enable or disable detectors/i),
    ).toBeInTheDocument();
  });

  it("shows verdicts and the quality ranking", () => {
    render(<StrategyQualityPage />);
    expect(screen.getByTestId("strategy-quality-verdict-trusted")).toHaveTextContent("1");
    expect(screen.getByTestId("strategy-quality-rank-liquidity_sweep")).toBeInTheDocument();
    expect(screen.getAllByText("Avoid for now").length).toBeGreaterThan(0);
  });

  it("has no order, execution, proposal, rule-change, or automation controls", () => {
    render(<StrategyQualityPage />);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /disable detector/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /change rule/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /automate/i })).not.toBeInTheDocument();
  });
});
