/**
 * Honest metric display helpers for Portfolio.
 * Missing values must never render as fabricated zeros or currency amounts.
 */

export type MetricDisplay =
  | { kind: "value"; text: string; numeric: number | null }
  | { kind: "unavailable"; text: string }
  | { kind: "partial"; text: string };

export function parseMetricNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const num = typeof value === "string" ? Number(value) : value;
  return Number.isFinite(num) ? num : null;
}

export function formatMetricValue(
  value: string | number | null | undefined,
  options?: { unavailableLabel?: string },
): MetricDisplay {
  if (value === null || value === undefined || value === "") {
    return {
      kind: "unavailable",
      text: options?.unavailableLabel ?? "Unavailable",
    };
  }
  const numeric = parseMetricNumber(value);
  if (numeric === null) {
    return { kind: "unavailable", text: options?.unavailableLabel ?? "Unavailable" };
  }
  return {
    kind: "value",
    text: numeric.toLocaleString(undefined, { maximumFractionDigits: 6 }),
    numeric,
  };
}

export function formatOptionalTimestamp(value: string | null | undefined): string {
  if (!value) return "Freshness unavailable";
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return "Freshness unavailable";
  return new Date(parsed).toLocaleString();
}

export function isValidTimestamp(value: string | null | undefined): boolean {
  if (!value) return false;
  return Number.isFinite(Date.parse(value));
}

export function coverageFromPage(loaded: number, total: number): "complete" | "truncated" {
  return loaded < total ? "truncated" : "complete";
}

export function pnlTone(
  numeric: number | null,
): "positive" | "negative" | "muted" | "default" {
  if (numeric == null) return "muted";
  if (numeric > 0) return "positive";
  if (numeric < 0) return "negative";
  return "default";
}
