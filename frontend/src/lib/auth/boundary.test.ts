import { describe, expect, it } from "vitest";

import {
  isPublicPath,
  PUBLIC_PATHS,
  resolveAuthRedirect,
  sanitizeNextPath,
} from "./boundary";

describe("sanitizeNextPath", () => {
  it("keeps safe internal paths", () => {
    expect(sanitizeNextPath("/portfolio")).toBe("/portfolio");
    expect(sanitizeNextPath("/proposals?id=abc")).toBe("/proposals?id=abc");
    expect(sanitizeNextPath("/")).toBe("/");
  });

  it("rejects open-redirect attempts", () => {
    expect(sanitizeNextPath("https://evil.example")).toBe("/");
    expect(sanitizeNextPath("//evil.example")).toBe("/");
    expect(sanitizeNextPath("/\\evil.example")).toBe("/");
    expect(sanitizeNextPath("javascript:alert(1)")).toBe("/");
    expect(sanitizeNextPath("/ok\u0000bad")).toBe("/");
    expect(sanitizeNextPath(null)).toBe("/");
    expect(sanitizeNextPath(undefined)).toBe("/");
    expect(sanitizeNextPath("")).toBe("/");
  });
});

describe("resolveAuthRedirect", () => {
  it("allows public routes without a session marker", () => {
    for (const path of PUBLIC_PATHS) {
      expect(isPublicPath(path)).toBe(true);
      expect(
        resolveAuthRedirect({ pathname: path, search: "", hasSessionMarker: false }),
      ).toBeNull();
    }
  });

  it("redirects unauthenticated protected routes and preserves the destination", () => {
    expect(
      resolveAuthRedirect({ pathname: "/portfolio", search: "", hasSessionMarker: false }),
    ).toBe(`/login?next=${encodeURIComponent("/portfolio")}`);
    expect(
      resolveAuthRedirect({ pathname: "/proposals", search: "?id=1", hasSessionMarker: false }),
    ).toBe(`/login?next=${encodeURIComponent("/proposals?id=1")}`);
  });

  it("redirects the root path without a next parameter", () => {
    expect(resolveAuthRedirect({ pathname: "/", search: "", hasSessionMarker: false })).toBe(
      "/login",
    );
  });

  it("allows protected routes when the session marker is present", () => {
    expect(
      resolveAuthRedirect({ pathname: "/portfolio", search: "", hasSessionMarker: true }),
    ).toBeNull();
    expect(resolveAuthRedirect({ pathname: "/", search: "", hasSessionMarker: true })).toBeNull();
  });

  it("never produces a redirect target on an external origin", () => {
    const redirect = resolveAuthRedirect({
      pathname: "/portfolio",
      search: "?next=https://evil.example",
      hasSessionMarker: false,
    });
    expect(redirect).not.toBeNull();
    expect(redirect!.startsWith("/login")).toBe(true);
  });
});
