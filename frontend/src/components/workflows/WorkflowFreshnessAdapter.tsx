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
   * Missing timestamps are excluded here (no freshness meaning) before aggregation.
   */
  timestamps?: Array<string | null | undefined>;
  fallbackUsed?: boolean;
  /** When true, clear shell freshness on unmount (page leave). */
  clearOnUnmount?: boolean;
};

function buildNormalizedSources(
  sources: FreshnessSourceInput[] | undefined,
  timestamps: Array<string | null | undefined>,
  fallbackUsed: boolean,
): FreshnessSourceInput[] {
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
}

function serializeFreshnessSources(sources: FreshnessSourceInput[]): string {
  return sources
    .map(
      (source) =>
        [
          source.name,
          source.available ? "1" : "0",
          source.required === false ? "0" : "1",
          source.fallbackUsed ? "1" : "0",
          source.timestamp ?? "",
        ].join(":"),
    )
    .join("|");
}

/**
 * Wires honest page-level freshness into ShellFreshnessContext.
 * Default remains unavailable when no timestamp/source exists.
 * Aggregation is conservative: least-fresh among included sources; failed required
 * sources force unavailable/fallback. Equivalent `sources` arrays do not re-push context.
 */
export function WorkflowFreshnessAdapter({
  sources,
  timestamps = [],
  fallbackUsed = false,
  clearOnUnmount = true,
}: WorkflowFreshnessAdapterProps) {
  const { setFreshness, clearFreshness } = useShellFreshness();

  const sourcesKey = useMemo(
    () => serializeFreshnessSources(buildNormalizedSources(sources, timestamps, fallbackUsed)),
    [sources, timestamps, fallbackUsed],
  );

  const derived = useMemo(() => {
    // Recompute from current props when the serialized key changes only.
    // Equivalent recreated `sources` arrays share the same key and reuse this result.
    const normalized = buildNormalizedSources(sources, timestamps, fallbackUsed);
    return aggregateShellFreshness(normalized);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sourcesKey is the content-equality gate
  }, [sourcesKey]);

  const derivedKey = `${derived.state ?? "null"}:${derived.ageLabel ?? ""}`;

  useEffect(() => {
    if (!derived.state) {
      clearFreshness();
      return;
    }
    setFreshness({ state: derived.state, ageLabel: derived.ageLabel });
  }, [derivedKey, derived.state, derived.ageLabel, setFreshness, clearFreshness]);

  useEffect(() => {
    if (!clearOnUnmount) return;
    return () => {
      clearFreshness();
    };
  }, [clearOnUnmount, clearFreshness]);

  return null;
}
