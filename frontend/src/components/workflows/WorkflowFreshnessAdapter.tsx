"use client";

import { useEffect, useMemo } from "react";

import { useShellFreshness } from "@/contexts/ShellFreshnessContext";
import {
  freshnessFromTimestamp,
  pickNewestTimestamp,
} from "@/components/workflows/freshness";

type WorkflowFreshnessAdapterProps = {
  /** Existing timestamps only — never inferred clock guesses. */
  timestamps?: Array<string | null | undefined>;
  fallbackUsed?: boolean;
  /** When true, clear shell freshness on unmount (page leave). */
  clearOnUnmount?: boolean;
};

/**
 * Wires honest page-level freshness into ShellFreshnessContext.
 * Default remains unavailable when no timestamp/source exists.
 */
export function WorkflowFreshnessAdapter({
  timestamps = [],
  fallbackUsed = false,
  clearOnUnmount = true,
}: WorkflowFreshnessAdapterProps) {
  const { setFreshness, clearFreshness } = useShellFreshness();
  const timestampKey = useMemo(
    () => timestamps.map((value) => value ?? "").join("|"),
    [timestamps],
  );

  useEffect(() => {
    const values = timestampKey.length ? timestampKey.split("|") : [];
    const newest = pickNewestTimestamp(values);
    const derived = freshnessFromTimestamp(newest, { fallbackUsed });
    if (!derived) {
      clearFreshness();
      return;
    }
    setFreshness(derived);
  }, [timestampKey, fallbackUsed, setFreshness, clearFreshness]);

  useEffect(() => {
    if (!clearOnUnmount) return;
    return () => {
      clearFreshness();
    };
  }, [clearOnUnmount, clearFreshness]);

  return null;
}
