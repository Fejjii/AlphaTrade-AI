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

const SETUP_UUID = "11111111-1111-1111-1111-111111111111";

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

  it("uses push for Setups tab and drops setup params when leaving", () => {
    searchParams = new URLSearchParams(
      `tab=setups&setup_id=${SETUP_UUID}&group_by=strategy&offset=20&symbol=BTCUSDT`,
    );
    const { result } = renderHook(() => useAnalyticsFilters());
    result.current.setTab("overview");
    expect(pushMock).toHaveBeenCalledWith("/analytics?symbol=BTCUSDT", { scroll: false });
  });

  it("uses push for grouping toggle and bucket pagination", () => {
    searchParams = new URLSearchParams("tab=setups");
    const { result } = renderHook(() => useAnalyticsFilters());
    result.current.setGroupBy("setup_version");
    expect(pushMock).toHaveBeenCalledWith("/analytics?tab=setups&group_by=setup_version", {
      scroll: false,
    });
    result.current.setBucketOffset(20);
    expect(pushMock).toHaveBeenCalledWith("/analytics?tab=setups&offset=20", { scroll: false });
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

  it("derives validated setup deep-link state without portfolio params", () => {
    searchParams = new URLSearchParams(
      `tab=setups&setup_id=${SETUP_UUID}&date_from=2026-01-01&portfolio_setup=breakout`,
    );
    const { result } = renderHook(() => useAnalyticsFilters());
    expect(result.current.state.setupId).toBe(SETUP_UUID);
    expect(result.current.setupApiParams.journal.setup_id).toBe(SETUP_UUID);
    expect(result.current.apiParams.portfolio).not.toHaveProperty("setup");
    expect(result.current.apiParams.journal.setup_id).toBeUndefined();
    expect(result.current.state.ignoredParams).toContain("portfolio_setup");
  });
});
