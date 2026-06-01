"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { HealthResponse, ProviderStatus, ProviderStatusResponse } from "@/lib/api/types";
import { appConfig } from "@/lib/config";

interface AppContextValue {
  health: HealthResponse | null;
  providers: ProviderStatusResponse | null;
  killSwitchActive: boolean;
  toggleKillSwitch: () => void;
  refreshStatus: () => Promise<void>;
  loading: boolean;
  error: string | null;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [providers, setProviders] = useState<ProviderStatusResponse | null>(null);
  const [killSwitchActive, setKillSwitchActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load backend status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const value = useMemo<AppContextValue>(
    () => ({
      health,
      providers,
      killSwitchActive,
      toggleKillSwitch: () => setKillSwitchActive((prev) => !prev),
      refreshStatus,
      loading,
      error,
    }),
    [health, providers, killSwitchActive, refreshStatus, loading, error],
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

export function useSafetyPosture() {
  const { health } = useAppContext();
  return {
    executionMode: health?.execution_mode ?? appConfig.executionMode,
    realTradingEnabled: health?.real_trading_enabled ?? false,
    providerMode: appConfig.providerMode,
  };
}
