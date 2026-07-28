import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import type { AuthResponse, HealthResponse, ProviderStatusResponse } from "@/lib/api/types";

import { AppProvider, useAppContext } from "./AppContext";
import { AuthProvider, useAuth } from "./AuthContext";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    health: { get: vi.fn() },
    providers: { status: vi.fn() },
    risk: {
      killSwitch: vi.fn(),
      activateKillSwitch: vi.fn(),
      deactivateKillSwitch: vi.fn(),
    },
    auth: {
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      me: vi.fn(),
    },
  },
  ApiError: class MockApiError extends Error {},
}));

vi.mock("@/lib/auth/session", () => ({
  // Unauthenticated at mount: profile and kill-switch reads stay local.
  isAuthenticated: () => false,
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  getRefreshToken: () => null,
}));

const healthVerificationOff: HealthResponse = {
  status: "ok",
  app: "alphatrade",
  version: "0.1.0",
  environment: "test",
  execution_mode: "paper",
  real_trading_enabled: false,
  must_verify_email: false,
  timestamp: "2026-07-28T00:00:00Z",
};

const providersOk: ProviderStatusResponse = {
  generated_at: "2026-07-28T00:00:00Z",
  providers: [],
};

const unverifiedLogin: AuthResponse = {
  user: {
    id: "user-1",
    email: "trader@example.com",
    role: "owner",
    risk_profile: "conservative",
    timezone: "UTC",
    is_active: true,
    email_verified: false,
    created_at: "2026-07-01T00:00:00Z",
  },
  organization: { id: "org-1", name: "Test Org", created_at: "2026-07-01T00:00:00Z" },
  tokens: {
    access_token: "access",
    refresh_token: "refresh",
    token_type: "bearer",
    expires_in: 900,
  },
};

function renderAuth() {
  return renderHook(() => ({ auth: useAuth(), app: useAppContext() }), {
    wrapper: ({ children }) => (
      <AppProvider>
        <AuthProvider>{children}</AuthProvider>
      </AppProvider>
    ),
  });
}

describe("AuthContext verification policy from shared health source (FP2-105)", () => {
  beforeEach(() => {
    vi.mocked(api.auth.login).mockResolvedValue(unverifiedLogin);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("provider-status failure alone does not force verification when /health said it is off", async () => {
    vi.mocked(api.health.get).mockResolvedValue(healthVerificationOff);
    vi.mocked(api.providers.status).mockRejectedValue(new Error("providers down"));

    const { result } = renderAuth();
    // Wait until the shared health result (with the verification policy) has
    // landed despite the provider-status failure.
    await waitFor(() => expect(result.current.app.health).toEqual(healthVerificationOff));
    await waitFor(() => expect(result.current.app.providers).toBeNull());
    await waitFor(() => expect(result.current.auth.loading).toBe(false));

    await act(async () => {
      await result.current.auth.login("trader@example.com", "pw");
    });

    // must_verify_email=false came from a successful /health; the provider
    // failure must not override that policy conservatively.
    expect(replaceMock).toHaveBeenCalledWith("/");
    expect(replaceMock).not.toHaveBeenCalledWith("/verify-email");
  });

  it("health failure stays conservative: verification required for unverified users", async () => {
    vi.mocked(api.health.get).mockRejectedValue(new Error("health unreachable"));
    vi.mocked(api.providers.status).mockResolvedValue(providersOk);

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.app.error).toBe("health unreachable"));
    // The sibling provider result is preserved and honest.
    await waitFor(() => expect(result.current.app.providers).toEqual(providersOk));
    await waitFor(() => expect(result.current.auth.loading).toBe(false));

    await act(async () => {
      await result.current.auth.login("trader@example.com", "pw");
    });

    expect(replaceMock).toHaveBeenCalledWith("/verify-email");
  });
});
