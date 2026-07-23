/**
 * Shared auth-boundary logic for the Next.js edge middleware and client helpers.
 *
 * The access token lives in sessionStorage and the httpOnly refresh cookie lives on
 * the API origin, so the middleware cannot verify authentication itself. Instead the
 * client sets a non-sensitive session marker cookie on the frontend origin whenever
 * tokens are stored, and clears it when they are cleared. The middleware only uses
 * the marker to redirect clearly-unauthenticated visitors before any app shell HTML
 * is served. The backend remains the sole authority for authorization: a forged
 * marker only yields an empty shell whose API calls all return 401.
 */

export const SESSION_MARKER_COOKIE = "alphatrade_session";
export const SESSION_MARKER_VALUE = "1";

/** Routes that must stay reachable without a session. */
export const PUBLIC_PATHS: readonly string[] = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
];

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.includes(pathname);
}

/**
 * Restrict a post-login redirect target to a safe internal path.
 *
 * Rejects absolute URLs, protocol-relative URLs ("//evil"), backslash tricks, and
 * control characters so the `next` query parameter can never become an open redirect.
 */
export function sanitizeNextPath(raw: string | null | undefined): string {
  if (!raw) return "/";
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\")) return "/";
  if (/[\u0000-\u001f]/.test(raw)) return "/";
  return raw;
}

/**
 * Decide whether a request must be redirected to the login page.
 *
 * Returns the redirect target (with the intended destination preserved in `next`)
 * or null when the request may proceed.
 */
export function resolveAuthRedirect(options: {
  pathname: string;
  search: string;
  hasSessionMarker: boolean;
}): string | null {
  const { pathname, search, hasSessionMarker } = options;
  if (isPublicPath(pathname)) return null;
  if (hasSessionMarker) return null;
  const next = sanitizeNextPath(`${pathname}${search}`);
  return next !== "/" ? `/login?next=${encodeURIComponent(next)}` : "/login";
}
