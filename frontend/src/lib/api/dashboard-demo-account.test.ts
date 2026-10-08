import { expect, it, vi } from "vitest";
import { apiFetch } from "./client";
import { demoAccountApi } from "./dashboard-demo-account";

vi.mock("./client", () => ({ apiFetch: vi.fn() }));

it("uses authenticated reads and an explicit POST for native account refresh", async () => {
  await demoAccountApi.latest();
  expect(apiFetch).toHaveBeenCalledWith("/dashboard/demo-account", {
    auth: true,
    signal: undefined,
  });
  await demoAccountApi.refresh();
  expect(apiFetch).toHaveBeenCalledWith("/dashboard/demo-account/refresh", {
    method: "POST",
    auth: true,
    signal: undefined,
  });
});

it("passes the abort signal through both saved reads and native refresh", async () => {
  const { signal } = new AbortController();
  await demoAccountApi.latest(signal);
  expect(apiFetch).toHaveBeenLastCalledWith("/dashboard/demo-account", { auth: true, signal });
  await demoAccountApi.refresh(signal);
  expect(apiFetch).toHaveBeenLastCalledWith("/dashboard/demo-account/refresh", {
    method: "POST", auth: true, signal,
  });
});
