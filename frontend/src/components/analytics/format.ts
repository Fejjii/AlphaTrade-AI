import type { DataNumberTone } from "@/components/ui/data-number";

/** Account-currency-agnostic monetary formatter — never emits currency symbols/codes. */
export function formatMonetary(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numeric)) return "—";
  const sign = numeric > 0 ? "+" : numeric < 0 ? "−" : "";
  return `${sign}${Math.abs(numeric).toFixed(2)}`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatSignedPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sign}${Math.abs(pct).toFixed(digits)}%`;
}

export function parseDecimal(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isNaN(numeric) ? null : numeric;
}

export function monetaryTone(value: number | null | undefined): DataNumberTone {
  if (value === null || value === undefined || value === 0) return "muted";
  return value > 0 ? "positive" : "negative";
}

export function formatProfitFactor(value: number | null | undefined, warnings?: string[]): string {
  if (value === null || value === undefined) {
    if (warnings?.some((w) => w.includes("no losing") || w.includes("no_losing"))) {
      return "n/a — no losing trades";
    }
    return "—";
  }
  return value.toFixed(2);
}

export function formatDateRangeLabel(from: string | null, to: string | null): string {
  if (!from && !to) return "All time";
  if (from && to) return `${from} → ${to}`;
  if (from) return `From ${from}`;
  return `Until ${to}`;
}

export function isoDateOnly(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(date: Date, days: number): Date {
  const copy = new Date(date);
  copy.setUTCDate(copy.getUTCDate() + days);
  return copy;
}

/** Returns true when a rendered monetary string accidentally contains currency markers. */
export function containsCurrencySymbol(text: string): boolean {
  return /[$£€]|USD|EUR|GBP/i.test(text);
}
