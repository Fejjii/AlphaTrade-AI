import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAnalyticsFilters } from "./useAnalyticsFilters";

const pushMock = vi.fn();
const replaceMock = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => "/analytics",
  useSearchParams: () => searchParams,
}));

describe("useAnalyticsFilters hook", () => {
  beforeEach(() => {
    pushMock.mockClear();
    replaceMock.mockClear();
    searchParams = new URLSearchParams();
  });

  it("uses push for tab changes and removes source outside Performance", () => {
    searchParams = new URLSearchParams("tab=performance&source=proposal_flow");
    const { result, rerender } = renderHook(() => useAnalyticsFilters());
    result.current.setTab("overview");
    expect(pushMock).toHaveBeenCalledWith("/analytics", { scroll: false });
    expect(replaceMock).not.toHaveBeenCalled();

    searchParams = new URLSearchParams("tab=overview");
    rerender();
    result.current.setTab("performance");
    expect(pushMock).toHaveBeenLastCalledWith("/analytics?tab=performance", { scroll: false });
  });

  it("uses push for submitted filters, presets, and clear", () => {
    const { result } = renderHook(() => useAnalyticsFilters());
    result.current.applyDraft({ symbol: "BTCUSDT", timeframe: "1h" });
    expect(pushMock).toHaveBeenCalledWith("/analytics?symbol=BTCUSDT&timeframe=1h", {
      scroll: false,
    });

    result.current.applyDatePreset("30d");
    expect(pushMock).toHaveBeenCalled();

    result.current.clearFilters();
    expect(pushMock).toHaveBeenCalledWith("/analytics", { scroll: false });
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("uses replace only for ignored-param cleanup", () => {
    searchParams = new URLSearchParams("setup_id=bad&symbol=BTCUSDT");
    const { result } = renderHook(() => useAnalyticsFilters());
    expect(result.current.state.ignoredParams).toContain("setup_id");
    result.current.cleanupIgnoredParams();
    expect(replaceMock).toHaveBeenCalledWith("/analytics?symbol=BTCUSDT", { scroll: false });
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("derives validated state from external URL changes", () => {
    searchParams = new URLSearchParams("date_from=2026-01-01&date_to=2026-01-31&symbol=BTCUSDT");
    const { result, rerender } = renderHook(() => useAnalyticsFilters());
    expect(result.current.state.dateFrom).toBe("2026-01-01");
    expect(result.current.apiParams.journal.symbol).toBe("BTCUSDT");

    searchParams = new URLSearchParams("date_from=not-a-date");
    rerender();
    expect(result.current.state.dateFrom).toBeNull();
    expect(result.current.state.ignoredParams).toContain("date_from");
    expect(result.current.apiParams.journal.date_from).toBeUndefined();
  });
});
