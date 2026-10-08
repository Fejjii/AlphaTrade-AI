import { expect, it, vi } from "vitest";
import { apiFetch } from "./client";
import { demoAccountApi } from "./dashboard-demo-account";

vi.mock("./client", () => ({ apiFetch: vi.fn() }));

it("uses authenticated reads and an explicit POST for native account refresh", async () => {
  await demoAccountApi.latest();
  expect(apiFetch).toHaveBeenCalledWith("/dashboard/demo-account", {
    auth: true,
  });
  await demoAccountApi.refresh();
  expect(apiFetch).toHaveBeenCalledWith("/dashboard/demo-account/refresh", {
    method: "POST",
    auth: true,
  });
});
