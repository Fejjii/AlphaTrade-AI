import { NextResponse, type NextRequest } from "next/server";

import {
  resolveAuthRedirect,
  SESSION_MARKER_COOKIE,
  SESSION_MARKER_VALUE,
} from "@/lib/auth/boundary";

/**
 * Edge auth boundary (AT-017): redirect clearly-unauthenticated visitors away from
 * protected app routes before any shell HTML is served. Defense in depth only —
 * the backend rejects unauthorized API calls regardless of this middleware.
 */
export function middleware(request: NextRequest) {
  const redirect = resolveAuthRedirect({
    pathname: request.nextUrl.pathname,
    search: request.nextUrl.search,
    hasSessionMarker:
      request.cookies.get(SESSION_MARKER_COOKIE)?.value === SESSION_MARKER_VALUE,
  });
  if (!redirect) return NextResponse.next();
  return NextResponse.redirect(new URL(redirect, request.nextUrl.origin));
}

export const config = {
  // Everything except Next internals and static files (paths with a file extension).
  matcher: ["/((?!_next/|.*\\..*).*)"],
};
