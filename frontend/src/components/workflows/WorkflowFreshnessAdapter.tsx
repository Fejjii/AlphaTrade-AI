"use client";

import { useEffect, useMemo } from "react";

import { useShellFreshness } from "@/contexts/ShellFreshnessContext";
import {
  aggregateShellFreshness,
  type FreshnessSourceInput,
} from "@/components/workflows/freshness";

type WorkflowFreshnessAdapterProps = {
  /** Per-source freshness inputs — never inferred clock guesses. */
  sources?: FreshnessSourceInput[];
  /**
   * Legacy convenience: timestamps alone. Prefer `sources` for conservative aggregation.
   * When used, each present timestamp is treated as an available optional source.
   */
  timestamps?: Array<string | null | undefined>;
  fallbackUsed?: boolean;
  /** When true, clear shell freshness on unmount (page leave). */
  clearOnUnmount?: boolean;
};

/**
 * Wires honest page-level freshness into ShellFreshnessContext.
 * Default remains unavailable when no timestamp/source exists.
 * Aggregation is conservative: least-fresh among available sources; failed required
 * sources force unavailable/fallback.
 */
export function WorkflowFreshnessAdapter({
  sources,
  timestamps = [],
  fallbackUsed = false,
  clearOnUnmount = true,
}: WorkflowFreshnessAdapterProps) {
  const { setFreshness, clearFreshness } = useShellFreshness();

  const normalizedSources = useMemo<FreshnessSourceInput[]>(() => {
    if (sources) return sources;
    return timestamps
      .filter((value): value is string => Boolean(value))
      .map((timestamp, index) => ({
        name: `timestamp-${index}`,
        timestamp,
        available: true,
        required: true,
        fallbackUsed,
      }));
  }, [sources, timestamps, fallbackUsed]);

  const sourcesKey = useMemo(
    () =>
      normalizedSources
        .map(
          (source) =>
            `${source.name}:${source.available ? "1" : "0"}:${source.required === false ? "0" : "1"}:${source.fallbackUsed ? "1" : "0"}:${source.timestamp ?? ""}`,
        )
        .join("|"),
    [normalizedSources],
  );

  useEffect(() => {
    const derived = aggregateShellFreshness(normalizedSources);
    if (!derived.state) {
      clearFreshness();
      return;
    }
    setFreshness({ state: derived.state, ageLabel: derived.ageLabel });
  }, [sourcesKey, normalizedSources, setFreshness, clearFreshness]);

  useEffect(() => {
    if (!clearOnUnmount) return;
    return () => {
      clearFreshness();
    };
  }, [clearOnUnmount, clearFreshness]);

  return null;
}
