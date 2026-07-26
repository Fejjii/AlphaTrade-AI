"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { FreshnessState } from "@/components/ui/freshness-pill";

/**
 * Optional page-level freshness for the app shell TopBar.
 * Phase B default is unavailable; pages may set honest values later (Phase C).
 */
export type ShellFreshnessValue = {
  state: FreshnessState | null;
  ageLabel?: string;
};

type ShellFreshnessContextValue = {
  freshness: ShellFreshnessValue;
  setFreshness: (value: ShellFreshnessValue) => void;
  clearFreshness: () => void;
};

const defaultFreshness: ShellFreshnessValue = { state: null };

const ShellFreshnessContext = createContext<ShellFreshnessContextValue | null>(null);

export function ShellFreshnessProvider({ children }: { children: ReactNode }) {
  const [freshness, setFreshnessState] = useState<ShellFreshnessValue>(defaultFreshness);

  const setFreshness = useCallback((value: ShellFreshnessValue) => {
    setFreshnessState(value);
  }, []);

  const clearFreshness = useCallback(() => {
    setFreshnessState(defaultFreshness);
  }, []);

  const value = useMemo(
    () => ({ freshness, setFreshness, clearFreshness }),
    [freshness, setFreshness, clearFreshness],
  );

  return (
    <ShellFreshnessContext.Provider value={value}>{children}</ShellFreshnessContext.Provider>
  );
}

export function useShellFreshness(): ShellFreshnessContextValue {
  const ctx = useContext(ShellFreshnessContext);
  if (!ctx) {
    return {
      freshness: defaultFreshness,
      setFreshness: () => undefined,
      clearFreshness: () => undefined,
    };
  }
  return ctx;
}
