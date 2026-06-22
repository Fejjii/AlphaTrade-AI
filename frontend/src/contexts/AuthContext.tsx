"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import { api, ApiError } from "@/lib/api";
import type { AuthResponse, MeResponse } from "@/lib/api/types";
import { clearTokens, getRefreshToken, isAuthenticated, setTokens } from "@/lib/auth/session";

interface AuthContextValue {
  user: MeResponse["user"] | null;
  organization: MeResponse["organization"] | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, organizationName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [mustVerifyEmail, setMustVerifyEmail] = useState(true);

  useEffect(() => {
    void api.health
      .get()
      .then((health) => setMustVerifyEmail(health.must_verify_email))
      .catch(() => setMustVerifyEmail(true));
  }, []);
  const [user, setUser] = useState<MeResponse["user"] | null>(null);
  const [organization, setOrganization] = useState<MeResponse["organization"] | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshProfile = useCallback(async () => {
    if (!isAuthenticated()) {
      setUser(null);
      setOrganization(null);
      return;
    }
    const me = await api.auth.me();
    setUser(me.user);
    setOrganization(me.organization);
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        await refreshProfile();
      } catch {
        clearTokens();
        setUser(null);
        setOrganization(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [refreshProfile]);

  const applyAuthResponse = useCallback(async (response: AuthResponse) => {
    setTokens(response.tokens.access_token, response.tokens.refresh_token || undefined);
    setUser(response.user);
    setOrganization(response.organization);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await api.auth.login({ email, password });
      await applyAuthResponse(response);
      if (mustVerifyEmail && !response.user.email_verified) {
        router.replace("/verify-email");
      } else {
        router.replace("/");
      }
    },
    [applyAuthResponse, mustVerifyEmail, router],
  );

  const register = useCallback(
    async (email: string, password: string, organizationName: string) => {
      const response = await api.auth.register({ email, password, organization_name: organizationName });
      await applyAuthResponse(response);
      if (mustVerifyEmail && !response.user.email_verified) {
        router.replace("/verify-email");
      } else {
        router.replace("/");
      }
    },
    [applyAuthResponse, mustVerifyEmail, router],
  );

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();
    try {
      await api.auth.logout(refreshToken ?? undefined);
    } catch {
      // Ignore logout failures; local session is cleared regardless.
    } finally {
      clearTokens();
      setUser(null);
      setOrganization(null);
      router.replace("/login");
    }
  }, [router]);

  const value = useMemo(
    () => ({
      user,
      organization,
      loading,
      isAuthenticated: Boolean(user) && isAuthenticated(),
      login,
      register,
      logout,
      refreshProfile,
    }),
    [user, organization, loading, login, register, logout, refreshProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useRequireAuth() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!auth.loading && !isAuthenticated()) {
      router.replace("/login");
    }
  }, [auth.loading, router]);

  return auth;
}

export function getAuthErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Authentication failed";
}
