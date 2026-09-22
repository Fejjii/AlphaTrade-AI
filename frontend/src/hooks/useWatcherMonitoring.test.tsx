import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useWatcherMonitoring } from "@/hooks/useWatcherMonitoring";
import { api } from "@/lib/api";
import { makeWatcherMonitoringSnapshot } from "@/lib/watcher-monitoring-fixtures";

vi.mock("@/lib/api", () => ({
  api: {
    marketWatcher: {
      monitoring: vi.fn(),
    },
  },
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe("useWatcherMonitoring", () => {
  it("loads the typed snapshot and reloads on focus and online", async () => {
    const snapshot = makeWatcherMonitoringSnapshot();
    vi.mocked(api.marketWatcher.monitoring).mockResolvedValue(snapshot);

    const { result } = renderHook(() => useWatcherMonitoring());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data?.watcher_status).toBe("STOPPED");
    expect(result.current.data?.paper_only).toBe(true);

    const callsAfterLoad = vi.mocked(api.marketWatcher.monitoring).mock.calls.length;
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
    });
    await waitFor(() =>
      expect(vi.mocked(api.marketWatcher.monitoring).mock.calls.length).toBeGreaterThan(
        callsAfterLoad,
      ),
    );

    const callsAfterFocus = vi.mocked(api.marketWatcher.monitoring).mock.calls.length;
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await waitFor(() =>
      expect(vi.mocked(api.marketWatcher.monitoring).mock.calls.length).toBeGreaterThan(
        callsAfterFocus,
      ),
    );
  });

  it("does not invent RUNNING when the API returns STOPPED", async () => {
    vi.mocked(api.marketWatcher.monitoring).mockResolvedValue(
      makeWatcherMonitoringSnapshot({
        watcher_status: "STOPPED",
        config_flags: {
          market_watcher_enabled: true,
          watcher_orchestration_enabled: true,
          worker_enabled: true,
          market_watcher_bridge_enabled: false,
          market_watcher_bridge_auto_tick: false,
          telegram_alerts_enabled: false,
          telegram_interaction_enabled: false,
          automatic_telegram_delivery_enabled: false,
        },
      }),
    );
    const { result } = renderHook(() => useWatcherMonitoring());
    await waitFor(() => expect(result.current.data).toBeTruthy());
    expect(result.current.data?.watcher_status).toBe("STOPPED");
  });
});
