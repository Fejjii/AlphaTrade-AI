import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnalyticsFilterState } from "./useAnalyticsFilters";
import { AnalyticsFilterBar } from "./AnalyticsFilterBar";

const validationState: AnalyticsFilterState = {
  tab: "validation",
  dateFrom: "2026-01-01",
  dateTo: "2026-01-31",
  symbol: null,
  timeframe: null,
  portfolioSource: null,
  setupId: null,
  userStrategyId: null,
  strategyVersionId: null,
  journalSource: null,
  ruleCompliance: null,
  marketRegime: null,
  groupBy: "setup",
  bucketOffset: 0,
  minSample: 5,
  dimension: "condition",
  ignoredParams: [],
};

describe("AnalyticsFilterBar Validation min_sample", () => {
  afterEach(() => cleanup());

  it("shows accurate Validation endpoint copy", () => {
    render(
      <AnalyticsFilterBar
        state={validationState}
        onApplyDraft={vi.fn()}
        onApplyPreset={vi.fn()}
        onClear={vi.fn()}
      />,
    );
    expect(screen.getByTestId("analytics-validation-filter-note")).toHaveTextContent(
      /setup-performance and setup-ranking also receive the selected dimension/i,
    );
    expect(screen.getByTestId("analytics-validation-filter-note")).toHaveTextContent(
      /Journal and portfolio filters are not sent/i,
    );
  });

  it("rejects blank, zero, and >100 min_sample without applying", () => {
    const onApplyDraft = vi.fn();
    render(
      <AnalyticsFilterBar
        state={validationState}
        onApplyDraft={onApplyDraft}
        onApplyPreset={vi.fn()}
        onClear={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByTestId("analytics-min-sample"), { target: { value: "" } });
    fireEvent.click(screen.getByTestId("analytics-apply-filters"));
    expect(screen.getByTestId("analytics-min-sample-error")).toBeInTheDocument();
    expect(onApplyDraft).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId("analytics-min-sample"), { target: { value: "0" } });
    fireEvent.click(screen.getByTestId("analytics-apply-filters"));
    expect(screen.getByTestId("analytics-min-sample-error")).toHaveTextContent(/at least 1/i);
    expect(onApplyDraft).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId("analytics-min-sample"), { target: { value: "101" } });
    fireEvent.click(screen.getByTestId("analytics-apply-filters"));
    expect(screen.getByTestId("analytics-min-sample-error")).toHaveTextContent(/cannot exceed 100/i);
    expect(onApplyDraft).not.toHaveBeenCalled();
  });

  it("applies a valid min_sample value", () => {
    const onApplyDraft = vi.fn();
    render(
      <AnalyticsFilterBar
        state={validationState}
        onApplyDraft={onApplyDraft}
        onApplyPreset={vi.fn()}
        onClear={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("analytics-min-sample"), { target: { value: "8" } });
    fireEvent.click(screen.getByTestId("analytics-apply-filters"));
    expect(screen.queryByTestId("analytics-min-sample-error")).not.toBeInTheDocument();
    expect(onApplyDraft).toHaveBeenCalledWith(
      expect.objectContaining({ minSample: 8, dateFrom: "2026-01-01", dateTo: "2026-01-31" }),
    );
  });
});
