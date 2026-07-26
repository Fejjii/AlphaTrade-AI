import type { FreshnessState } from "@/components/ui/freshness-pill";

const STALE_MS = 30 * 60 * 1000;
const DELAYED_MS = 5 * 60 * 1000;

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
  const age = Math.max(0, nowMs - date.getTime());
  const ageLabel = ageLabelFromTimestamp(value, nowMs);
  if (age >= STALE_MS) return { state: "stale", ageLabel };
  if (age >= DELAYED_MS) return { state: "delayed", ageLabel };
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
