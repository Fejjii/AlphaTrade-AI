import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { BehaviorInsightsCard } from "./BehaviorInsightsCard";

describe("BehaviorInsightsCard", () => {
  afterEach(() => cleanup());

  it("renders insights with sample size and confidence", () => {
    render(
      <BehaviorInsightsCard
        insights={[
          {
            code: "price_moves_without_entry",
            message: "Price frequently moves without entry after your trigger.",
            severity: "info",
            sample_size: 7,
            confidence: "medium",
          },
        ]}
      />,
    );
    expect(screen.getByTestId("learning-behavior-insights-card")).toBeInTheDocument();
    expect(screen.getByTestId("learning-insight-price_moves_without_entry")).toHaveTextContent(
      "n=7",
    );
  });

  it("shows an empty state when there are no insights", () => {
    render(<BehaviorInsightsCard insights={[]} />);
    expect(screen.getByText(/no insights yet/i)).toBeInTheDocument();
  });
});
