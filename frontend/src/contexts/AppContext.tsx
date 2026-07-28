"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { api, ApiError } from "@/lib/api";
import type { HealthResponse, KillSwitchStatus, ProviderStatusResponse } from "@/lib/api/types";
import { appConfig } from "@/lib/config";
import { isAuthenticated } from "@/lib/auth/session";

/** Health and kill-switch posture refresh cadence (~60 s, FP2-105). */
export const POSTURE_REFRESH_INTERVAL_MS = 60_000;

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

  // Request-generation guards: only the latest refresh may apply its response,
  // so a slow older request can never overwrite newer posture (FP2-105).
  const statusGenerationRef = useRef(0);
  const killSwitchGenerationRef = useRef(0);
  const refreshInFlightRef = useRef(false);

  const refreshKillSwitch = useCallback(async () => {
    if (!isAuthenticated()) {
      setKillSwitchStatus(null);
      return;
    }
    const generation = ++killSwitchGenerationRef.current;
    try {
      const status = await api.risk.killSwitch();
      if (generation !== killSwitchGenerationRef.current) return;
      setKillSwitchStatus(status);
      setKillSwitchError(null);
    } catch (err) {
      if (generation !== killSwitchGenerationRef.current) return;
      // Read failures must not invent an inactive local state.
      setKillSwitchError(err instanceof Error ? err.message : "Failed to load kill switch");
    }
  }, []);

  const runStatusRefresh = useCallback(
    async ({ background }: { background: boolean }) => {
      // Background ticks never stack on top of an in-flight refresh.
      if (background && refreshInFlightRef.current) return;
      const generation = ++statusGenerationRef.current;
      refreshInFlightRef.current = true;
      if (!background) {
        setLoading(true);
        setError(null);
      }
      try {
        const [healthRes, providersRes] = await Promise.all([
          api.health.get(),
          api.providers.status(),
        ]);
        if (generation !== statusGenerationRef.current) return;
        setHealth(healthRes);
        setProviders(providersRes);
        setError(null);
      } catch (err) {
        if (generation !== statusGenerationRef.current) return;
        // Fail closed: after a failed refresh the posture is no longer
        // verified — never keep presenting the old health/providers snapshot
        // as current (FP2-101 class). Consumers already render explicit
        // "unverified"/"unknown" states for null.
        setHealth(null);
        setProviders(null);
        setError(err instanceof Error ? err.message : "Failed to load backend status");
      } finally {
        if (generation === statusGenerationRef.current) {
          refreshInFlightRef.current = false;
          if (!background) setLoading(false);
        }
      }
      // Kill-switch posture refreshes alongside health; its read failures are
      // handled internally (last authoritative state + explicit error).
      await refreshKillSwitch();
    },
    [refreshKillSwitch],
  );

  const refreshStatus = useCallback(
    () => runStatusRefresh({ background: false }),
    [runStatusRefresh],
  );

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  // Periodic + focus/visibility posture refresh (FP2-105). Background ticks
  // are silent (no global loading flicker) and never overlap.
  useEffect(() => {
    const refreshInBackground = () => {
      void runStatusRefresh({ background: true });
    };
    const onVisibilityOrFocus = () => {
      if (document.visibilityState === "hidden") return;
      refreshInBackground();
    };

    const intervalId = window.setInterval(refreshInBackground, POSTURE_REFRESH_INTERVAL_MS);
    window.addEventListener("focus", onVisibilityOrFocus);
    document.addEventListener("visibilitychange", onVisibilityOrFocus);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", onVisibilityOrFocus);
      document.removeEventListener("visibilitychange", onVisibilityOrFocus);
    };
  }, [runStatusRefresh]);

  const setKillSwitchActive = useCallback(
    async (active: boolean, reason: string) => {
      setKillSwitchBusy(true);
      setKillSwitchError(null);
      // The mutation response is authoritative: invalidate any in-flight
      // background read so a stale status can never overwrite it.
      killSwitchGenerationRef.current += 1;
      try {
        const body = {
          confirm: true,
          reason,
          expected_version: killSwitchStatus?.version ?? null,
        };
        const status = active
          ? await api.risk.activateKillSwitch(body)
          : await api.risk.deactivateKillSwitch(body);
        // Discard reads that started during the mutation window as well.
        killSwitchGenerationRef.current += 1;
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
