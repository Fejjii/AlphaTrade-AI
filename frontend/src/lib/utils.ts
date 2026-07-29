import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

import { formatDateTime, formatMonetary, formatPrice, UNAVAILABLE } from "@/lib/format";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Human date-time for UI surfaces (alias of shared formatDateTime). */
export function formatDate(value: string | Date | null | undefined): string {
  return formatDateTime(value);
}

/**
 * Compact decimal for general UI metrics.
 * Prefer formatMonetary / formatPrice / formatCurrency from @/lib/format for typed values.
 */
export function formatDecimal(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return UNAVAILABLE;
  const num = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(num)) return UNAVAILABLE;
  // Keep signed money-like readability for PnL-style figures without inventing currency.
  if (Math.abs(num) >= 1 || num === 0) {
    return num.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    });
  }
  return formatPrice(num);
}

export function truncate(value: string, max = 120): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
}

export { formatMonetary, formatPrice, UNAVAILABLE };
