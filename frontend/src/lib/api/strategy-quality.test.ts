import { afterEach, describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn().mockResolvedValue({});

vi.mock("@/lib/api/client", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}));

describe("api.strategyQuality client (Slice 89)", () => {
  afterEach(() => {
    apiFetch.mockClear();
  });

  it("requests detectors with query params", async () => {
    const { api } = await import("@/lib/api");
    await api.strategyQuality.detectors({ min_sample: 8, condition: "sfp" });
    expect(apiFetch).toHaveBeenCalledWith("/strategy-quality/detectors", {
      query: { min_sample: 8, condition: "sfp" },
    });
  });

  it("requests summary", async () => {
    const { api } = await import("@/lib/api");
    await api.strategyQuality.summary();
    expect(apiFetch).toHaveBeenCalledWith("/strategy-quality/summary", { query: undefined });
  });

  it("requests a per-detector explain by condition", async () => {
    const { api } = await import("@/lib/api");
    await api.strategyQuality.explain("liquidity_sweep", { start_date: "2026-01-01" });
    expect(apiFetch).toHaveBeenCalledWith("/strategy-quality/detectors/liquidity_sweep/explain", {
      query: { start_date: "2026-01-01" },
    });
  });
});
