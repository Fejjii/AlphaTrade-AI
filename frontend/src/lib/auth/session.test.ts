import { afterEach, describe, expect, it, vi } from "vitest";

import { clearTokens, getAccessToken, getRefreshToken, isAuthenticated, setTokens, usesCookieRefresh } from "./session";

describe("session storage", () => {
  afterEach(() => {
    clearTokens();
    vi.unstubAllEnvs();
  });

  it("stores bearer tokens in sessionStorage", () => {
    setTokens("access-token-value", "refresh-token-value");
    expect(getAccessToken()).toBe("access-token-value");
    expect(getRefreshToken()).toBe("refresh-token-value");
    expect(isAuthenticated()).toBe(true);
    clearTokens();
    expect(getAccessToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("cookie mode keeps refresh out of sessionStorage", () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_COOKIE_MODE", "true");
    expect(usesCookieRefresh()).toBe(true);
    setTokens("access-only", "should-not-store");
    expect(getAccessToken()).toBe("access-only");
    expect(getRefreshToken()).toBeNull();
  });
});
