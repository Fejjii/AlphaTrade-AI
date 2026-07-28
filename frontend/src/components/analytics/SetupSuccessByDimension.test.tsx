import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows";
import type { SetupPerformanceResponse } from "@/lib/api/types";

import { SetupSuccessByDimension } from "./SetupSuccessByDimension";

function ok(data: SetupPerformanceResponse): SourceResult<SetupPerformanceResponse> {
  return { data, available: true, error: null, fallbackUsed: false };
}

const performance: SetupPerformanceResponse = {
  organization_id: "org",
  user_id: null,
  date_range: {},
  min_sample: 5,
  dimension: "condition",
  groups: [
    {
      dimension_value: "breakout",
      sample_size: 8,
      insufficient_data: false,
      success_rate: 0.5,
      outcome_distribution: [],
    },
    {
      dimension_value: "trend",
      sample_size: 2,
      insufficient_data: true,
      success_rate: 1,
      outcome_distribution: [],
    },
  ],
};

describe("SetupSuccessByDimension", () => {
  afterEach(() => cleanup());

  it("renders success rate, sample size, and insufficient muted groups", () => {
    render(
      <SetupSuccessByDimension
        source={ok(performance)}
        dimension="condition"
        onDimensionChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("setup-success-row-breakout")).toHaveTextContent(/50\.0%/);
    expect(screen.getByTestId("setup-success-row-breakout")).toHaveTextContent(/n=8/);
    expect(screen.getByTestId("setup-success-row-trend")).toHaveTextContent(/insufficient/);
    expect(screen.getByTestId("setup-success-no-pnl-caption")).toHaveTextContent(
      /Categorical session outcomes — no P&L/,
    );
    expect(screen.getByTestId("setup-success-by-dimension-a11y-table")).toBeInTheDocument();
  });

  it("commits dimension changes through the provided handler", () => {
    const onDimensionChange = vi.fn();
    render(
      <SetupSuccessByDimension
        source={ok(performance)}
        dimension="condition"
        onDimensionChange={onDimensionChange}
      />,
    );
    fireEvent.click(screen.getByTestId("validation-dimension-timeframe"));
    expect(onDimensionChange).toHaveBeenCalledWith("timeframe");
  });

  it("supports arrow-key dimension navigation with roving focus", () => {
    const onDimensionChange = vi.fn();
    const { rerender } = render(
      <SetupSuccessByDimension
        source={ok(performance)}
        dimension="condition"
        onDimensionChange={onDimensionChange}
      />,
    );
    const condition = screen.getByTestId("validation-dimension-condition");
    condition.focus();
    fireEvent.keyDown(condition, { key: "ArrowDown" });
    expect(onDimensionChange).toHaveBeenCalledWith("timeframe");
    rerender(
      <SetupSuccessByDimension
        source={ok(performance)}
        dimension="timeframe"
        onDimensionChange={onDimensionChange}
      />,
    );
    expect(screen.getByTestId("validation-dimension-timeframe")).toHaveFocus();
  });

  it("does not fabricate zeros on failure", () => {
    render(
      <SetupSuccessByDimension
        source={{ data: null, available: false, error: "setup performance down", fallbackUsed: false }}
        dimension="symbol"
        onDimensionChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("setup-success-by-dimension-error")).toHaveTextContent(
      /setup performance down/i,
    );
    expect(screen.queryByTestId("setup-success-by-dimension-plot")).not.toBeInTheDocument();
  });
});
