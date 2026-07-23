"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { HealthResponse, KillSwitchStatus, ProviderStatus, ProviderStatusResponse } from "@/lib/api/types";
import { appConfig } from "@/lib/config";
import { isAuthenticated } from "@/lib/auth/session";

interface AppContextValue {
  health: HealthResponse | null;
  providers: ProviderStatusResponse | null;
  killSwitchActive: boolean;
  killSwitchStatus: KillSwitchStatus | null;
  killSwitchError: string | null;
  killSwitchBusy: boolean;
  refreshKillSwitch: () => Promise<void>;
  setKillSwitchActive: (active: boolean, reason: string) => Promise<void>;
  refreshStatus: () => Promise<void>;
  loading: boolean;
  error: string | null;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [providers, setProviders] = useState<ProviderStatusResponse | null>(null);
  const [killSwitchStatus, setKillSwitchStatus] = useState<KillSwitchStatus | null>(null);
  const [killSwitchError, setKillSwitchError] = useState<string | null>(null);
  const [killSwitchBusy, setKillSwitchBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshKillSwitch = useCallback(async () => {
    if (!isAuthenticated()) {
      setKillSwitchStatus(null);
      return;
    }
    try {
      const status = await api.risk.killSwitch();
      setKillSwitchStatus(status);
      setKillSwitchError(null);
    } catch (err) {
      // Read failures must not invent an inactive local state.
      setKillSwitchError(err instanceof Error ? err.message : "Failed to load kill switch");
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, providersRes] = await Promise.all([
        api.health.get(),
        api.providers.status(),
      ]);
      setHealth(healthRes);
      setProviders(providersRes);
      await refreshKillSwitch();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load backend status");
    } finally {
      setLoading(false);
    }
  }, [refreshKillSwitch]);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const setKillSwitchActive = useCallback(
    async (active: boolean, reason: string) => {
      setKillSwitchBusy(true);
      setKillSwitchError(null);
      try {
        const body = {
          confirm: true,
          reason,
          expected_version: killSwitchStatus?.version ?? null,
        };
        const status = active
          ? await api.risk.activateKillSwitch(body)
          : await api.risk.deactivateKillSwitch(body);
        setKillSwitchStatus(status);
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Kill switch update failed";
        setKillSwitchError(message);
        throw err;
      } finally {
        setKillSwitchBusy(false);
      }
    },
    [killSwitchStatus?.version],
  );

  const value = useMemo<AppContextValue>(
    () => ({
      health,
      providers,
      killSwitchActive: Boolean(killSwitchStatus?.execution_blocked),
      killSwitchStatus,
      killSwitchError,
      killSwitchBusy,
      refreshKillSwitch,
      setKillSwitchActive,
      refreshStatus,
      loading,
      error,
    }),
    [
      health,
      providers,
      killSwitchStatus,
      killSwitchError,
      killSwitchBusy,
      refreshKillSwitch,
      setKillSwitchActive,
      refreshStatus,
      loading,
      error,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be used within AppProvider");
  return ctx;
}

export function useMockProviders(): ProviderStatus[] {
  const { providers } = useAppContext();
  return providers?.providers ?? [];
}

export interface SafetyPosture {
  /** Execution mode reported by backend /health, or null until verified. */
  executionMode: string | null;
  /** Real-trading flag reported by backend /health, or null until verified. */
  realTradingEnabled: boolean | null;
  providerMode: string;
  /** True only after /health has been loaded — never inferred from build config. */
  postureKnown: boolean;
}

export function useSafetyPosture(): SafetyPosture {
  const { health } = useAppContext();
  return {
    executionMode: health?.execution_mode ?? null,
    realTradingEnabled: health?.real_trading_enabled ?? null,
    providerMode: appConfig.providerMode,
    postureKnown: health != null,
  };
}
