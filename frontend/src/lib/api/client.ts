import { appConfig } from "@/lib/config";
import { clearTokens, getAccessToken, getRefreshToken, setTokens, usesCookieRefresh } from "@/lib/auth/session";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function buildUrl(path: string, query?: Record<string, string | number | boolean | undefined | null>) {
  const url = new URL(path, appConfig.apiBaseUrl);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

function fetchCredentials(): RequestCredentials {
  return usesCookieRefresh() ? "include" : "same-origin";
}

function parseErrorMessage(body: unknown, fallback: string): string {
  if (typeof body === "object" && body && "error" in body) {
    const err = (body as { error?: { message?: string } }).error;
    if (err?.message) return err.message;
  }
  if (typeof body === "object" && body && "detail" in body) {
    return String((body as { detail: unknown }).detail);
  }
  return fallback;
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  const body = refreshToken ? JSON.stringify({ refresh_token: refreshToken }) : JSON.stringify({});
  const response = await fetch(buildUrl("/auth/refresh"), {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body,
    credentials: fetchCredentials(),
    cache: "no-store",
  });
  if (!response.ok) {
    clearTokens();
    return false;
  }
  const payload = (await response.json()) as {
    access_token: string;
    refresh_token?: string;
  };
  setTokens(payload.access_token, payload.refresh_token);
  return true;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & {
    query?: Record<string, string | number | boolean | undefined | null>;
    auth?: boolean;
    retryOnUnauthorized?: boolean;
  } = {},
): Promise<T> {
  const {
    query,
    headers,
    auth = !path.startsWith("/auth/"),
    retryOnUnauthorized = true,
    ...rest
  } = options;

  const requestHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(rest.body ? { "Content-Type": "application/json" } : {}),
    ...(headers as Record<string, string> | undefined),
  };

  if (auth) {
    const token = getAccessToken();
    if (token) requestHeaders.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(buildUrl(path, query), {
    ...rest,
    headers: requestHeaders,
    credentials: fetchCredentials(),
    cache: "no-store",
  });

  if (response.status === 401 && auth && retryOnUnauthorized) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch<T>(path, { ...options, retryOnUnauthorized: false });
    }
    if (typeof window !== "undefined") {
      clearTokens();
      window.location.assign("/login");
    }
    throw new ApiError("Session expired", 401, null);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const body = text ? (JSON.parse(text) as unknown) : null;

  if (!response.ok) {
    throw new ApiError(parseErrorMessage(body, response.statusText), response.status, body);
  }

  return body as T;
}
