/**
 * Session helpers for MVP auth.
 *
 * Bearer mode (default): access + refresh tokens in sessionStorage — fine for local dev.
 * Cookie mode: refresh token in httpOnly cookie; access token in sessionStorage only.
 *
 * A non-sensitive session marker cookie (no token material) is kept on the frontend
 * origin so the edge middleware can redirect unauthenticated visitors before serving
 * protected shell HTML (AT-017). See docs/security.md.
 */

import { SESSION_MARKER_COOKIE, SESSION_MARKER_VALUE } from "@/lib/auth/boundary";

const ACCESS_KEY = "alphatrade_access_token";
const REFRESH_KEY = "alphatrade_refresh_token";

export function usesCookieRefresh(): boolean {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_AUTH_COOKIE_MODE === "true";
  }
  return process.env.NEXT_PUBLIC_AUTH_COOKIE_MODE === "true";
}

function markerCookieSuffix(): string {
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  return `; Path=/; SameSite=Lax${secure}`;
}

function setSessionMarker(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${SESSION_MARKER_COOKIE}=${SESSION_MARKER_VALUE}${markerCookieSuffix()}`;
}

function clearSessionMarker(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${SESSION_MARKER_COOKIE}=; Max-Age=0${markerCookieSuffix()}`;
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
  setSessionMarker();
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS_KEY);
  if (!usesCookieRefresh()) {
    sessionStorage.removeItem(REFRESH_KEY);
  }
  clearSessionMarker();
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}
