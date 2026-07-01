import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { OutcomeRatesCard } from "./OutcomeRatesCard";

const rates = {
  success_rate: 0.75,
  failure_rate: 0.25,
  invalidated_rate: null,
  missed_entry_rate: 0,
  no_trade_rate: 0,
  inconclusive_rate: 0,
  behaved_as_expected_rate: 0.5,
  invalidation_hit_rate: 0.1,
};

const distribution = [
  { outcome: "success", count: 3, rate: 0.75 },
  { outcome: "failure", count: 1, rate: 0.25 },
];

describe("OutcomeRatesCard", () => {
  afterEach(() => cleanup());

  it("renders rates and outcome distribution", () => {
    render(<OutcomeRatesCard rates={rates} distribution={distribution} resultsCount={4} />);
    expect(screen.getByTestId("learning-outcome-rates-card")).toBeInTheDocument();
    expect(screen.getByTestId("learning-rate-success_rate")).toHaveTextContent("75%");
    expect(screen.getByTestId("learning-outcome-success")).toHaveTextContent("3");
  });

  it("renders an em dash when a rate is null", () => {
    render(<OutcomeRatesCard rates={rates} distribution={distribution} resultsCount={4} />);
    expect(screen.getByTestId("learning-rate-invalidated_rate")).toHaveTextContent("—");
  });
});
