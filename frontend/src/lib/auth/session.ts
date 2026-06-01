/**
 * Session helpers for MVP auth.
 *
 * Bearer mode (default): access + refresh tokens in sessionStorage — fine for local dev.
 * Cookie mode: refresh token in httpOnly cookie; access token in sessionStorage only.
 * See docs/security.md.
 */

const ACCESS_KEY = "alphatrade_access_token";
const REFRESH_KEY = "alphatrade_refresh_token";

export function usesCookieRefresh(): boolean {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_AUTH_COOKIE_MODE === "true";
  }
  return process.env.NEXT_PUBLIC_AUTH_COOKIE_MODE === "true";
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  if (usesCookieRefresh()) return null;
  return sessionStorage.getItem(REFRESH_KEY);
}

export function setTokens(accessToken: string, refreshToken?: string): void {
  sessionStorage.setItem(ACCESS_KEY, accessToken);
  if (!usesCookieRefresh() && refreshToken) {
    sessionStorage.setItem(REFRESH_KEY, refreshToken);
  }
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS_KEY);
  if (!usesCookieRefresh()) {
    sessionStorage.removeItem(REFRESH_KEY);
  }
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}
