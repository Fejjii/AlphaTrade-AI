import { expect, it, vi } from "vitest";

const apiFetch = vi.fn().mockResolvedValue({});
vi.mock("@/lib/api/client", () => ({ apiFetch: (...args: unknown[]) => apiFetch(...args) }));

it("requests attention as an authenticated read with no client-selected tenant", async () => {
  const { api } = await import("@/lib/api");
  await api.dashboard.attention();
  expect(apiFetch).toHaveBeenCalledWith("/dashboard/attention", { auth: true });
});
