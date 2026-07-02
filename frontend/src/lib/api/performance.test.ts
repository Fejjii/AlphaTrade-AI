import { afterEach, describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn().mockResolvedValue({});

vi.mock("@/lib/api/client", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}));

describe("api.performance client (Slice 91B)", () => {
  afterEach(() => {
    apiFetch.mockClear();
  });

  it("requests portfolio with query params", async () => {
    const { api } = await import("@/lib/api");
    await api.performance.portfolio({
      start_date: "2026-01-01",
      end_date: "2026-03-01",
      source: "proposal_flow",
      symbol: "BTCUSDT",
    });
    expect(apiFetch).toHaveBeenCalledWith("/performance/portfolio", {
      query: {
        start_date: "2026-01-01",
        end_date: "2026-03-01",
        source: "proposal_flow",
        symbol: "BTCUSDT",
      },
      auth: true,
    });
  });

  it("requests snapshots with limit", async () => {
    const { api } = await import("@/lib/api");
    await api.performance.snapshots({ limit: 25 });
    expect(apiFetch).toHaveBeenCalledWith("/performance/snapshots", {
      query: { limit: 25 },
      auth: true,
    });
  });
});
