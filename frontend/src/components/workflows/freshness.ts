import type { FreshnessState } from "@/components/ui/freshness-pill";

const STALE_MS = 30 * 60 * 1000;
const DELAYED_MS = 5 * 60 * 1000;
/** Treat timestamps materially in the future as clock-skewed, not live. */
const FUTURE_SKEW_MS = 60 * 1000;

const STATE_RANK: Record<FreshnessState, number> = {
  unavailable: 0,
  fallback: 1,
  stale: 2,
  delayed: 3,
  live: 4,
};

function parseTimestamp(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Format a short age label from a known timestamp. Never invents freshness. */
export function ageLabelFromTimestamp(
  value: string | null | undefined,
  nowMs: number = Date.now(),
): string | undefined {
  const date = parseTimestamp(value);
  if (!date) return undefined;
  const delta = Math.max(0, nowMs - date.getTime());
  const minutes = Math.floor(delta / 60_000);
  if (minutes < 1) return "<1m";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

/**
 * Derive an honest freshness state from an existing timestamp only.
 * Returns null when no trustworthy timestamp exists (default remains unavailable).
 * Future/clock-skewed timestamps are treated as unavailable, not live.
 */
export function freshnessFromTimestamp(
  value: string | null | undefined,
  options?: { fallbackUsed?: boolean; nowMs?: number },
): { state: FreshnessState; ageLabel?: string } | null {
  if (options?.fallbackUsed) {
    return {
      state: "fallback",
      ageLabel: ageLabelFromTimestamp(value, options.nowMs),
    };
  }
  const date = parseTimestamp(value);
  if (!date) return null;
  const nowMs = options?.nowMs ?? Date.now();
  const age = nowMs - date.getTime();
  if (age < -FUTURE_SKEW_MS) {
    return { state: "unavailable", ageLabel: "clock skew" };
  }
  const ageLabel = ageLabelFromTimestamp(value, nowMs);
  const nonNegativeAge = Math.max(0, age);
  if (nonNegativeAge >= STALE_MS) return { state: "stale", ageLabel };
  if (nonNegativeAge >= DELAYED_MS) return { state: "delayed", ageLabel };
  return { state: "live", ageLabel };
}

/**
 * Prefer the newest honest timestamp among known sources.
 * Does not fabricate status when every source is missing.
 */
export function pickNewestTimestamp(
  values: Array<string | null | undefined>,
): string | null {
  let newest: string | null = null;
  let newestMs = Number.NEGATIVE_INFINITY;
  for (const value of values) {
    const date = parseTimestamp(value);
    if (!date) continue;
    const ms = date.getTime();
    if (ms > newestMs) {
      newestMs = ms;
      newest = value ?? null;
    }
  }
  return newest;
}

export type FreshnessSourceInput = {
  name: string;
  timestamp?: string | null;
  available: boolean;
  required?: boolean;
  fallbackUsed?: boolean;
};

/**
 * Conservatively aggregate page-level freshness across sources.
 * One fresh source never makes the whole page live when others are worse/failed.
 */
export function aggregateShellFreshness(
  sources: FreshnessSourceInput[],
  options?: { nowMs?: number },
): { state: FreshnessState | null; ageLabel?: string } {
  if (!sources.length) return { state: null };

  const requiredFailed = sources.some(
    (source) => source.required !== false && !source.available,
  );
  if (requiredFailed) {
    const anyFallback = sources.some((source) => source.fallbackUsed);
    return { state: anyFallback ? "fallback" : "unavailable" };
  }

  const derived = sources
    .filter((source) => source.available)
    .map((source) => {
      if (source.fallbackUsed) {
        return {
          state: "fallback" as const,
          ageLabel: ageLabelFromTimestamp(source.timestamp, options?.nowMs),
        };
      }
      return freshnessFromTimestamp(source.timestamp, {
        nowMs: options?.nowMs,
        fallbackUsed: false,
      });
    })
    .filter((item): item is { state: FreshnessState; ageLabel?: string } => item != null);

  if (!derived.length) return { state: null };

  let least = derived[0];
  for (const item of derived.slice(1)) {
    if (STATE_RANK[item.state] < STATE_RANK[least.state]) {
      least = item;
    }
  }
  return least;
}
