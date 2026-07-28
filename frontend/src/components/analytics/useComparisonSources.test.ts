import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import type { AnalyticsFilterParams } from "./filterValidation";
import { useComparisonSources } from "./useComparisonSources";

vi.mock("@/lib/api", () => ({
  api: {
    journal: { comparison: vi.fn() },
  },
}));

const comparisonResponse = {
  filters: {},
  human: null,
  system: null,
  deltas: null,
  sample_warnings: [],
  generated_at: "2026-07-25T12:00:00Z",
};

const defaultParams: AnalyticsFilterParams = {
  journal: { group_by: "overall" as const },
  portfolio: { timezone: "UTC" },
  ruleComplianceJournal: { group_by: "rule_compliance", limit: 20 },
  comparison: {},
  analyticsWindow: {},
  learningWindow: {},
  validation: { dimension: "condition", min_sample: 5 },
  strategyQuality: { min_sample: 5 },
  state: {
    tab: "comparison" as const,
    dateFrom: null,
    dateTo: null,
    symbol: null,
    timeframe: null,
    portfolioSource: null,
    journalSource: null,
    setupId: null,
    userStrategyId: null,
    strategyVersionId: null,
    ruleCompliance: null,
    marketRegime: null,
    groupBy: "setup" as const,
    bucketOffset: 0,
    minSample: 5,
    dimension: "condition" as const,
    ignoredParams: [],
  },
};

describe("useComparisonSources", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads the comparison source when enabled", async () => {
    vi.mocked(api.journal.comparison).mockResolvedValue(comparisonResponse as never);

    const { result } = renderHook(() => useComparisonSources(defaultParams, true));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.comparison?.available).toBe(true);
    expect(result.current.retryLoading).toBe(false);
  });

  it("does not fetch when disabled", async () => {
    renderHook(() => useComparisonSources(defaultParams, false));
    await act(async () => {
      await Promise.resolve();
    });
    expect(api.journal.comparison).not.toHaveBeenCalled();
  });

  it("reports retryLoading during a same-filter reload while prior data stays mounted (FP2-126)", async () => {
    vi.mocked(api.journal.comparison).mockResolvedValue(comparisonResponse as never);

    const { result } = renderHook(() => useComparisonSources(defaultParams, true));
    await waitFor(() => expect(result.current.loading).toBe(false));

    let resolveSlow: (value: unknown) => void = () => undefined;
    vi.mocked(api.journal.comparison).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSlow = resolve;
      }) as never,
    );

    act(() => {
      void result.current.reload();
    });

    expect(result.current.retryLoading).toBe(true);
    expect(result.current.comparison).not.toBeNull();

    await act(async () => {
      resolveSlow(comparisonResponse);
    });
    await waitFor(() => expect(result.current.retryLoading).toBe(false));
    expect(result.current.comparison?.available).toBe(true);
  });
});
