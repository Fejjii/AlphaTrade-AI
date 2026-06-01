import { afterEach, describe, expect, it, vi } from "vitest";

describe("api client deployment config", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  it("uses configured NEXT_PUBLIC_API_URL", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.staging.example.com");
    const { appConfig } = await import("@/lib/config");
    expect(appConfig.apiBaseUrl).toBe("https://api.staging.example.com");
  });

  it("cookie mode enables credentials include on fetch", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_COOKIE_MODE", "true");
    const { usesCookieRefresh } = await import("@/lib/auth/session");
    expect(usesCookieRefresh()).toBe(true);

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ access_token: "new-access" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { apiFetch } = await import("@/lib/api/client");
    await apiFetch("/health", { auth: false });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/health"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("bearer mode uses same-origin credentials", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_COOKIE_MODE", "false");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ app: "AlphaTrade AI" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { apiFetch } = await import("@/lib/api/client");
    await apiFetch("/health", { auth: false });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/health"),
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });
});
