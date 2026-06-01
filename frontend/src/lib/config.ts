/** Frontend runtime configuration (safe defaults for local dev). */

export const appConfig = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "AlphaTrade AI",
  executionMode: process.env.NEXT_PUBLIC_EXECUTION_MODE ?? "paper",
  providerMode: process.env.NEXT_PUBLIC_PROVIDER_MODE ?? "mock",
  /** When true, refresh token lives in httpOnly cookie; access token stays in sessionStorage. */
  authCookieMode: process.env.NEXT_PUBLIC_AUTH_COOKIE_MODE === "true",
} as const;
